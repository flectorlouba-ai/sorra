import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app import db
from app.models import Province, Localite, Profil
from app.utils.permissions import profil_requis

referentiel_bp = Blueprint('referentiel', __name__)

_CODE = re.compile(r'^[A-Z]{2,5}$')


@referentiel_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    provinces = Province.query.order_by(Province.ordre).all()
    choisie = request.args.get('province', type=int)
    province = db.session.get(Province, choisie) if choisie else None
    province = province or (provinces[0] if provinces else None)
    return render_template('administration/provinces.html', provinces=provinces,
                           province=province)


@referentiel_bp.route('/<int:province_id>/modifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier_province(province_id):
    province = db.session.get(Province, province_id) or abort(404)
    code = request.form.get('code', '').strip().upper()
    nom = request.form.get('nom', '').strip()
    erreur = None
    if not _CODE.match(code):
        erreur = 'Le code doit faire de 2 à 5 lettres majuscules.'
    elif not nom:
        erreur = 'Le nom est obligatoire.'
    elif Province.query.filter(Province.code == code, Province.id != province.id).first():
        erreur = f'Le code {code} est déjà pris.'
    elif Province.query.filter(Province.nom == nom, Province.id != province.id).first():
        erreur = f'La province « {nom} » existe déjà.'
    if erreur:
        flash(erreur, 'danger')
    else:
        province.code, province.nom = code, nom
        province.actif = request.form.get('actif') == 'on'
        db.session.commit()
        flash(f'Province « {nom} » mise à jour.', 'success')
    return redirect(url_for('referentiel.index', province=province.id))


def _nom_localite_libre(province_id, nom, sauf_id=None):
    q = Localite.query.filter(Localite.province_id == province_id,
                              db.func.lower(Localite.nom) == nom.lower())
    if sauf_id:
        q = q.filter(Localite.id != sauf_id)
    return q.first() is None


@referentiel_bp.route('/<int:province_id>/localites/creer', methods=['POST'])
@profil_requis(Profil.ADMIN)
def creer_localite(province_id):
    province = db.session.get(Province, province_id) or abort(404)
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom de la localité est obligatoire.', 'danger')
    elif not _nom_localite_libre(province.id, nom):
        flash(f'La localité « {nom} » existe déjà dans cette province.', 'danger')
    else:
        db.session.add(Localite(province_id=province.id, nom=nom, actif=True))
        db.session.commit()
        flash(f'Localité « {nom} » ajoutée.', 'success')
    return redirect(url_for('referentiel.index', province=province.id))


@referentiel_bp.route('/localites/<int:localite_id>/modifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier_localite(localite_id):
    loc = db.session.get(Localite, localite_id) or abort(404)
    nom = request.form.get('nom', '').strip()
    if not nom:
        flash('Le nom de la localité est obligatoire.', 'danger')
    elif not _nom_localite_libre(loc.province_id, nom, loc.id):
        flash(f'La localité « {nom} » existe déjà dans cette province.', 'danger')
    else:
        loc.nom = nom
        loc.actif = request.form.get('actif') == 'on'
        db.session.commit()
        flash(f'Localité « {nom} » mise à jour.', 'success')
    return redirect(url_for('referentiel.index', province=loc.province_id))
