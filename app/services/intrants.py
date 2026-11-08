"""Règles des intrants : livraisons, confirmation de réception, stock, alertes."""
from datetime import date, timedelta

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.intrant import (Livraison, LivraisonLigne, Produit, StatutLivraison as S,
                                TYPE_POUSSINS)
from app.services import parametres
from app.services.journal import enregistrer, Action
from app.services.numerotation import generer_numero
from app.utils.dates import en_utc

# Après « Tout reçu », le bandeau « Annuler » reste 10 s à l'écran ; le serveur
# accepte l'annulation un peu plus longtemps pour couvrir un réseau lent.
DELAI_ANNULATION_SECONDES = 10
TOLERANCE_RESEAU_SECONDES = 20


# ── Droits ──────────────────────────────────────────────────────────────

def peut_creer(user):
    return user.profil in (Profil.ADMIN, Profil.DGE, Profil.AGENT)


def peut_modifier(user, livraison):
    """Modifier une livraison encore « À confirmer » (ferme déjà dans le périmètre)."""
    return livraison.a_confirmer and peut_creer(user)


def peut_confirmer(user, livraison):
    """Confirmer = geste de l'éleveur, ou de son agent pour son compte."""
    return livraison.a_confirmer and user.profil in (Profil.ELEVEUR, Profil.AGENT)


def peut_annuler(user, livraison):
    return livraison.a_confirmer and user.profil in (Profil.ADMIN, Profil.DGE)


def peut_corriger(user, livraison):
    return livraison.confirmee and user.profil in (Profil.ADMIN, Profil.AGENT)


# ── Création / modification ─────────────────────────────────────────────

def nouvelle_livraison(ferme, date_livraison, fournisseur):
    return Livraison(numero_metier=generer_numero('LIVRAISON', 'LIV', annuel=True), ferme=ferme,
                     date_livraison=date_livraison, fournisseur=fournisseur or None,
                     statut=S.A_CONFIRMER)


def remplacer_lignes(livraison, lignes):
    """`lignes` : liste de dicts (produit, quantite_livree, subventionne, part_subventionnee,
    valeur_unitaire). Les lignes existantes du même produit sont mises à jour."""
    actuelles = {l.produit_id: l for l in livraison.lignes}
    voulues = {d['produit'].id for d in lignes}
    for pid, l in list(actuelles.items()):
        if pid not in voulues:
            livraison.lignes.remove(l)
    for d in lignes:
        l = actuelles.get(d['produit'].id)
        if l is None:
            l = LivraisonLigne(produit=d['produit'])
            livraison.lignes.append(l)
        l.quantite_livree = d['quantite_livree']
        l.subventionne = d['subventionne']
        l.part_subventionnee = d['part_subventionnee'] if d['subventionne'] else None
        l.valeur_unitaire = d['valeur_unitaire']


# ── Confirmation ────────────────────────────────────────────────────────

def _signature(user):
    if user.profil == Profil.AGENT:
        return f' — confirmé par l\'agent {user.nom_complet} pour l\'éleveur'
    return f' — par l\'éleveur {user.nom_complet}'


def _statut_apres_reception(livraison):
    ecart = any(l.quantite_recue != l.quantite_livree for l in livraison.lignes)
    return S.RECUE_ECART if ecart else S.RECUE


def confirmer(livraison, user, receptions=None, morts=None):
    """`receptions` : {ligne_id: (quantité reçue, motif)} ; absent = tout reçu.
    `morts` : {ligne_id: morts à l'arrivée} pour les lignes de poussins."""
    receptions, morts = receptions or {}, morts or {}
    for l in livraison.lignes:
        recue, motif = receptions.get(l.id, (l.quantite_livree, None))
        l.quantite_recue = recue
        l.motif_ecart = motif if recue != l.quantite_livree else None
        l.morts_arrivee = morts.get(l.id, 0) if l.produit.type == TYPE_POUSSINS else None
    livraison.statut = _statut_apres_reception(livraison)
    livraison.confirmee_le = maintenant()
    livraison.confirmee_par = user.id
    livraison.confirmee_par_agent = user.profil == Profil.AGENT
    resume = 'tout reçu' if livraison.statut == S.RECUE else 'reçue avec écart'
    enregistrer(Action.CONFIRMATION, table='livraison', enregistrement_id=livraison.id,
                detail=f'Livraison {livraison.numero} confirmée : {resume}{_signature(user)}.')


def annulation_possible(livraison, user):
    """« Reçue ✓ — Annuler » : par la même personne, juste après « Tout reçu »."""
    if livraison.statut != S.RECUE or livraison.confirmee_par != user.id or not livraison.confirmee_le:
        return False
    ecoule = (maintenant() - en_utc(livraison.confirmee_le)).total_seconds()
    return ecoule <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def annuler_confirmation(livraison, user):
    for l in livraison.lignes:
        l.quantite_recue = l.motif_ecart = l.morts_arrivee = None
    livraison.statut = S.A_CONFIRMER
    livraison.confirmee_le = livraison.confirmee_par = None
    livraison.confirmee_par_agent = False
    enregistrer(Action.CONFIRMATION_ANNULEE, table='livraison', enregistrement_id=livraison.id,
                detail=f'Confirmation de la livraison {livraison.numero} annulée aussitôt par '
                       f'{user.nom_complet} : la livraison est de nouveau à confirmer.')


