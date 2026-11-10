"""Lot R — version ordinateur : tableau de bord de chaque profil (indicateurs du lot C, carte du périmètre, fermes en
alerte, 3 courbes, tableau de synthèse), écrans d'appoint (plans d'actions en attente du lot D, diagnostics, droits,
exports, recherche, visites, lots de l'éleveur), exports Excel et impressions journalisés, bascule terrain /
ordinateur. Les règles et les droits sont ceux des écrans existants."""
import io
import json
from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, session, abort, Response, jsonify, flash
from flask_login import login_required, current_user
from openpyxl import Workbook
from openpyxl.styles import Font

from app import db, indicateurs as ind
from app.models import Ferme, Profil, Province, Utilisateur
from app.models.bande import Bande, StatutBande
from app.services import mes_indicateurs, pilotage, conformite
from app.services.journal import enregistrer, Action
from app.utils import terrain as style
from app.utils.permissions import filtre_perimetre, profil_requis

bureau_bp = Blueprint('bureau', __name__, url_prefix='/bureau')
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
TERRAIN = (Profil.ELEVEUR, Profil.AGENT, Profil.OPERATEUR)


# ── Alertes selon le profil ─────────────────────────────────────────────

def raisons_alerte(ferme, infos, user):
    """Les raisons pour lesquelles une ferme est en alerte, selon ce que ce profil suit."""
    r = []
    p = user.profil
    if p in (Profil.DGE, Profil.VETO, Profil.AGENT, Profil.ELEVEUR, Profil.ADMIN):
        if infos['couleurs']['feu'] == 'rouge':
            r.append('mortalité anormale (feu rouge)')
        elif infos['couleurs']['feu'] == 'orange':
            r.append('attention (saisie manquante ou mortalité)')
    if p in (Profil.DGE, Profil.AGENT, Profil.ADMIN):
        if infos['couleurs']['regularite'] == 'rouge':
            r.append('saisies irrégulières')
        if infos['couleurs']['atteinte'] == 'rouge' and ferme.programme_poufa:
            r.append('production loin de la cible')
    if p in (Profil.DGE, Profil.ADMIN):
        from app.services import intrants
        from app.models import Livraison
        base = Livraison.query.filter_by(ferme_id=ferme.id)
        if intrants.requete_ecart(base).count():
            r.append("écart sur une livraison d'intrants")
    if p == Profil.ADMIN and ferme.position_a_verifier:
        r.append('position corrigée à vérifier')
    if p == Profil.AUDITEUR:
        from app.models import JournalAudit
        n = JournalAudit.query.filter(JournalAudit.action == Action.CORRECTION,
                                      JournalAudit.horodatage >= __import__('app.models.base', fromlist=['maintenant']).maintenant() - timedelta(days=30),
                                      JournalAudit.detail.like(f'%{ferme.numero}%')).count()
        if n:
            r.append(f'{n} correction(s) ce mois')
    return r


