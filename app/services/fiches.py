"""Lot A1 — fiches modifiables et archivage (règle des formulaires, docs/ergonomie.md section K).

Une ligne touchée ouvre la fiche PRÉREMPLIE : « Enregistrer la modification » · « 🗄️ Archiver » · ✕.
- Chacun modifie ou archive SES propres saisies tant que la bande est ouverte.
- Bande terminée : lecture seule (« 🔒 Cette bande est terminée… ») ; seul un profil habilité (l'agent de la ferme,
  l'ADMIN) corrige, avec un motif.
- Correction par une autre personne (point 3 validé) : la saisie du jour garde les deux versions (lot 12) ; ailleurs,
  motif obligatoire, avant / après au journal, et un message « Votre agent a corrigé… » dans « À vérifier ».
- ARCHIVER remplace SUPPRIMER : l'élément est masqué des listes et exclu des calculs (app/models/base.py), conservé,
  et un profil habilité le restaure. Archivage et restauration sont au journal (avant / après, motif).
"""
import uuid
from datetime import date

from app import db
from app.models import Profil, Ferme, Utilisateur
from app.models.base import maintenant, AVEC_ARCHIVES
from app.models.journal import JournalAudit
from app.services.journal import enregistrer, detailler, Action


class RegleFiche(Exception):
    pass


VERROU = '🔒 Cette bande est terminée. Pour corriger, appelez votre agent.'


# ── Lecture des champs ──────────────────────────────────────────────────

def _nombre(brut, entier=False, minimum=None):
    texte = str(brut if brut is not None else '').strip().replace(' ', '').replace(' ', '').replace(',', '.')
    try:
        n = int(texte) if entier else float(texte)
    except ValueError:
        raise RegleFiche('Tapez un nombre entier.' if entier else 'Tapez un nombre (ex. 12,5).')
    if minimum is not None and n < minimum:
        raise RegleFiche('Le nombre doit être positif.' if minimum > 0 else 'Le nombre ne peut pas être négatif.')
    return n


def _jour(brut):
    try:
        j = date.fromisoformat(str(brut))
    except ValueError:
        raise RegleFiche('Date invalide.')
    if j > date.today():
        raise RegleFiche('La date ne peut pas être dans le futur.')
    return j


class Champ:
    """genre : entier, decimal, texte, date, choix. `facultatif` : vide accepté (None)."""

    def __init__(self, nom, libelle, genre='entier', valeur=None, choix=None, facultatif=False, minimum=1):
        self.nom, self.libelle, self.genre, self.valeur = nom, libelle, genre, valeur
        self.choix, self.facultatif, self.minimum = choix, facultatif, minimum

    def lire(self, brut):
        vide = not str(brut if brut is not None else '').strip()
        if vide and self.facultatif:
            return None
        if self.genre in ('entier', 'decimal'):
            return _nombre(brut, entier=self.genre == 'entier', minimum=self.minimum)
        if self.genre == 'date':
            return _jour(brut)
        if self.genre == 'choix':
            if brut not in [v for v, _ in self.choix]:
                raise RegleFiche(f'Choisissez : {self.libelle.lower()}')
            return brut
        if vide:
            raise RegleFiche(f'{self.libelle} : à remplir.')
        return brut.strip()


# ── Les genres de fiches ────────────────────────────────────────────────

class Genre:
    """Une sorte de saisie : modèle, titre, champs, application des valeurs, contrôles."""
    cle = modele_nom = None
    icone = '✏️'

    def modele(self):
        import app.models as m
        from app.models import entretien
        return getattr(m, self.modele_nom, None) or getattr(entretien, self.modele_nom)

    def bande(self, o):
        return getattr(o, 'bande', None)

    def ferme(self, o):
        b = self.bande(o)
        return b.ferme if b is not None else o.ferme

    def auteur_id(self, o):
        return o.cree_par

    def titre(self, o):
        raise NotImplementedError

    def champs(self, o):
        return []

    def appliquer(self, o, v, user):
        for nom, valeur in v.items():
            setattr(o, nom, valeur)

    def avant_archivage(self, o, user, motif):
        pass

    def apres_restauration(self, o, user):
        pass

    def visible(self, o):
        return True