def corriger(livraison, user, receptions, morts, motif):
    for l in livraison.lignes:
        recue, motif_ecart = receptions[l.id]
        l.quantite_recue = recue
        l.motif_ecart = motif_ecart if recue != l.quantite_livree else None
        if l.produit.type == TYPE_POUSSINS:
            l.morts_arrivee = morts.get(l.id, 0)
    livraison.statut = _statut_apres_reception(livraison)
    enregistrer(Action.CORRECTION, table='livraison', enregistrement_id=livraison.id,
                detail=f'Livraison {livraison.numero} corrigée par {user.nom_complet} : {motif}')


def annuler(livraison, user, motif):
    livraison.statut = S.ANNULEE
    livraison.annulee_le = maintenant()
    livraison.annulee_par = user.id
    livraison.motif_annulation = motif


# ── Stock ───────────────────────────────────────────────────────────────

def quantites_utilisees(ferme):
    """Quantités consommées par produit ({produit_id: quantité}) : poussins mis en
    bande, sacs d'aliment saisis chaque jour (et, plus tard, vaccins et traitements)."""
    from app.models.bande import Bande, BandePoussins, SaisieJour, SaisieAliment
    utilises = {}
    poussins = (db.session.query(LivraisonLigne.produit_id, db.func.sum(BandePoussins.quantite))
                .join(BandePoussins, BandePoussins.livraison_ligne_id == LivraisonLigne.id)
                .join(Bande, BandePoussins.bande_id == Bande.id)
                .filter(Bande.ferme_id == ferme.id).group_by(LivraisonLigne.produit_id).all())
    aliment = (db.session.query(SaisieAliment.produit_id, db.func.sum(SaisieAliment.sacs))
               .join(SaisieJour, SaisieAliment.saisie_id == SaisieJour.id)
               .join(Bande, SaisieJour.bande_id == Bande.id)
               .filter(Bande.ferme_id == ferme.id).group_by(SaisieAliment.produit_id).all())
    for pid, q in poussins + aliment:
        utilises[pid] = utilises.get(pid, 0) + float(q or 0)
    return utilises


def stock_ferme(ferme):
    """Stock par produit : reçus confirmés − utilisés. Pour les poussins, les morts à
    l'arrivée sont retirés : il reste les poussins « en attente de bande »."""
    lignes = (LivraisonLigne.query.join(Livraison)
              .filter(Livraison.ferme_id == ferme.id, Livraison.statut.in_(S.CONFIRMEES)).all())
    recus = {}
    for l in lignes:
        net = (l.quantite_recue or 0) - (l.morts_arrivee or 0)
        recus[l.produit_id] = recus.get(l.produit_id, 0) + net
    utilises = quantites_utilisees(ferme)
    resultat = []
    for pid, quantite in recus.items():
        produit = db.session.get(Produit, pid)
        stock = quantite - utilises.get(pid, 0)
        resultat.append({'produit': produit, 'stock': stock,
                         'kg': stock * produit.poids_sac_kg if produit.en_sacs else None})
    ordre = {t: i for i, t in enumerate(['Poussins', 'Aliment', 'Vaccin', 'Médicament', 'Autre'])}
    return sorted(resultat, key=lambda r: (ordre.get(r['produit'].type, 9), r['produit'].nom))


# ── Alertes ─────────────────────────────────────────────────────────────

def requete_retard(base):
    jours = parametres.obtenir('intrants.delai_confirmation_jours', 3)
    return base.filter(Livraison.statut == S.A_CONFIRMER,
                       Livraison.date_livraison < date.today() - timedelta(days=jours))


def requete_ecart(base):
    jours = parametres.obtenir('intrants.alerte_ecart_jours', 30)
    return base.filter(Livraison.statut == S.RECUE_ECART,
                       Livraison.confirmee_le >= maintenant() - timedelta(days=jours))


def alertes(base):
    """Alertes des livraisons visibles (requête déjà filtrée par le périmètre)."""
    jours = parametres.obtenir('intrants.delai_confirmation_jours', 3)
    resultat = []
    n = requete_retard(base).count()
    if n:
        resultat.append({'texte': f'{n} livraison{"s" if n > 1 else ""} non confirmée{"s" if n > 1 else ""} '
                                  f'depuis plus de {jours} jour{"s" if jours > 1 else ""}',
                         'filtre': 'retard', 'niveau': 'warning', 'nombre': n})
    n = requete_ecart(base).count()
    if n:
        resultat.append({'texte': f'{n} livraison{"s" if n > 1 else ""} reçue{"s" if n > 1 else ""} avec écart',
                         'filtre': 'ecart', 'niveau': 'urgence', 'nombre': n})
    return resultat
