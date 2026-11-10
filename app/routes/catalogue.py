"""Catalogue des intrants (ADMIN) : produits, avec type et unité fixés dans le code."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app import db
from app.models import Produit, Profil
from app.models.intrant import TYPES_INTRANT, UNITES, TYPE_ALIMENT, UNITE_SACS
from app.utils.permissions import profil_requis

catalogue_bp = Blueprint('catalogue', __name__)


@catalogue_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    f = {k: request.args.get(k, '') for k in ('type', 'etat')}
    q = Produit.query
    if f['type'] in TYPES_INTRANT:
        q = q.filter(Produit.type == f['type'])
    if f['etat'] != 'tous':
        q = q.filter(Produit.actif.is_(f['etat'] != 'archives'))
    produits = q.order_by(Produit.type, Produit.nom).all()
    return render_template('administration/catalogue.html', produits=produits, filtre=f,
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
    donnees = {'nom': nom, 'type': type_, 'unite': unite,
               'poids_sac_kg': poids if unite == UNITE_SACS else None,
               'delai_attente_jours': int(delai) if delai.isdigit() and type_ == 'Médicament' else None}
    return donnees, erreur


@catalogue_bp.route('/creer', methods=['POST'])
@profil_requis(Profil.ADMIN)
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
@profil_requis(Profil.ADMIN)
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
