"""Lot 19 ter — espace TERRAIN de l'agent et de l'opérateur (même charte que l'éleveur).
Ce module ne change aucune règle : il présente autrement les données des services existants et renvoie vers
les écrans existants (saisies, visites, vérifications, stock, nouvel éleveur, réceptions).
La « Version bureau » de l'agent (sur ordinateur) rend son accueil de pilotage et ses écrans de bureau."""
from datetime import date, timedelta

from flask import Blueprint, render_template, redirect, url_for, session, request, abort
from flask_login import current_user

from app import db, indicateurs
from app.models import Profil, Ferme, Bande, Utilisateur
from app.models.bande import StatutBande
from app.models.base import maintenant
from app.utils import terrain as style
from app.utils.permissions import profil_requis, filtre_perimetre

terrain_bp = Blueprint('terrain', __name__, url_prefix='/terrain')
TERRAIN = (Profil.AGENT, Profil.OPERATEUR)
EMOJI = {'rouge': '🔴', 'orange': '🟠', 'vert': '🟢'}


# ── Version bureau / version terrain (agent) ────────────────────────────

@terrain_bp.route('/bureau')
@profil_requis(Profil.AGENT)
def bureau():
    session[style.CLE_BUREAU] = True
    return redirect(url_for('accueil.index'))


@terrain_bp.route('/version-terrain')
@profil_requis(Profil.AGENT)
def version_terrain():
    session.pop(style.CLE_BUREAU, None)
    return redirect(url_for('accueil.index'))


def _terrain_agent():
    if current_user.profil != Profil.AGENT or style.profil_terrain(current_user) != 'agent':
        abort(404)


# ── Phrases de l'agent : la raison d'une ferme en mots simples ──────────

def jours_sans_saisie(ferme):
    """Jours depuis la dernière saisie du jour des bandes en cours (None sans bande en cours)."""
    bandes = Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).all()
    if not bandes:
        return None
    derniere = max((s.date for b in bandes for s in b.saisies), default=None)
    debut = min(indicateurs.debut_suivi(b) for b in bandes)
    return (date.today() - (derniere or debut)).days


def phrases(ferme, urgence):
    """Raisons d'une ferme, la plus urgente d'abord : [(couleur, phrase)]."""
    resultat = []
    for couleur, texte in (urgence or {}).get('raisons', []):
        t = texte
        if texte.startswith('Bande ') and texte.endswith(' en rouge'):
            t = 'Beaucoup de morts'
        elif texte.startswith('Bande ') and texte.endswith(' en orange'):
            t = 'Des morts à surveiller'
        elif texte == 'Saisie à vérifier':
            t = 'Saisies à vérifier'
        elif texte == 'Signalement sanitaire sans réponse':
            t = 'Poulets malades signalés'
        resultat.append((couleur, f'{EMOJI.get(couleur, "")} {t}'))
    jours = jours_sans_saisie(ferme)
    if jours is not None and jours >= 2:
        resultat.append(('orange', f'🟠 Rien noté depuis {jours} jours'))
    if not ferme.a_une_position:
        resultat.append(('gris', '📍 Position à relever'))
    vues, uniques = set(), []
    for c, p in resultat:
        if p not in vues:
            vues.add(p)
            uniques.append((c, p))
    return sorted(uniques, key=lambda x: {'rouge': 0, 'orange': 1}.get(x[0], 2))


def prenom_eleveur(ferme):
    """Le prénom à afficher pour l'éleveur d'une ferme : celui de son compte, sinon le nom de l'exploitant."""
    from app.models import UtilisateurFerme
    u = (Utilisateur.query.join(UtilisateurFerme, UtilisateurFerme.utilisateur_id == Utilisateur.id)
         .filter(UtilisateurFerme.ferme_id == ferme.id, Utilisateur.profil == Profil.ELEVEUR)
         .order_by(Utilisateur.nom).first())
    if u is not None:
        return u.prenom or u.nom
    return ferme.exploitant_nom or "l'éleveur"


@terrain_bp.app_template_global('prenom_eleveur')
def _prenom_eleveur_gabarit(ferme):
    return prenom_eleveur(ferme)


def _fermes_agent():
    return Ferme.query.filter_by(agent_id=current_user.id).order_by(Ferme.numero_metier).all()


