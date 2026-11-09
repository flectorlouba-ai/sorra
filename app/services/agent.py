"""Lot 16 — l'agent technique : urgence des fermes (une seule fonction pour Mes fermes, la tournée
et la fiche), nouvel éleveur, inventaire de stock, commandes d'intrants, biosécurité."""
import secrets
from datetime import date

from app import db, indicateurs
from app.models import Ferme, Profil, Utilisateur, UtilisateurFerme
from app.models.agent import CommandeIntrant, InventaireStock, StatutCommande as SC
from app.models.base import maintenant
from app.services import parametres

ROUGE, ORANGE = 10, 3


class RegleAgent(Exception):
    pass


# ── Urgence ─────────────────────────────────────────────────────────────

def urgences(fermes):
    """{ferme_id: {'score', 'couleur', 'raisons': [(couleur, texte)]}} — rouge 10, orange 3."""
    from app.models import Bande, Livraison
    from app.models.bande import StatutBande
    from app.models.hors_ligne import ConflitHorsLigne, StatutVerification
    from app.models.sante import AlerteSanitaire, StatutAlerte
    from app.models.visite import Visite, StatutVisite
    from app.services import intrants, verifications
    ids = [f.id for f in fermes]
    raisons = {i: [] for i in ids}
    if not ids:
        return {}

    def ajouter(fid, couleur, texte):
        if fid in raisons:
            raisons[fid].append((couleur, texte))

    for a in AlerteSanitaire.query.filter(AlerteSanitaire.ferme_id.in_(ids),
                                          AlerteSanitaire.statut.in_(StatutAlerte.OUVERTES)):
        if not a.reponses:
            ajouter(a.ferme_id, 'rouge', 'Signalement sanitaire sans réponse')
    for b in Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS):
        couleur, _ = indicateurs.feu(b)
        if couleur in ('rouge', 'orange'):
            ajouter(b.ferme_id, couleur, f'Bande {b.numero} en {couleur}')
    for c in verifications.a_trancher(ConflitHorsLigne.query.filter(ConflitHorsLigne.ferme_id.in_(ids))):
        ajouter(c.ferme_id, 'rouge' if verifications.en_retard(c) else 'orange', 'Saisie à vérifier')
    for liv in intrants.requete_retard(Livraison.query.filter(Livraison.ferme_id.in_(ids))):
        ajouter(liv.ferme_id, 'orange', f'Livraison {liv.numero} pas confirmée')
    for v in Visite.query.filter(Visite.ferme_id.in_(ids), Visite.statut == StatutVisite.PREVUE,
                                 Visite.date_prevue < date.today()):
        ajouter(v.ferme_id, 'orange', f'Visite prévue le {v.date_prevue:%d/%m} pas faite')
    for inv in derniers_inventaires(ids):
        if hors_seuil(inv):
            ajouter(inv.ferme_id, 'orange', f'Écart de stock {inv.produit.nom} : {inv.ecart_pct:g} %')
    for c in CommandeIntrant.query.filter(CommandeIntrant.ferme_id.in_(ids), CommandeIntrant.statut == SC.REFUSEE,
                                          CommandeIntrant.refus_lu_le.is_(None)):
        ajouter(c.ferme_id, 'orange', f'Commande refusée : {c.produit.nom}')
    for fid, score in derniers_scores_biosecurite(ids).items():
        if score < 50:
            ajouter(fid, 'rouge', f'Biosécurité {score} %')
    resultat = {}
    for fid, r in raisons.items():
        score = sum(ROUGE if c == 'rouge' else ORANGE for c, _ in r)
        couleur = 'rouge' if any(c == 'rouge' for c, _ in r) else 'orange' if r else 'vert'
        resultat[fid] = {'score': score, 'couleur': couleur, 'raisons': sorted(r, key=lambda x: x[0] != 'rouge')}
    return resultat


def trier_par_urgence(fermes):
    u = urgences(fermes)
    return sorted(fermes, key=lambda f: (-u[f.id]['score'], f.numero_metier or '')), u


def tournee(user):
    """Visites prévues aujourd'hui ou en retard, puis fermes en rouge sans visite prévue."""
    from app.services import visites
    fermes = Ferme.query.filter_by(agent_id=user.id).all()
    u = urgences(fermes)
    lignes, vues = [], set()
    for v in visites.du_jour_pour_agent(user):
        lignes.append({'ferme': v.ferme, 'visite': v, 'urgence': u.get(v.ferme_id)})
        vues.add(v.ferme_id)
    for f in sorted(fermes, key=lambda f: -u[f.id]['score']):
        if f.id not in vues and u[f.id]['couleur'] == 'rouge':
            lignes.append({'ferme': f, 'visite': None, 'urgence': u[f.id]})
    return lignes


