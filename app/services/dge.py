"""Lot 18 — la DGE : planning des livraisons de l'État (Prévue → Livrée → Confirmée), « Créer la
livraison » d'une commande validée, arbitrages par province, classement pondéré des fermes, rapports
mensuels gardés (e-mail préparé, coupé), affectation et charge des agents."""
import os
from datetime import date, timedelta

from app import db
from app.models import Ferme, Profil, Utilisateur, Livraison, Bande
from app.models.base import maintenant
from app.models.intrant import StatutLivraison as S, OrigineLivraison
from app.services import parametres


class RegleDge(Exception):
    pass


NATIONAUX = (Profil.DGE, Profil.ADMIN)


# ── A. Planning des livraisons de l'État ────────────────────────────────

COLONNES = [('PREVUE', 'Prévue'), ('LIVREE', 'Livrée'), ('CONFIRMEE', 'Confirmée')]


def colonne(liv):
    if liv.statut == S.PREVUE:
        return 'PREVUE'
    if liv.statut == S.A_CONFIRMER:
        return 'LIVREE'
    if liv.statut in S.CONFIRMEES:
        return 'CONFIRMEE'
    return None


def planning(user, debut=None, fin=None):
    from app.utils.permissions import filtre_perimetre
    debut = debut or date.today() - timedelta(days=14)
    fin = fin or date.today() + timedelta(days=28)
    q = (filtre_perimetre(Livraison.query, utilisateur=user)
         .filter(Livraison.origine == OrigineLivraison.ETAT, Livraison.statut != S.ANNULEE)
         .filter((Livraison.statut == S.PREVUE) | Livraison.date_livraison.between(debut, fin))
         .order_by(Livraison.date_livraison, Livraison.numero_metier))
    resultat = {c: [] for c, _ in COLONNES}
    for liv in q:
        c = colonne(liv)
        if c:
            resultat[c].append(liv)
    return resultat, debut, fin


def prevoir(ferme, jour, produit, quantite, fournisseur, user):
    from app.services import intrants
    if ferme is None or produit is None:
        raise RegleDge('Choisissez la ferme et le produit.')
    if not ferme.programme_poufa:                                  # lot A3
        raise RegleDge("Cette ferme est hors programme : pas de livraison ni de commande de l'État.")
    if jour is None:
        raise RegleDge('Indiquez la date prévue.')
    if not quantite or quantite <= 0:
        raise RegleDge('Indiquez une quantité supérieure à 0.')
    liv = intrants.nouvelle_livraison(ferme, jour, fournisseur)
    liv.statut = S.PREVUE
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': produit, 'quantite_livree': quantite, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    db.session.flush()
    return liv


def marquer_livree(liv, user):
    """Prévue → Livrée (« À confirmer ») : l'éleveur la voit et la confirme comme avant."""
    if liv.statut != S.PREVUE:
        raise RegleDge('Seule une livraison prévue peut être marquée livrée.')
    liv.statut = S.A_CONFIRMER
    if liv.date_livraison > date.today():
        liv.date_livraison = date.today()


def annuler_prevue(liv, motif, user):
    if liv.statut != S.PREVUE:
        raise RegleDge('Seule une livraison prévue peut être annulée ici.')
    if not (motif or '').strip():
        raise RegleDge("Indiquez le motif de l'annulation.")
    liv.statut, liv.annulee_le, liv.annulee_par, liv.motif_annulation = S.ANNULEE, maintenant(), user.id, motif.strip()


# ── B. Commande validée → livraison prévue ──────────────────────────────

def creer_livraison_commande(commande, user):
    from app.models.agent import StatutCommande
    from app.services import agent
    if user.profil not in NATIONAUX:
        raise RegleDge('Réservé à la DGE et à l’administration.')
    if commande.statut != StatutCommande.VALIDEE:
        raise RegleDge('Seule une commande validée peut devenir une livraison.')
    liv = prevoir(commande.ferme, date.today() + timedelta(days=7), commande.produit, commande.quantite, None, user)
    agent.marquer_livree(commande, liv)
    return liv


# ── C. Arbitrages par province ──────────────────────────────────────────

def arbitrages_par_province(user):
    from app.models.hors_ligne import ConflitHorsLigne
    from app.services import verifications
    from app.utils.permissions import filtre_perimetre
    compte = {}
    for c in verifications.a_trancher(filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)):
        if c.ferme is None:
            continue
        d = compte.setdefault(c.ferme.province, {'province': c.ferme.province, 'n': 0, 'retard': 0})
        d['n'] += 1
        d['retard'] += 1 if verifications.en_retard(c) else 0
    return sorted(compte.values(), key=lambda d: (-d['retard'], -d['n'], d['province'].ordre))


# ── D. Classement pondéré ───────────────────────────────────────────────

CRITERES = [('mortalite', 'Mortalité'), ('ic', 'Indice de consommation'), ('gmq', 'Croissance (GMQ)'),
            ('regularite', 'Régularité des saisies')]