def cloche(user):
    """🔔 de l'agent : le nombre d'alertes de son accueil (les mêmes que l'accueil de pilotage)."""
    from app.routes.accueil import _alertes
    return sum(a.get('nombre', 1) for a in _alertes(user))


# ── Accueil de l'agent ──────────────────────────────────────────────────

def accueil_agent(user):
    from app.services import agent
    from app.routes.hors_ligne import conflits_a_voir
    from app.routes.accueil import _n_commandes
    fermes = Ferme.query.filter_by(agent_id=user.id).all()
    triees, u = agent.trier_par_urgence(fermes)
    tournee = agent.tournee(user)
    a_verifier = conflits_a_voir(user).count()
    etat = []
    for f in triees:
        rouges = [p for c, p in phrases(f, u[f.id]) if c == 'rouge']
        if rouges:
            etat.append({'texte': f'{f.numero} : {rouges[0][2:].lower()}', 'ico': '🔴',
                         'lien': url_for('terrain.fiche', numero=f.numero)})
    etat = etat[:2]
    if a_verifier:
        etat.append({'ico': '⚖️', 'texte': f'{a_verifier} saisie{"s" if a_verifier > 1 else ""} à vérifier',
                     'lien': url_for('hors_ligne.conflits')})
    n_tournee = len(tournee)
    rouges = sum(1 for x in u.values() if x['couleur'] == 'rouge')
    tuiles = [
        {'cle': 'fermes', 'ico': '🏠', 'nom': 'Mes fermes', 'lien': url_for('terrain.fermes'),
         'pastille': rouges, 'pastille_classe': 'rouge', 'sous': f'{len(fermes)} fermes'},
        {'cle': 'saisir', 'ico': '✍️', 'nom': 'Saisir pour un éleveur', 'lien': url_for('terrain.saisir')},
        {'cle': 'visite', 'ico': '📋', 'nom': 'Visite', 'sous': 'compte rendu', 'lien': url_for('terrain.visite')},
        {'cle': 'a_verifier', 'ico': '⚖️', 'nom': 'À vérifier', 'lien': url_for('hors_ligne.conflits'),
         'pastille': a_verifier, 'pastille_classe': ''},
        {'cle': 'stock', 'ico': '📦', 'nom': 'Stock et commandes', 'lien': url_for('terrain.stock'),
         'pastille': _n_commandes(user), 'pastille_classe': ''},
        {'cle': 'nouvel_eleveur', 'ico': '➕', 'nom': 'Nouvel éleveur', 'lien': url_for('terrain.nouvel_eleveur')},
    ]
    from app.routes.accueil import _alertes
    return {'tournee': {'n': n_tournee, 'lien': url_for('terrain.tournee')}, 'etat': etat[:2], 'tuiles': tuiles,
            'alertes': _alertes(user),                           # les mêmes alertes que l'accueil de pilotage
            'moi': {'cle': 'moi', 'ico': '👤', 'nom': 'Moi', 'sous': 'compte, aide', 'lien': url_for('terrain.moi')}}


# ── Ma tournée ──────────────────────────────────────────────────────────

@terrain_bp.route('/tournee')
@profil_requis(Profil.AGENT)
def tournee():
    _terrain_agent()
    from app.services import agent, pilotage
    lignes = agent.tournee(current_user)
    for i, l in enumerate(lignes, start=1):
        l['rang'] = i
        l['phrases'] = phrases(l['ferme'], l['urgence'])
        a_faire = []
        if l['visite']:
            a_faire.append(f'visite « {l["visite"].objet.lower()} »'
                           + (f' (prévue le {l["visite"].date_prevue:%d/%m})' if l['visite'].date_prevue < date.today() else ''))
        if any('morts' in p for _, p in l['phrases']):
            a_faire.append('voir les poulets malades')
        if any('Saisies' in p for _, p in l['phrases']):
            a_faire.append('vérifier les saisies')
        if any('Rien noté' in p for _, p in l['phrases']):
            a_faire.append('noter les jours manqués')
        if any('Position' in p for _, p in l['phrases']):
            a_faire.append('relever la position')
        l['a_faire'] = a_faire
    carte = None
    pid = current_user.province_ids[0] if current_user.province_ids else None
    if lignes:
        carte = pilotage.carte(current_user, pid, largeur=320, hauteur=220, marge=8)
        if carte:
            rangs = {l['ferme'].id: l['rang'] for l in lignes}
            carte['points'] = [dict(p, rang=rangs[p['ferme'].id]) for p in carte['points'] if p['ferme'].id in rangs]
    return render_template('terrain/agent/tournee.html', lignes=lignes, carte=carte, prepare_le=maintenant())


