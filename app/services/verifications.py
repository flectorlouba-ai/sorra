"""Saisies à vérifier (lot 12) : deux personnes, deux versions gardées, aucune donnée perdue.

- Même personne, même bande, même jour : les saisies s'additionnent (inchangé, services/bandes.saisir).
- Saisie du jour ou confirmation de livraison par deux personnes, valeurs différentes : les deux
  versions sont gardées ; celle de l'éleveur compte jusqu'à la décision (agent, DGE, ADMIN), motif
  obligatoire, inscrite au journal, indicateurs recalculés.
- Sorties du même jour par deux personnes : « doublon possible » seulement si le nombre ET le
  destinataire sont identiques ; celle de l'autre personne est mise de côté (ni comptée, ni lot QR).
- Garde-fou : un doublon de sortie non tranché sous 48 h passe en rouge et remonte à la DGE."""
import uuid
from datetime import timedelta

from app import db
from app.models import Profil, Utilisateur
from app.models.base import maintenant
from app.models.bande import SaisieAliment, Sortie, StatutBande
from app.models.hors_ligne import ConflitHorsLigne, GenreVerification as G, StatutVerification as SV
from app.models.intrant import Produit
from app.services.journal import enregistrer, Action
from app.utils.dates import en_utc

DELAI_ROUGE_HEURES = 48


class RegleVerification(Exception):
    pass


def _auteur(user_id):
    u = db.session.get(Utilisateur, user_id) if user_id else None
    return u


def _version(user, valeurs, libelle, saisi_le=None):
    return {'auteur_id': str(user.id) if user else None, 'auteur': user.nom_complet if user else '—',
            'profil': user.profil.value if user else None,
            'saisi_le': (saisi_le or maintenant()).isoformat(), 'valeurs': valeurs, 'libelle': libelle}


def _eleveur_d_abord(versions):
    return sorted(versions, key=lambda v: v['profil'] != Profil.ELEVEUR.value)


def ouverte(objet_table, objet_id):
    return ConflitHorsLigne.query.filter_by(objet_table=objet_table, objet_id=str(objet_id),
                                            statut=SV.A_VERIFIER).first()


def _ouvrir(ferme, bande, genre, objet_table, objet_id, versions, quoi, detail, user):
    c = ouverte(objet_table, objet_id)
    if c is None:
        c = ConflitHorsLigne(ferme_id=ferme.id, bande_id=bande.id if bande else None, genre=genre,
                             statut=SV.A_VERIFIER, objet_table=objet_table, objet_id=str(objet_id),
                             utilisateur_id=user.id, quoi=quoi[:150], detail=detail, versions=[])
        db.session.add(c)
    anciennes = {v['auteur_id']: v for v in (c.versions or [])}
    for v in versions:
        anciennes[v['auteur_id']] = v                  # une version par personne (la plus complète)
    c.versions = _eleveur_d_abord(list(anciennes.values()))
    c.detail = detail
    return c


# ── Saisie du jour ──────────────────────────────────────────────────────

def valeurs_saisie(morts, aliments):
    """{morts, aliments: {produit_id: sacs}} et libellé lisible."""
    al = {str(p.id): float(s) for p, s in aliments.items() if s}
    noms = ', '.join(f'{s:g} sac{"s" if s > 1 else ""} {p.nom}' for p, s in aliments.items() if s) or "pas d'aliment"
    return {'morts': int(morts), 'aliments': al}, f'{morts} mort{"s" if morts > 1 else ""} · {noms}'


def valeurs_de(saisie):
    return valeurs_saisie(saisie.morts, {a.produit: a.sacs for a in saisie.aliments})


def memes_valeurs(saisie, morts, aliments):
    return valeurs_de(saisie)[0] == valeurs_saisie(morts, aliments)[0]


def _appliquer_saisie(saisie, valeurs):
    saisie.morts = valeurs['morts']
    voulus = {int(pid): sacs for pid, sacs in valeurs['aliments'].items()}
    for a in list(saisie.aliments):
        if a.produit_id not in voulus:
            saisie.aliments.remove(a)
    for pid, sacs in voulus.items():
        ligne = next((a for a in saisie.aliments if a.produit_id == pid), None)
        if ligne is None:
            ligne = SaisieAliment(produit=db.session.get(Produit, pid), sacs=0, kg=0)
            saisie.aliments.append(ligne)
        ligne.sacs = sacs
        ligne.kg = sacs * float(ligne.produit.poids_sac_kg or 0)


