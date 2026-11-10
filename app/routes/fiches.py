"""Lot A1 — fiches : modifier, archiver, restaurer une saisie, et voir les archivées.

Les fiches s'ouvrent en fenêtre depuis les listes (le formulaire prérempli est déjà dans la page : il marche sans
réseau). L'envoi passe par une seule adresse, avec `action` = modifier | archiver | restaurer ; sans réseau, il part
dans la file d'attente du téléphone comme les autres saisies (hors_ligne.js).
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app import db
from app.models import Profil, Ferme, Bande
from app.services import fiches
from app.services.fiches import RegleFiche
from app.utils.permissions import filtre_perimetre, profil_requis

fiches_bp = Blueprint('fiches', __name__, url_prefix='/fiches')

MESSAGES = {'modifie': '✓ Modification enregistrée.',
            'inchange': 'Rien à changer.',
            'deux_versions': 'Les deux versions sont gardées : la saisie passe « À vérifier ».'}


def retour_sur(defaut=None):
    """Adresse de retour : un chemin du site seulement (jamais une autre adresse)."""
    r = request.values.get('retour') or ''
    if r.startswith('/') and not r.startswith('//') and '\\' not in r:
        return r
    return defaut or url_for('accueil.index')


def _charger(genre, ident):
    o = fiches.charger(genre, ident)
    if o is None:
        abort(404)
    g = fiches.genre_de(o)
    if g.ferme(o).id not in fiches.fermes_visibles(current_user, [g.ferme(o)]):
        abort(404)
    return o


@fiches_bp.route('/<genre>/<ident>', methods=['POST'])
@login_required
def enregistrer(genre, ident):
    o = _charger(genre, ident)
    action, motif = request.form.get('action', 'modifier'), request.form.get('motif')
    try:
        if action == 'archiver':
            fiches.archiver(o, current_user, motif)
            message = '🗄️ Archivée : elle ne compte plus. Votre agent peut la restaurer.'
        elif action == 'restaurer':
            fiches.restaurer(o, current_user, motif)
            message = '✓ Restaurée : elle compte de nouveau.'
        else:
            message = MESSAGES[fiches.modifier(o, request.form, current_user)]
        db.session.commit()
        flash(message, 'success')
    except RegleFiche as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(retour_sur())


@fiches_bp.route('/<genre>/archivees')
@login_required
def archivees(genre):
    """« Voir les archivées (n) » : d'une bande, d'une ferme, ou de toutes les fermes de l'éleveur."""
    if genre not in fiches.GENRES:
        abort(404)
    bande = ferme = None
    if request.args.get('bande'):
        bande = filtre_perimetre(Bande.query).filter(Bande.numero_metier == request.args['bande']).first_or_404()
        elements = fiches.archivees(genre, bande=bande)
    elif request.args.get('ferme'):
        ferme = filtre_perimetre(Ferme.query).filter(Ferme.numero_metier == request.args['ferme']).first_or_404()
        elements = fiches.archivees(genre, ferme=ferme)
    elif current_user.profil == Profil.ELEVEUR:
        elements = [e for f in filtre_perimetre(Ferme.query).all() for e in fiches.archivees(genre, ferme=f)]
    else:
        abort(404)
    return render_template('fiches/archivees.html', genre=genre, elements=elements, bande=bande, ferme=ferme,
                           infos=fiches.infos(elements, current_user), retour=retour_sur())


# ── Fermes et bandes (ADMIN) ────────────────────────────────────────────

def _entite(genre, numero):
    from app.models.base import AVEC_ARCHIVES
    modele = {'ferme': Ferme, 'bande': Bande}.get(genre) or abort(404)
    return (modele.query.execution_options(**{AVEC_ARCHIVES: True})
            .filter(modele.numero_metier == numero).first_or_404())


@fiches_bp.route('/entite/<genre>/<numero>', methods=['POST'])
@profil_requis(Profil.ADMIN)
def entite(genre, numero):
    o = _entite(genre, numero)
    try:
        if request.form.get('action') == 'restaurer':
            fiches.restaurer_entite(o, current_user, request.form.get('motif'))
            message = f'{o.numero} restaurée.'
        else:
            fiches.archiver_entite(o, current_user, request.form.get('motif'))
            message = f'🗄️ {o.numero} archivée : masquée des listes et des calculs, conservée.'
        db.session.commit()
        flash(message, 'success')
    except RegleFiche as e:
        db.session.rollback()
        flash(str(e), 'danger')
        return redirect(retour_sur())
    if request.form.get('action') == 'restaurer':
        return redirect(url_for('fermes.fiche' if genre == 'ferme' else 'bandes.fiche', numero=o.numero))
    return redirect(url_for('fermes.liste' if genre == 'ferme' else 'bandes.liste'))


@fiches_bp.route('/entite/<genre>/archivees')
@profil_requis(Profil.ADMIN)
def entites_archivees(genre):
    from app.models.base import AVEC_ARCHIVES
    modele = {'ferme': Ferme, 'bande': Bande}.get(genre) or abort(404)
    elements = (modele.query.execution_options(**{AVEC_ARCHIVES: True}).filter(modele.archive_le.isnot(None))
                .order_by(modele.archive_le.desc()).all())
    return render_template('fiches/entites_archivees.html', genre=genre, elements=elements)
