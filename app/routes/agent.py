"""Lot 16 — écrans de l'agent technique : tournée du jour, nouvel éleveur, inventaire de stock,
commandes d'intrants, biosécurité. « Mes fermes » trie la liste existante par urgence (routes/fermes)."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Ferme, Profil, Produit
from app.models.agent import CommandeIntrant, StatutCommande as SC
from app.models.base import maintenant
from app.routes.fermes import charger
from app.services import agent as regles
from app.utils.permissions import profil_requis, filtre_perimetre

agent_bp = Blueprint('agent', __name__)


def _nombre(texte):
    try:
        return float((texte or '').replace(',', '.').replace(' ', ''))
    except ValueError:
        return None


def _gerer(ferme):
    if not regles.peut_gerer(current_user, ferme):
        abort(403)


# ── B. Tournée du jour ──────────────────────────────────────────────────

@agent_bp.route('/tournee')
@profil_requis(Profil.AGENT)
def tournee():
    return render_template('agent/tournee.html', lignes=regles.tournee(current_user), maintenant=maintenant())


# ── D. Nouvel éleveur ───────────────────────────────────────────────────

@agent_bp.route('/fermes/<numero>/eleveurs/nouveau', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def nouvel_eleveur(numero):
    ferme = charger(numero)
    _gerer(ferme)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            u, provisoire = regles.creer_eleveur(ferme, f.get('nom'), f.get('prenom'), f.get('telephone'), current_user)
            db.session.commit()
            # Affiché une seule fois, jamais gardé en clair ni envoyé
            return render_template('agent/eleveur_cree.html', ferme=ferme, eleveur=u, provisoire=provisoire)
        except regles.RegleAgent as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('agent/nouvel_eleveur.html', ferme=ferme, erreur=erreur, saisie=request.form)


# ── E. Inventaire de stock ──────────────────────────────────────────────

@agent_bp.route('/fermes/<numero>/stock/compter', methods=['POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def compter(numero):
    ferme = charger(numero)
    _gerer(ferme)
    produit = db.session.get(Produit, request.form.get('produit_id', type=int) or 0)
    if produit is None:
        abort(404)
    try:
        inv = regles.compter(ferme, produit, _nombre(request.form.get('compte')), current_user)
        db.session.commit()
        if regles.hors_seuil(inv):
            flash(f'Stock compté. Écart de {inv.ecart:g} ({inv.ecart_pct:g} %) au-delà du seuil de '
                  f'{regles.seuil_ecart():g} % : à expliquer avec l’éleveur.', 'warning')
        else:
            flash(f'Stock compté ✓ (écart {inv.ecart:g}).', 'success')
    except regles.RegleAgent as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#stock')


# ── F. Commandes d'intrants ─────────────────────────────────────────────

@agent_bp.route('/commandes')
@profil_requis(Profil.AGENT, Profil.DGE, Profil.ADMIN)
def commandes():
    statut = request.args.get('statut', '')
    q = filtre_perimetre(CommandeIntrant.query)
    if statut in SC.LIBELLES:
        q = q.filter(CommandeIntrant.statut == statut)
    liste = q.order_by(CommandeIntrant.cree_le.desc()).limit(200).all()
    if current_user.profil == Profil.AGENT:                 # l'agent a lu ses refus
        for c in liste:
            if c.statut == SC.REFUSEE and c.refus_lu_le is None:
                c.refus_lu_le = maintenant()
        db.session.commit()
    return render_template('agent/commandes.html', commandes=liste, statut=statut, libelles=SC.LIBELLES,
                           peut_decider=regles.peut_decider_commande(current_user),
                           fermes=(filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
                                   if current_user.profil == Profil.AGENT else []),
                           produits=Produit.query.filter_by(actif=True).order_by(Produit.type, Produit.nom).all())


@agent_bp.route('/commandes/nouvelle', methods=['POST'])
@profil_requis(Profil.AGENT)
def commander():
    ferme = filtre_perimetre(Ferme.query).filter(Ferme.numero_metier == request.form.get('ferme', '')).first()
    if ferme is None:
        abort(404)
    _gerer(ferme)
    try:
        regles.commander(ferme, db.session.get(Produit, request.form.get('produit_id', type=int) or 0),
                         _nombre(request.form.get('quantite')), request.form.get('motif'), current_user)
        db.session.commit()
        flash('Commande envoyée à la DGE ✓', 'success')
    except regles.RegleAgent as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(request.form.get('retour') or url_for('agent.commandes'))


@agent_bp.route('/commandes/<int:ident>/decider', methods=['POST'])
@profil_requis(Profil.DGE, Profil.ADMIN)
def decider(ident):
    c = filtre_perimetre(CommandeIntrant.query).filter(CommandeIntrant.id == ident).first_or_404()
    try:
        regles.decider_commande(c, current_user, request.form.get('decision') == 'valider', request.form.get('motif'))
        db.session.commit()
        flash(f'Commande {c.libelle_statut.lower()} ✓', 'success')
    except regles.RegleAgent as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('agent.commandes'))


# ── G. Biosécurité ──────────────────────────────────────────────────────

@agent_bp.route('/fermes/<numero>/biosecurite', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT)
def biosecurite(numero):
    ferme = charger(numero)
    _gerer(ferme)
    points = regles.grille()
    erreur = None
    if request.method == 'POST':
        reponses = {p: request.form.get(f'r{i}') for i, p in enumerate(points)}
        mesures = {p: request.form.get(f'm{i}') for i, p in enumerate(points)}
        try:
            v = regles.evaluer(ferme, current_user, reponses, mesures)
            db.session.commit()
            flash(f'Biosécurité enregistrée ✓ : {v.score_biosecurite} %. L’éleveur voit les mesures dans « Mes visites ».',
                  'success')
            return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#biosecurite')
        except regles.RegleAgent as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('agent/biosecurite.html', ferme=ferme, points=points, erreur=erreur, saisie=request.form)
