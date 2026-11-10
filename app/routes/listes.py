"""Listes configurables — fonctionnement de YL.1 : les catégories sont
déclarées ici, l'administrateur gère seulement les valeurs (ajouter, modifier,
activer / désactiver, ordonner par glisser-déposer). Une valeur ne se
supprime pas : des fiches pourront la référencer.
Chaque lot ajoute ses catégories ici ; leurs valeurs de départ sont posées
par la migration du lot."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify

from app import db
from app.models import ListeDeroulante, Profil
from app.utils.permissions import profil_requis

listes_bp = Blueprint('listes', __name__)

CATEGORIES = {
    'statuts_ferme':         'Statuts de ferme',
    'types_infrastructures': "Types d'infrastructures",
    'types_operateurs':      "Types d'opérateurs",
    'fournisseurs':          'Fournisseurs',
    'motifs_ecart':          "Motifs d'écart à la réception",
    'signes_cliniques':      'Signes cliniques',
    'modes_administration':  "Modes d'administration des vaccins",
    'categories_depenses':   "Catégories de dépenses (« J'ai payé », l'émoji en tête sert d'image)",
    'conseils_veterinaire':  "Conseils du vétérinaire à l'éleveur (provisoire)",
    'recommandations_visite': "Recommandations de visite (provisoire)",
    'objets_visite':         "Objets de visite (provisoire)",
    'grille_biosecurite':    "Grille de biosécurité de l'agent (provisoire, à valider par les vétérinaires)",
    'maladies_suspectees':   "Maladies suspectées du diagnostic vétérinaire (provisoire)",
    'motifs_verification':   "Raisons d'un choix entre deux versions (« À vérifier » de l'agent) ; « Autre » demande un texte",
    'motifs_ecart_quai':     "Motifs d'écart à la réception des poulets (abattoir, marché) ; « Autre » demande un texte",
    'souches':               'Souches des bandes (chair et ponte)',
}


@listes_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    listes = {cat: ListeDeroulante.query.filter_by(categorie=cat)
              .order_by(ListeDeroulante.ordre, ListeDeroulante.id).all()
              for cat in CATEGORIES}
    return render_template('administration/listes.html', CATEGORIES=CATEGORIES, listes=listes)


def _valeur_libre(categorie, valeur, sauf_id=None):
    q = ListeDeroulante.query.filter(ListeDeroulante.categorie == categorie,
                                     db.func.lower(ListeDeroulante.valeur) == valeur.lower())
    if sauf_id:
        q = q.filter(ListeDeroulante.id != sauf_id)
    return q.first() is None


@listes_bp.route('/ajouter', methods=['POST'])
@profil_requis(Profil.ADMIN)
def ajouter():
    categorie = request.form.get('categorie', '').strip()
    valeur = request.form.get('valeur', '').strip()
    if categorie not in CATEGORIES or not valeur:
        flash('Données invalides.', 'danger')
        return redirect(url_for('listes.index'))
    if not _valeur_libre(categorie, valeur):
        flash(f'« {valeur} » existe déjà dans cette liste.', 'danger')
        return redirect(url_for('listes.index') + f'#{categorie}')
    dernier = (ListeDeroulante.query.filter_by(categorie=categorie)
               .order_by(ListeDeroulante.ordre.desc()).first())
    ordre = (dernier.ordre + 1) if dernier else 0
    db.session.add(ListeDeroulante(categorie=categorie, valeur=valeur, ordre=ordre, actif=True))
    db.session.commit()
    flash(f'Valeur « {valeur} » ajoutée.', 'success')
    return redirect(url_for('listes.index') + f'#{categorie}')


@listes_bp.route('/modifier/<int:id>', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier(id):
    item = db.session.get(ListeDeroulante, id) or abort(404)
    if request.form.get('archiver') or request.form.get('restaurer'):
        # Lot A1 : « Archiver » remplace « Désactiver » (journal : archivage / restauration)
        item.actif = bool(request.form.get('restaurer'))
        db.session.commit()
        flash(f'« {item.valeur} » ' + ('restaurée.' if item.actif else "archivée : elle n'est plus proposée."), 'success')
        return redirect(url_for('listes.index') + f'#{item.categorie}')
    valeur = request.form.get('valeur', '').strip()
    if not valeur:
        flash('La valeur ne peut pas être vide.', 'danger')
    elif not _valeur_libre(item.categorie, valeur, item.id):
        flash(f'« {valeur} » existe déjà dans cette liste.', 'danger')
    else:
        item.valeur = valeur
        item.actif = request.form.get('actif') == '1'
        db.session.commit()
        flash('Valeur modifiée.', 'success')
    return redirect(url_for('listes.index') + f'#{item.categorie}')


@listes_bp.route('/reordonner', methods=['POST'])
@profil_requis(Profil.ADMIN)
def reordonner():
    ids = (request.get_json(silent=True) or {}).get('ids', [])
    items = {i.id: i for i in ListeDeroulante.query.filter(ListeDeroulante.id.in_(ids)).all()}
    for rang, item_id in enumerate(ids):
        if item_id in items:
            items[item_id].ordre = rang
    db.session.commit()
    return jsonify(ok=True)
