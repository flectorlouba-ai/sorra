"""Entretien (lot 10) : écran de l'éleveur (et de l'agent pour lui), pannes, liste des tâches (ADMIN)."""
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file
from flask_login import current_user

from app import db
from app.models import Ferme, Profil
from app.models.entretien import (TacheEntretien, EntretienFait, Panne, Frequence, Portee, TypePanne,
                                  StatutPanne)
from app.models.liste_deroulante import ld_choices
from app.services import entretien as regles, hors_ligne, sante
from app.utils.permissions import profil_requis, filtre_perimetre

entretien_bp = Blueprint('entretien', __name__)

UTILISATEURS = (Profil.ELEVEUR, Profil.AGENT)


def _ferme():
    """Ferme de l'éleveur, ou celle que l'agent ouvre pour lui (?ferme=EST-001)."""
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    voulue = request.values.get('ferme')
    ferme = next((f for f in fermes if f.numero == voulue), None) if voulue else (fermes[0] if fermes else None)
    if ferme is None:
        abort(404)
    return ferme


def _retour(ferme):
    if current_user.profil == Profil.ELEVEUR:
        return redirect(url_for('entretien.ecran'))
    return redirect(url_for('entretien.ecran', ferme=ferme.numero))


def _lignes_recentes(ids):
    """Lignes « Fait ✓ » gardées en session (identifiants en texte)."""
    try:
        ids = [uuid.UUID(i) for i in ids or []]
    except (ValueError, TypeError):
        return []
    return EntretienFait.query.filter(EntretienFait.id.in_(ids)).all() if ids else []


def _bandeau_fait():
    lignes = _lignes_recentes(session.get('entretien_recent'))
    if not regles.annulable(lignes, current_user):
        session.pop('entretien_recent', None)
        return None
    from app.models.base import maintenant
    from app.utils.dates import en_utc
    ecoule = (maintenant() - en_utc(lignes[0].cree_le)).total_seconds()
    return {'tache': lignes[0].tache, 'secondes': max(1, round(regles.DELAI_ANNULATION_SECONDES - ecoule))}


def _bandeau_repare():
    try:
        ident = uuid.UUID(session.get('panne_reparee') or '')
    except ValueError:
        ident = None
    p = db.session.get(Panne, ident) if ident else None
    if p is None or not regles.reparation_annulable(p, current_user):
        session.pop('panne_reparee', None)
        return None
    from app.models.base import maintenant
    from app.utils.dates import en_utc
    ecoule = (maintenant() - en_utc(p.reparee_le)).total_seconds()
    return {'panne': p, 'secondes': max(1, round(regles.DELAI_ANNULATION_SECONDES - ecoule))}


@entretien_bp.route('/entretien')
@profil_requis(*UTILISATEURS)
def ecran():
    ferme = _ferme()
    from app.models.entretien import EntretienFait
    from app.services import fiches
    faits = (EntretienFait.query.filter_by(ferme_id=ferme.id, annule=False)
             .order_by(EntretienFait.fait_le.desc(), EntretienFait.cree_le.desc()).limit(10).all())
    return render_template('entretien/ecran.html', ferme=ferme, cartes=regles.cartes(ferme),
                           pannes=regles.pannes_en_cours(ferme), bandeau_fait=_bandeau_fait(),
                           bandeau_repare=_bandeau_repare(), faits=faits,
                           n_archives={g: fiches.nombre_archivees(g, ferme=ferme) for g in ('entretien', 'panne')})


@entretien_bp.route('/entretien/fait', methods=['POST'])
@profil_requis(*UTILISATEURS)
def fait():
    ferme = _ferme()
    tache = db.session.get(TacheEntretien, request.form.get('tache', type=int) or 0)
    if tache is None:
        abort(404)
    try:
        lignes = regles.marquer_fait(ferme, tache, current_user)
        db.session.commit()
        if lignes and not hors_ligne.actif():
            session['entretien_recent'] = [str(l.id) for l in lignes]   # « Fait ✓ — Annuler (10) »
    except regles.RegleEntretien as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return _retour(ferme)


@entretien_bp.route('/entretien/fait/annuler', methods=['POST'])
@profil_requis(*UTILISATEURS)
def annuler_fait():
    ferme = _ferme()
    lignes = _lignes_recentes(session.pop('entretien_recent', None))
    if regles.annulable(lignes, current_user):
        regles.annuler_fait(lignes)
        db.session.commit()
        flash('Annulé : la tâche est de nouveau à faire.', 'info')
    else:
        flash('Le délai pour annuler est passé.', 'warning')
    return _retour(ferme)


