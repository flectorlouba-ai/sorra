"""Règles des bandes : ouverture, saisie du jour, pesée, sortie, clôture, correction.
Les calculs (effectif, mortalité, feu…) sont dans app/indicateurs.py."""
from datetime import date, timedelta

from app import db, indicateurs
from app.models import Profil, Batiment, Livraison, LivraisonLigne
from app.models.bande import (Bande, BandePoussins, SaisieJour, SaisieAliment, Pesee, Sortie,
                              StatutBande, MotifSortie)
from app.models.intrant import StatutLivraison, TYPE_POUSSINS, TYPE_ALIMENT, Produit
from app.services import parametres, intrants
from app.services.journal import enregistrer, Action
from app.services.numerotation import prochain_rang


class RegleBande(ValueError):
    """Saisie refusée, avec un message clair pour l'utilisateur."""


# ── Droits ──────────────────────────────────────────────────────────────

def peut_ouvrir(user):
    return user.profil in (Profil.ELEVEUR, Profil.AGENT, Profil.ADMIN)


def peut_rattrapage(user):
    return user.profil in (Profil.AGENT, Profil.ADMIN)


def peut_saisir(user, bande):
    return bande.en_cours and user.profil in (Profil.ELEVEUR, Profil.AGENT)


def peut_cloturer(user, bande):
    if not bande.en_cours:
        return False
    if user.profil in (Profil.AGENT, Profil.ADMIN):
        return True
    return user.profil == Profil.ELEVEUR and indicateurs.calculer(bande)['effectif_present'] <= 0


def peut_corriger(user, bande):
    if user.profil == Profil.ADMIN:
        return True
    return user.profil == Profil.AGENT and bande.en_cours


def limite_jour_passe(user):
    """Jour le plus ancien que l'utilisateur peut saisir (None = sans limite)."""
    if user.profil in (Profil.AGENT, Profil.ADMIN):
        return None
    return date.today() - timedelta(days=int(parametres.obtenir('bandes.saisie_passee_jours', 3)))


def _signer(user, bande, quoi):
    """Saisie de l'agent pour l'éleveur : inscrite au journal d'audit, en clair."""
    if user.profil == Profil.AGENT:
        enregistrer(Action.POUR_ELEVEUR, table='bande', enregistrement_id=bande.id,
                    detail=f'Bande {bande.numero} : {quoi} — agent {user.nom_complet} pour l\'éleveur.')
        return True
    return False


# ── Poussins en attente, bâtiments libres ───────────────────────────────

def utilises_par_ligne(lignes_ids):
    if not lignes_ids:
        return {}
    rows = (db.session.query(BandePoussins.livraison_ligne_id, db.func.sum(BandePoussins.quantite))
            .filter(BandePoussins.livraison_ligne_id.in_(lignes_ids))
            .group_by(BandePoussins.livraison_ligne_id).all())
    return {lid: int(q) for lid, q in rows}


def poussins_en_attente(ferme):
    """Lignes de poussins reçues et pas encore toutes mises en bande : [(ligne, disponibles)]."""
    lignes = (LivraisonLigne.query.join(Livraison).join(Produit, LivraisonLigne.produit_id == Produit.id)
              .filter(Livraison.ferme_id == ferme.id, Livraison.statut.in_(StatutLivraison.CONFIRMEES),
                      Produit.type == TYPE_POUSSINS)
              .order_by(Livraison.date_livraison).all())
    utilises = utilises_par_ligne([l.id for l in lignes])
    resultat = []
    for l in lignes:
        dispo = int((l.quantite_recue or 0) - (l.morts_arrivee or 0) - utilises.get(l.id, 0))
        if dispo > 0:
            resultat.append((l, dispo))
    return resultat


def bande_ouverte(batiment):
    return Bande.query.filter_by(batiment_id=batiment.id, statut=StatutBande.EN_COURS).first()


def derniere_cloturee(batiment):
    return (Bande.query.filter_by(batiment_id=batiment.id, statut=StatutBande.CLOTUREE)
            .order_by(Bande.date_cloture.desc(), Bande.rang.desc()).first())


def batiments_libres(ferme):
    return [b for b in ferme.batiments if b.actif and bande_ouverte(b) is None]


def aliments_disponibles(ferme, bande=None):
    """Produits d'aliment proposés à la saisie : ceux en stock, plus le dernier utilisé."""
    stock = {s['produit'].id: s for s in intrants.stock_ferme(ferme) if s['produit'].type == TYPE_ALIMENT}
    produits = {pid: s['produit'] for pid, s in stock.items() if s['stock'] > 0}
    dernier = dernier_aliment(bande) if bande else None
    if dernier:
        produits[dernier.id] = dernier
    return sorted(produits.values(), key=lambda p: (dernier is None or p.id != dernier.id, p.nom)), stock


def dernier_aliment(bande):
    for s in reversed(bande.saisies):
        if s.aliments:
            return s.aliments[-1].produit
    return None


# ── Ouverture ───────────────────────────────────────────────────────────