# ── Mes fermes, fiche ferme ─────────────────────────────────────────────

@terrain_bp.route('/fermes')
@profil_requis(Profil.AGENT)
def fermes():
    _terrain_agent()
    from app.services import agent
    triees, u = agent.trier_par_urgence(_fermes_agent())
    return render_template('terrain/agent/fermes.html',
                           fermes=[{'ferme': f, 'couleur': u[f.id]['couleur'], 'phrases': phrases(f, u[f.id])}
                                   for f in triees])


def _ma_ferme(numero):
    f = filtre_perimetre(Ferme.query).filter(Ferme.numero_metier == numero).first()
    if f is None:
        abort(404)
    return f


def situation(ferme):
    """Une ligne par bande en cours : feu, bâtiment, jour, poulets présents, morts d'hier."""
    from app.services import veto
    hier = date.today() - timedelta(days=1)
    lignes = []
    for b in Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).order_by(Bande.numero_metier):
        v = indicateurs.calculer(b)
        couleur = indicateurs.feu(b, valeurs=v)[0]
        s = indicateurs.saisie_du(b, hier)
        present = v['effectif_present']
        morts_hier = None
        if s is not None and s.morts is not None and present:
            morts_hier = s.morts / (present + s.morts) * 100
        lignes.append({'bande': b, 'couleur': couleur, 'age': indicateurs.age(b), 'present': present,
                       'morts_hier': morts_hier, 'blocage': veto.blocage_actif(b)})
    return lignes


@terrain_bp.route('/fermes/<numero>')
@profil_requis(Profil.AGENT)
def fiche(numero):
    _terrain_agent()
    from app.models.visite import Visite, StatutVisite
    ferme = _ma_ferme(numero)
    from app.services import fiches
    visites = (Visite.query.filter_by(ferme_id=ferme.id, statut=StatutVisite.FAITE)
               .order_by(Visite.faite_le.desc()).limit(5).all())
    derniere = visites[0] if visites else None
    sit = situation(ferme)
    prenom = prenom_eleveur(ferme)
    return render_template('terrain/agent/fiche.html', ferme=ferme, situation=sit, derniere=derniere,
                           prenom=prenom, bande=sit[0]['bande'] if sit else None, visites=visites,
                           n_visites_archivees=fiches.nombre_archivees('visite', ferme=ferme))


# ── Saisir pour un éleveur ──────────────────────────────────────────────

def _fermes_en_pastilles(choisie=None):
    """Fermes de l'agent : celles de la tournée d'abord, puis les autres (avec recherche)."""
    from app.services import agent
    tournee = [l['ferme'] for l in agent.tournee(current_user)]
    autres = [f for f in _fermes_agent() if f not in tournee]
    return tournee, autres


@terrain_bp.route('/saisir')
@profil_requis(Profil.AGENT)
def saisir():
    _terrain_agent()
    tournee, autres = _fermes_en_pastilles()
    numero = request.args.get('ferme') or ((tournee or autres)[0].numero if (tournee or autres) else None)
    ferme = _ma_ferme(numero) if numero else None
    bandes = (Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).order_by(Bande.numero_metier).all()
              if ferme else [])
    bande = next((b for b in bandes if str(b.batiment_id) == request.args.get('bat')), bandes[0] if bandes else None)
    return render_template('terrain/agent/saisir.html', tournee=tournee, autres=autres, ferme=ferme, bandes=bandes,
                           bande=bande)


# ── Visite : compte rendu de la ferme choisie ───────────────────────────

@terrain_bp.route('/visite')
@profil_requis(Profil.AGENT)
def visite():
    _terrain_agent()
    tournee, autres = _fermes_en_pastilles()
    if request.args.get('ferme'):
        return redirect(url_for('visites.compte_rendu', numero=_ma_ferme(request.args['ferme']).numero))
    premiere = (tournee or autres)
    if not premiere:
        return render_template('terrain/agent/sans_ferme.html', titre='📋 Visite')
    return redirect(url_for('visites.compte_rendu', numero=premiere[0].numero))


