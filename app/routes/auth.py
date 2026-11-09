import math
from datetime import timedelta

from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import Utilisateur
from app.models.base import maintenant
from app.services import parametres
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
            session.clear()
            login_user(user)
            user.derniere_connexion = maintenant()
            user.echecs_connexion = 0
            enregistrer(Action.CONNEXION, utilisateur=user)
            db.session.commit()
            if user.doit_changer_mdp:
                return redirect(url_for('auth.mot_de_passe'))
            next_page = request.args.get('next', '')
            if next_page and next_page.startswith('/') and not next_page.startswith('//'):
                return redirect(next_page)
            return redirect(url_for('accueil.index'))

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