class GSaisie(Genre):
    cle, modele_nom, icone = 'saisie', 'SaisieJour', '✏️'

    def titre(self, o):
        return f'Saisie du {o.date:%d/%m} · {o.bande.numero}'

    def champs(self, o):
        return [Champ('morts', 'Morts', valeur=o.morts, minimum=0)] + [
            Champ(f'aliment-{a.produit_id}', f'Sacs · {a.produit.nom}', 'decimal', valeur=a.sacs, minimum=0)
            for a in o.aliments]

    def aliments(self, o, v):
        return {a.produit: v[f'aliment-{a.produit_id}'] for a in o.aliments}

    def appliquer(self, o, v, user):
        from app.services import verifications
        verifications._appliquer_saisie(o, verifications.valeurs_saisie(v['morts'], self.aliments(o, v))[0])


class GPesee(Genre):
    cle, modele_nom, icone = 'pesee', 'Pesee', '⚖️'

    def titre(self, o):
        return f'Pesée du {o.date:%d/%m} · {o.bande.numero}'

    def champs(self, o):
        return [Champ('nombre_pesees', 'Poulets pesés', valeur=o.nombre_pesees),
                Champ('poids_total_kg', 'Poids total (kg)', 'decimal', valeur=o.poids_total_kg)]

    def appliquer(self, o, v, user):
        o.nombre_pesees, o.poids_total_kg = v['nombre_pesees'], v['poids_total_kg']
        o.poids_moyen_g = round(o.poids_total_kg / o.nombre_pesees * 1000, 1)


class GSortie(Genre):
    cle, modele_nom, icone = 'sortie', 'Sortie', '🚚'

    def titre(self, o):
        return f'Sortie du {o.date:%d/%m} · {o.motif} · {o.bande.numero}'

    def champs(self, o):
        from app.services.argent import VENTES
        c = [Champ('nombre', 'Nombre de poulets', valeur=o.nombre),
             Champ('poids_total_kg', 'Poids total (kg)', 'decimal', valeur=o.poids_total_kg)]
        if o.motif in VENTES:
            c.append(Champ('montant_fcfa', 'Combien avez-vous reçu ? (FCFA)', valeur=o.montant_fcfa, facultatif=True))
        return c

    def avant_archivage(self, o, user, motif):
        # Point 4 validé : sortie dont le lot a été reçu → refus ; sinon la sortie est archivée et son lot annulé.
        from app.services import receptions, tracabilite
        lot = getattr(o, 'lot', None)
        if lot is None or lot.annule:
            return
        recu = receptions.derniere_reception(lot)
        if recu is not None:
            raise RegleFiche(f'Ce lot a déjà été reçu ({recu.operateur.nom}) : la sortie ne peut pas être archivée.')
        tracabilite.annuler(lot, 'Sortie archivée' + (f' — {motif}' if motif else ''))

    def apres_restauration(self, o, user):
        lot = getattr(o, 'lot', None)
        if lot is not None and lot.annule:
            lot.annule, lot.motif_annulation = False, None


class GVaccin(Genre):
    cle, modele_nom, icone = 'vaccin', 'Vaccination', '💉'

    def titre(self, o):
        return f'Vaccin {o.produit.nom} · {o.date:%d/%m}'

    def champs(self, o):
        return [Champ('nombre_animaux', 'Poulets vaccinés', valeur=o.nombre_animaux),
                Champ('quantite', f'Quantité utilisée ({o.produit.unite})', 'decimal', valeur=o.quantite, minimum=0)]


class GTraitement(Genre):
    cle, modele_nom, icone = 'traitement', 'Traitement', '💊'

    def titre(self, o):
        return f'Traitement {o.produit.nom} · {o.date_debut:%d/%m}'

    def champs(self, o):
        return [Champ('motif', 'Pourquoi ?', 'texte', valeur=o.motif),
                Champ('date_fin', 'Dernier jour du traitement', 'date', valeur=o.date_fin),
                Champ('nombre_animaux', 'Poulets traités', valeur=o.nombre_animaux),
                Champ('quantite', f'Quantité utilisée ({o.produit.unite})', 'decimal', valeur=o.quantite, minimum=0)]

    def appliquer(self, o, v, user):
        if v['date_fin'] < o.date_debut:
            raise RegleFiche('Le dernier jour ne peut pas être avant le premier.')
        v['motif'] = v['motif'][:200]
        super().appliquer(o, v, user)