SEUIL_COMPLET = 80          # valeur par défaut du paramètre classement.seuil_complet_pct


def seuil_complet():
    return parametres.obtenir('classement.seuil_complet_pct', SEUIL_COMPLET)


def bareme():
    """Bornes des notes (paramètres classement.*, quatre yeux) : valeur qui donne 0 et valeur qui donne 100."""
    o = parametres.obtenir
    return {'mortalite_zero': float(o('classement.mortalite_note_zero_pct', 10)),
            'ic_100': float(o('classement.ic_note_100', 1.4)), 'ic_zero': float(o('classement.ic_note_zero', 2.6)),
            'gmq_zero': float(o('classement.gmq_note_zero', 30)), 'gmq_100': float(o('classement.gmq_note_100', 70))}


def poids():
    return {c: parametres.obtenir(f'classement.poids_{c}', d) for c, d in
            (('mortalite', 35), ('ic', 25), ('gmq', 20), ('regularite', 20))}


def _borne(x):
    return max(0.0, min(100.0, x))


def _lineaire(x, zero, cent):
    """0 à `zero`, 100 à `cent`, droite entre les deux (dans un sens ou dans l'autre)."""
    return _borne((x - zero) / (cent - zero) * 100) if cent != zero else 0.0


def notes(bilan, b=None):
    """Notes sur 100 de chaque critère, selon le barème des paramètres (à valider : docs/a_faire_valider.md)."""
    b = b or bareme()
    return {'mortalite': _lineaire(bilan.get('mortalite') or 0, b['mortalite_zero'], 0),
            'ic': _lineaire(bilan.get('indice_consommation') or b['ic_zero'], b['ic_zero'], b['ic_100']),
            'gmq': _lineaire(bilan.get('gmq') or b['gmq_zero'], b['gmq_zero'], b['gmq_100']),
            'regularite': _borne(bilan.get('regularite') or 0)}


def incomplete(bilan, seuil=None):
    seuil = seuil_complet() if seuil is None else seuil
    return bool(bilan.get('incomplet')) or (bilan.get('regularite') or 0) < seuil or not bilan.get('gmq')


def classement(user, province_id=None, cohorte=None):
    from app.models.bande import StatutBande
    from app.utils.permissions import filtre_perimetre
    p, b, seuil = poids(), bareme(), seuil_complet()
    total = sum(p.values()) or 1
    depuis = date.today() - timedelta(days=365)
    q = filtre_perimetre(Ferme.query, utilisateur=user)
    if province_id:
        q = q.filter(Ferme.province_id == province_id)
    if cohorte in (1, 2):
        q = q.filter(Ferme.cohorte == cohorte)
    classees, non_classees, ignorees = [], [], 0
    for f in q:
        bandes = Bande.query.filter(Bande.ferme_id == f.id, Bande.statut == StatutBande.CLOTUREE,
                                    Bande.date_cloture >= depuis).all()
        completes = [x for x in bandes if x.bilan and not incomplete(x.bilan, seuil)]
        n_inc = len(bandes) - len(completes)
        ignorees += n_inc
        if not completes:
            if bandes:
                non_classees.append({'ferme': f, 'incompletes': n_inc})
            continue
        moyennes = {c: sum(notes(x.bilan, b)[c] for x in completes) / len(completes) for c, _ in CRITERES}
        score = sum(moyennes[c] * p[c] for c, _ in CRITERES) / total
        classees.append({'ferme': f, 'score': round(score, 1), 'notes': {c: round(v) for c, v in moyennes.items()},
                         'bandes': len(completes), 'incompletes': n_inc})
    classees.sort(key=lambda x: (-x['score'], x['ferme'].numero_metier))
    for i, x in enumerate(classees, 1):
        x['rang'] = i
    return {'classees': classees, 'non_classees': non_classees, 'ignorees': ignorees, 'poids': p, 'bareme': b,
            'seuil': seuil}


# ── E. Rapports mensuels gardés ─────────────────────────────────────────

def dossier_rapports():
    from flask import current_app
    d = os.path.join(current_app.instance_path, 'rapports')
    os.makedirs(d, exist_ok=True)
    return d


def mois_termines(nombre=12):
    """Les `nombre` derniers mois terminés, du plus récent au plus ancien (« 2026-10 »…)."""
    premier = date.today().replace(day=1)
    resultat = []
    for _ in range(nombre):
        premier = (premier - timedelta(days=1)).replace(day=1)
        resultat.append(premier.strftime('%Y-%m'))
    return resultat


