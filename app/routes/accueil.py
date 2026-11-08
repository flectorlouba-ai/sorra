from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.models import Province, Localite, Profil
from app.routes.listes import CATEGORIES
from app.utils.permissions import filtre_perimetre

accueil_bp = Blueprint('accueil', __name__)

# Ce que chaque profil trouvera ici aux lots suivants (cahier des charges, § 3)
A_VENIR = {
    Profil.ADMIN:     'Les modules métier (fermes, bandes, traçabilité). '
                      'L\'administration est déjà dans l\'onglet Administration.',
    Profil.DGE:       'Pilotage du programme POUFA : suivi de toutes les fermes, '
                      'validation des commandes, paramètres de suivi.',
    Profil.AGENT:     'Visite et accompagnement de vos fermes, vérification des déclarations.',
    Profil.ELEVEUR:   'Fiche d\'élevage de votre ferme : mortalités, aliment, pesées, '
                      'sorties, déclarations sanitaires et tableau de bord.',
    Profil.VETO:      'Seuils d\'alerte, calendrier vaccinal, alertes, diagnostics et interventions.',
    Profil.BCEG:      'Suivi des fermes financées.',
    Profil.MAEDR:     'Données consolidées du programme.',
    Profil.OPERATEUR: 'Réception et confirmation des lots qui vous concernent.',
    Profil.AUDITEUR:  'Contrôle à partir du journal des opérations.',
}


@accueil_bp.route('/')
@login_required
def index():
    provinces = (filtre_perimetre(Province.query.filter_by(actif=True))
                 .order_by(Province.ordre).all())
    localites = (filtre_perimetre(Localite.query.filter_by(actif=True))
                 .order_by(Localite.nom).all())
    par_province = {}
    for loc in localites:
        par_province.setdefault(loc.province_id, []).append(loc)
    return render_template('accueil.html', provinces=provinces, par_province=par_province,
                           a_venir=A_VENIR[current_user.profil],
                           listes_presentes=bool(CATEGORIES))
