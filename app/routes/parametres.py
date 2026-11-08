from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Parametre, Profil
from app.services.parametres import normaliser
from app.utils.permissions import profil_requis

parametres_bp = Blueprint('parametres', __name__)


@parametres_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    return render_template('administration/parametres.html',
                           parametres=Parametre.query.order_by(Parametre.cle).all())


@parametres_bp.route('/<int:param_id>/modifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier(param_id):
    p = db.session.get(Parametre, param_id) or abort(404)
    try:
        valeur = normaliser(p.type, request.form.get('valeur', ''))
        # Les réglages de sécurité à 0 désactiveraient la protection
        if p.cle.startswith('securite.') and int(valeur) < 1:
            raise ValueError('La valeur doit être au moins 1.')
        if p.cle == 'bandes.courbe_poids':
            from app.indicateurs import lire_courbe
            lire_courbe(valeur)
    except ValueError as e:
        flash(f'{p.description} — {e}', 'danger')
        return redirect(url_for('parametres.index'))
    if valeur != p.valeur:
        p.valeur = valeur
        p.modifie_par = current_user.id
        db.session.commit()
    flash('Paramètre enregistré.', 'success')
    return redirect(url_for('parametres.index'))