class GDepense(Genre):
    cle, modele_nom, icone = 'depense', 'Depense', '💸'

    def titre(self, o):
        return f'Dépense du {o.date:%d/%m} · {o.libelle}'

    def champs(self, o):
        from app.models.liste_deroulante import ld_choices
        choix = list(ld_choices('categories_depenses'))
        if o.categorie not in [c for c, _ in choix]:
            choix.insert(0, (o.categorie, o.categorie))
        return [Champ('categorie', 'Pour quoi ?', 'choix', valeur=o.categorie, choix=choix),
                Champ('montant_fcfa', 'Montant (FCFA)', valeur=o.montant_fcfa),
                Champ('date', 'Date', 'date', valeur=o.date)]

    def appliquer(self, o, v, user):
        v['categorie'] = v['categorie'][:60]
        super().appliquer(o, v, user)


class GVenteOeufs(Genre):
    cle, modele_nom, icone = 'vente_oeufs', 'VenteOeufs', '🥚'

    def titre(self, o):
        return f"Vente d'œufs du {o.date:%d/%m} · {o.oeufs} œufs"

    def champs(self, o):
        return [Champ('oeufs', "Œufs vendus (à l'unité)", valeur=o.oeufs), Champ('montant_fcfa', 'Prix total (FCFA)', valeur=o.montant_fcfa),
                Champ('acheteur', 'Acheteur', 'texte', valeur=o.acheteur), Champ('date', 'Date', 'date', valeur=o.date)]


class GAchat(Genre):
    cle, modele_nom, icone = 'achat', 'Livraison', '🛒'

    def visible(self, o):
        return o.est_achat

    def titre(self, o):
        return f'Achat du {o.date_livraison:%d/%m} · {o.lignes[0].produit.nom}'

    def _utilises(self, o):
        from app.services.bandes import utilises_par_ligne
        return utilises_par_ligne([o.lignes[0].id]).get(o.lignes[0].id, 0)

    def champs(self, o):
        l = o.lignes[0]
        return [Champ('quantite', f'Quantité ({l.produit.unite})', 'decimal', valeur=l.quantite_recue),
                Champ('prix_paye_fcfa', 'Prix payé (FCFA)', valeur=o.prix_paye_fcfa, facultatif=True),
                Champ('fournisseur', 'Où ?', 'texte', valeur=o.fournisseur, facultatif=True),
                Champ('date_livraison', 'Date', 'date', valeur=o.date_livraison)]

    def appliquer(self, o, v, user):
        l = o.lignes[0]
        if v['quantite'] < self._utilises(o):
            raise RegleFiche('Une partie de ces poussins est déjà dans une bande : la quantité ne peut pas baisser autant.')
        l.quantite_livree = l.quantite_recue = v['quantite']
        o.prix_paye_fcfa = v['prix_paye_fcfa']
        l.valeur_unitaire = round(v['prix_paye_fcfa'] / v['quantite'], 2) if v['prix_paye_fcfa'] else None
        o.fournisseur = (v['fournisseur'] or '')[:150] or None
        o.date_livraison = v['date_livraison']

    def avant_archivage(self, o, user, motif):
        if self._utilises(o):
            raise RegleFiche("Ces poussins sont déjà dans une bande : l'achat ne peut pas être archivé.")


class GPanne(Genre):
    cle, modele_nom, icone = 'panne', 'Panne', '⚠️'

    def titre(self, o):
        return f'Panne · {o.libelle} · {o.ou}'

    def champs(self, o):
        from app.models.entretien import TypePanne
        return [Champ('type', "Qu'est-ce qui ne marche pas ?", 'choix', valeur=o.type,
                      choix=[(c, f'{i} {n}') for c, i, n in TypePanne.TOUS])]


