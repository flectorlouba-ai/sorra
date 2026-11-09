"""Règles des intrants : livraisons, confirmation de réception, stock, alertes."""
from datetime import date, timedelta

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.intrant import (Livraison, LivraisonLigne, Produit, StatutLivraison as S,
                                TYPE_POUSSINS, OrigineLivraison)
from app.services import parametres
from app.services.journal import enregistrer, Action
from app.services.numerotation import generer_numero
from app.utils.dates import en_utc

# Après « Tout reçu », le bandeau « Annuler » reste 10 s à l'écran ; le serveur
# accepte l'annulation un peu plus longtemps pour couvrir un réseau lent.
DELAI_ANNULATION_SECONDES = 10
TOLERANCE_RESEAU_SECONDES = 20


def livraisons_de_l_etat(requete):
    """Seulement les livraisons de l'État (pas les achats personnels de l'éleveur).
    À utiliser pour tout contrôle des intrants subventionnés : listes, alertes,
    mortalité à l'arrivée par fournisseur, exports, et le futur recoupement
    livraisons / consommations."""
    return requete.filter(Livraison.origine == OrigineLivraison.ETAT)


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


# ── Achats personnels de l'éleveur (lot 9) ─────────────────────────────

class RegleAchat(Exception):
    pass


def jour_le_plus_ancien_achat(user):
    """Comme les saisies : l'éleveur remonte au plus de N jours (paramètre), l'agent sans limite."""
    if user.profil in (Profil.AGENT, Profil.ADMIN):
        return None
    from app.services import hors_ligne
    return hors_ligne.jour_de_saisie() - timedelta(days=int(parametres.obtenir('bandes.saisie_passee_jours', 3)))


def produits_frequents(ferme, nombre=6):
    """Produits du catalogue les plus présents dans les livraisons et achats de la ferme."""
    from sqlalchemy import func
    rangs = dict(db.session.query(LivraisonLigne.produit_id, func.count(LivraisonLigne.id))
                 .join(Livraison).filter(Livraison.ferme_id == ferme.id)
                 .group_by(LivraisonLigne.produit_id).all())
    actifs = Produit.query.filter_by(actif=True).all()
    actifs.sort(key=lambda p: (-rangs.get(p.id, 0), p.type != 'Aliment', p.nom))
    return actifs[:nombre]


def enregistrer_achat(ferme, produit, quantite, morts, prix, lieu, jour, user, photo=None, batiment=None):
    """Achat personnel : une « livraison » d'origine ACHAT, reçue d'emblée, non subventionnée."""
    if produit is None or not produit.actif:
        raise RegleAchat('Choisissez le produit acheté.')
    if not quantite or quantite <= 0:
        raise RegleAchat('Indiquez la quantité achetée.')
    if jour > date.today():
        raise RegleAchat('La date ne peut pas être dans le futur.')
    limite = jour_le_plus_ancien_achat(user)
    if limite and jour < limite:
        raise RegleAchat('Cet achat est trop ancien : demandez à votre agent de le saisir.')
    poussins = produit.type == TYPE_POUSSINS
    morts = int(morts or 0) if poussins else None
    if poussins and (morts < 0 or morts > quantite):
        raise RegleAchat("Le nombre de poussins morts à l'arrivée est impossible.")
    if prix is not None and prix < 0:
        raise RegleAchat('Le prix payé ne peut pas être négatif.')
    if batiment is not None and (batiment.ferme_id != ferme.id or poussins):
        batiment = None          # poussins : ils vont à la bande qui les reçoit (lot 11)
    achat = Livraison(numero_metier=generer_numero('ACHAT', 'ACH', annuel=True), ferme=ferme,
                      date_livraison=jour, fournisseur=(lieu or '').strip()[:150] or None,
                      origine=OrigineLivraison.ACHAT, statut=S.RECUE, prix_paye_fcfa=prix,
                      confirmee_le=maintenant(), confirmee_par=user.id,
                      confirmee_par_agent=user.profil == Profil.AGENT, photo_recu=photo,
                      batiment_id=batiment.id if batiment else None)
    achat.lignes.append(LivraisonLigne(produit=produit, quantite_livree=quantite, quantite_recue=quantite,
                                       morts_arrivee=morts, subventionne=False, part_subventionnee=None,
                                       valeur_unitaire=round(prix / quantite, 2) if prix else None))
    db.session.add(achat)
    db.session.flush()
    return achat