def _numero(ferme, batiment):
    prefixe = f'{ferme.numero_metier}-{batiment.code}'
    return prefixe, f'{prefixe}-{prochain_rang("BANDE", prefixe):02d}'


def _controle_batiment(ferme, batiment):
    if batiment is None or batiment.ferme_id != ferme.id or not batiment.actif:
        raise RegleBande('Choisissez un bâtiment de la ferme.')
    if bande_ouverte(batiment):
        raise RegleBande(f'Le bâtiment {batiment.code} a déjà une bande en cours.')


def ouvrir(ferme, batiment, ligne, effectif, jour, poids_g, auteur):
    """Ouverture normale, à partir des poussins en attente d'une livraison."""
    _controle_batiment(ferme, batiment)
    dispo = dict((l.id, d) for l, d in poussins_en_attente(ferme)).get(ligne.id if ligne else None, 0)
    if not dispo:
        raise RegleBande('Ces poussins ne sont plus en attente de bande.')
    if not effectif or effectif <= 0 or effectif > dispo:
        raise RegleBande(f'Le nombre de poussins doit être entre 1 et {dispo}.')
    if jour > date.today() or (ligne.livraison.date_livraison and jour < ligne.livraison.date_livraison):
        raise RegleBande('La date de mise en place doit être entre la livraison et aujourd\'hui.')
    bande = _nouvelle(ferme, batiment, jour, effectif, poids_g, rattrapage=False)
    bande.poussins.append(BandePoussins(ligne=ligne, quantite=effectif))
    db.session.flush()
    _signer(auteur, bande, f'ouverture avec {effectif} poussins')
    return bande


def ouvrir_rattrapage(ferme, batiment, jour, effectif, morts_cumules, poids_g, auteur):
    """Bande déjà en cours avant la mise en service : indicateurs partiels."""
    _controle_batiment(ferme, batiment)
    if not effectif or effectif <= 0:
        raise RegleBande('Indiquez l\'effectif de départ.')
    if morts_cumules < 0 or morts_cumules > effectif:
        raise RegleBande('Les morts à ce jour doivent être entre 0 et l\'effectif de départ.')
    if jour > date.today():
        raise RegleBande('La date de mise en place ne peut pas être dans le futur.')
    bande = _nouvelle(ferme, batiment, jour, effectif, poids_g, rattrapage=True)
    bande.morts_avant_suivi = morts_cumules
    db.session.flush()
    _signer(auteur, bande, f'ouverture de rattrapage ({effectif} poulets, {morts_cumules} morts à ce jour)')
    return bande


def _nouvelle(ferme, batiment, jour, effectif, poids_g, rattrapage):
    _, numero = _numero(ferme, batiment)
    duree = int(parametres.obtenir('bandes.duree_reference_jours', 45))
    poids = float(poids_g) if poids_g else float(parametres.obtenir('bandes.poids_poussin_g', 40))
    bande = Bande(numero_metier=numero, ferme=ferme, batiment=batiment,
                  rang=int(numero.rsplit('-', 1)[1]), date_mise_en_place=jour,
                  effectif_initial=effectif, poids_initial_g=poids, rattrapage=rattrapage,
                  date_fin_prevue=jour + timedelta(days=duree), statut=StatutBande.EN_COURS)
    db.session.add(bande)
    return bande


def depasse_capacite(bande):
    return bande.batiment.capacite and bande.effectif_initial > bande.batiment.capacite


# ── Saisie du jour ──────────────────────────────────────────────────────

def _controle_jour(bande, jour, user):
    if jour > date.today():
        raise RegleBande('On ne peut pas saisir un jour à venir.')
    if jour < indicateurs.debut_suivi(bande):
        raise RegleBande('Ce jour est avant le début de la bande.')
    limite = limite_jour_passe(user)
    if limite and jour < limite:
        raise RegleBande('Ce jour est trop ancien : demandez à votre agent de le saisir.')


def saisir(bande, jour, morts, aliments, user, ajouter=False):
    """`aliments` : {produit: sacs}. Renvoie (saisie, avertissements).
    Lève RegleBande, ou DejaEnvoye si une saisie existe déjà ce jour-là."""
    _controle_jour(bande, jour, user)
    existante = indicateurs.saisie_du(bande, jour)
    if existante and not ajouter:
        raise DejaEnvoye(existante)
    present = indicateurs.calculer(bande)['effectif_present']
    if morts < 0 or morts > present:
        raise RegleBande(f'Les morts du jour doivent être entre 0 et {present} (poulets présents).')
    avertissements = []
    stock = {s['produit'].id: s['stock'] for s in intrants.stock_ferme(bande.ferme)}
    for produit, sacs in aliments.items():
        if sacs < 0:
            raise RegleBande('Le nombre de sacs ne peut pas être négatif.')
        if sacs > stock.get(produit.id, 0):
            avertissements.append(f'Stock insuffisant de « {produit.nom} » ({stock.get(produit.id, 0):g} sacs '
                                  f'enregistrés) : vérifiez les livraisons.')
    s = existante or SaisieJour(bande=bande, date=jour, morts=0)
    if existante is None:
        db.session.add(s)
    s.morts += morts
    for produit, sacs in aliments.items():
        if not sacs:
            continue
        ligne = next((a for a in s.aliments if a.produit_id == produit.id), None)
        if ligne is None:
            ligne = SaisieAliment(produit=produit, sacs=0, kg=0)
            s.aliments.append(ligne)
        ligne.sacs += sacs
        ligne.kg = ligne.sacs * float(produit.poids_sac_kg or 0)
    if _signer(user, bande, f'saisie du {jour.strftime("%d/%m")} : {morts} morts, '
                            f'{sum(aliments.values()):g} sacs'):
        s.saisi_par_agent = True
    db.session.flush()
    return s, avertissements