class GEntretien(Genre):
    cle, modele_nom, icone = 'entretien', 'EntretienFait', '🔧'

    def titre(self, o):
        return f'{o.tache.nom} · fait le {o.fait_le:%d/%m}'

    def champs(self, o):
        return [Champ('fait_le', 'Fait le', 'date', valeur=o.fait_le)]


class GSignalement(Genre):
    cle, modele_nom, icone = 'signalement', 'Declaration', '🩺'

    def ferme(self, o):
        return o.ferme

    def titre(self, o):
        return f'Signalement du {o.cree_le:%d/%m}'

    def champs(self, o):
        return [Champ('nombre_animaux', 'Poulets malades', valeur=o.nombre_animaux)]

    def _alerte(self, o):
        from app.models.sante import AlerteSanitaire
        return AlerteSanitaire.query.filter_by(declaration_id=o.id).first()

    def avant_archivage(self, o, user, motif):
        from app.models.sante import StatutAlerte, AlerteHistorique
        a = self._alerte(o)
        if a is None:
            return
        if a.statut != StatutAlerte.NOUVELLE or a.reponses:
            raise RegleFiche('Le vétérinaire suit déjà ce signalement : il ne peut plus être archivé.')
        a.statut = StatutAlerte.CLOSE
        db.session.add(AlerteHistorique(alerte=a, statut=StatutAlerte.CLOSE, utilisateur_id=user.id,
                                        commentaire='Signalement archivé' + (f' — {motif}' if motif else '')))

    def apres_restauration(self, o, user):
        from app.models.sante import StatutAlerte, AlerteHistorique
        a = self._alerte(o)
        if a is not None and a.statut == StatutAlerte.CLOSE and not a.reponses:
            a.statut = StatutAlerte.NOUVELLE
            db.session.add(AlerteHistorique(alerte=a, statut=StatutAlerte.NOUVELLE, utilisateur_id=user.id,
                                            commentaire='Signalement restauré'))


class GVisite(Genre):
    cle, modele_nom, icone = 'visite', 'Visite', '📋'

    def ferme(self, o):
        return o.ferme

    def auteur_id(self, o):
        return o.agent_id

    def titre(self, o):
        quand = o.faite_le or o.date_prevue
        return f'Visite · {o.objet}' + (f' · {quand:%d/%m}' if quand else '')

    def champs(self, o):
        return [Champ('constats', 'Ce que vous avez vu', 'texte', valeur=o.constats, facultatif=True),
                Champ('recommandation_libre', 'Autre conseil', 'texte', valeur=o.recommandation_libre, facultatif=True)]

    def appliquer(self, o, v, user):
        o.constats = (v['constats'] or '')[:500] or None
        o.recommandation_libre = (v['recommandation_libre'] or '')[:300] or None


GENRES = {g.cle: g for g in (GSaisie(), GPesee(), GSortie(), GVaccin(), GTraitement(), GDepense(), GAchat(), GVenteOeufs(),
                             GPanne(), GEntretien(), GSignalement(), GVisite())}
DU_MODELE = {g.modele_nom: g for g in GENRES.values()}


def genre_de(obj):
    return DU_MODELE[type(obj).__name__]


def charger(cle, ident):
    """La saisie (archivée comprise), ou None."""
    g = GENRES.get(cle)
    if g is None:
        return None
    m = g.modele()
    try:
        ident = uuid.UUID(str(ident))
    except ValueError:
        return None
    obj = m.query.execution_options(**{AVEC_ARCHIVES: True}).filter(m.id == ident).first()
    return obj if obj is not None and g.visible(obj) else None


# ── Droits ──────────────────────────────────────────────────────────────

def fermes_visibles(user, fermes):
    from app.utils.permissions import filtre_perimetre
    ids = {f.id for f in fermes if f is not None}
    if not ids:
        return set()
    return {f.id for f in filtre_perimetre(Ferme.query, utilisateur=user).filter(Ferme.id.in_(ids))}


def est_habilite(user, ferme):
    """L'agent de la ferme ou l'ADMIN : corrige les saisies des autres et celles d'une bande terminée."""
    return user.profil == Profil.ADMIN or (user.profil == Profil.AGENT and ferme is not None
                                           and ferme.agent_id == user.id)


