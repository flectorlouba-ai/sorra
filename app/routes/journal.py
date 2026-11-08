import csv
import io
import json
from datetime import date, timedelta

from flask import Blueprint, render_template, request, Response, abort, current_app

from app import db
from app.models import JournalAudit, Utilisateur, Profil
from app.services.journal import enregistrer, Action
from app.utils.dates import date_locale, debut_jour_utc
from app.utils.permissions import profil_requis

journal_bp = Blueprint('journal', __name__)

# Mots simples à l'écran à la place des noms techniques
TABLES = {
    'utilisateur': 'Compte utilisateur',
    'province': 'Province',
    'localite': 'Localité',
    'liste_deroulante': 'Valeur de liste',
    'parametre': 'Paramètre',
}

CHAMPS = {
    'identifiant': 'Identifiant', 'nom': 'Nom', 'prenom': 'Prénom', 'email': 'E-mail',
    'telephone': 'Téléphone', 'mot_de_passe_hash': 'Mot de passe', 'profil': 'Profil',
    'actif': 'Actif', 'doit_changer_mdp': 'Mot de passe à changer',
    'provinces': 'Provinces', 'code': 'Code', 'ordre': 'Ordre', 'province_id': 'Province',
    'categorie': 'Liste', 'valeur': 'Valeur', 'cle': 'Réglage', 'type': 'Type',
    'description': 'Description', 'modifie_par': 'Modifié par', 'cree_le': 'Créé le',
    'modifie_le': 'Modifié le', 'derniere_connexion': 'Dernière connexion',
}

# Champs internes sans intérêt pour le lecteur
_CACHES = {'id', 'cree_le', 'modifie_le', 'modifie_par', 'derniere_connexion'}


def libelle_element(ligne):
    """Nom lisible de l'élément concerné (identifiant, nom, valeur…)."""
    donnees = ligne.apres or ligne.avant or {}
    for champ in ('identifiant', 'nom', 'valeur', 'description', 'cle'):
        if donnees.get(champ):
            return str(donnees[champ])
    return ''


def _filtrer(args):
    q = JournalAudit.query
    du = args.get('du', type=date.fromisoformat)
    au = args.get('au', type=date.fromisoformat)
    if du:
        q = q.filter(JournalAudit.horodatage >= debut_jour_utc(du))
    if au:
        q = q.filter(JournalAudit.horodatage < debut_jour_utc(au + timedelta(days=1)))
    if args.get('personne'):
        q = q.filter(JournalAudit.identifiant == args['personne'])
    if args.get('element') in TABLES:
        q = q.filter(JournalAudit.table_nom == args['element'])
    if args.get('action') in Action.TOUTES:
        q = q.filter(JournalAudit.action == args['action'])
    return q.order_by(JournalAudit.horodatage.desc(), JournalAudit.id.desc())


@journal_bp.route('/')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def index():
    page = request.args.get('page', 1, type=int)
    pagination = _filtrer(request.args).paginate(
        page=page, per_page=current_app.config['JOURNAL_PAR_PAGE'], error_out=False)
    personnes = [i for (i,) in db.session.query(Utilisateur.identifiant)
                 .order_by(Utilisateur.identifiant).all()]
    filtres = {k: v for k, v in request.args.items() if k != 'page' and v}
    return render_template('journal/index.html', pagination=pagination, filtres=filtres,
                           personnes=personnes, tables=TABLES, actions=Action.LIBELLES,
                           libelle_element=libelle_element)


@journal_bp.route('/<int:ligne_id>')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def detail(ligne_id):
    ligne = db.session.get(JournalAudit, ligne_id) or abort(404)
    avant, apres = ligne.avant or {}, ligne.apres or {}
    champs = [c for c in dict.fromkeys(list(avant) + list(apres)) if c not in _CACHES]
    lignes = [(CHAMPS.get(c, c), avant.get(c), apres.get(c)) for c in champs]
    return render_template('journal/detail.html', ligne=ligne, lignes=lignes,
                           tables=TABLES, actions=Action.LIBELLES,
                           element=libelle_element(ligne), filtres=request.args)


@journal_bp.route('/export.csv')
@profil_requis(Profil.ADMIN, Profil.AUDITEUR)
def export():
    lignes = _filtrer(request.args).all()
    tampon = io.StringIO()
    tampon.write('﻿')  # Excel reconnaît ainsi les accents
    ecrivain = csv.writer(tampon, delimiter=';')
    ecrivain.writerow(['Date', 'Personne', 'Adresse IP', 'Action', 'Élément', 'Nom',
                       'Référence', 'Avant', 'Après', 'Détail'])
    for l in lignes:
        ecrivain.writerow([
            date_locale(l.horodatage, '%d/%m/%Y %H:%M:%S'), l.identifiant or '', l.adresse_ip or '',
            Action.LIBELLES.get(l.action, l.action), TABLES.get(l.table_nom, l.table_nom or ''),
            libelle_element(l), l.enregistrement_id or '',
            json.dumps(l.avant, ensure_ascii=False) if l.avant else '',
            json.dumps(l.apres, ensure_ascii=False) if l.apres else '',
            l.detail or '',
        ])
    filtres = ', '.join(f'{k}={v}' for k, v in request.args.items() if v) or 'aucun filtre'
    enregistrer(Action.EXPORT, table='journal_audit',
                detail=f'Export CSV du journal : {len(lignes)} ligne(s) ; {filtres}')
    db.session.commit()
    return Response(tampon.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition':
                             f'attachment; filename=journal_kimba_{date.today():%Y%m%d}.csv'})
