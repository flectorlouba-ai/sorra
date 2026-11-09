"""Hors connexion : service worker, jeton d'envoi, saisies à vérifier par l'agent."""
import os

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, make_response, current_app
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.hors_ligne import ConflitHorsLigne
from app.utils import statiques
from app.utils.permissions import profil_requis, filtre_perimetre

hors_ligne_bp = Blueprint('hors_ligne', __name__)


# Fichiers gardés dès l'installation (adresses versionnées par url_for : ?v=<empreinte>)
A_GARDER = ['css/perform.css', 'css/eleveur.css', 'polices/polices.css',
            'vendor/bootstrap-5.3.3/css/bootstrap.min.css', 'vendor/bootstrap-icons-1.11.3/bootstrap-icons.min.css',
            'vendor/bootstrap-5.3.3/js/bootstrap.bundle.min.js', 'js/compteurs.js', 'js/hors_ligne.js',
            'js/eleveur.js', 'manifest.webmanifest', 'icones/icone-192.png',
            'polices/nunito-latin-400-normal.woff2', 'polices/nunito-latin-600-normal.woff2',
            'polices/nunito-latin-700-normal.woff2', 'polices/nunito-latin-800-normal.woff2',
            'polices/space-grotesk-latin-400-normal.woff2', 'polices/space-grotesk-latin-500-normal.woff2',
            'polices/space-grotesk-latin-600-normal.woff2', 'polices/space-grotesk-latin-700-normal.woff2',
            'polices/jetbrains-mono-latin-700-normal.woff2']
# Police d'icônes appelée par bootstrap-icons.min.css avec sa propre empreinte
POLICE_ICONES = '/static/vendor/bootstrap-icons-1.11.3/fonts/bootstrap-icons.woff2?dd67030699838ea613ee6dbda90effa6'


def version():
    """Empreinte de l'application (fichiers statiques et gabarits) : nomme les caches."""
    return statiques.version_application(current_app.static_folder,
                                         os.path.join(current_app.root_path, current_app.template_folder))


@hors_ligne_bp.route('/sw.js')
def service_worker():
    """Servi à la racine pour couvrir tout le site ; jamais gardé en cache par le navigateur."""
    a_garder = [url_for('static', filename=f) for f in A_GARDER] + [POLICE_ICONES]
    r = make_response(render_template('sw.js', version=version(), a_garder=a_garder))
    r.mimetype = 'application/javascript'
    r.headers['Service-Worker-Allowed'] = '/'
    r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
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