def _droit(user, g, o, visible):
    """('auteur' | 'habilite' | None, message)."""
    if not visible:
        return None, None
    ferme, bande = g.ferme(o), g.bande(o)
    if bande is not None and not bande.en_cours:
        return ('habilite', None) if est_habilite(user, ferme) else (None, VERROU)
    if g.auteur_id(o) == user.id or _eleveur_sans_auteur(user, g, o):
        return 'auteur', None
    if est_habilite(user, ferme):
        return 'habilite', None
    return None, 'Seule la personne qui a fait cette saisie peut la modifier.'


def _eleveur_sans_auteur(user, g, o):
    """Saisie reprise sans auteur enregistré (import, données anciennes) : elle est à l'éleveur de la ferme,
    sauf si elle est marquée « saisie par l'agent »."""
    return (g.auteur_id(o) is None and user.profil == Profil.ELEVEUR
            and not getattr(o, 'saisi_par_agent', False) and not getattr(o, 'saisie_par_agent', False))


def droit(user, o):
    g = genre_de(o)
    return _droit(user, g, o, g.ferme(o).id in fermes_visibles(user, [g.ferme(o)]))


def motif_demande(user, o, mode):
    """Vrai si la modification demande un motif : correction de la saisie d'une autre personne, ou bande terminée."""
    g = genre_de(o)
    b = g.bande(o)
    return mode == 'habilite' and (_par_un_autre(o, g, user) or (b is not None and not b.en_cours))


class Info:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def infos(objets, user):
    """{id: Info} pour une liste : droits, auteur, nombre de modifications — en quelques requêtes."""
    objets = [o for o in objets if o is not None]
    if not objets:
        return {}
    genres = {o.id: genre_de(o) for o in objets}
    visibles = fermes_visibles(user, [genres[o.id].ferme(o) for o in objets])
    auteurs_ids = {genres[o.id].auteur_id(o) for o in objets} - {None}
    auteurs = {u.id: u for u in Utilisateur.query.filter(Utilisateur.id.in_(auteurs_ids))} if auteurs_ids else {}
    nb = nombres_modifications(objets)
    resultat = {}
    for o in objets:
        g = genres[o.id]
        ferme = g.ferme(o)
        mode, message = _droit(user, g, o, ferme.id in visibles)
        auteur = auteurs.get(g.auteur_id(o))
        agent = ferme.agent
        resultat[o.id] = Info(
            genre=g.cle, objet=o, titre=g.titre(o), icone=g.icone, mode=mode, message=message,
            motif=motif_demande(user, o, mode), auteur=auteur.nom_complet if auteur else None,
            nb=nb.get(str(o.id), 0), champs=g.champs(o), archive=o.archive_le is not None,
            restaurer=o.archive_le is not None and ferme.id in visibles and est_habilite(user, ferme),
            telephone_agent=agent.telephone if agent is not None and agent.telephone else None)
    return resultat


def nombres_modifications(objets):
    """{id (texte): nombre} de modifications au journal (« Saisie par … · modifiée N fois ») : modifications par
    une fiche et corrections de l'agent (lignes avec un détail ; les lignes automatiques n'en ont pas)."""
    par_table = {}
    for o in objets:
        par_table.setdefault(o.__tablename__, []).append(str(o.id))
    nb = {}
    for table, ids in par_table.items():
        lignes = (db.session.query(JournalAudit.enregistrement_id, db.func.count(JournalAudit.id))
                  .filter(JournalAudit.table_nom == table, JournalAudit.enregistrement_id.in_(ids),
                          JournalAudit.action.in_((Action.MODIFICATION, Action.CORRECTION)),
                          JournalAudit.detail.isnot(None))
                  .group_by(JournalAudit.enregistrement_id))
        nb.update({i: n for i, n in lignes})
    return nb


# ── Modifier, archiver, restaurer ───────────────────────────────────────

def _motif(user, o, mode, motif):
    motif = (motif or '').strip()[:300]
    if motif_demande(user, o, mode) and not motif:
        raise RegleFiche('Indiquez le motif de la correction.')
    return motif


