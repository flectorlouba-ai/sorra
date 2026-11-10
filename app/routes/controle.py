"""Écrans du socle de sécurité (lot 15) : Paramètres à approuver (quatre yeux), Sessions (ADMIN),
Intégrité du journal (AUDITEUR, ADMIN), Configuration (ADMIN : les écrans de réglage)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Profil
from app.models.securite import Proposition, StatutProposition
from app.services import approbations, securite
from app.services.journal import verifier_chaine, enregistrer, Action
from app.utils.permissions import profil_requis

controle_bp = Blueprint('controle', __name__)

DECIDEURS = (Profil.ADMIN, Profil.DGE, Profil.VETO)


@controle_bp.route('/approbations')
@profil_requis(*DECIDEURS)
def approbations_ecran():
    historique = Proposition.query.filter(Proposition.statut != StatutProposition.EN_ATTENTE) \
        .order_by(Proposition.decide_le.desc()).limit(50).all()
    mes_propositions = Proposition.query.filter_by(statut=StatutProposition.EN_ATTENTE, propose_par=current_user.id).all()
    from app.services import conformite
    a_decider = approbations.a_decider(current_user)
    cle = 'VETO-8' if current_user.profil == Profil.VETO else 'ADMIN-5'
    return render_template('controle/approbations.html', a_decider=a_decider, mes_propositions=mes_propositions, historique=historique,
                           conforme=(cle, conformite.spec(cle.split('-')[0], int(cle.split('-')[1])),
                                     conformite.validations(current_user, a_decider, mes_propositions, historique, cle)))


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
    from app.services import conformite
    sessions = securite.ouvertes().all()
    enregistrer(Action.CONSULTATION, table='session_utilisateur', detail=f'Sessions ouvertes consultées ({len(sessions)})')   # lot S
    db.session.commit()
    return render_template('controle/sessions.html', sessions=sessions,
                           conforme=('ADMIN-6', conformite.spec('ADMIN', 6), conformite.admin_sessions(current_user, sessions)))


@controle_bp.route('/integrite')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def integrite():
    intact, nombre, rompue = verifier_chaine()
    from app.services import conformite
    return render_template('controle/integrite.html', intact=intact, nombre=nombre, rompue=rompue,
                           conforme=('AUDITEUR-3', conformite.spec('AUDITEUR', 3), conformite.auditeur_verifications(current_user)))


@controle_bp.route('/configuration')
@profil_requis(Profil.ADMIN)
def configuration():
    from app.routes.accueil import TUILES_CONFIGURATION
    tuiles = [{'titre': t, 'sous_titre': s, 'icone': i, 'lien': url_for(e)} for t, s, i, e in TUILES_CONFIGURATION]
    from app.services import conformite
    return render_template('controle/configuration.html', tuiles=tuiles,
                           conforme=('ADMIN-4', conformite.spec('ADMIN', 4), conformite.admin_parametres(current_user)))
