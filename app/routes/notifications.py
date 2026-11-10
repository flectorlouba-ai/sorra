"""Lot T — notifications Web Push : clé publique, abonnement du téléphone, « 🔔 Mes notifications » (préférences),
actions de l'agent sur le téléphone, fiche papier de la semaine."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, abort
from flask_login import login_required, current_user

from app import db
from app.models import Profil
from app.models.action import Action
from app.models.bande import Bande, StatutBande
from app.models.notification import TypeNotification as T
from app.services import notifications as regles, actions as services_actions
from app.services.journal import enregistrer, Action as J
from app.utils import terrain as style
from app.utils.permissions import profil_requis

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.route('/notifications/cle-publique')
@login_required
def cle_publique():
    return jsonify(cle=regles.cle_publique(), types=list(regles.types_du_profil(current_user)))


@notifications_bp.route('/notifications/abonner', methods=['POST'])
@login_required
def abonner():
    donnees = request.get_json(silent=True) or {}
    try:
        regles.abonner(current_user, donnees.get('abonnement'), donnees.get('appareil'))
    except ValueError as e:
        return jsonify(etat='erreur', message=str(e)), 400
    enregistrer(J.MODIFICATION, table='abonnement_push', detail=f'Téléphone abonné aux notifications ({current_user.identifiant})')
    db.session.commit()
    return jsonify(etat='ok')


@notifications_bp.route('/notifications/desabonner', methods=['POST'])
@login_required
def desabonner():
    donnees = request.get_json(silent=True) or {}
    regles.desabonner(current_user, (donnees.get('abonnement') or {}).get('endpoint'))
    enregistrer(J.MODIFICATION, table='abonnement_push', detail=f'Téléphone désabonné des notifications ({current_user.identifiant})')
    db.session.commit()
    return jsonify(etat='ok')


@notifications_bp.route('/moi/notifications', methods=['GET', 'POST'])
@login_required
def mes_notifications():
    types = regles.types_du_profil(current_user)
    if not types:
        abort(404)
    if request.method == 'POST':
        f = request.form
        for t in types:
            regles.regler(current_user, t, f.get(f'type_{t}') == '1' or t in T.TOUJOURS,
                          int(f['heure']) if t == T.SAISIE_OUBLIEE and (f.get('heure') or '').isdigit() else None)
        enregistrer(J.MODIFICATION, table='preference_notification',
                    detail='Préférences de notification modifiées : ' + ', '.join(
                        f'{t.lower()}={"oui" if f.get(f"type_{t}") == "1" or t in T.TOUJOURS else "non"}' for t in types))
        db.session.commit()
        flash('Vos choix sont enregistrés ✓', 'success')
        return redirect(url_for('notifications.mes_notifications'))
    prefs = regles.preferences(current_user)
    lignes = [{'type': t, 'icone': T.LIBELLES[t][0], 'nom': T.LIBELLES[t][1], 'sous': T.LIBELLES[t][2],
               'actif': regles.actif(current_user, t, prefs), 'toujours': t in T.TOUJOURS} for t in types]
    abonnes = [a for a in current_user_abonnements() if a.actif]
    return render_template('notifications/mes_notifications.html', lignes=lignes, heure=regles.heure_rappel(current_user, prefs),
                           avec_rappel=T.SAISIE_OUBLIEE in types, n_appareils=len(abonnes), cles=regles.cle_publique() is not None,
                           terrain=style.profil_terrain(current_user) is not None)


def current_user_abonnements():
    from app.models.notification import AbonnementPush
    return AbonnementPush.query.filter_by(utilisateur_id=current_user.id).all()


# ── Actions de l'agent sur le téléphone (lot T-B) ───────────────────────

@notifications_bp.route('/terrain/actions')
@profil_requis(Profil.AGENT)
def actions_terrain():
    if style.profil_terrain(current_user) != 'agent':
        return redirect(url_for('actions.liste'))
    actions = [a for a in services_actions.mes_actions(current_user) if a.archive_le is None]
    return render_template('terrain/agent/actions.html', actions=actions, phrase=services_actions.phrase_echeance,
                           fermes=services_actions_fermes(), ouvrir=request.args.get('ouvrir'))


def services_actions_fermes():
    from app.models import Ferme
    return Ferme.query.filter_by(agent_id=current_user.id).order_by(Ferme.numero_metier).all()


@notifications_bp.route('/terrain/actions/<int:ident>', methods=['POST'])
@profil_requis(Profil.AGENT)
def action_terrain(ident):
    """Feuille « avancement / ce que j'ai fait / photo » : Pas commencé, En cours, ✓ Fait (hors ligne : file d'attente)."""
    a = services_actions.visibles(current_user).filter(Action.id == ident).first_or_404()
    f = request.form
    etat = f.get('etat', 'en_cours')
    try:
        photo = None
        if request.files.get('photo') and request.files['photo'].filename:
            from app.services import sante
            enregistre = sante._enregistrer(request.files['photo'], sante._SIGNATURES, sous_dossier='actions')
            photo = enregistre[0] if enregistre else None
        if etat == 'fait':
            services_actions.cloturer(current_user, a, f.get('commentaire'), photo)
            flash(f'Action {a.numero} faite ✓', 'success')
        else:
            if a.faite_le is not None:
                services_actions.rouvrir(current_user, a)
            avancement = 0 if etat == 'pas_commence' else max(a.avancement, 10) if a.avancement < 100 else 50
            services_actions.modifier(current_user, a, avancement=avancement, commentaire=f.get('commentaire'), photo=photo)
            flash(f'Action {a.numero} enregistrée ✓', 'success')
        db.session.commit()
    except Exception as e:                     # RegleAction, RegleSante
        db.session.rollback()
        flash(str(e) or 'Saisie invalide.', 'danger')
    return redirect(url_for('notifications.actions_terrain'))


# ── Fiche papier de la semaine (lot T-C) ────────────────────────────────

@notifications_bp.route('/bandes/<numero>/fiche-semaine.pdf')
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.DGE, Profil.ADMIN)
def fiche_semaine(numero):
    from app.routes.bandes import charger
    from app.services import fiche_semaine as service
    bande = charger(numero)
    pdf = service.fiche_pdf(bande)
    enregistrer(J.EXPORT, table='bande', enregistrement_id=bande.id, detail=f'Fiche papier de la semaine imprimée · bande {bande.numero}')
    db.session.commit()
    return Response(pdf, mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename="SORRA_fiche_semaine_{bande.numero}.pdf"'})


def bande_en_cours_de(ferme):
    return Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).order_by(Bande.date_mise_en_place.desc()).first()
