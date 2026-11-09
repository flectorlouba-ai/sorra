"""Écrans du socle de sécurité (lot 15) : Paramètres à approuver (quatre yeux), Sessions (ADMIN),
Intégrité du journal (AUDITEUR, ADMIN), Configuration (ADMIN : les écrans de réglage)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Profil
from app.models.securite import Proposition, StatutProposition
from app.services import approbations, securite
from app.services.journal import verifier_chaine
from app.utils.permissions import profil_requis

controle_bp = Blueprint('controle', __name__)

DECIDEURS = (Profil.ADMIN, Profil.DGE, Profil.VETO)


@controle_bp.route('/approbations')
@profil_requis(*DECIDEURS)
def approbations_ecran():
    historique = Proposition.query.filter(Proposition.statut != StatutProposition.EN_ATTENTE) \
        .order_by(Proposition.decide_le.desc()).limit(50).all()
    mes_propositions = Proposition.query.filter_by(statut=StatutProposition.EN_ATTENTE, propose_par=current_user.id).all()
    return render_template('controle/approbations.html', a_decider=approbations.a_decider(current_user),
                           mes_propositions=mes_propositions, historique=historique)


@controle_bp.route('/approbations/<int:ident>', methods=['POST'])
@profil_requis(*DECIDEURS)
def decider(ident):
    p = db.session.get(Proposition, ident) or abort(404)
    try:
        approbations.decider(p, current_user, request.form.get('decision') == 'approuver', request.form.get('motif', ''))
        db.session.commit()
        flash(f'« {p.libelle} » : {p.libelle_statut.lower()}.', 'success')
    except approbations.RegleApprobation as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('controle.approbations_ecran'))


@controle_bp.route('/sessions')
@profil_requis(Profil.ADMIN)
def sessions():
    return render_template('controle/sessions.html', sessions=securite.ouvertes().all())


@controle_bp.route('/integrite')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def integrite():
    intact, nombre, rompue = verifier_chaine()
    return render_template('controle/integrite.html', intact=intact, nombre=nombre, rompue=rompue)


@controle_bp.route('/configuration')
@profil_requis(Profil.ADMIN)
def configuration():
    from app.routes.accueil import TUILES_CONFIGURATION
    tuiles = [{'titre': t, 'sous_titre': s, 'icone': i, 'lien': url_for(e)} for t, s, i, e in TUILES_CONFIGURATION]
    return render_template('controle/configuration.html', tuiles=tuiles)