def _par_un_autre(o, g, user):
    """La saisie est celle d'une autre personne (sans auteur enregistré : celle de l'éleveur de la ferme)."""
    if g.auteur_id(o) is None:
        return user.profil != Profil.ELEVEUR
    return g.auteur_id(o) != user.id


def _prevenir(o, g, user, quoi, detail):
    """Point 3 validé : message dans « À vérifier » quand l'agent corrige la saisie d'une autre personne."""
    from app.models.hors_ligne import ConflitHorsLigne
    b = g.bande(o)
    db.session.add(ConflitHorsLigne(ferme_id=g.ferme(o).id, bande_id=b.id if b is not None else None,
                                    utilisateur_id=user.id, quoi=quoi[:150], detail=detail,
                                    objet_table=o.__tablename__, objet_id=str(o.id)))


def _apres(o, g):
    """Contrôle de l'effectif, bilans et alertes recalculés comme après une saisie."""
    from app import indicateurs
    from app.services import argent, sante
    db.session.flush()
    b = g.bande(o)
    if b is not None:
        if indicateurs.calculer(b)['effectif_present'] < 0:
            raise RegleFiche("Avec ces chiffres, l'effectif deviendrait négatif.")
        if not b.en_cours:
            b.bilan = indicateurs.bilan(b)
        else:
            sante.alerte_si_feu_rouge(b)
    argent.rafraichir_bilans(g.ferme(o).id)


def modifier(o, formulaire, user):
    """'modifie', 'inchange' ou 'deux_versions' (saisie du jour d'un éleveur modifiée par une autre personne)."""
    g = genre_de(o)
    if o.archive_le is not None:
        raise RegleFiche("Cet élément est archivé : restaurez-le d'abord.")
    mode, message = droit(user, o)
    if mode is None:
        raise RegleFiche(message or 'Vous ne pouvez pas modifier cette saisie.')
    motif = _motif(user, o, mode, formulaire.get('motif'))
    valeurs = {c.nom: c.lire(formulaire.get(c.nom)) for c in g.champs(o)}
    titre = g.titre(o)
    if g.cle == 'saisie' and _par_un_autre(o, g, user):
        from app.services import verifications
        aliments = g.aliments(o, valeurs)
        if verifications.memes_valeurs(o, valeurs['morts'], aliments):
            return 'inchange'
        auteur = db.session.get(Utilisateur, o.cree_par) if o.cree_par else None
        if auteur is not None and auteur.profil == Profil.ELEVEUR and o.bande.en_cours:
            verifications.deux_versions_saisie(o.bande, o, valeurs['morts'], aliments, user)   # règle du lot 12
            enregistrer(Action.CORRECTION, table=o.__tablename__, enregistrement_id=o.id,
                        detail=f'{titre} : autre version de {user.nom_complet} — {motif}')
            return 'deux_versions'
    g.appliquer(o, valeurs, user)
    _apres(o, g)
    if _par_un_autre(o, g, user):
        enregistrer(Action.CORRECTION, table=o.__tablename__, enregistrement_id=o.id,
                    detail=f'{titre} corrigée par {user.nom_complet} — {motif}')
        _prevenir(o, g, user, f'Correction · {titre}',
                  f'Votre agent a corrigé « {titre} » ({user.nom_complet}). Motif : {motif}')
    else:
        enregistrer(Action.MODIFICATION, table=o.__tablename__, enregistrement_id=o.id,
                    detail=f'{titre} modifiée par {user.nom_complet}' + (f' — {motif}' if motif else ''))
    return 'modifie'


def archiver(o, user, motif=None):
    g = genre_de(o)
    if o.archive_le is not None:
        return
    mode, message = droit(user, o)
    if mode is None:
        raise RegleFiche(message or 'Vous ne pouvez pas archiver cette saisie.')
    motif = _motif(user, o, mode, motif)
    titre = g.titre(o)
    g.avant_archivage(o, user, motif)
    o.archive_le, o.archive_par = maintenant(), user.id
    if isinstance(getattr(o, 'annule', None), bool):
        o.annule = True                       # anciens écrans et calculs (lots 10–11)
    detailler(db.session, o, f'{titre} archivée par {user.nom_complet}' + (f' — {motif}' if motif else ''))
    _apres(o, g)
    if _par_un_autre(o, g, user):
        _prevenir(o, g, user, f'Archivage · {titre}',
                  f'Votre agent a archivé « {titre} » ({user.nom_complet}). Motif : {motif}')