@entretien_bp.route('/entretien/panne', methods=['GET', 'POST'])
@profil_requis(*UTILISATEURS)
def panne():
    ferme = _ferme()
    batiments = sorted([b for b in ferme.batiments if b.actif], key=lambda b: b.code)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            choix = f.get('batiment', '')
            if len(batiments) == 1:
                batiment = batiments[0]
            elif choix in ('', 'ferme'):
                batiment = None
            else:
                batiment = next((b for b in batiments if str(b.id) == choix), None)
                if batiment is None:
                    raise regles.RegleEntretien('Bâtiment inconnu.')
            photo = None
            if request.files.get('photo') and request.files['photo'].filename:
                try:
                    enregistre = sante._enregistrer(request.files['photo'], sante._SIGNATURES, sous_dossier='pannes')
                except sante.RegleSante as e:
                    raise regles.RegleEntretien(str(e))
                photo = enregistre[0] if enregistre else None
            regles.signaler(ferme, f.get('type'), batiment, current_user, photo)
            db.session.commit()
            flash('Envoyé ✓ : votre agent est prévenu.' if current_user.profil == Profil.ELEVEUR
                  else 'Panne enregistrée pour l\'éleveur.', 'success')
            return _retour(ferme)
        except regles.RegleEntretien as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('entretien/panne.html', ferme=ferme, batiments=batiments, types=TypePanne.TOUS,
                           erreur=erreur, saisie=request.form)


def _charger_panne(ident):
    p = filtre_perimetre(Panne.query.filter(Panne.id == ident)).first()
    if p is None:
        abort(404)
    return p


@entretien_bp.route('/entretien/panne/<uuid:ident>/reparee', methods=['POST'])
@profil_requis(*UTILISATEURS)
def reparee(ident):
    p = _charger_panne(ident)
    regles.reparer(p, current_user)
    db.session.commit()
    if not hors_ligne.actif():
        session['panne_reparee'] = str(p.id)     # « Réparé ✓ — Annuler (10) »
    return _retour(p.ferme)


@entretien_bp.route('/entretien/panne/<uuid:ident>/annuler', methods=['POST'])
@profil_requis(*UTILISATEURS)
def annuler_reparation(ident):
    p = _charger_panne(ident)
    session.pop('panne_reparee', None)
    if regles.reparation_annulable(p, current_user):
        regles.annuler_reparation(p, current_user)
        db.session.commit()
        flash('Annulé : la panne est de nouveau signalée, votre agent la voit toujours.', 'info')
    else:
        flash('Le délai pour annuler est passé.', 'warning')
    return _retour(p.ferme)


@entretien_bp.route('/entretien/panne/<uuid:ident>/photo')
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.DGE, Profil.ADMIN)
def photo(ident):
    p = _charger_panne(ident)
    chemin = sante.chemin_fichier(p.photo, sous_dossier='pannes') if p.photo else None
    if chemin is None:
        abort(404)
    return send_file(chemin)


# ── Liste des tâches (ADMIN, Configuration) ─────────────────────────────

@entretien_bp.route('/administration/entretien', methods=['GET', 'POST'])
@profil_requis(Profil.ADMIN)
def taches():
    if request.method == 'POST':
        f = request.form
        t = db.session.get(TacheEntretien, f.get('id', type=int)) if f.get('id') else TacheEntretien()
        if t is None:
            abort(404)
        nom = f.get('nom', '').strip()
        if not nom or f.get('frequence') not in Frequence.TOUTES or f.get('portee') not in Portee.TOUTES:
            flash('Indiquez le nom, la fréquence et la portée.', 'danger')
            return redirect(url_for('entretien.taches'))
        t.nom, t.icone = nom[:120], (f.get('icone') or '🔧').strip()[:16]
        t.frequence, t.portee = f.get('frequence'), f.get('portee')
        t.infrastructure = f.get('infrastructure') or None
        t.actif = f.get('actif') == 'on'
        if t.id is None:
            t.ordre = (db.session.query(db.func.max(TacheEntretien.ordre)).scalar() or 0) + 1
            db.session.add(t)
        db.session.commit()
        flash(f'Tâche « {t.nom} » enregistrée.', 'success')
        return redirect(url_for('entretien.taches'))
    return render_template('entretien/taches.html',
                           taches=TacheEntretien.query.order_by(TacheEntretien.ordre, TacheEntretien.id).all(),
                           frequences=Frequence.LIBELLES, portees=Portee.LIBELLES,
                           infrastructures=[v for v, _ in ld_choices('types_infrastructures')],
                           modifiee=db.session.get(TacheEntretien, request.args.get('modifier', type=int) or 0))
