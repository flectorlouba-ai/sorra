"""Hors connexion : service worker, jeton d'envoi, saisies à vérifier par l'agent."""
import os

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, send_from_directory, current_app
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.hors_ligne import ConflitHorsLigne
from app.utils.permissions import profil_requis, filtre_perimetre

hors_ligne_bp = Blueprint('hors_ligne', __name__)


@hors_ligne_bp.route('/sw.js')
def service_worker():
    """Servi à la racine pour couvrir tout le site."""
    r = send_from_directory(os.path.join(current_app.static_folder, 'js'), 'sw.js', max_age=0)
    r.headers['Service-Worker-Allowed'] = '/'
    r.headers['Cache-Control'] = 'no-cache'
    return r


@hors_ligne_bp.route('/hors-ligne/ping')
def ping():
    return '', 204


@hors_ligne_bp.route('/hors-ligne/jeton')
def jeton():
    """Jeton de formulaire frais pour envoyer les saisies gardées sur le téléphone."""
    if not current_user.is_authenticated:
        return jsonify(etat='connexion'), 401
    return jsonify(etat='ok', jeton=generate_csrf(), utilisateur=current_user.identifiant)


def conflits_a_voir(user):
    return (filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)
            .filter(ConflitHorsLigne.vu_le.is_(None)))


@hors_ligne_bp.route('/hors-ligne/a-verifier')
@profil_requis(Profil.AGENT, Profil.ADMIN)
def conflits():
    liste = (filtre_perimetre(ConflitHorsLigne.query)
             .order_by(ConflitHorsLigne.vu_le.isnot(None), ConflitHorsLigne.cree_le.desc()).limit(100).all())
    return render_template('hors_ligne/conflits.html', conflits=liste)


@hors_ligne_bp.route('/hors-ligne/a-verifier/<int:ident>/vu', methods=['POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def vu(ident):
    c = filtre_perimetre(ConflitHorsLigne.query.filter_by(id=ident)).first_or_404()
    if c.vu_le is None:
        c.vu_le, c.vu_par = maintenant(), current_user.id
        db.session.commit()
        flash('Marqué comme vu.', 'success')
    return redirect(url_for('hors_ligne.conflits'))