# ── Nouvel éleveur ──────────────────────────────────────────────────────

LETTRES = 'abcdefghjkmnpqrstuvwxyz23456789'           # sans 0/O, 1/l/i : lisibles à l'oral


def mot_de_passe_provisoire():
    return ''.join(secrets.choice(LETTRES) for _ in range(10))


def identifiant_propose(nom, prenom):
    import re
    import unicodedata
    base = unicodedata.normalize('NFKD', f'{prenom or ""}.{nom or ""}'.strip('.')).encode('ascii', 'ignore').decode()
    base = re.sub(r'[^a-z0-9.]', '', base.lower()) or 'eleveur'
    ident, n = base, 2
    while Utilisateur.query.filter_by(identifiant=ident).first():
        ident, n = f'{base}{n}', n + 1
    return ident


def peut_gerer(user, ferme):
    return user.profil == Profil.ADMIN or (user.profil == Profil.AGENT and ferme.agent_id == user.id)


def _chiffres(tel):
    return ''.join(c for c in (tel or '') if c.isdigit())[-8:]


def creer_eleveur(ferme, nom, prenom, telephone, user, identifiant=None, provisoire=None):
    """Compte ÉLEVEUR rattaché à la ferme ; mot de passe provisoire rendu UNE fois, à changer.
    Création inscrite au journal automatiquement (mot de passe masqué)."""
    nom, prenom, telephone = (nom or '').strip(), (prenom or '').strip(), (telephone or '').strip()
    if not nom:
        raise RegleAgent("Indiquez le nom de l'éleveur.")
    if not telephone:
        raise RegleAgent("Indiquez le téléphone de l'éleveur.")
    # Même éleveur inscrit deux fois (deux agents sans réseau, ou deux envois) : le second est refusé
    ids = [uf.utilisateur_id for uf in UtilisateurFerme.query.filter_by(ferme_id=ferme.id)]
    deja = [x for x in (Utilisateur.query.filter(Utilisateur.id.in_(ids)).all() if ids else [])
            if x.profil == Profil.ELEVEUR and _chiffres(x.telephone) == _chiffres(telephone)]
    if deja:
        raise RegleAgent(f'Cet éleveur a déjà un compte sur cette ferme : {deja[0].identifiant}.')
    # Préparés sur le téléphone (marche sans réseau) ; sinon ici
    if not (provisoire and len(provisoire) == 10 and all(c in LETTRES for c in provisoire)):
        provisoire = mot_de_passe_provisoire()
    voulu = (identifiant or '').strip().lower()
    libre = voulu and all(c.isalnum() or c == '.' for c in voulu) \
        and Utilisateur.query.filter_by(identifiant=voulu).first() is None
    u = Utilisateur(identifiant=voulu if libre else identifiant_propose(nom, prenom), nom=nom[:100], prenom=prenom[:100] or None,
                    telephone=telephone[:30], profil=Profil.ELEVEUR, actif=True, doit_changer_mdp=True)
    u.set_password(provisoire)
    u.fermes = [UtilisateurFerme(ferme=ferme)]
    db.session.add(u)
    db.session.flush()
    u.identifiant_change = bool(voulu) and not libre
    return u, provisoire


# ── Inventaire de stock ─────────────────────────────────────────────────

def seuil_ecart():
    return parametres.obtenir('intrants.seuil_ecart_stock_pct', 10)


def hors_seuil(inv):
    return inv.livre and inv.ecart_pct > seuil_ecart()


def compter(ferme, produit, compte, user, jour=None):
    from app.models.intrant import Livraison, LivraisonLigne, StatutLivraison
    from app.services import intrants
    if compte is None or compte < 0:
        raise RegleAgent('Indiquez la quantité comptée (0 ou plus).')
    livre = sum(((l.quantite_recue or 0) - (l.morts_arrivee or 0)) for l in
                LivraisonLigne.query.join(Livraison).filter(Livraison.ferme_id == ferme.id,
                                                            Livraison.statut.in_(StatutLivraison.CONFIRMEES),
                                                            LivraisonLigne.produit_id == produit.id))
    utilise = intrants.quantites_utilisees(ferme).get(produit.id, 0)
    inv = InventaireStock(ferme_id=ferme.id, produit_id=produit.id, jour=jour or date.today(), livre=livre,
                          utilise=utilise, compte=compte, agent_id=user.id)
    db.session.add(inv)
    db.session.flush()
    return inv


