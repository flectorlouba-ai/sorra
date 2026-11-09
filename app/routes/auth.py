import math
from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session, abort
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import Utilisateur, Profil
from app.models.base import maintenant
from app.services import parametres, securite
from app.services.journal import enregistrer, Action
from app.utils.dates import en_utc

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if current_user.is_authenticated:
        return redirect(url_for('accueil.index'))

    erreur = None
    if request.method == 'POST':
        identifiant = request.form.get('identifiant', '').strip().lower()
        mot_de_passe = request.form.get('mot_de_passe', '')
        user = Utilisateur.query.filter_by(identifiant=identifiant).first()

        if user and user.bloque_jusqu_a:
            if user.est_bloque:
                enregistrer(Action.ECHEC_CONNEXION, identifiant=user.identifiant,
                            detail='compte bloqué')
                db.session.commit()
                return render_template('auth/connexion.html', erreur=_message_blocage(user))
            # Délai écoulé : le compte se débloque à la tentative suivante
            _debloquer(user, 'Fin du délai de blocage')

        if user and user.actif and user.check_password(mot_de_passe):
            next_page = request.args.get('next', '')
            if securite.a_demander(user):
                # Lot 15 : second facteur avant d'ouvrir la session
                user.echecs_connexion = 0
                db.session.commit()
                session.clear()
                session['2fa_utilisateur'] = str(user.id)
                session['2fa_suite'] = next_page
                return redirect(url_for('auth.deux_facteurs' if user.totp_active else 'auth.mise_en_place'))
            return _ouvrir_session(user, next_page)

        erreur = 'Identifiant ou mot de passe incorrect.'
        if user and not user.actif and user.check_password(mot_de_passe):
            motif = 'compte désactivé'
        else:
            motif = 'identifiant ou mot de passe incorrect'
        enregistrer(Action.ECHEC_CONNEXION, identifiant=identifiant[:64] or '(vide)',
                    detail=motif)
        if user and user.actif and motif != 'compte désactivé':
            user.echecs_connexion += 1
            maximum = parametres.obtenir('securite.echecs_avant_blocage', 5)
            if user.echecs_connexion >= maximum:
                duree = parametres.obtenir('securite.blocage_minutes', 15)
                user.bloque_jusqu_a = maintenant() + timedelta(minutes=duree)
                user.echecs_connexion = 0
                enregistrer(Action.BLOCAGE, table='utilisateur', enregistrement_id=user.id,
                            identifiant=user.identifiant,
                            detail=f'{maximum} échecs de connexion consécutifs : '
                                   f'compte bloqué {duree} minutes')
                erreur = _message_blocage(user)
        db.session.commit()

    return render_template('auth/connexion.html', erreur=erreur)


def _ouvrir_session(user, next_page=''):
    session.clear()
    login_user(user)
    user.derniere_connexion = maintenant()
    user.echecs_connexion = 0
    s = securite.ouvrir(user)
    session['sid'] = s.id
    enregistrer(Action.CONNEXION, utilisateur=user, detail=s.appareil)
    db.session.commit()
    if user.doit_changer_mdp:
        return redirect(url_for('auth.mot_de_passe'))
    if next_page and next_page.startswith('/') and not next_page.startswith('//'):
        return redirect(next_page)
    return redirect(url_for('accueil.index'))


def _en_attente_2fa():
    import uuid as _uuid
    try:
        return db.session.get(Utilisateur, _uuid.UUID(session.get('2fa_utilisateur') or ''))
    except ValueError:
        return None


@auth_bp.route('/2fa', methods=['GET', 'POST'])
def deux_facteurs():
    """Second facteur : code de l'application (6 chiffres) ou code de secours (usage unique)."""
    user = _en_attente_2fa()
    if user is None or not user.totp_active:
        return redirect(url_for('auth.connexion'))
    erreur = None
    if request.method == 'POST':
        saisi = request.form.get('code', '')
        if securite.verifier_code(user.totp_secret, saisi):
            return _ouvrir_session(user, session.get('2fa_suite', ''))
        if securite.utiliser_code_secours(user, saisi):
            enregistrer(Action.CONNEXION, utilisateur=user, detail='code de secours utilisé')
            return _ouvrir_session(user, session.get('2fa_suite', ''))
        enregistrer(Action.ECHEC_CONNEXION, identifiant=user.identifiant, detail='code de double authentification faux')
        db.session.commit()
        erreur = 'Code incorrect.'
    return render_template('auth/deux_facteurs.html', erreur=erreur)


