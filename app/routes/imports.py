"""Lot B — imports Excel / CSV (ADMIN, DGE) : choix du modèle, fichier, correspondance des colonnes (proposée, mémorisée),
aperçu et vérification, import en un lot annulable, rapport, liste des lots."""
import base64
import json

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, abort, session
from flask_login import current_user

from app import db
from app.models import Profil
from app.models.imports import LotImport
from app.services import imports as regles
from app.utils.permissions import profil_requis

imports_bp = Blueprint('imports', __name__)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
GESTIONNAIRES = (Profil.ADMIN, Profil.DGE)


@imports_bp.route('/')
@profil_requis(*GESTIONNAIRES)
def index():
    lots = LotImport.query.order_by(LotImport.cree_le.desc()).limit(100).all()
    return render_template('imports/index.html', modeles=regles.MODELES, lots=lots, apercu=None)


@imports_bp.route('/modele/<cle>.xlsx')
@profil_requis(*GESTIONNAIRES)
def modele(cle):
    if cle not in regles.MODELES:
        abort(404)
    return Response(regles.modele_xlsx(cle), mimetype=XLSX, headers={'Content-Disposition': f'attachment; filename="SORRA_modele_{cle}.xlsx"'})


def _fichier_en_session():
    d = session.get('import_fichier')
    if not d:
        return None, None, None
    return d['cle'], d['nom'], base64.b64decode(d['contenu'])


@imports_bp.route('/apercu', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def apercu():
    """Fichier reçu → entêtes, correspondance proposée, 20 premières lignes."""
    cle = request.form.get('modele')
    f = request.files.get('fichier')
    if cle not in regles.MODELES or f is None or not f.filename:
        flash('Choisissez un modèle et un fichier (.xlsx ou .csv).', 'danger')
        return redirect(url_for('imports.index'))
    contenu = f.read()
    if len(contenu) > 5 * 1024 * 1024:
        flash('Fichier trop lourd (5 Mo au plus).', 'danger')
        return redirect(url_for('imports.index'))
    try:
        entetes, lignes = regles.lire(contenu, f.filename)
    except regles.RegleImport as e:
        flash(str(e), 'danger')
        return redirect(url_for('imports.index'))
    session['import_fichier'] = {'cle': cle, 'nom': f.filename, 'contenu': base64.b64encode(contenu).decode()}
    corresp = regles.correspondance(cle, entetes)
    return render_template('imports/index.html', modeles=regles.MODELES, lots=LotImport.query.order_by(LotImport.cree_le.desc()).limit(100).all(),
                           apercu={'cle': cle, 'nom': f.filename, 'entetes': entetes, 'lignes': lignes[:20], 'total': len(lignes), 'corresp': corresp})


@imports_bp.route('/verifier', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def verifier():
    """Correspondance confirmée → vérification ligne à ligne (rien n'est créé)."""
    cle, nom, contenu = _fichier_en_session()
    if cle is None:
        flash('Recommencez : le fichier n\'est plus en mémoire.', 'warning')
        return redirect(url_for('imports.index'))
    entetes, lignes = regles.lire(contenu, nom)
    corresp = {e: request.form.get(f'col_{i}', '') for i, e in enumerate(entetes) if e}
    manquantes = [lib for k, lib, obl, _ in regles.MODELES[cle]['colonnes'] if obl and k not in corresp.values()]
    if manquantes:
        flash('Colonnes obligatoires sans correspondance : ' + ', '.join(manquantes), 'danger')
        return render_template('imports/index.html', modeles=regles.MODELES, lots=[], apercu={'cle': cle, 'nom': nom, 'entetes': entetes,
                               'lignes': lignes[:20], 'total': len(lignes), 'corresp': corresp})
    regles.memoriser(cle, corresp, current_user)
    db.session.commit()
    resultats = regles.verifier(cle, entetes, lignes, corresp, current_user)
    session['import_corresp'] = corresp
    return render_template('imports/verification.html', cle=cle, nom=nom, modele=regles.MODELES[cle], resultats=resultats,
                           ok=sum(1 for r in resultats if r['ok']))


@imports_bp.route('/importer', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def importer():
    cle, nom, contenu = _fichier_en_session()
    corresp = session.get('import_corresp')
    if cle is None or not corresp:
        flash('Recommencez : le fichier n\'est plus en mémoire.', 'warning')
        return redirect(url_for('imports.index'))
    entetes, lignes = regles.lire(contenu, nom)
    resultats = regles.verifier(cle, entetes, lignes, corresp, current_user)
    lot = regles.importer(cle, nom, resultats, current_user)
    db.session.commit()
    session.pop('import_fichier', None)
    session.pop('import_corresp', None)
    flash(f'{lot.nb_importees} ligne(s) importée(s) sur {lot.nb_lignes} · lot n° {lot.id} (annulable).', 'success')
    return redirect(url_for('imports.lot', ident=lot.id))


@imports_bp.route('/lots/<int:ident>')
@profil_requis(*GESTIONNAIRES)
def lot(ident):
    lot = db.session.get(LotImport, ident) or abort(404)
    return render_template('imports/lot.html', lot=lot, modele=regles.MODELES.get(lot.modele, {'nom': lot.modele}),
                           lignes=json.loads(lot.rapport or '[]'))


@imports_bp.route('/lots/<int:ident>/rapport.xlsx')
@profil_requis(*GESTIONNAIRES)
def rapport(ident):
    lot = db.session.get(LotImport, ident) or abort(404)
    return Response(regles.rapport_xlsx(lot), mimetype=XLSX, headers={'Content-Disposition': f'attachment; filename="SORRA_import_{lot.id}_rapport.xlsx"'})


@imports_bp.route('/lots/<int:ident>/annuler', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def annuler(ident):
    lot = db.session.get(LotImport, ident) or abort(404)
    try:
        n = regles.annuler(lot, current_user, request.form.get('motif'))
        db.session.commit()
        flash(f'Lot n° {lot.id} annulé : {n} enregistrement(s) archivé(s).', 'success')
    except regles.RegleImport as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('imports.lot', ident=lot.id))
