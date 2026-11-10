"""Argent de l'éleveur (lot 11) : ventes, achats personnels, dépenses « J'ai payé ».

Règle de rattachement (validée le 09/11) :
1. avec un bâtiment : à la bande en cours de ce bâtiment à la date ;
2. sans bâtiment : réparti entre les bandes en cours de la ferme à la date, au prorata des
   poulets présents (arrondis : la somme retombe exactement sur le montant) ;
3. poussins (achetés ou livrés par l'État) : à la bande qui les a reçus ;
4. aucune bande concernée : « hors bande » (compte dans le mois et dans « Tout »).
La répartition est calculée ici, et figée dans le bilan de la bande à la clôture."""
from datetime import date

from app import db
from app.models import Livraison, Profil
from app.models.argent import Depense, icone_et_nom
from app.models.bande import Bande, BandePoussins, Sortie, MotifSortie, StatutBande
from app.models.base import maintenant
from app.models.intrant import StatutLivraison, OrigineLivraison, TYPE_POUSSINS
from app.services.journal import enregistrer, Action
from app.utils.dates import en_utc

DELAI_ANNULATION_SECONDES = 10
TOLERANCE_RESEAU_SECONDES = 20
VENTES = (MotifSortie.ABATTOIR, MotifSortie.VENTE)
PERIODES = {'mois': 'Ce mois', 'bande': 'Cette bande', 'tout': '12 mois'}   # lot G / K4 : « Tout » devient « 12 mois »
SEUIL_AGREGAT = 3        # tableau de bord : moins de 3 fermes → « — »


class RegleArgent(Exception):
    pass


# ── Rattachement aux bandes ─────────────────────────────────────────────

def presents(bande, jour):
    """Poulets présents dans la bande le jour donné."""
    morts = bande.morts_avant_suivi + sum(s.morts for s in bande.saisies if s.date <= jour)
    sortis = sum(s.nombre for s in bande.sorties_comptees if s.date <= jour)
    return max(0, bande.effectif_initial - morts - sortis)


def bandes_du_jour(ferme_id, jour):
    """Bandes de la ferme en cours ce jour-là (commencées, pas encore clôturées)."""
    return [b for b in Bande.query.filter(Bande.ferme_id == ferme_id, Bande.date_mise_en_place <= jour)
            if b.date_cloture is None or jour <= b.date_cloture]


def partager(montant, poids):
    """Partage `montant` (entier) selon {clé: poids} ; arrondis au plus fort reste."""
    total = sum(poids.values())
    if not poids or montant is None:
        return {}
    if total <= 0:
        poids = {k: 1 for k in poids}
        total = len(poids)
    exacts = {k: montant * p / total for k, p in poids.items()}
    parts = {k: int(v) for k, v in exacts.items()}
    reste = montant - sum(parts.values())
    for k in sorted(exacts, key=lambda k: exacts[k] - parts[k], reverse=True)[:reste]:
        parts[k] += 1
    return parts


def repartir(montant, ferme_id, jour, batiment_id=None):
    """{bande: part} selon les règles 1, 2 et 4."""
    bandes = bandes_du_jour(ferme_id, jour)
    if batiment_id:
        bandes = [b for b in bandes if b.batiment_id == batiment_id]
        return {bandes[0]: montant} if bandes else {}
    return partager(montant, {b: presents(b, jour) for b in bandes})


def _parts_achat(achat, montant):
    """Achat personnel ou livraison de l'État : les poussins vont aux bandes qui les ont reçus
    (au prorata des poussins pris), le reste suit la règle du bâtiment ou du partage."""
    ligne = achat.lignes[0] if achat.lignes else None
    if ligne is not None and ligne.produit.type == TYPE_POUSSINS:
        pris = {}
        for bp in BandePoussins.query.filter_by(livraison_ligne_id=ligne.id):
            pris[bp.bande] = pris.get(bp.bande, 0) + bp.quantite
        return partager(montant, pris)
    return repartir(montant, achat.ferme_id, achat.date_livraison, achat.batiment_id)


# ── Mouvements ──────────────────────────────────────────────────────────