@auth_bp.route('/2fa/mise-en-place', methods=['GET', 'POST'])
def mise_en_place():
    """Mise en place guidée : à la première connexion d'un profil obligatoire, ou depuis « Ma sécurité »."""
    user = current_user if current_user.is_authenticated else _en_attente_2fa()
    if user is None or not securite.possible(user):
        return redirect(url_for('auth.connexion'))
    if not session.get('2fa_secret'):
        session['2fa_secret'] = securite.nouveau_secret()
    secret = session['2fa_secret']
    erreur = None
    if request.method == 'POST':
        if securite.verifier_code(secret, request.form.get('code', '')):
            user.totp_secret, user.totp_active = secret, True
            session['2fa_codes'] = securite.nouveaux_codes_secours(user)
            session.pop('2fa_secret', None)
            enregistrer(Action.MODIFICATION, table='utilisateur', enregistrement_id=user.id,
                        utilisateur=user, detail='Double authentification mise en place')
            if current_user.is_authenticated:
                db.session.commit()
                return redirect(url_for('auth.codes_secours'))
            codes = session['2fa_codes']
            _ouvrir_session(user, session.get('2fa_suite', ''))
            session['2fa_codes'] = codes              # session.clear() les avait effacés
            return redirect(url_for('auth.codes_secours'))
        erreur = 'Code incorrect : vérifiez l\'heure du téléphone et recommencez.'
    adresse = securite.adresse_otpauth(user, secret)
    return render_template('auth/mise_en_place_2fa.html', secret=secret, qr=securite.qr_svg(adresse),
                           erreur=erreur, obligatoire=securite.obligatoire(user))


@auth_bp.route('/2fa/codes-de-secours')
@login_required
def codes_secours():
    """Les 8 codes de secours, affichés UNE seule fois."""
    codes = session.pop('2fa_codes', None)
    if not codes:
        return redirect(url_for('auth.securite'))
    return render_template('auth/codes_secours.html', codes=codes)


@auth_bp.route('/securite', endpoint='securite')
@login_required
def securite_ecran():
    if current_user.profil == Profil.ELEVEUR:            # ni 2FA ni sessions pour l'éleveur : son écran à lui
        return redirect(url_for('eleveur.mon_compte'))
    return render_template('auth/securite.html', mes_sessions=securite.ouvertes(current_user.id).all(),
                           sid=session.get('sid'), obligatoire=securite.obligatoire(current_user),
                           possible=securite.possible(current_user), active=securite.active_sur_ce_serveur())


@auth_bp.route('/sessions/<sid>/fermer', methods=['POST'])
@login_required
def fermer_session(sid):
    from app.models import Profil
    from app.models.securite import SessionUtilisateur
    s = db.session.get(SessionUtilisateur, sid)
    if s is None or (s.utilisateur_id != current_user.id and current_user.profil != Profil.ADMIN):
        abort(404)
    securite.fermer(sid, current_user, (request.form.get('motif') or 'Fermée').strip()[:200])
    enregistrer(Action.DECONNEXION, table='session_utilisateur', enregistrement_id=sid,
                detail=f'Session de {s.utilisateur.identifiant} ({s.appareil}) fermée par {current_user.identifiant}')
    db.session.commit()
    flash('Session fermée.', 'success')
    return redirect(request.referrer or url_for('auth.securite'))


def _message_blocage(user):
    reste = max(1, math.ceil((en_utc(user.bloque_jusqu_a) - maintenant()).total_seconds() / 60))
    return (f'Trop d\'essais : ce compte est bloqué pendant encore {reste} minute{"s" if reste > 1 else ""}. '
            'Réessayez plus tard ou demandez à l\'administrateur de le débloquer.')


def _debloquer(user, motif):
    user.bloque_jusqu_a = None
    user.echecs_connexion = 0
    enregistrer(Action.DEBLOCAGE, table='utilisateur', enregistrement_id=user.id,
                identifiant=None if current_user.is_authenticated else user.identifiant,
                detail=f'Compte « {user.identifiant} » débloqué : {motif}')


@auth_bp.route('/deconnexion', methods=['POST'])
@login_required
def deconnexion():
    securite.fermer(session.get('sid'), current_user, 'Déconnexion')
    enregistrer(Action.DECONNEXION)
    db.session.commit()
    logout_user()
    session.clear()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('auth.connexion'))


@auth_bp.route('/mot-de-passe', methods=['GET', 'POST'])
@login_required
def mot_de_passe():
    longueur_min = parametres.obtenir('securite.mdp_longueur_min', 10)
    erreur = None
    obligatoire = current_user.doit_changer_mdp
    if request.method == 'POST':
        actuel = request.form.get('actuel', '')
        nouveau = request.form.get('nouveau', '')
        confirmation = request.form.get('confirmation', '')
        if not current_user.check_password(actuel):
            erreur = 'Le mot de passe actuel est incorrect.'
        elif len(nouveau) < longueur_min:
            erreur = f'Le nouveau mot de passe doit contenir au moins {longueur_min} caractères.'
        elif nouveau != confirmation:
            erreur = 'La confirmation ne correspond pas au nouveau mot de passe.'
        elif nouveau == actuel:
            erreur = 'Le nouveau mot de passe doit être différent de l\'actuel.'
        else:
            current_user.set_password(nouveau)
            current_user.doit_changer_mdp = False
            enregistrer(Action.CHANGEMENT_MDP)
            db.session.commit()
            flash('Votre mot de passe a été changé.', 'success')
            if current_user.profil.value == 'ELEVEUR' and not obligatoire:
                return redirect(url_for('eleveur.mon_compte'))
            return redirect(url_for('accueil.index'))
    return render_template('auth/mot_de_passe.html', erreur=erreur, longueur_min=longueur_min,
                           obligatoire=current_user.doit_changer_mdp)