def restaurer(o, user, motif=None):
    g = genre_de(o)
    if o.archive_le is None:
        return
    ferme = g.ferme(o)
    if ferme.id not in fermes_visibles(user, [ferme]) or not est_habilite(user, ferme):
        raise RegleFiche("Seul l'agent de la ferme ou l'administrateur restaure.")
    titre = g.titre(o)
    o.archive_le, o.archive_par = None, None
    if isinstance(getattr(o, 'annule', None), bool):
        o.annule = False
    g.apres_restauration(o, user)
    motif = (motif or '').strip()[:300]
    detailler(db.session, o, f'{titre} restaurée par {user.nom_complet}' + (f' — {motif}' if motif else ''))
    _apres(o, g)


def archivees(cle, ferme=None, bande=None):
    """Éléments archivés (« Voir les archivées (n) »), les plus récents d'abord."""
    g = GENRES[cle]
    m = g.modele()
    q = m.query.execution_options(**{AVEC_ARCHIVES: True}).filter(m.archive_le.isnot(None))
    if cle == 'achat':
        from app.models.intrant import OrigineLivraison
        q = q.filter(m.origine == OrigineLivraison.ACHAT)
    if bande is not None and hasattr(m, 'bande_id'):
        q = q.filter(m.bande_id == bande.id)
    elif ferme is not None and hasattr(m, 'ferme_id'):
        q = q.filter(m.ferme_id == ferme.id)
    elif ferme is not None:
        from app.models import Bande
        q = q.join(Bande, m.bande_id == Bande.id).filter(Bande.ferme_id == ferme.id)
    return q.order_by(m.archive_le.desc()).all()


def nombre_archivees(cle, ferme=None, bande=None, fermes=None):
    """Nombre d'archivées pour le lien « Voir les archivées (n) » (fermes : plusieurs fermes, éleveur)."""
    if fermes is not None:
        return sum(len(archivees(cle, ferme=f)) for f in fermes)
    return len(archivees(cle, ferme=ferme, bande=bande))


# ── Fermes et bandes (bureau, ADMIN) : ne s'archivent que vides ─────────

def _compte(modele, **filtres):
    return modele.query.execution_options(**{AVEC_ARCHIVES: True}).filter_by(**filtres).count()


def pourquoi_pas_archivable(o):
    """Message de refus, ou None : une ferme ou une bande qui a déjà servi garde son histoire."""
    from app.models import Bande, Livraison
    from app.models.bande import SaisieJour, Pesee, Sortie
    from app.models.sante import Vaccination, Traitement
    if isinstance(o, Ferme):
        if _compte(Bande, ferme_id=o.id) or _compte(Livraison, ferme_id=o.id):
            return 'Cette ferme a déjà des bandes ou des livraisons : elle ne peut pas être archivée.'
        return None
    if any(_compte(m, bande_id=o.id) for m in (SaisieJour, Pesee, Sortie, Vaccination, Traitement)):
        return 'Cette bande a déjà des saisies : elle ne peut pas être archivée (corrigez ou archivez les saisies).'
    return None


def archiver_entite(o, user, motif):
    motif = (motif or '').strip()[:300]
    if not motif:
        raise RegleFiche("Indiquez le motif de l'archivage.")
    refus = pourquoi_pas_archivable(o)
    if refus:
        raise RegleFiche(refus)
    o.archive_le, o.archive_par = maintenant(), user.id
    detailler(db.session, o, f'{o.numero} archivée par {user.nom_complet} — {motif}')


def restaurer_entite(o, user, motif=None):
    o.archive_le, o.archive_par = None, None
    motif = (motif or '').strip()[:300]
    detailler(db.session, o, f'{o.numero} restaurée par {user.nom_complet}' + (f' — {motif}' if motif else ''))