def _ventes(ferme_ids):
    return (Sortie.query.join(Bande).filter(Bande.ferme_id.in_(ferme_ids), Sortie.motif.in_(VENTES),
                                            Sortie.mise_de_cote.is_(False), Sortie.archive_le.is_(None))
            .order_by(Sortie.date.desc()).all())


def _achats(ferme_ids):
    return (Livraison.query.filter(Livraison.ferme_id.in_(ferme_ids), Livraison.origine == OrigineLivraison.ACHAT,
                                   Livraison.statut == StatutLivraison.RECUE)
            .order_by(Livraison.date_livraison.desc()).all())


def _depenses(ferme_ids):
    return (Depense.query.filter(Depense.ferme_id.in_(ferme_ids), Depense.annule.is_(False))
            .order_by(Depense.date.desc()).all())


def mouvements(ferme_ids):
    """Tous les mouvements d'argent des fermes, du plus récent au plus ancien. Chaque mouvement
    porte ses parts par bande ({bande_id: montant})."""
    resultat = []
    for s in _ventes(ferme_ids):
        resultat.append({'genre': 'vente', 'objet': s, 'date': s.date, 'ferme_id': s.bande.ferme_id,
                         'ico': '🏭' if s.motif == MotifSortie.ABATTOIR else '🚚',
                         'texte': f'{s.motif} · {s.nombre} poulets · {s.bande.batiment.code}',
                         'montant': s.montant_fcfa, 'signe': 1, 'a_completer': s.montant_fcfa is None,
                         'agent': s.saisi_par_agent, 'a_verifier': s.a_verifier,
                         'parts': {s.bande_id: s.montant_fcfa} if s.montant_fcfa else {}})
    from app.models.oeufs import VenteOeufs                    # lot F : ventes d'œufs
    for v in (VenteOeufs.query.join(Bande).filter(Bande.ferme_id.in_(ferme_ids), VenteOeufs.archive_le.is_(None))
              .order_by(VenteOeufs.date.desc()).all()):
        resultat.append({'genre': 'vente_oeufs', 'objet': v, 'date': v.date, 'ferme_id': v.bande.ferme_id, 'ico': '🥚',
                         'texte': f'Vente d\'œufs · {v.oeufs} œufs · {v.bande.batiment.code}' + (f' · {v.acheteur}' if v.acheteur else ''),
                         'montant': v.montant_fcfa, 'signe': 1, 'a_completer': False, 'agent': v.saisi_par_agent,
                         'a_verifier': False, 'parts': {v.bande_id: v.montant_fcfa} if v.montant_fcfa else {}})
    for a in _achats(ferme_ids):
        l = a.lignes[0]
        parts = _parts_achat(a, a.prix_paye_fcfa) if a.prix_paye_fcfa else {}
        resultat.append({'genre': 'achat', 'objet': a, 'date': a.date_livraison, 'ferme_id': a.ferme_id,
                         'ico': '🛒', 'texte': f'{l.produit.nom}' + (f' · {a.batiment.code}' if a.batiment else ''),
                         'montant': a.prix_paye_fcfa, 'signe': -1, 'a_completer': False,
                         'agent': a.confirmee_par_agent,
                         'parts': {b.id: m for b, m in parts.items()}})
    for d in _depenses(ferme_ids):
        parts = repartir(d.montant_fcfa, d.ferme_id, d.date, d.batiment_id)
        resultat.append({'genre': 'depense', 'objet': d, 'date': d.date, 'ferme_id': d.ferme_id, 'ico': d.icone,
                         'texte': d.libelle + (f' · {d.batiment.code}' if d.batiment else
                                               (' · partagée' if len(parts) > 1 else '')),
                         'montant': d.montant_fcfa, 'signe': -1, 'a_completer': False, 'agent': d.saisi_par_agent,
                         'parts': {b.id: m for b, m in parts.items()}})
    for m in resultat:
        m['hors_bande'] = m['genre'] != 'vente' and m['montant'] and not m['parts']
    resultat.sort(key=lambda m: (m['date'], en_utc(m['objet'].cree_le)), reverse=True)
    return resultat


def totaux(mvts, bande_id=None):
    """Gagné, Dépensé, Reste. Pour une bande : seulement sa part de chaque mouvement."""
    gagne = depense = 0
    for m in mvts:
        montant = m['parts'].get(bande_id, 0) if bande_id else (m['montant'] or 0)
        if m['signe'] > 0:
            gagne += montant
        else:
            depense += montant
    return {'gagne': gagne, 'depense': depense, 'reste': gagne - depense}


