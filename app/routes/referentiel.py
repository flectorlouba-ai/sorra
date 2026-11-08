import re

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app import db
from app.models import Province, Localite, Profil, Ferme, Operateur
from app.services.journal import enregistrer, Action
from app.utils.permissions import profil_requis

referentiel_bp = Blueprint('referentiel', __name__)

_CODE = re.compile(r'^[A-Z]{2,5}$')


@referentiel_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    provinces = Province.query.order_by(Province.ordre).all()
    a_verifier = (Localite.query.filter_by(a_verifier=True)
                  .join(Province).order_by(Province.ordre, Localite.nom).all())
    vue_a_verifier = request.args.get('a_verifier') == '1'
    choisie = request.args.get('province', type=int)
    province = db.session.get(Province, choisie) if choisie else None
    province = province or (provinces[0] if provinces else None)
    avec_fermes = {pid for (pid,) in db.session.query(Ferme.province_id).distinct()}
    fermes_par_localite = dict(db.session.query(Ferme.localite_id, db.func.count(Ferme.id))
                               .group_by(Ferme.localite_id).all())
    return render_template('administration/provinces.html', provinces=provinces,
                           province=None if vue_a_verifier else province,
                           a_verifier=a_verifier, vue_a_verifier=vue_a_verifier,
                           avec_fermes=avec_fermes, fermes_par_localite=fermes_par_localite)


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
    elif code != province.code and Ferme.query.filter_by(province_id=province.id).first():
        erreur = (f'Le code {province.code} ne peut plus changer : des fermes de la province '
                  f'portent un numéro qui commence par {province.code}.')
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


# ── Localités saisies sur le terrain : à vérifier ───────────────────────

def _retour(loc_province_id):
    if request.form.get('depuis') == 'a_verifier':
        return redirect(url_for('referentiel.index', a_verifier=1))
    return redirect(url_for('referentiel.index', province=loc_province_id))


@referentiel_bp.route('/localites/<int:localite_id>/valider', methods=['POST'])
@profil_requis(Profil.ADMIN)
def valider_localite(localite_id):
    loc = db.session.get(Localite, localite_id) or abort(404)
    loc.a_verifier = False
    db.session.commit()
    flash(f'Localité « {loc.nom} » validée.', 'success')
    return _retour(loc.province_id)


@referentiel_bp.route('/localites/<int:localite_id>/fusionner', methods=['POST'])
@profil_requis(Profil.ADMIN)
def fusionner_localite(localite_id):
    """Rattache les fermes et opérateurs de la localité à une localité existante,
    puis retire la localité en double."""
    loc = db.session.get(Localite, localite_id) or abort(404)
    cible_id = request.form.get('cible_id', type=int)
    cible = Localite.query.filter(Localite.id == cible_id, Localite.id != loc.id,
                                  Localite.province_id == loc.province_id).first()
    if cible is None:
        flash('Choisissez la localité de la même province qui doit la remplacer.', 'danger')
        return _retour(loc.province_id)
    fermes = Ferme.query.filter_by(localite_id=loc.id).all()
    for f in fermes:
        f.localite = cible
    operateurs = Operateur.query.filter_by(localite_id=loc.id).all()
    for o in operateurs:
        o.localite = cible
    nom, numeros = loc.nom, ', '.join(f.numero_metier for f in fermes) or 'aucune'
    db.session.flush()
    db.session.delete(loc)
    enregistrer(Action.FUSION, table='localite', enregistrement_id=cible.id,
                detail=f'« {nom} » fusionnée avec « {cible.nom} » ({loc.province.nom}) : '
                       f'{len(fermes)} ferme(s) rattachée(s) ({numeros}), '
                       f'{len(operateurs)} opérateur(s).')
    db.session.commit()
    flash(f'« {nom} » fusionnée avec « {cible.nom} » : {len(fermes)} ferme(s) rattachée(s).', 'success')
    return _retour(cible.province_id)
