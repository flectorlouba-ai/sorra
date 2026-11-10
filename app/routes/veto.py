"""Lot 17 — écrans du vétérinaire : diagnostic d'un signalement, surveillance et blocage des sorties,
paramètres sanitaires (quatre yeux), recherche de lots amont et aval (export CSV, journal)."""
import csv
import io
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import current_user

from app import db
from app.models import Profil, Bande, Parametre
from app.models.bande import Sortie, StatutBande
from app.models.sante import AlerteSanitaire
from app.models.veto import BlocageSorties
from app.services import veto as regles, sante
from app.services.journal import enregistrer, Action
from app.utils.permissions import profil_requis, filtre_perimetre

veto_bp = Blueprint('veto', __name__)


# ── B. Diagnostic ───────────────────────────────────────────────────────

@veto_bp.route('/sante/alertes/<numero>/diagnostic', methods=['POST'])
@profil_requis(Profil.VETO)
def diagnostic(numero):
    a = sante.alertes_visibles(current_user).filter(AlerteSanitaire.numero == numero).first_or_404()
    maladie = request.form.get('maladie')
    if maladie == 'Autre':
        maladie = request.form.get('autre_maladie') or ''
    try:
        regles.diagnostiquer(a, maladie, request.form.get('prelevement') == 'on', request.form.get('observations'),
                             current_user)
        db.session.commit()
        flash('Diagnostic enregistré ✓ (réservé aux vétérinaires).', 'success')
    except regles.RegleVeto as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('sante.alerte', numero=a.numero) + '#diagnostic')


# ── C. Surveillance et blocage ──────────────────────────────────────────

@veto_bp.route('/surveillance')
@profil_requis(Profil.VETO, Profil.ADMIN)
def surveillance():
    actifs = regles.blocages_visibles(current_user).filter(BlocageSorties.leve_le.is_(None)) \
        .order_by(BlocageSorties.cree_le.desc()).all()
    leves = regles.blocages_visibles(current_user).filter(BlocageSorties.leve_le.isnot(None)) \
        .order_by(BlocageSorties.leve_le.desc()).limit(10).all()
    bloquees = {b.bande_id for b in actifs}
    bandes = [b for b in filtre_perimetre(Bande.query.filter_by(statut=StatutBande.EN_COURS)).order_by(Bande.numero_metier)
              if b.id not in bloquees]
    from app.services import conformite
    return render_template('veto/surveillance.html', conforme=('VETO-6', conformite.spec('VETO', 6), conformite.veto_bloquees(current_user, actifs, leves)),
                           actifs=actifs, leves=leves, bandes=bandes,
                           a_verifier=regles.sorties_a_verifier(regles.blocages_visibles(current_user).all()),
                           peut_agir=current_user.profil == Profil.VETO)


@veto_bp.route('/surveillance/bloquer', methods=['POST'])
@profil_requis(Profil.VETO)
def bloquer():
    bande = filtre_perimetre(Bande.query).filter(Bande.numero_metier == request.form.get('bande', '')).first()
    if bande is None:
        abort(404)
    alerte = None
    if request.form.get('alerte'):
        alerte = sante.alertes_visibles(current_user).filter(AlerteSanitaire.numero == request.form['alerte']).first()
    try:
        regles.bloquer(bande, request.form.get('motif'), current_user, alerte)
        db.session.commit()
        flash(f'Sorties de la bande {bande.numero} bloquées. L’éleveur voit le message, aucun lot ne sera créé.', 'warning')
    except regles.RegleVeto as e:
        db.session.rollback()
        flash(str(e), 'danger')
    if alerte is not None:
        return redirect(url_for('sante.alerte', numero=alerte.numero) + '#blocage')
    return redirect(url_for('veto.surveillance'))


@veto_bp.route('/surveillance/<int:ident>/lever', methods=['POST'])
@profil_requis(Profil.VETO)
def lever(ident):
    b = regles.blocages_visibles(current_user).filter(BlocageSorties.id == ident).first_or_404()
    try:
        regles.lever(b, request.form.get('motif'), current_user)
        db.session.commit()
        flash(f'Blocage levé : la bande {b.bande.numero} peut de nouveau sortir.', 'success')
    except regles.RegleVeto as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('veto.surveillance'))