def filtrer(mvts, periode, bande=None, jour=None):
    jour = jour or date.today()
    if periode == 'mois':
        return [m for m in mvts if (m['date'].year, m['date'].month) == (jour.year, jour.month)]
    if periode == 'bande' and bande is not None:
        return [m for m in mvts if bande.id in m['parts'] or (m['genre'] == 'vente' and m['objet'].bande_id == bande.id)]
    if periode == 'tout':                                      # lot G / K4 : les 12 derniers mois glissants
        debut = date(jour.year - 1, jour.month, 1)
        return [m for m in mvts if m['date'] >= debut]
    return list(mvts)


# ── Aide de l'État, bilan ───────────────────────────────────────────────

def aide_etat(bande):
    """Valeur des livraisons subventionnées de l'État rattachées à la bande ; None si une de ces
    lignes n'a pas de valeur (une phrase partielle serait fausse) ou s'il n'y en a aucune."""
    debut, fin = bande.date_mise_en_place, bande.date_cloture or date.today()
    livraisons = (Livraison.query.filter(Livraison.ferme_id == bande.ferme_id,
                                         Livraison.origine == OrigineLivraison.ETAT,
                                         Livraison.statut.in_(StatutLivraison.CONFIRMEES)).all())
    total, lignes = 0, 0
    for liv in livraisons:
        for l in liv.lignes:
            if not l.subventionne:
                continue
            quantite = l.quantite_recue if l.quantite_recue is not None else l.quantite_livree
            if l.produit.type == TYPE_POUSSINS:
                pris = sum(bp.quantite for bp in BandePoussins.query.filter_by(livraison_ligne_id=l.id,
                                                                               bande_id=bande.id))
                if not pris:
                    continue
                part = pris / quantite if quantite else 0
            else:
                if not (debut <= liv.date_livraison <= fin):
                    continue
                parts = repartir(1_000_000, liv.ferme_id, liv.date_livraison)
                if bande not in parts:
                    continue
                part = parts[bande] / 1_000_000
            lignes += 1
            if l.valeur_unitaire is None:
                return None
            total += quantite * l.valeur_unitaire * (l.part_subventionnee or 100) / 100 * part
    return round(total) if lignes else None


def bilan_financier(bande):
    """Chiffre d'affaires, dépenses et marge de la bande (ajoutés au bilan du lot 8)."""
    mvts = mouvements([bande.ferme_id])
    t = totaux(filtrer(mvts, 'bande', bande), bande.id)
    return {'chiffre_affaires': t['gagne'], 'depenses': t['depense'], 'marge': t['reste'],
            'aide_etat': aide_etat(bande),
            'ventes_a_completer': sum(1 for s in bande.sorties_comptees if s.motif in VENTES and s.montant_fcfa is None)}


def rafraichir_bilans(ferme_id):
    """Après une saisie d'argent : le bilan figé des bandes terminées de la ferme est mis à jour."""
    for b in Bande.query.filter_by(ferme_id=ferme_id, statut=StatutBande.CLOTUREE):
        if b.bilan is not None:
            b.bilan = {**b.bilan, **bilan_financier(b)}


# ── J'ai payé ───────────────────────────────────────────────────────────

def payer(ferme, categorie, montant, batiment, jour, user, photo=None):
    from app.services import intrants
    if not categorie:
        raise RegleArgent('Touchez ce que vous avez payé.')
    if not montant or montant <= 0:
        raise RegleArgent('Indiquez le montant payé.')
    if jour > date.today():
        raise RegleArgent('La date ne peut pas être dans le futur.')
    limite = intrants.jour_le_plus_ancien_achat(user)
    if limite and jour < limite:
        raise RegleArgent('Cette dépense est trop ancienne : demandez à votre agent de la saisir.')
    if batiment is not None and batiment.ferme_id != ferme.id:
        raise RegleArgent('Bâtiment inconnu.')
    from app.services.numerotation import generer_numero
    d = Depense(numero_metier=generer_numero('DEPENSE', 'DEP', annuel=True), ferme_id=ferme.id,
                batiment_id=batiment.id if batiment else None, categorie=categorie[:60], montant_fcfa=montant,
                date=jour, photo_recu=photo, saisi_par_agent=user.profil == Profil.AGENT)
    db.session.add(d)
    db.session.flush()
    if user.profil == Profil.AGENT:
        enregistrer(Action.POUR_ELEVEUR, table='depense', enregistrement_id=d.id,
                    detail=f'Dépense {d.numero} ({d.libelle}, {montant} FCFA) saisie par l\'agent '
                           f'{user.nom_complet} pour l\'éleveur.')
    rafraichir_bilans(ferme.id)
    return d