def achat_annulable(achat, user):
    """« Enregistré ✓ — Annuler (10) » : par la même personne, juste après, et tant que
    rien n'a été pris dans cet achat (poussins mis en bande)."""
    if not achat.est_achat or achat.statut != S.RECUE or achat.confirmee_par != user.id or not achat.confirmee_le:
        return False
    from app.services.bandes import utilises_par_ligne
    if any(utilises_par_ligne([l.id for l in achat.lignes]).values()):
        return False
    ecoule = (maintenant() - en_utc(achat.confirmee_le)).total_seconds()
    return ecoule <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def annuler_achat(achat, user):
    """Statut annulé (inscrit au journal), l'achat sort du stock."""
    achat.statut = S.ANNULEE
    achat.annulee_le = maintenant()
    achat.annulee_par = user.id
    achat.motif_annulation = "Annulé aussitôt par l'éleveur"


def corriger_achat(achat, user, quantite, morts, prix, lieu, jour, motif):
    """Correction par l'agent (ou l'ADMIN), avec motif inscrit au journal."""
    if not motif:
        raise RegleAchat('Indiquez le motif de la correction.')
    if not quantite or quantite <= 0:
        raise RegleAchat('Indiquez la quantité achetée.')
    if jour > date.today():
        raise RegleAchat('La date ne peut pas être dans le futur.')
    l = achat.lignes[0]
    if l.produit.type == TYPE_POUSSINS:
        morts = int(morts or 0)
        if morts < 0 or morts > quantite:
            raise RegleAchat("Le nombre de poussins morts à l'arrivée est impossible.")
        l.morts_arrivee = morts
    l.quantite_livree = l.quantite_recue = quantite
    achat.prix_paye_fcfa = prix
    l.valeur_unitaire = round(prix / quantite, 2) if prix else None
    achat.fournisseur = (lieu or '').strip()[:150] or None
    achat.date_livraison = jour
    enregistrer(Action.CORRECTION, table='livraison', enregistrement_id=achat.id,
                detail=f'Achat {achat.numero} corrigé par {user.nom_complet} : {motif}')


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
    from app.models.sante import Vaccination, Traitement
    soins = []
    for modele in (Vaccination, Traitement):
        q = (db.session.query(modele.produit_id, db.func.sum(modele.quantite))
             .join(Bande, modele.bande_id == Bande.id).filter(Bande.ferme_id == ferme.id))
        if modele is Vaccination:
            q = q.filter(Vaccination.annule.is_(False))      # « Annuler (10) » (lot 11)
        soins += q.group_by(modele.produit_id).all()
    for pid, q in poussins + aliment + soins:
        utilises[pid] = utilises.get(pid, 0) + float(q or 0)
    return utilises


def stock_ferme(ferme):
    """Stock par produit : reçus confirmés − utilisés. Pour les poussins, les morts à
    l'arrivée sont retirés : il reste les poussins « en attente de bande »."""
    lignes = (LivraisonLigne.query.join(Livraison)
              .filter(Livraison.ferme_id == ferme.id, Livraison.statut.in_(S.CONFIRMEES)).all())
    recus, sources = {}, {}
    for l in lignes:
        net = (l.quantite_recue or 0) - (l.morts_arrivee or 0)
        recus[l.produit_id] = recus.get(l.produit_id, 0) + net
        s = sources.setdefault(l.produit_id, {OrigineLivraison.ETAT: 0, OrigineLivraison.ACHAT: 0})
        s[l.livraison.origine] = s.get(l.livraison.origine, 0) + net
    utilises = quantites_utilisees(ferme)
    resultat = []
    for pid, quantite in recus.items():
        produit = db.session.get(Produit, pid)
        stock = quantite - utilises.get(pid, 0)
        resultat.append({'produit': produit, 'stock': stock,
                         'kg': stock * produit.poids_sac_kg if produit.en_sacs else None,
                         # entrées par source (lot 9) : livraisons de l'État, achats personnels
                         'etat': sources[pid][OrigineLivraison.ETAT], 'achat': sources[pid][OrigineLivraison.ACHAT]})
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
    base = livraisons_de_l_etat(base)
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