def derniers_inventaires(ferme_ids):
    """Le dernier inventaire de chaque produit de chaque ferme."""
    if not ferme_ids:
        return []
    vus, resultat = set(), []
    for inv in (InventaireStock.query.filter(InventaireStock.ferme_id.in_(ferme_ids))
                .order_by(InventaireStock.jour.desc(), InventaireStock.id.desc())):
        if (inv.ferme_id, inv.produit_id) not in vus:
            vus.add((inv.ferme_id, inv.produit_id))
            resultat.append(inv)
    return resultat


# ── Commandes d'intrants ────────────────────────────────────────────────

def commander(ferme, produit, quantite, motif, user):
    if produit is None:
        raise RegleAgent('Choisissez le produit.')
    if not quantite or quantite <= 0:
        raise RegleAgent('Indiquez une quantité supérieure à 0.')
    c = CommandeIntrant(ferme_id=ferme.id, produit_id=produit.id, quantite=quantite,
                        motif=(motif or '').strip()[:300] or None, demandee_par=user.id)
    db.session.add(c)
    db.session.flush()
    return c


def peut_decider_commande(user):
    return user.profil in (Profil.DGE, Profil.ADMIN)


def decider_commande(c, user, valider, motif=None):
    if not peut_decider_commande(user):
        raise RegleAgent('Seules la DGE et l’administration décident des commandes.')
    if c.statut != SC.ENVOYEE:
        raise RegleAgent('Cette commande a déjà été décidée.')
    if not valider and not (motif or '').strip():
        raise RegleAgent('Indiquez le motif du refus.')
    c.statut = SC.VALIDEE if valider else SC.REFUSEE
    c.decidee_par, c.decidee_le = user.id, maintenant()
    c.motif_refus = None if valider else motif.strip()[:300]


def marquer_livree(c, livraison):
    """Appelé quand la livraison liée à une commande validée est créée (lot 18 B)."""
    if c.statut != SC.VALIDEE:
        raise RegleAgent('Seule une commande validée peut être livrée.')
    c.statut, c.livraison_id = SC.LIVREE, livraison.id


# ── Biosécurité ─────────────────────────────────────────────────────────

def grille():
    from app.models.liste_deroulante import ld_choices
    return [v for v, _ in ld_choices('grille_biosecurite')]


def score(reponses):
    """Oui ÷ (Oui + Non) × 100, arrondi ; « Sans objet » ne compte pas. None sans réponse."""
    oui = sum(1 for r in reponses.values() if r == 'oui')
    non = sum(1 for r in reponses.values() if r == 'non')
    return round(oui * 100 / (oui + non)) if oui + non else None


def couleur_score(s):
    if s is None:
        return 'gris'
    return 'rouge' if s < 50 else 'orange' if s < 80 else 'vert'


def evaluer(ferme, user, reponses, mesures, jour=None):
    """Grille remplie → une visite « Biosécurité » faite, que l'éleveur lit dans « Mes visites »."""
    from app.models.visite import Visite, StatutVisite
    points = grille()
    reponses = {p: reponses.get(p) for p in points if reponses.get(p) in ('oui', 'non', 'so')}
    if len(reponses) < len(points):
        raise RegleAgent('Répondez à chaque point de la grille (Oui, Non ou Sans objet).')
    mesures = [{'point': p, 'mesure': (mesures.get(p) or '').strip()[:200]} for p in points if reponses[p] == 'non']
    if any(not m['mesure'] for m in mesures):
        raise RegleAgent('Indiquez une mesure corrective pour chaque point « Non ».')
    v = Visite(ferme_id=ferme.id, agent_id=user.id, objet='Biosécurité', statut=StatutVisite.FAITE,
               faite_le=jour or date.today(), recommandations=[], biosecurite=reponses,
               score_biosecurite=score(reponses), mesures_correctives=mesures)
    db.session.add(v)
    db.session.flush()
    return v


def derniers_scores_biosecurite(ferme_ids):
    from app.models.visite import Visite, StatutVisite
    scores = {}
    if not ferme_ids:
        return scores
    for v in (Visite.query.filter(Visite.ferme_id.in_(ferme_ids), Visite.statut == StatutVisite.FAITE,
                                  Visite.score_biosecurite.isnot(None))
              .order_by(Visite.faite_le.desc(), Visite.cree_le.desc())):
        scores.setdefault(v.ferme_id, v.score_biosecurite)
    return scores