# ── Stock et commandes ──────────────────────────────────────────────────

def stock_en_mots(ferme):
    """Une carte par intrant : reçu, utilisé, reste ; « 🟠 5 sacs manquent » ou « ✓ ça correspond » d'après le
    dernier comptage (jamais de pourcentage à l'écran)."""
    from app.services import agent, intrants
    inventaires = {i.produit_id: i for i in agent.derniers_inventaires([ferme.id])}
    utilises = intrants.quantites_utilisees(ferme)
    cartes = []
    for s in intrants.stock_ferme(ferme):
        p = s['produit']
        recu = s['stock'] + utilises.get(p.id, 0)
        inv = inventaires.get(p.id)
        unite = 'sacs' if p.en_sacs else p.unite
        constat = None
        if inv is not None and p.type != 'Poussins':
            manque = round(inv.ecart or 0, 1)
            constat = ('✓ ça correspond', 'ok') if abs(manque) < 0.5 else \
                (f'🟠 {manque:g} {unite} manquent', 'manque') if manque > 0 else (f'🟠 {-manque:g} {unite} en trop', 'manque')
        cartes.append({'produit': p, 'unite': unite, 'recu': recu, 'utilise': utilises.get(p.id, 0),
                       'reste': inv.compte if inv is not None else s['stock'], 'compte': inv, 'constat': constat,
                       'programme': s['programme'], 'externe': s['externe']})
    return cartes


@terrain_bp.route('/stock')
@profil_requis(Profil.AGENT)
def stock():
    _terrain_agent()
    from app.models import Livraison, Produit
    from app.models.agent import CommandeIntrant, StatutCommande as SC
    from app.models.intrant import StatutLivraison
    tournee, autres = _fermes_en_pastilles()
    numero = request.args.get('ferme') or ((tournee or autres)[0].numero if (tournee or autres) else None)
    if not numero:
        return render_template('terrain/agent/sans_ferme.html', titre='📦 Stock et commandes')
    ferme = _ma_ferme(numero)
    commande = CommandeIntrant.query.filter_by(ferme_id=ferme.id).order_by(CommandeIntrant.id.desc()).first()
    etats = {SC.ENVOYEE: '◷ En attente de la DGE', SC.VALIDEE: '✓ Validée', SC.REFUSEE: '✗ Refusée',
             SC.LIVREE: '🚚 Livrée'}
    return render_template('terrain/agent/stock.html', ferme=ferme, tournee=tournee, autres=autres,
                           cartes=stock_en_mots(ferme), commande=commande,
                           etat_commande=etats.get(commande.statut, commande.statut) if commande else None,
                           livraisons=Livraison.query.filter_by(ferme_id=ferme.id, statut=StatutLivraison.A_CONFIRMER).all(),
                           produits=Produit.query.filter_by(actif=True).order_by(Produit.type, Produit.nom).all())


# ── Nouvel éleveur : choisir la ferme (enregistrée, ou nouvelle avec du réseau) ─

@terrain_bp.route('/nouvel-eleveur')
@profil_requis(Profil.AGENT)
def nouvel_eleveur():
    _terrain_agent()
    from app.models import UtilisateurFerme
    fermes = _fermes_agent()
    avec_compte = {l.ferme_id for l in UtilisateurFerme.query.filter(UtilisateurFerme.ferme_id.in_([f.id for f in fermes]))} \
        if fermes else set()
    return render_template('terrain/agent/nouvel_eleveur_choix.html',
                           sans_compte=[f for f in fermes if f.id not in avec_compte],
                           avec_compte=[f for f in fermes if f.id in avec_compte])


# ── Moi (agent et opérateur), présentation ──────────────────────────────

def telephone_dge():
    """Téléphone de contact de la DGE : le paramètre s'il est rempli, sinon le premier compte DGE actif avec
    un téléphone ; None s'il n'y en a pas."""
    from app.services import parametres
    tel = (parametres.obtenir('contact.telephone_dge', '') or '').strip()
    if tel:
        return tel
    u = (Utilisateur.query.filter(Utilisateur.profil == Profil.DGE, Utilisateur.actif.is_(True),
                                  Utilisateur.telephone.isnot(None), Utilisateur.telephone != '')
         .order_by(Utilisateur.nom).first())
    return u.telephone if u else None