@veto_bp.route('/surveillance/sorties/<uuid:ident>', methods=['POST'])
@profil_requis(Profil.VETO)
def verifier_sortie(ident):
    s = db.session.get(Sortie, ident) or abort(404)
    if filtre_perimetre(Bande.query.filter(Bande.id == s.bande_id)).first() is None:
        abort(403)
    try:
        regles.verifier_sortie(s, request.form.get('choix') == 'sortis', current_user)
        db.session.commit()
        flash('Sortie vérifiée ✓', 'success')
    except regles.RegleVeto as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('veto.surveillance'))


# ── D. Paramètres sanitaires ────────────────────────────────────────────

@veto_bp.route('/parametres-sanitaires')
@profil_requis(Profil.VETO)
def parametres():
    from app.models.securite import Proposition
    from app.services import conformite
    parametres = regles.parametres_sanitaires()
    propositions = Proposition.query.filter_by(statut='EN_ATTENTE').all()
    return render_template('veto/parametres.html', parametres=parametres, en_attente={p.cle for p in propositions},
                           conforme=('VETO-3', conformite.spec('VETO', 3), conformite.veto_seuils(current_user, parametres, propositions)))


@veto_bp.route('/parametres-sanitaires/<int:param_id>', methods=['POST'])
@profil_requis(Profil.VETO)
def proposer(param_id):
    from app.services import approbations
    from app.services.parametres import normaliser
    p = db.session.get(Parametre, param_id) or abort(404)
    if p not in regles.parametres_sanitaires():
        abort(403)
    try:
        valeur = normaliser(p.type, request.form.get('valeur', ''))
        if p.cle == 'bandes.courbe_poids':
            from app.indicateurs import lire_courbe
            lire_courbe(valeur)
        if valeur == p.valeur:
            flash('Aucun changement.', 'info')
        else:
            approbations.proposer('PARAMETRE', p.cle, p.description or p.cle, p.valeur, valeur, {'valeur': valeur},
                                  request.form.get('motif', ''), current_user)
            db.session.commit()
            flash('Proposition envoyée : elle s’appliquera après l’accord d’un autre vétérinaire, de la DGE ou de l’administration.',
                  'info')
    except (ValueError, approbations.RegleApprobation) as e:
        db.session.rollback()
        flash(f'{p.description} — {e}', 'danger')
    return redirect(url_for('veto.parametres'))


# ── E. Recherche de lots ────────────────────────────────────────────────

CHERCHEURS = (Profil.VETO, Profil.DGE, Profil.ADMIN)


def _rechercher():
    q = request.args.get('q', '').strip()
    if not q:
        return q, None, None
    try:
        r = regles.rechercher(q, current_user)
        enregistrer(Action.RECHERCHE, table='lot', detail=f'Recherche « {q} » : {len(r["fiches"])} bande(s)')
        db.session.commit()
        return q, r, None
    except regles.RegleVeto as e:
        return q, None, str(e)


@veto_bp.route('/recherche-lots')
@profil_requis(*CHERCHEURS)
def recherche():
    q, r, erreur = _rechercher()
    from app.services import conformite
    return render_template('veto/recherche.html', q=q, r=r, erreur=erreur,
                           conforme=('VETO-7', conformite.spec('VETO', 7), conformite.veto_tracabilite(current_user, q, r)))


@veto_bp.route('/recherche-lots.csv')
@profil_requis(*CHERCHEURS)
def recherche_csv():
    q, r, erreur = _rechercher()
    if r is None:
        abort(400)
    tampon = io.StringIO()
    csv.writer(tampon, delimiter=';').writerows(regles.lignes_csv(r))
    enregistrer(Action.EXPORT, table='lot', detail=f'Export de la recherche « {q} »')
    db.session.commit()
    return Response('﻿' + tampon.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=recherche-lots-{uuid.uuid4().hex[:6]}.csv'})
