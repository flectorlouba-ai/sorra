"""Catalogue des intrants : articles (produits) et fournisseurs. Lot A2 : ADMIN et DGE écrivent, l'agent lit.
Type et unité restent fixés dans le code."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Produit, Profil, Fournisseur
from app.models.intrant import TYPES_INTRANT, UNITES, TYPE_ALIMENT, UNITE_SACS, TYPES_FOURNISSEUR
from app.utils.permissions import profil_requis

catalogue_bp = Blueprint('catalogue', __name__)

ECRIVAINS = (Profil.ADMIN, Profil.DGE)
LECTEURS = ECRIVAINS + (Profil.AGENT,)


@catalogue_bp.route('/')
@profil_requis(*LECTEURS)
def index():
    f = {k: request.args.get(k, '') for k in ('type', 'etat', 'fournisseur')}
    q = Produit.query
    if f['type'] in TYPES_INTRANT:
        q = q.filter(Produit.type == f['type'])
    if f['etat'] != 'tous':
        q = q.filter(Produit.actif.is_(f['etat'] != 'archives'))
    if f.get('fournisseur', '').isdigit():
        q = q.filter(Produit.fournisseur_id == int(f['fournisseur']))
    produits = q.order_by(Produit.type, Produit.nom).all()
    return render_template('administration/catalogue.html', produits=produits, filtre=f,
                           ecrire=current_user.profil in ECRIVAINS,
                           fournisseurs=Fournisseur.query.filter_by(actif=True).order_by(Fournisseur.nom).all(),
                           n_archives=Produit.query.filter(Produit.actif.is_(False)).count(),
                           types=TYPES_INTRANT, unites=UNITES)


def _lire(produit=None):
    f = request.form
    nom = f.get('nom', '').strip()
    type_, unite = f.get('type'), f.get('unite')
    erreur = None
    try:
        poids = float(f.get('poids_sac_kg', '').replace(',', '.')) if f.get('poids_sac_kg', '').strip() else None
    except ValueError:
        poids, erreur = None, 'Le poids du sac doit être un nombre de kilos (ex. 25).'
    if not nom:
        erreur = 'Le nom du produit est obligatoire.'
    elif type_ not in TYPES_INTRANT:
        erreur = 'Choisissez le type.'
    elif unite not in UNITES:
        erreur = 'Choisissez l\'unité.'
    elif type_ == TYPE_ALIMENT and unite == UNITE_SACS and not poids:
        erreur = 'Pour un aliment vendu en sacs, le poids du sac est obligatoire.'
    elif poids is not None and poids <= 0:
        erreur = 'Le poids du sac doit être positif.'
    elif Produit.query.filter(db.func.lower(Produit.nom) == nom.lower(),
                              Produit.id != (produit.id if produit else -1)).first():
        erreur = f'Le produit « {nom} » existe déjà.'
    delai = f.get('delai_attente_jours', '').strip()
    if delai and (not delai.isdigit() or int(delai) > 365):
        erreur = erreur or "Le délai d'attente est un nombre de jours (0 à 365)."
    fournisseur = f.get('fournisseur_id', '')
    fournisseur = db.session.get(Fournisseur, int(fournisseur)) if fournisseur.isdigit() else None
    donnees = {'nom': nom, 'type': type_, 'unite': unite,
               'reference': f.get('reference', '').strip()[:40] or None,
               'conditionnement': f.get('conditionnement', '').strip()[:60] or None,
               'fournisseur_id': fournisseur.id if fournisseur else None,
               'poids_sac_kg': poids if unite == UNITE_SACS else None,
               'delai_attente_jours': int(delai) if delai.isdigit() and type_ == 'Médicament' else None}
    return donnees, erreur


@catalogue_bp.route('/creer', methods=['POST'])
@profil_requis(*ECRIVAINS)
def creer():
    donnees, erreur = _lire()
    if erreur:
        flash(erreur, 'danger')
    else:
        db.session.add(Produit(actif=True, **donnees))
        db.session.commit()
        flash(f'Produit « {donnees["nom"]} » ajouté.', 'success')
    return redirect(url_for('catalogue.index'))


@catalogue_bp.route('/<int:produit_id>/modifier', methods=['POST'])
@profil_requis(*ECRIVAINS)
def modifier(produit_id):
    produit = db.session.get(Produit, produit_id) or abort(404)
    if request.form.get('archiver') or request.form.get('restaurer'):
        # Lot A1 : « Archiver » remplace « Désactiver » (journal : archivage / restauration, avant / après)
        produit.actif = bool(request.form.get('restaurer'))
        db.session.commit()
        flash(f'Produit « {produit.nom} » ' + ('restauré.' if produit.actif else "archivé : il n'est plus proposé."), 'success')
        return redirect(url_for('catalogue.index'))
    donnees, erreur = _lire(produit)
    if erreur:
        flash(erreur, 'danger')
    else:
        for cle, valeur in donnees.items():
            setattr(produit, cle, valeur)
        db.session.commit()
        flash(f'Produit « {produit.nom} » enregistré.', 'success')
    return redirect(url_for('catalogue.index'))


# ── Fournisseurs (lot A2) ───────────────────────────────────────────────

@catalogue_bp.route('/fournisseurs')
@profil_requis(*LECTEURS)
def fournisseurs():
    etat = request.args.get('etat', '')
    q = Fournisseur.query.filter(Fournisseur.actif.is_(etat != 'archives'))
    return render_template('administration/fournisseurs.html', fournisseurs=q.order_by(Fournisseur.nom).all(),
                           etat=etat, types=TYPES_FOURNISSEUR, ecrire=current_user.profil in ECRIVAINS,
                           n_archives=Fournisseur.query.filter(Fournisseur.actif.is_(False)).count())


def _lire_fournisseur(fournisseur=None):
    f = request.form
    d = {'nom': f.get('nom', '').strip()[:150], 'type': f.get('type'),
         'telephone': f.get('telephone', '').strip()[:30] or None, 'ville': f.get('ville', '').strip()[:80] or None}
    if not d['nom']:
        return d, 'Le nom du fournisseur est obligatoire.'
    if d['type'] not in TYPES_FOURNISSEUR:
        return d, 'Choisissez le type de fournisseur.'
    if Fournisseur.query.filter(db.func.lower(Fournisseur.nom) == d['nom'].lower(),
                                Fournisseur.id != (fournisseur.id if fournisseur else -1)).first():
        return d, f'Le fournisseur « {d["nom"]} » existe déjà.'
    return d, None


@catalogue_bp.route('/fournisseurs/creer', methods=['POST'])
@profil_requis(*ECRIVAINS)
def creer_fournisseur():
    d, erreur = _lire_fournisseur()
    if erreur:
        flash(erreur, 'danger')
    else:
        db.session.add(Fournisseur(actif=True, **d))
        db.session.commit()
        flash(f'Fournisseur « {d["nom"]} » ajouté.', 'success')
    return redirect(url_for('catalogue.fournisseurs'))


@catalogue_bp.route('/fournisseurs/<int:ident>/modifier', methods=['POST'])
@profil_requis(*ECRIVAINS)
def modifier_fournisseur(ident):
    fo = db.session.get(Fournisseur, ident) or abort(404)
    if request.form.get('archiver') or request.form.get('restaurer'):
        fo.actif = bool(request.form.get('restaurer'))      # archivage synchronisé (lot A1)
        db.session.commit()
        flash(f'Fournisseur « {fo.nom} » ' + ('restauré.' if fo.actif else 'archivé.'), 'success')
        return redirect(url_for('catalogue.fournisseurs'))
    d, erreur = _lire_fournisseur(fo)
    if erreur:
        flash(erreur, 'danger')
    else:
        for cle, valeur in d.items():
            setattr(fo, cle, valeur)
        db.session.commit()
        flash(f'Fournisseur « {fo.nom} » enregistré.', 'success')
    return redirect(url_for('catalogue.fournisseurs'))
