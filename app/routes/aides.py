"""« Comment faire ? » (lot 13) : l'aide de chaque écran principal de l'éleveur (bouton « ? »), la liste
complète (👤 Moi → Comment faire ?), et leur modification par l'ADMIN (Configuration → Aides)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import current_user

from app import db
from app.models import Profil
from app.models.aide import Aide, CAPTURES, GROUPES
from app.utils.permissions import profil_requis

aides_bp = Blueprint('aides', __name__)


@aides_bp.route('/aide')
@profil_requis(Profil.ELEVEUR)
def liste():
    aides = Aide.query.filter_by(actif=True).order_by(Aide.ordre).all()
    groupes = [(g, [a for a in aides if a.groupe == g]) for g in GROUPES]
    return render_template('aides/liste.html', groupes=[(g, l) for g, l in groupes if l])


@aides_bp.route('/aide/<cle>')
@profil_requis(Profil.ELEVEUR)
def aide(cle):
    a = Aide.query.filter_by(cle=cle, actif=True).first()
    if a is None:
        abort(404)
    return render_template('aides/aide.html', a=a, captures=CAPTURES, retour=request.args.get('retour'))


@aides_bp.route('/administration/aides', methods=['GET', 'POST'])
@profil_requis(Profil.ADMIN)
def administrer():
    if request.method == 'POST':
        a = Aide.query.filter_by(cle=request.form.get('cle')).first_or_404()
        titre = (request.form.get('titre') or '').strip()
        etapes = []
        for i in range(3):
            texte = (request.form.get(f'texte-{i}') or '').strip()
            capture = request.form.get(f'capture-{i}') or ''
            if texte:
                etapes.append({'texte': texte[:200], 'capture': capture if capture in CAPTURES else ''})
        if not titre or not etapes:
            flash('Indiquez un titre et au moins une étape.', 'danger')
            return redirect(url_for('aides.administrer', modifier=a.cle))
        a.titre, a.etapes, a.actif = titre[:120], etapes, request.form.get('actif') == 'on'   # journal automatique
        db.session.commit()
        flash(f'Aide « {a.titre} » enregistrée (inscrite au journal).', 'success')
        return redirect(url_for('aides.administrer'))
    return render_template('aides/administrer.html', aides=Aide.query.order_by(Aide.ordre).all(),
                           modifiee=Aide.query.filter_by(cle=request.args.get('modifier')).first(),
                           captures=CAPTURES)