def deux_versions_saisie(bande, saisie, morts, aliments, user, saisi_le=None):
    """Une autre personne a déjà saisi ce jour-là, avec d'autres valeurs : les deux versions sont
    gardées, celle de l'éleveur compte, la journée passe « à vérifier »."""
    existante_auteur = _auteur(saisie.modifie_par or saisie.cree_par)
    v_existante = _version(existante_auteur, *valeurs_de(saisie), saisi_le=en_utc(saisie.modifie_le))
    v_nouvelle = _version(user, *valeurs_saisie(morts, aliments), saisi_le=saisi_le)
    if user.profil == Profil.ELEVEUR and (existante_auteur is None or existante_auteur.profil != Profil.ELEVEUR):
        _appliquer_saisie(saisie, v_nouvelle['valeurs'])        # la version de l'éleveur compte
    saisie.a_verifier = True
    jour = saisie.date.strftime('%d/%m')
    c = _ouvrir(bande.ferme, bande, G.SAISIE_JOUR, 'saisie_jour', saisie.id, [v_existante, v_nouvelle],
                f'Saisie du {jour} · bande {bande.numero}',
                f'Deux versions pour la saisie du {jour} : à trancher. En attendant, la version de l\'éleveur compte.',
                user)
    db.session.flush()
    return c


# ── Confirmation de livraison ───────────────────────────────────────────

def valeurs_livraison(liv, receptions=None, morts=None):
    """Version d'une confirmation : {ligne_id: [reçue, morts, motif]} (receptions/morts : celles du
    téléphone ; sans elles, la confirmation enregistrée)."""
    valeurs, morceaux = {}, []
    for l in liv.lignes:
        if receptions is None and morts is None:
            recue, m, motif = l.quantite_recue, l.morts_arrivee, l.motif_ecart
        else:
            recue, motif = (receptions or {}).get(l.id, (l.quantite_livree, None))
            m = (morts or {}).get(l.id, 0) if l.produit.type == 'Poussins' else None
        valeurs[str(l.id)] = [float(recue) if recue is not None else None, m, motif]
        morceaux.append(f'{recue:g} {l.produit.unite} {l.produit.nom}' + (f' ({m} morts)' if m else ''))
    return valeurs, ' · '.join(morceaux)


def deux_versions_livraison(liv, receptions, morts, user, saisi_le=None):
    """Confirmation envoyée après coup alors qu'une autre personne a déjà confirmé, avec d'autres
    valeurs : les deux gardées ; celle de l'éleveur compte. Visible de l'agent ET de la DGE."""
    from app.services import intrants
    existante_auteur = _auteur(liv.confirmee_par)
    v_existante = _version(existante_auteur, *valeurs_livraison(liv), saisi_le=en_utc(liv.confirmee_le))
    v_nouvelle = _version(user, *valeurs_livraison(liv, receptions, morts), saisi_le=saisi_le)
    if v_existante['valeurs'] == v_nouvelle['valeurs']:
        return None
    if user.profil == Profil.ELEVEUR and (existante_auteur is None or existante_auteur.profil != Profil.ELEVEUR):
        intrants.confirmer(liv, user, receptions, morts)
    c = _ouvrir(liv.ferme, None, G.LIVRAISON, 'livraison', liv.id, [v_existante, v_nouvelle],
                f'Livraison {liv.numero} · {liv.date_livraison.strftime("%d/%m")}',
                'Deux confirmations différentes de cette livraison de l\'État : à trancher. '
                'En attendant, celle de l\'éleveur compte.', user)
    db.session.flush()
    return c


def _appliquer_livraison(liv, valeurs, user):
    from app.services import intrants
    for l in liv.lignes:
        recue, m, motif = valeurs.get(str(l.id), [l.quantite_livree, None, None])
        l.quantite_recue, l.morts_arrivee = recue, m
        l.motif_ecart = motif if recue != l.quantite_livree else None
    liv.statut = intrants._statut_apres_reception(liv)


# ── Doublon possible de sortie ──────────────────────────────────────────

def _destinataire(s):
    return ('op', s.operateur_id) if s.operateur_id else ('libre', (s.destinataire_libre or '').strip().lower())


