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
    from app.services import approbations
    from app.models.securite import Proposition
    return render_template('administration/parametres.html',
                           parametres=Parametre.query.filter(~Parametre.cle.like('formule.%'))
                           .order_by(Parametre.cle).all(), sensible=approbations.sensible,
                           en_attente={p.cle for p in Proposition.query.filter_by(statut='EN_ATTENTE')})


@parametres_bp.route('/<int:param_id>/modifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier(param_id):
    p = db.session.get(Parametre, param_id) or abort(404)
    try:
        valeur = normaliser(p.type, request.form.get('valeur', ''))
        # Les réglages de sécurité à 0 désactiveraient la protection
        if p.cle.startswith('securite.') and p.type.value in ('ENTIER', 'JOURS') and int(valeur) < 1:
            raise ValueError('La valeur doit être au moins 1.')
        if p.cle == 'bandes.courbe_poids':
            from app.indicateurs import lire_courbe
            lire_courbe(valeur)
    except ValueError as e:
        flash(f'{p.description} — {e}', 'danger')
        return redirect(url_for('parametres.index'))
    if valeur == p.valeur:
        flash('Aucun changement.', 'info')
        return redirect(url_for('parametres.index'))
    from app.services import approbations
    if approbations.sensible(p.cle):
        # Lot 15 : quatre yeux — l'ancienne valeur s'applique jusqu'à l'approbation
        try:
            approbations.proposer('PARAMETRE', p.cle, p.description or p.cle, p.valeur, valeur,
                                  {'valeur': valeur}, request.form.get('motif', ''), current_user)
            db.session.commit()
            flash('Modification proposée : elle s\'appliquera quand une autre personne l\'aura approuvée.', 'info')
        except approbations.RegleApprobation as e:
            db.session.rollback()
            flash(str(e), 'danger')
        return redirect(url_for('parametres.index'))
    p.valeur = valeur
    p.modifie_par = current_user.id
    db.session.commit()
    flash('Paramètre enregistré.', 'success')
    return redirect(url_for('parametres.index'))