class DejaEnvoye(Exception):
    def __init__(self, saisie):
        super().__init__('déjà envoyé')
        self.saisie = saisie


# ── Pesée, sortie ───────────────────────────────────────────────────────

def peser(bande, jour, nombre, total_kg, user):
    _controle_jour(bande, jour, user)
    present = indicateurs.calculer(bande)['effectif_present']
    if not nombre or nombre <= 0 or nombre > max(present, 1):
        raise RegleBande(f'Le nombre de poulets pesés doit être entre 1 et {present}.')
    if not total_kg or total_kg <= 0:
        raise RegleBande('Indiquez le poids total lu sur la balance.')
    moyen = total_kg / nombre * 1000
    p = Pesee(bande=bande, date=jour, nombre_pesees=nombre, poids_total_kg=total_kg, poids_moyen_g=round(moyen, 1),
              poids_attendu_g=round(indicateurs.poids_attendu(indicateurs.age(bande, jour)), 1))
    db.session.add(p)
    p.saisi_par_agent = _signer(user, bande, f'pesée de {nombre} poulets ({total_kg:g} kg)')
    db.session.flush()
    return p


def sortir(bande, jour, motif, operateur, libre, nombre, poids_kg, user):
    _controle_jour(bande, jour, user)
    if motif not in MotifSortie.TOUS:
        raise RegleBande('Choisissez pour qui sont les poulets.')
    if motif == MotifSortie.ABATTOIR and (operateur is None or operateur.type != 'Abattoir'):
        raise RegleBande('Choisissez l\'abattoir dans la liste.')
    if motif == MotifSortie.VENTE and operateur is None and not libre:
        raise RegleBande('Indiquez l\'acheteur (dans la liste ou son nom).')
    present = indicateurs.calculer(bande)['effectif_present']
    if not nombre or nombre <= 0 or nombre > present:
        raise RegleBande(f'Le nombre de poulets doit être entre 1 et {present} (poulets présents).')
    if not poids_kg or poids_kg <= 0:
        raise RegleBande('Indiquez le poids total des poulets (kg).')
    s = Sortie(bande=bande, date=jour, motif=motif, operateur=operateur,
               destinataire_libre=(libre or None) if operateur is None else None,
               nombre=nombre, poids_total_kg=poids_kg)
    db.session.add(s)
    s.saisi_par_agent = _signer(user, bande, f'sortie de {nombre} poulets ({motif})')
    db.session.flush()
    from app.services import tracabilite
    tracabilite.creer_lot(s, user)   # abattoir ou vente : lot tracé avec son QR code
    db.session.flush()
    return s


# ── Clôture, correction ─────────────────────────────────────────────────

def cloturer(bande, user, motif=None):
    present = indicateurs.calculer(bande)['effectif_present']
    if present > 0 and not motif:
        raise RegleBande(f'Il reste {present} poulets : indiquez le motif de la clôture.')
    bande.statut = StatutBande.CLOTUREE
    bande.date_cloture = date.today()
    bande.cloturee_par = user.id
    bande.motif_cloture = motif or None
    db.session.flush()
    bande.bilan = indicateurs.bilan(bande)


def apres_correction(bande, user, quoi, motif):
    if not bande.en_cours:
        bande.bilan = indicateurs.bilan(bande)   # le bilan figé est recalculé
    enregistrer(Action.CORRECTION, table='bande', enregistrement_id=bande.id,
                detail=f'Bande {bande.numero} : {quoi} corrigé(e) par {user.nom_complet} — {motif}')


# ── Bâtiment : état pour l'affichage ────────────────────────────────────

def etat_batiment(batiment):
    """('bande', bande) | ('vide', jours depuis la clôture, dernière bande) | ('neuf', None)."""
    ouverte = bande_ouverte(batiment)
    if ouverte:
        return {'etat': 'bande', 'bande': ouverte}
    derniere = derniere_cloturee(batiment)
    if derniere:
        return {'etat': 'vide', 'jours': (date.today() - derniere.date_cloture).days, 'derniere': derniere}
    return {'etat': 'neuf'}


def precedente(bande):
    """Bande clôturée précédente du même bâtiment (pour comparer)."""
    return (Bande.query.filter(Bande.batiment_id == bande.batiment_id, Bande.statut == StatutBande.CLOTUREE,
                               Bande.rang < bande.rang)
            .order_by(Bande.rang.desc()).first())