def doublon_sortie(sortie, user):
    """Après une sortie : même bande, même jour, même nombre, même destinataire, autre personne ?
    Renvoie True si la nouvelle sortie est mise de côté (pas de lot QR à créer)."""
    autre = next((o for o in Sortie.query.filter(Sortie.bande_id == sortie.bande_id, Sortie.date == sortie.date,
                                                  Sortie.id != sortie.id, Sortie.nombre == sortie.nombre,
                                                  Sortie.archive_le.is_(None))
                  if _destinataire(o) == _destinataire(sortie) and o.cree_par and o.cree_par != user.id), None)
    if autre is None:
        return False
    autre_auteur = _auteur(autre.cree_par)
    eleveur_nouveau = user.profil == Profil.ELEVEUR and (autre_auteur is None or autre_auteur.profil != Profil.ELEVEUR)
    mise_de_cote = autre if eleveur_nouveau else sortie
    mise_de_cote.mise_de_cote = True
    if mise_de_cote.lot is not None:
        mise_de_cote.lot.annule = True           # lot tracé suspendu jusqu'à la décision
    autre.a_verifier = sortie.a_verifier = True

    def version(s, auteur):
        return _version(auteur, {'sortie_id': str(s.id), 'nombre': s.nombre, 'destinataire': s.destinataire,
                                 'poids_kg': float(s.poids_total_kg), 'mise_de_cote': s.mise_de_cote},
                        f'{s.nombre} poulets · {s.destinataire} · {s.poids_total_kg:g} kg',
                        saisi_le=en_utc(s.cree_le) if s.cree_le else None)
    bande = sortie.bande
    _ouvrir(bande.ferme, bande, G.SORTIE, 'sortie', autre.id, [version(autre, autre_auteur), version(sortie, user)],
            f'Sorties du {sortie.date.strftime("%d/%m")} · bande {bande.numero}',
            'Doublon possible : deux sorties identiques (même nombre, même destinataire) par deux personnes. '
            'En attendant, seule celle de l\'éleveur compte.', user)
    db.session.flush()
    return mise_de_cote is sortie


# ── Décision ────────────────────────────────────────────────────────────

CHOIX_SORTIE = {'deux': 'Ce sont deux sorties différentes', 'eleveur': "Garder celle de l'éleveur",
                'autre': "Garder celle de l'autre personne"}


def trancher(c, choix, motif, user):
    """`choix` : index de la version retenue (saisie, livraison) ou 'deux' / 'eleveur' / 'autre' (sortie)."""
    if not c.a_trancher:
        raise RegleVerification('Cette saisie est déjà tranchée.')
    if not (motif or '').strip():
        raise RegleVerification('Indiquez le motif de la décision.')
    from app import indicateurs
    from app.models import Livraison
    from app.models.bande import SaisieJour
    bande = c.bande
    if c.genre == G.SORTIE:
        if choix not in CHOIX_SORTIE:
            raise RegleVerification('Choisissez une décision.')
        sorties = {v['valeurs']['sortie_id']: (db.session.get(Sortie, uuid.UUID(v['valeurs']['sortie_id'])), v)
                   for v in c.versions}
        for sid, (s, v) in sorties.items():
            garder = (choix == 'deux' or (choix == 'eleveur') == (v['profil'] == Profil.ELEVEUR.value))
            s.mise_de_cote = not garder
            s.a_verifier = False
            if garder:
                if s.lot is not None:
                    s.lot.annule = False
                else:
                    from app.services import tracabilite
                    tracabilite.creer_lot(s, user)
            elif s.lot is not None:
                s.lot.annule = True
        libelle = CHOIX_SORTIE[choix]
        bande = bande or next(iter(sorties.values()))[0].bande
    else:
        try:
            v = c.versions[int(choix)]
        except (ValueError, TypeError, IndexError):
            raise RegleVerification('Choisissez la version à retenir.')
        if c.genre == G.SAISIE_JOUR:
            s = db.session.get(SaisieJour, uuid.UUID(c.objet_id))
            _appliquer_saisie(s, v['valeurs'])
            s.a_verifier = False
        else:
            liv = db.session.get(Livraison, uuid.UUID(c.objet_id))
            _appliquer_livraison(liv, v['valeurs'], user)
        libelle = f'version de {v["auteur"]} retenue ({v["libelle"]})'
    c.statut, c.retenue, c.motif = SV.TRANCHE, str(choix), motif.strip()
    c.decide_par, c.decide_le = user.id, maintenant()
    enregistrer(Action.VERIFICATION, table='conflit_hors_ligne', enregistrement_id=c.id,
                detail=f'{c.quoi} : {libelle} par {user.nom_complet} — {motif.strip()}')
    db.session.flush()
    if bande is not None and bande.statut == StatutBande.CLOTUREE:
        bande.bilan = indicateurs.bilan(bande)       # recalcul du bilan figé
    return c


# ── Pour les alertes ────────────────────────────────────────────────────

def en_retard(c):
    from app.services import parametres
    heures = parametres.obtenir('verifications.delai_rouge_heures', DELAI_ROUGE_HEURES)
    return c.genre == G.SORTIE and c.a_trancher and maintenant() - en_utc(c.cree_le) > timedelta(hours=heures)


def a_trancher(requete):
    return requete.filter(ConflitHorsLigne.genre.in_(G.A_TRANCHER), ConflitHorsLigne.statut == SV.A_VERIFIER)
