"""Lot 19 — écrans de l'opérateur (abattoir, marché, acheteur, distributeur), téléphone d'abord :
scanner un lot, résultat (vert, orange, rouge), réception, lots attendus, mes réceptions.
La décision du vétérinaire sur un lot reçu sous réserve est ici aussi (formulaire dans ses Signalements)."""
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Profil
from app.models.tracabilite import Reception, EtatReception as E, ResultatScan as R
from app.services import receptions as regles, hors_ligne
from app.utils.permissions import profil_requis, filtre_perimetre

operateur_bp = Blueprint('operateur', __name__, url_prefix='/operateur')

ATTENDUS_SEMAINE = 7


def operateur_courant():
    op = current_user.operateur
    if op is None:
        abort(403)
    return op


def accueil(user):
    """Données de l'accueil de l'opérateur (gabarit operateur/_accueil.html)."""
    op = user.operateur
    if op is None:
        return {'operateur': None}
    return {'operateur': op, 'attendus': regles.attendus(op), 'semaine': regles.attendus(op, ATTENDUS_SEMAINE),
            'a_traiter': regles.a_traiter(op)}


def _attendus_pour_le_telephone(op):
    """Lots attendus, gardés dans la page du scanner : sans réseau, le téléphone reconnaît le lot lu et
    affiche l'annoncé (la vérification reste faite par le serveur à l'arrivée)."""
    return {lot.code: {'numero': lot.numero, 'nombre': lot.sortie.nombre, 'ferme': lot.ferme.nom,
                       'date': lot.sortie.date.strftime('%d/%m')} for lot in regles.attendus(op)}


@operateur_bp.route('/scanner')
@profil_requis(Profil.OPERATEUR)
def scanner():
    op = operateur_courant()
    return render_template('operateur/scanner.html', operateur=op, attendus=_attendus_pour_le_telephone(op),
                           motifs=regles.motifs_ecart(), motif_autre=regles.MOTIF_AUTRE, saisie={}, annonce=None,
                           seuil_morts=regles.seuil_morts())


def _ecran_lot(lot, op, examen, erreur=None, saisie=None):
    return render_template('operateur/lot.html', lot=lot, operateur=op, examen=examen, R=R, erreur=erreur,
                           saisie=saisie or {}, motifs=regles.motifs_ecart(), motif_autre=regles.MOTIF_AUTRE,
                           abattoir=regles.est_abattoir(op), seuil_morts=regles.seuil_morts(),
                           annonce=lot.sortie.nombre if lot is not None else None)


@operateur_bp.route('/lot')
@profil_requis(Profil.OPERATEUR)
def lot():
    """Résultat d'un scan (QR lu par la caméra) ou d'un numéro tapé : chaque lecture est inscrite au journal."""
    op = operateur_courant()
    code, numero = request.args.get('code', '').strip(), request.args.get('numero', '').strip()
    if not code and not numero:
        return redirect(url_for('operateur.scanner'))
    source = 'CAMERA' if code else 'NUMERO'
    lt = regles.trouver(code or None, None if code else numero)
    examen = regles.examiner(lt, op)
    regles.noter_scan(lt, op, current_user, source, examen['couleur'], examen['refus'], code or None,
                      None if code else numero)
    db.session.commit()
    return _ecran_lot(lt, op, examen)


@operateur_bp.route('/recevoir', methods=['POST'])
@profil_requis(Profil.OPERATEUR)
def recevoir():
    op = operateur_courant()
    f = request.form
    try:
        r = regles.recevoir(op, current_user, f.get('vivants'), f.get('morts'), f.get('poids'),
                            choix=f.get('choix', 'valider'), motif_ecart=f.get('motif_ecart'),
                            explication=f.get('explication'), code=f.get('code') or None,
                            numero=f.get('numero') or None, hors_ligne=hors_ligne.actif())
        db.session.commit()
    except regles.RegleReception as e:
        db.session.rollback()
        if hors_ligne.actif():
            flash(str(e), 'danger')
            return redirect(url_for('accueil.index'))
        lt = regles.trouver(f.get('code') or None, f.get('numero') or None)
        return _ecran_lot(lt, op, regles.examiner(lt, op), erreur=str(e), saisie=f), 400
    if r.etat == E.VALIDEE:
        flash(f'Réception du lot {r.lot_saisi} validée ✓', 'success')
    elif r.etat == E.SOUS_RESERVE:
        flash(f'Lot {r.lot_saisi} reçu sous réserve : ne pas abattre, ne pas vendre avant la décision du '
              'vétérinaire.', 'warning')
    elif r.hors_ligne:
        flash(f'Réception du lot {r.lot_saisi} refusée à la vérification : {r.motif_refus}', 'danger')
    else:
        flash(f'Lot {r.lot_saisi} refusé. La ferme est prévenue.', 'info')
    return redirect(url_for('accueil.index'))


@operateur_bp.route('/attendus')
@profil_requis(Profil.OPERATEUR)
def attendus():
    op = operateur_courant()
    return render_template('operateur/attendus.html', operateur=op, lots=regles.attendus(op))


@operateur_bp.route('/receptions')
@profil_requis(Profil.OPERATEUR)
def receptions():
    op = operateur_courant()
    rs = (filtre_perimetre(Reception.query).order_by(Reception.recu_le.desc()).limit(100).all())
    return render_template('operateur/receptions.html', operateur=op, receptions=rs, E=E)


def _charger(ident):
    try:
        rid = uuid.UUID(ident)
    except ValueError:
        abort(404)
    r = filtre_perimetre(Reception.query).filter(Reception.id == rid).first()
    if r is None:
        abort(404 if db.session.get(Reception, rid) is None else 403)
    return r


@operateur_bp.route('/receptions/<ident>')
@profil_requis(Profil.OPERATEUR, Profil.VETO, Profil.ADMIN, Profil.DGE)
def reception(ident):
    r = _charger(ident)
    if current_user.profil == Profil.OPERATEUR:
        regles.marquer_vu(r)
        db.session.commit()
    return render_template('operateur/reception.html', r=r, E=E, motifs=regles.motifs_ecart(),
                           motif_autre=regles.MOTIF_AUTRE, a_completer=regles.explication_manquante(r),
                           peut_decider=regles.peut_decider(current_user, r))


@operateur_bp.route('/receptions/<ident>/expliquer', methods=['POST'])
@profil_requis(Profil.OPERATEUR)
def expliquer(ident):
    r = _charger(ident)
    try:
        regles.expliquer(r, request.form.get('motif_ecart'), request.form.get('explication'), current_user)
        regles.marquer_vu(r)
        db.session.commit()
        flash('Merci : la raison de l\'écart est envoyée.', 'success')
    except regles.RegleReception as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('operateur.reception', ident=ident))


@operateur_bp.route('/receptions/<ident>/decider', methods=['POST'])
@profil_requis(Profil.VETO)
def decider(ident):
    r = _charger(ident)
    choix = request.form.get('choix')
    try:
        if choix not in ('liberer', 'refuser'):
            raise regles.RegleReception('Choisissez : libérer ou refuser le lot.')
        regles.decider(r, choix == 'liberer', request.form.get('motif'), current_user)
        db.session.commit()
        flash(f'Lot {r.lot_saisi} {"libéré" if choix == "liberer" else "refusé"}. L\'établissement est prévenu.',
              'success')
    except regles.RegleReception as e:
        db.session.rollback()
        flash(str(e), 'danger')
    retour = request.form.get('retour', '')
    return redirect(retour if retour.startswith('/') and not retour.startswith('//') else url_for('sante.alertes'))
