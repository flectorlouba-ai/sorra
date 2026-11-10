"""Visites techniques (lot 12) : l'agent planifie et rédige le compte rendu (sans réseau aussi),
l'éleveur lit les recommandations dans « 👤 Moi → 📋 Mes visites »."""
import uuid
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file
from app.models.liste_deroulante import ld_choices
from flask_login import current_user

from app import db
from app.models import Ferme, Profil
from app.models.visite import Visite, StatutVisite
from app.services import visites as regles, sante, hors_ligne
from app.utils.permissions import profil_requis, filtre_perimetre

visites_bp = Blueprint('visites', __name__)


def _ferme(numero):
    f = filtre_perimetre(Ferme.query.filter(Ferme.du_numero(numero))).first()
    if f is None:
        abort(404)
    return f


def _visite(ident):
    v = filtre_perimetre(Visite.query.filter(Visite.id == ident)).first()
    if v is None:
        abort(404)
    return v


def _jour(texte):
    try:
        return date.fromisoformat(texte) if texte else None
    except ValueError:
        raise regles.RegleVisite('Date invalide.')


def _nombre(texte):
    try:
        return float(texte) if texte not in (None, '') else None
    except ValueError:
        return None


@visites_bp.route('/fermes/<numero>/visites/planifier', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT)
def planifier(numero):
    ferme = _ferme(numero)
    erreur = None
    if request.method == 'POST':
        try:
            v = regles.planifier(ferme, _jour(request.form.get('date')), request.form.get('objet'), current_user)
            db.session.commit()
            flash(f'Visite prévue {regles.quand(v.date_prevue)} : l\'éleveur la voit sur son accueil.', 'success')
            return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#visites')
        except regles.RegleVisite as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('visites/planifier.html', ferme=ferme, objets=regles.objets(), erreur=erreur,
                           saisie=request.form)


def _distance_visite_m():
    from app.services import positions
    return positions.distance_visite_m()


@visites_bp.route('/fermes/<numero>/visites/compte-rendu', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT)
def compte_rendu(numero):
    ferme = _ferme(numero)
    visite = None
    if request.values.get('visite'):
        try:
            visite = _visite(uuid.UUID(request.values.get('visite')))
        except ValueError:
            abort(404)
        if visite.ferme_id != ferme.id:
            abort(404)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            photo = None
            if request.files.get('photo') and request.files['photo'].filename:
                try:
                    enregistre = sante._enregistrer(request.files['photo'], sante._SIGNATURES, sous_dossier='visites')
                except sante.RegleSante as e:
                    raise regles.RegleVisite(str(e))
                photo = enregistre[0] if enregistre else None
            regles.compte_rendu(ferme, visite, current_user, f.get('objet'), f.get('constats'),
                                f.getlist('recommandations'), f.get('recommandation_libre'),
                                _nombre(f.get('latitude')), _nombre(f.get('longitude')), photo,
                                hors_ligne.jour_de_saisie(), precision=_nombre(f.get('precision')),
                                motif_distance=(f.get('motif_distance_autre') or '').strip() or f.get('motif_distance'))
            db.session.commit()
            flash('Compte rendu enregistré ✓ : l\'éleveur voit vos recommandations.', 'success')
            from app.utils import terrain
            if terrain.profil_terrain(current_user) == 'agent':      # lot 19 ter : retour à la fiche terrain
                return redirect(url_for('terrain.fiche', numero=ferme.numero))
            return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#visites')
        except regles.RegleVisite as e:
            db.session.rollback()
            erreur = str(e)
    from app.utils import terrain
    if terrain.profil_terrain(current_user) == 'agent':              # lot 19 ter : une page de haut en bas
        from app.routes.terrain import _fermes_en_pastilles
        from app.services import agent
        tournee, autres = _fermes_en_pastilles()
        return render_template('terrain/agent/visite.html', ferme=ferme, visite=visite, objets=regles.objets(),
                               recommandations=regles.recommandations_types(), erreur=erreur, saisie=request.form,
                               tournee=tournee, autres=autres, n_questions=len(agent.grille()),
                               distance_max_m=_distance_visite_m(),
                               motifs_distance=[v for v, _ in ld_choices('motifs_visite_eloignee')])
    return render_template('visites/compte_rendu.html', ferme=ferme, visite=visite, objets=regles.objets(),
                           recommandations=regles.recommandations_types(), erreur=erreur, saisie=request.form)


@visites_bp.route('/visites/<uuid:ident>/annuler', methods=['POST'])
@profil_requis(Profil.AGENT)
def annuler(ident):
    v = _visite(ident)
    try:
        regles.annuler(v, request.form.get('motif'), current_user)
        db.session.commit()
        flash('Visite annulée (inscrite au journal).', 'info')
    except regles.RegleVisite as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('fermes.fiche', numero=v.ferme.numero) + '#visites')


@visites_bp.route('/visites/<uuid:ident>/photo')
@profil_requis(Profil.AGENT, Profil.ELEVEUR, Profil.ADMIN, Profil.DGE)
def photo(ident):
    v = _visite(ident)
    chemin = sante.chemin_fichier(v.photo, sous_dossier='visites') if v.photo else None
    if chemin is None:
        abort(404)
    return send_file(chemin)


@visites_bp.route('/mes-visites')
@profil_requis(Profil.ELEVEUR)
def mes_visites():
    ids = [f.id for f in filtre_perimetre(Ferme.query)]
    liste = regles.faites(ids)
    nouvelles = {v.id for v in liste if v.vue_par_eleveur_le is None}
    regles.marquer_vues(ids)
    db.session.commit()
    p = regles.prochaine(ids)
    return render_template('visites/mes_visites.html', visites=liste, nouvelles=nouvelles, prochaine=p,
                           quand=regles.quand)