def tableau_de_bord(user):
    # Lot K : l'auditeur voit la carte nationale (lecture seule, sans chiffre financier) ; son périmètre de données reste vide
    lecteur = Utilisateur.query.filter_by(profil=Profil.DGE, actif=True).first() if user.profil == Profil.AUDITEUR else None
    fermes = filtre_perimetre(Ferme.query, utilisateur=lecteur or user).order_by(Ferme.numero_metier).all()
    d = mes_indicateurs.pour(user) or {'cartes': [], 'courbes': []}
    production = ind.production_fermes(fermes)
    pid = None
    if not user.est_national:
        provinces = {f.province_id for f in fermes} | set(user.province_ids)
        pid = next(iter(provinces)) if len(provinces) == 1 else None
    carte = pilotage.carte(lecteur or user, pid, largeur=640, hauteur=460, details=True) if fermes else None
    alertes, synthese = [], []
    for f in fermes:
        infos = pilotage.infos_ferme(f, production)
        raisons = raisons_alerte(f, infos, user)
        pire = infos['couleurs']['feu']
        if raisons:
            alertes.append({'ferme': f, 'raisons': raisons, 'couleur': 'rouge' if any('rouge' in x or 'anormale' in x for x in raisons) else 'orange'})
        synthese.append({'ferme': f, 'infos': infos, 'production': production.get(f.id), 'feu': pire,
                         'alerte': bool(raisons)})
    if carte:
        en_alerte = {a['ferme'].id for a in alertes}
        for pt in carte['points']:
            pt['alerte'] = pt['ferme'].id in en_alerte
            pt['raisons'] = next((a['raisons'] for a in alertes if a['ferme'].id == pt['ferme'].id), [])
    mes_actions = []
    if user.profil in (Profil.AGENT, Profil.DGE, Profil.ADMIN):
        from app.services import actions as services_actions
        mes_actions = [a for a in services_actions.mes_actions(user) if a.archive_le is None and a.etat != 'FAITE'][:12]
    # Lot K : le tableau de l'accueil suit le cahier (DGE : situation par province ; vétérinaire : alertes ouvertes)
    conforme = None
    if user.profil == Profil.DGE:
        conforme = ('DGE-1', conformite.spec('DGE', 1), conformite.dge_accueil(user))
    elif user.profil == Profil.VETO:
        conforme = ('VETO-1', conformite.spec('VETO', 1), conformite.veto_accueil(user))
    elif user.profil == Profil.ELEVEUR:
        conforme = ('ELEVEUR-1', conformite.spec('ELEVEUR', 1), conformite.eleveur_accueil(user))
    elif user.profil == Profil.AGENT:
        conforme = ('AGENT-1', conformite.spec('AGENT', 1), conformite.agent_accueil(user, mes_actions))
    elif user.profil == Profil.ADMIN:
        conforme = ('ADMIN-1', conformite.spec('ADMIN', 1), conformite.admin_accueil(user))
    elif user.profil == Profil.AUDITEUR:
        conforme = ('AUDITEUR-1', conformite.spec('AUDITEUR', 1), conformite.auditeur_verifications(user))
    return {'cartes': d['cartes'], 'courbes': d['courbes'], 'carte': carte, 'alertes': alertes, 'synthese': synthese,
            'fermes': fermes, 'mes_actions': mes_actions, 'conforme': conforme}


@bureau_bp.route('/')
@login_required
def accueil():
    return redirect(url_for('accueil.index'))          # l'accueil (terrain ou ordinateur) est à la racine


# ── Lot K : gestes de la fiche d'un tableau conforme ─────────────────────

@bureau_bp.route('/fiche/<cle>/<path:ident>', methods=['POST'])
@login_required
def fiche_conforme(cle, ident):
    """« Enregistrer la modification » / « Archiver » / décision d'une fiche ouverte depuis un tableau conforme :
    la règle existante de l'écran s'applique (conformite.GESTES), tout est au journal."""
    retour = request.form.get('retour') or request.referrer or url_for('bureau.accueil')
    if not retour.startswith('/') and request.host not in retour:
        retour = url_for('bureau.accueil')
    try:
        message = conformite.geste(cle, ident, current_user, request.form)
        db.session.commit()
        flash(message, 'success')
    except conformite.RegleConformite as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:                               # règle d'un service existant
        db.session.rollback()
        flash(str(e) or 'Saisie invalide.', 'danger')
    return redirect(retour)


@bureau_bp.route('/creer/<cle>', methods=['POST'])
@login_required
def creation_conforme(cle):
    """Le bouton « ＋ … » d'un tableau conforme : création par la règle existante (conformite.CREATIONS)."""
    retour = request.form.get('retour') or request.referrer or url_for('bureau.accueil')
    try:
        message = conformite.creation(cle, current_user, request.form)
        db.session.commit()
        flash(message, 'success')
    except conformite.RegleConformite as e:
        db.session.rollback()
        flash(str(e), 'danger')
    except Exception as e:
        db.session.rollback()
        flash(str(e) or 'Saisie invalide.', 'danger')
    return redirect(retour if retour.startswith('/') or request.host in retour else url_for('bureau.accueil'))


# ── Bascule terrain / ordinateur ────────────────────────────────────────

@bureau_bp.route('/version-ordinateur', methods=['GET', 'POST'])
@login_required
def version_ordinateur():
    session[style.CLE_BUREAU] = True
    session['version_choisie'] = True
    return redirect(url_for('bureau.accueil'))


@bureau_bp.route('/version-terrain', methods=['GET', 'POST'])
@login_required
def version_terrain():
    session.pop(style.CLE_BUREAU, None)
    session['version_choisie'] = True
    return redirect(url_for('accueil.index'))


@bureau_bp.route('/bascule-automatique', methods=['POST'])
@login_required
def bascule_automatique():
    """Le téléphone ou l'ordinateur dit sa largeur ; ≥ 900 px → version ordinateur, une fois, sauf choix explicite."""
    if session.get('version_choisie') or current_user.profil not in TERRAIN:
        return jsonify(etat='inchange')
    large = (request.get_json(silent=True) or {}).get('largeur', 0) >= 900
    if large and not session.get(style.CLE_BUREAU):
        session[style.CLE_BUREAU] = True
        return jsonify(etat='ordinateur')
    return jsonify(etat='inchange')


