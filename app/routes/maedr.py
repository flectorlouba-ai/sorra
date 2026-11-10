"""Lot M — écrans de la BCEG (fermes financées) et du MAEDR (rapports à viser)."""
from flask import Blueprint, render_template
from flask_login import current_user

from app.models import Profil
from app.services import conformite, maedr as regles
from app.utils.permissions import profil_requis

maedr_bp = Blueprint('maedr', __name__)


@maedr_bp.route('/bceg/fermes')
@profil_requis(Profil.BCEG, Profil.ADMIN)
def bceg_fermes():
    from app import db
    from app.services.journal import enregistrer, Action
    enregistrer(Action.CONSULTATION, table='ferme', detail='Fermes financées consultées par la BCEG')   # lot S
    db.session.commit()
    return render_template('maedr/tableau.html', titre='🏘️ Fermes financées', sous_titre="Avec l'accord de l'éleveur seulement ; un clic ouvre le mini bilan",
                           conforme=('BCEG-1', conformite.SPEC_BCEG, conformite.bceg_fermes(current_user)))


@maedr_bp.route('/maedr/visas')
@profil_requis(Profil.MAEDR, Profil.ADMIN, Profil.DGE)
def visas():
    return render_template('maedr/tableau.html', titre='📑 Rapports à viser', sous_titre='Soumis par la DGE ; valider la diffusion ou refuser avec motif',
                           conforme=('MAEDR-2', conformite.SPEC_VISAS, conformite.maedr_visas(current_user, regles.rapports_diffusables())))
