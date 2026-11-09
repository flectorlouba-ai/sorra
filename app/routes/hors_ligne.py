"""Hors connexion : service worker, jeton d'envoi, saisies à vérifier par l'agent."""
import os

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, make_response, current_app, request
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


VERIFICATEURS = (Profil.AGENT, Profil.DGE, Profil.ADMIN)


def conflits_a_voir(user):
    """Refus à marquer « vus » et versions à trancher (lot 12)."""
    from sqlalchemy import or_, and_
    from app.models.hors_ligne import GenreVerification as G, StatutVerification as SV
    return (filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)
            .filter(or_(and_(ConflitHorsLigne.genre == G.MESSAGE, ConflitHorsLigne.vu_le.is_(None)),
                        and_(ConflitHorsLigne.genre != G.MESSAGE, ConflitHorsLigne.statut == SV.A_VERIFIER))))


@hors_ligne_bp.route('/hors-ligne/a-verifier')
@profil_requis(*VERIFICATEURS)
def conflits():
    from app.models.hors_ligne import GenreVerification as G
    from app.services import verifications
    tous = filtre_perimetre(ConflitHorsLigne.query)
    a_trancher = (verifications.a_trancher(tous).order_by(ConflitHorsLigne.cree_le).all())
    from sqlalchemy import or_
    from app.models.hors_ligne import StatutVerification as SV
    autres = (tous.filter(or_(ConflitHorsLigne.statut.is_(None), ConflitHorsLigne.statut != SV.A_VERIFIER))
              .order_by(ConflitHorsLigne.cree_le.desc()).limit(100).all())
    return render_template('hors_ligne/conflits.html', a_trancher=a_trancher, conflits=autres, G=G,
                           en_retard=verifications.en_retard, choix_sortie=verifications.CHOIX_SORTIE)


@hors_ligne_bp.route('/hors-ligne/a-verifier/<int:ident>/trancher', methods=['POST'])
@profil_requis(*VERIFICATEURS)
def trancher(ident):
    from app.services import verifications
    c = filtre_perimetre(ConflitHorsLigne.query.filter_by(id=ident)).first_or_404()
    try:
        verifications.trancher(c, request.form.get('choix'), request.form.get('motif', ''), current_user)
        db.session.commit()
        flash('Décision enregistrée (inscrite au journal) : les chiffres sont recalculés.', 'success')
    except verifications.RegleVerification as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('hors_ligne.conflits') + f'#verif-{ident}')


@hors_ligne_bp.route('/hors-ligne/a-verifier/<int:ident>/vu', methods=['POST'])
@profil_requis(*VERIFICATEURS)
def vu(ident):
    c = filtre_perimetre(ConflitHorsLigne.query.filter_by(id=ident)).first_or_404()
    if c.vu_le is None:
        c.vu_le, c.vu_par = maintenant(), current_user.id
        db.session.commit()
        flash('Marqué comme vu.', 'success')
    return redirect(url_for('hors_ligne.conflits'))