@terrain_bp.route('/moi')
@profil_requis(*TERRAIN)
def moi():
    if style.profil_terrain(current_user) is None:
        return redirect(url_for('accueil.index'))
    visites = None
    if current_user.profil == Profil.AGENT:
        from app.models.visite import Visite, StatutVisite
        debut = date.today().replace(day=1)
        ids = [f.id for f in _fermes_agent()]
        q = Visite.query.filter(Visite.ferme_id.in_(ids)) if ids else None
        faites = q.filter(Visite.statut == StatutVisite.FAITE, Visite.faite_le >= debut).count() if q else 0
        prevues = q.filter(Visite.statut == StatutVisite.PREVUE).count() if q else 0
        visites = {'faites': faites, 'prevues': prevues, 'total': faites + prevues}
    return render_template('terrain/moi.html', visites=visites, telephone_dge=telephone_dge(),
                           n_fermes=len(_fermes_agent()) if current_user.profil == Profil.AGENT else None)


@terrain_bp.route('/presentation')
@profil_requis(*TERRAIN)
def presentation():
    return render_template('terrain/presentation.html')


@terrain_bp.route('/presentation/vue', methods=['POST'])
@profil_requis(*TERRAIN)
def presentation_vue():
    if current_user.presentation_vue_le is None:
        current_user.presentation_vue_le = maintenant()
        db.session.commit()
    return redirect(url_for('accueil.index'))


# ── Opérateur : accueil ─────────────────────────────────────────────────

def accueil_operateur(user):
    from app.services import receptions
    op = user.operateur
    if op is None:
        return {'operateur': None}
    semaine = receptions.attendus(op, 7)
    a_traiter = receptions.a_traiter(op)
    attente = sum(1 for r in a_traiter if r.etat == 'SOUS_RESERVE')
    refusees = sum(1 for r in a_traiter if r.etat == 'REFUSEE')
    accords = sum(1 for r in a_traiter if r.etat == 'VALIDEE' and r.decision_par)
    a_expliquer = sum(1 for r in a_traiter if receptions.explication_manquante(r))
    etat = []
    if refusees:
        etat.append({'ico': '✗', 'texte': f'{refusees} réception{"s" if refusees > 1 else ""} à revoir',
                     'lien': url_for('operateur.receptions')})
    if a_expliquer:
        etat.append({'ico': '⚠️', 'texte': f'{a_expliquer} écart{"s" if a_expliquer > 1 else ""} à expliquer',
                     'lien': url_for('operateur.receptions')})
    if accords:
        etat.append({'ico': '✓', 'texte': f'Le vétérinaire a donné son accord ({accords} lot{"s" if accords > 1 else ""})',
                     'lien': url_for('operateur.receptions')})
    if semaine:
        etat.append({'ico': '🚚', 'texte': f'{len(semaine)} lot{"s" if len(semaine) > 1 else ""} '
                                          f'arrive{"nt" if len(semaine) > 1 else ""} cette semaine',
                     'lien': url_for('operateur.attendus')})
    if attente:
        etat.append({'ico': '◷', 'texte': f'{attente} lot{"s" if attente > 1 else ""} '
                                         f'attend{"ent" if attente > 1 else ""} le vétérinaire',
                     'lien': url_for('operateur.receptions')})
    tuiles = [
        {'cle': 'arrivent', 'ico': '🚚', 'nom': 'Lots qui arrivent', 'lien': url_for('operateur.attendus'),
         'pastille': len(receptions.attendus(op)), 'pastille_classe': ''},
        {'cle': 'receptions', 'ico': '📦', 'nom': 'Mes réceptions', 'lien': url_for('operateur.receptions'),
         'pastille': len(a_traiter), 'pastille_classe': ''},
    ]
    return {'operateur': op, 'etat': etat, 'tuiles': tuiles, 'a_traiter': a_traiter,
            'moi': {'cle': 'moi', 'ico': '👤', 'nom': 'Moi · aide · mon compte', 'lien': url_for('terrain.moi')}}