def generer_mensuel(mois, user):
    """PDF du rapport mensuel national, gardé ; jamais régénéré s'il existe déjà."""
    from app.models.dge import RapportMensuel
    from app.routes.pilotage import contenu_mensuel
    existant = RapportMensuel.query.filter_by(mois=mois).first()
    if existant is not None:
        return existant, False
    contenu = contenu_mensuel(mois, user)
    nom = f'rapport_mensuel_{mois.replace("-", "")}.pdf'
    with open(os.path.join(dossier_rapports(), nom), 'wb') as f:
        f.write(contenu)
    r = RapportMensuel(mois=mois, fichier=nom, genere_par=user.id if user else None)
    db.session.add(r)
    db.session.flush()
    preparer_email(r)
    return r, True


def generer_manquants(user, nombre=1):
    """Rapports des mois terminés pas encore produits (par défaut : le dernier mois)."""
    return [r for r, nouveau in (generer_mensuel(m, user) for m in mois_termines(nombre)) if nouveau]


def destinataires():
    texte = parametres.obtenir('rapports.email_destinataires', '') or ''
    return [a.strip() for a in texte.replace(';', ',').split(',') if '@' in a]


def email_actif():
    return bool(parametres.obtenir('rapports.email_actif', False))


def preparer_email(rapport):
    """Construit le message (objet, texte, PDF joint). Envoi COUPÉ : interrupteur `rapports.email_actif`
    à 0 et aucun serveur de messagerie configuré. Rien ne part ; le journal dit « préparé, non envoyé »."""
    from email.message import EmailMessage
    from app.services.journal import enregistrer, Action
    m = EmailMessage()
    m['Subject'] = f'SORRA — Rapport mensuel national {rapport.mois[5:]}/{rapport.mois[:4]}'
    m['To'] = ', '.join(destinataires()) or '(aucun destinataire)'
    m.set_content(f'Bonjour,\n\nVeuillez trouver ci-joint le rapport mensuel national de {rapport.mois[5:]}/{rapport.mois[:4]}.\n\nSORRA')
    with open(os.path.join(dossier_rapports(), rapport.fichier), 'rb') as f:
        m.add_attachment(f.read(), maintype='application', subtype='pdf', filename=rapport.fichier)
    rapport.email_prepare_le = maintenant()
    enregistrer(Action.EXPORT, table='rapport_mensuel', enregistrement_id=str(rapport.id),
                detail=f'Rapport mensuel {rapport.mois} : e-mail préparé, non envoyé (envoi coupé)')
    return m


# ── F. Agents : affectation et charge ───────────────────────────────────

CHARGE_ORANGE, CHARGE_ROUGE = 15, 25


def charge_des_agents(user):
    from app.models.bande import StatutBande
    from app.models.hors_ligne import ConflitHorsLigne
    from app.models.visite import Visite, StatutVisite
    from app.services import agent, verifications
    resultat = []
    for a in Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True).order_by(Utilisateur.nom):
        if not user.est_national and not set(a.province_ids) & set(user.province_ids):
            continue
        fermes = Ferme.query.filter_by(agent_id=a.id).all()
        ids = [f.id for f in fermes]
        u = agent.urgences(fermes)
        n = len(fermes)
        resultat.append({
            'agent': a, 'fermes': n,
            'bandes': Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS).count() if ids else 0,
            'rouges': sum(1 for x in u.values() if x['couleur'] == 'rouge'),
            'visites_retard': Visite.query.filter(Visite.agent_id == a.id, Visite.statut == StatutVisite.PREVUE,
                                                  Visite.date_prevue < date.today()).count(),
            'a_verifier': verifications.a_trancher(ConflitHorsLigne.query.filter(ConflitHorsLigne.ferme_id.in_(ids))).count()
            if ids else 0,
            'charge': 'rouge' if n > CHARGE_ROUGE else 'orange' if n > CHARGE_ORANGE else 'vert'})
    return sorted(resultat, key=lambda x: -x['fermes'])


def reaffecter(ferme, nouvel_agent, motif, user):
    """Change l'agent d'une ferme (journal automatique : modification de la ferme, avec le motif)."""
    from app.services.journal import enregistrer, Action
    if user.profil not in NATIONAUX:
        raise RegleDge('Réservé à la DGE et à l’administration.')
    if nouvel_agent is None or nouvel_agent.profil != Profil.AGENT or not nouvel_agent.actif:
        raise RegleDge('Choisissez un agent actif.')
    if ferme.province_id not in nouvel_agent.province_ids:
        raise RegleDge(f"Cet agent ne travaille pas dans la province {ferme.province.nom}.")
    if nouvel_agent.id == ferme.agent_id:
        raise RegleDge('Cette ferme est déjà suivie par cet agent.')
    if not (motif or '').strip():
        raise RegleDge('Indiquez le motif du changement.')
    ancien = ferme.agent
    ferme.agent_id = nouvel_agent.id
    enregistrer(Action.MODIFICATION, table='ferme', enregistrement_id=str(ferme.id),
                detail=f'Ferme {ferme.numero} : agent {ancien.nom_complet if ancien else "aucun"} → '
                       f'{nouvel_agent.nom_complet}. Motif : {motif.strip()}')