# ── Exports et impressions journalisés ──────────────────────────────────

@bureau_bp.route('/exports/tableau.xlsx', methods=['POST'])
@login_required
def export_tableau():
    """Excel des lignes affichées d'un tableau (déjà filtrées par le périmètre dans la page), toutes colonnes."""
    try:
        d = json.loads(request.form.get('donnees') or '{}')
        colonnes, lignes = list(d['colonnes']), [list(l) for l in d['lignes']]
    except (ValueError, KeyError, TypeError):
        abort(400)
    if len(lignes) > 5000 or any(len(l) != len(colonnes) for l in lignes):
        abort(400)
    titre = (request.form.get('titre') or 'Tableau')[:80]
    enregistrer(Action.EXPORT, table='tableau',
                detail=f'Export Excel « {titre} » : {len(lignes)} ligne(s) · filtres : {(request.form.get("filtres") or "aucun")[:200]}')
    db.session.commit()
    wb = Workbook()
    ws = wb.active
    ws.title = titre[:31].replace('/', '-') or 'Tableau'
    ws.append([f'SORRA — {titre}'])
    ws.append([f'Filtres : {request.form.get("filtres") or "aucun"} · {date.today():%d/%m/%Y} · {current_user.nom_complet}'])
    ws.append([])
    ws.append(colonnes)
    for c in ws[4]:
        c.font = Font(bold=True)
    ws['A1'].font = Font(bold=True, size=13)
    for l in lignes:
        ws.append([_valeur(x) for x in l])
    tampon = io.BytesIO()
    wb.save(tampon)
    nom = f'sorra_{titre.lower().replace(" ", "_")[:40]}_{date.today():%Y%m%d}.xlsx'
    return Response(tampon.getvalue(), mimetype=XLSX, headers={'Content-Disposition': f'attachment; filename={nom}'})


def _valeur(texte):
    t = (texte or '').strip()
    brut = t.replace(' ', '').replace(' ', '').replace(',', '.')
    if brut and brut.replace('.', '', 1).replace('-', '', 1).isdigit() and '%' not in t:
        try:
            return float(brut) if '.' in brut else int(brut)
        except ValueError:
            pass
    return t


@bureau_bp.route('/exports/impression', methods=['POST'])
@login_required
def impression():
    d = request.get_json(silent=True) or {}
    enregistrer(Action.EXPORT, table='impression',
                detail=f'Impression « {str(d.get("titre", ""))[:80]} » : {int(d.get("lignes") or 0)} ligne(s)')
    db.session.commit()
    return jsonify(etat='ok')


# ── Écrans d'appoint (gabarit du lot R, contenu complet aux lots suivants) ──

@bureau_bp.route('/plans-actions')
@profil_requis(Profil.DGE, Profil.ADMIN, Profil.AGENT)
def plans_actions():
    return render_template('bureau/a_venir.html', titre="🎯 Plans d'actions", lot='D',
                           texte="Les plans d'actions (création, affectation, suivi, retards) arrivent au lot D.")


@bureau_bp.route('/diagnostics')
@profil_requis(Profil.VETO, Profil.ADMIN)
def diagnostics():
    from app.services import sante
    from app.models.sante import AlerteSanitaire
    alertes = sante.alertes_visibles(current_user).filter(AlerteSanitaire.statut.in_(('CONFIRMEE', 'INFIRMEE', 'CLOSE'))) \
        .order_by(AlerteSanitaire.modifie_le.desc()).limit(200).all()
    return render_template('bureau/diagnostics.html', alertes=alertes,
                           conforme=('VETO-5', conformite.spec('VETO', 5), conformite.veto_diagnostics(current_user, alertes)))


def _profils_de(f, vus=None):
    """Profils lus dans la fermeture de @profil_requis (même méthode que la matrice du dossier de présentation)."""
    vus = vus or set()
    if f is None or id(f) in vus:
        return None, False
    vus.add(id(f))
    login = getattr(getattr(f, '__code__', None), 'co_name', '') == 'decorated_view'
    for c in (getattr(f, '__closure__', None) or []):
        try:
            v = c.cell_contents
        except ValueError:
            continue
        if isinstance(v, tuple) and v and all(isinstance(x, Profil) for x in v):
            return set(v), True
        if callable(v):
            p, l = _profils_de(v, vus)
            login = login or l
            if p is not None:
                return p, True
    return None, login