def annulable(depense, user):
    if depense.annule or depense.cree_par != user.id:
        return False
    ecoule = (maintenant() - en_utc(depense.cree_le)).total_seconds()
    return ecoule <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def annuler(depense):
    depense.annule = True          # journal : ANNULATION automatique
    rafraichir_bilans(depense.ferme_id)


def corriger_depense(depense, user, categorie, montant, jour, motif):
    if not motif:
        raise RegleArgent('Indiquez le motif de la correction.')
    if not categorie or not montant or montant <= 0:
        raise RegleArgent('Indiquez la catégorie et le montant.')
    if jour > date.today():
        raise RegleArgent('La date ne peut pas être dans le futur.')
    depense.categorie, depense.montant_fcfa, depense.date = categorie[:60], montant, jour
    enregistrer(Action.CORRECTION, table='depense', enregistrement_id=depense.id,
                detail=f'Dépense {depense.numero} corrigée par {user.nom_complet} : {motif}')
    rafraichir_bilans(depense.ferme_id)


# ── Montant d'une vente ─────────────────────────────────────────────────

def completer_vente(sortie, user, montant, motif=None):
    """L'éleveur complète une fois un montant vide ; l'agent (ou l'ADMIN) corrige avec motif."""
    if sortie.motif not in VENTES:
        raise RegleArgent('Seules les ventes et les sorties à l\'abattoir ont un montant.')
    if montant is None or montant <= 0:
        raise RegleArgent('Indiquez le montant reçu.')
    if user.profil == Profil.ELEVEUR:
        if sortie.montant_fcfa is not None:
            raise RegleArgent('Le montant est déjà indiqué : demandez une correction à votre agent.')
    elif sortie.montant_fcfa is not None:
        if not motif:
            raise RegleArgent('Indiquez le motif de la correction.')
        enregistrer(Action.CORRECTION, table='sortie', enregistrement_id=sortie.id,
                    detail=f'Montant de la sortie du {sortie.date.strftime("%d/%m/%Y")} ({sortie.bande.numero}) '
                           f'corrigé par {user.nom_complet} : {sortie.montant_fcfa} → {montant} FCFA — {motif}')
    sortie.montant_fcfa = montant
    rafraichir_bilans(sortie.bande.ferme_id)


# ── Tableau de bord (DGE) : totaux agrégés seulement ───────────────────

def agregats(fermes, du=None, au=None):
    """Par province : chiffre d'affaires, dépenses, fermes qui saisissent ; « — » sous 3 fermes."""
    par = {}
    ids = [f.id for f in fermes]
    province = {f.id: f.province for f in fermes}
    for m in mouvements(ids) if ids else []:
        if (du and m['date'] < du) or (au and m['date'] > au) or not m['montant']:
            continue
        p = par.setdefault(province[m['ferme_id']].id, {'province': province[m['ferme_id']], 'ca': 0, 'depenses': 0,
                                                        'fermes': set()})
        p['ca' if m['signe'] > 0 else 'depenses'] += m['montant']
        p['fermes'].add(m['ferme_id'])
    lignes = []
    for p in sorted(par.values(), key=lambda p: p['province'].ordre):
        n = len(p['fermes'])
        cache = n < SEUIL_AGREGAT
        lignes.append({'province': p['province'], 'fermes': n,
                       'ca': None if cache else p['ca'], 'depenses': None if cache else p['depenses']})
    return lignes


def categories():
    from app.models.liste_deroulante import ld_choices
    return [(v, *icone_et_nom(v)) for v, _ in ld_choices('categories_depenses')]