@bureau_bp.route('/droits')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def droits():
    """Profils et droits : matrice lue dans les routes (lecture seule), une ligne par adresse."""
    from flask import current_app
    lignes = []
    for regle in sorted(current_app.url_map.iter_rules(), key=lambda r: r.rule):
        if regle.rule.startswith('/static') or regle.endpoint == 'static':
            continue
        vue = current_app.view_functions.get(regle.endpoint)
        profils, login = _profils_de(vue)
        lignes.append({'adresse': regle.rule, 'methodes': ' '.join(sorted(m for m in regle.methods if m in ('GET', 'POST'))),
                       'profils': ', '.join(sorted(p.value for p in profils)) if profils else ('tout compte connecté' if login else 'public'),
                       'doc': ((vue.__doc__ or '').strip().splitlines() or [''])[0][:120] if vue else ''})
    return render_template('bureau/droits.html', lignes=lignes, conforme=('ADMIN-3', conformite.spec('ADMIN', 3), conformite.admin_droits(current_user)))


@bureau_bp.route('/exports')
@profil_requis(Profil.AUDITEUR, Profil.ADMIN)
def exports():
    from app.models import JournalAudit
    lignes = JournalAudit.query.filter(JournalAudit.action == Action.EXPORT).order_by(JournalAudit.horodatage.desc()).limit(300).all()
    return render_template('bureau/exports.html', lignes=lignes, conforme=('AUDITEUR-5', conformite.spec('AUDITEUR', 5), conformite.auditeur_exports(current_user, lignes)))


@bureau_bp.route('/recherche')
@profil_requis(Profil.AUDITEUR, Profil.ADMIN)
def recherche():
    from app.models import JournalAudit
    q = (request.args.get('q') or '').strip()
    lignes = []
    if q:
        motif = f'%{q}%'
        lignes = (JournalAudit.query.filter(db.or_(JournalAudit.identifiant.ilike(motif), JournalAudit.detail.ilike(motif),
                                                   JournalAudit.enregistrement_id.ilike(motif)))
                  .order_by(JournalAudit.horodatage.desc()).limit(300).all())
        enregistrer(Action.RECHERCHE, table='journal', detail=f'Recherche « {q[:80]} » : {len(lignes)} résultat(s)')
        db.session.commit()
    return render_template('bureau/recherche.html', q=q, lignes=lignes, conforme=('AUDITEUR-6', conformite.spec('AUDITEUR', 6), conformite.auditeur_recherche(current_user, q, lignes)))


@bureau_bp.route('/visites')
@profil_requis(Profil.AGENT, Profil.DGE, Profil.ADMIN)
def visites():
    from app.models.visite import Visite
    from app.services import positions
    lignes = filtre_perimetre(Visite.query).order_by(Visite.faite_le.desc().nullslast(), Visite.date_prevue.desc()).limit(300).all()
    conforme = ('AGENT-5', conformite.spec('AGENT', 5), conformite.agent_visites(current_user, lignes, positions.etat_visite)) \
        if current_user.profil == Profil.AGENT else None
    return render_template('bureau/visites.html', visites=lignes, etat=positions.etat_visite, conforme=conforme)


@bureau_bp.route('/enrolement')
@profil_requis(Profil.AGENT, Profil.DGE, Profil.ADMIN)
def enrolement():
    """Lot K : enrôlements récents (fermes créées ces 90 jours) ; « ＋ Enrôler une ferme » ouvre le formulaire existant."""
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.cree_le.desc()).all()
    return render_template('bureau/enrolement.html', conforme=('AGENT-3', conformite.spec('AGENT', 3), conformite.agent_enrolement(current_user, fermes)))


@bureau_bp.route('/mes-lots')
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.DGE, Profil.ADMIN)
def mes_lots():
    from app.models.tracabilite import LotTrace
    from app.services import receptions
    lots = filtre_perimetre(LotTrace.query).order_by(LotTrace.cree_le.desc()).limit(300).all()
    conforme = ('ELEVEUR-7', conformite.spec('ELEVEUR', 7), conformite.eleveur_lots(current_user, lots, receptions.etat_pour_eleveur)) \
        if current_user.profil == Profil.ELEVEUR else None
    return render_template('bureau/mes_lots.html', lots=lots, etat=receptions.etat_pour_eleveur, conforme=conforme)
