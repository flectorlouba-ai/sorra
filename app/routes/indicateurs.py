"""Lot C — indicateurs : mortalité et viabilité à 5 niveaux (bande, ferme, cohorte, province, national) avec passage
d'un niveau à l'autre, participation à l'objectif national (C2), et « Mes indicateurs » par profil (C3).
Calculs : app/indicateurs.py ; choix par profil : app/services/mes_indicateurs.py."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request, abort, url_for
from flask_login import login_required, current_user

from app import db, indicateurs as ind
from app.models import Ferme, Province, Profil
from app.models.bande import Bande
from app.services import mes_indicateurs
from app.utils.permissions import filtre_perimetre, profil_requis

indicateurs_bp = Blueprint('indicateurs', __name__)

NIVEAUX = ('national', 'province', 'cohorte', 'ferme', 'bande')
LECTEURS = (Profil.ADMIN, Profil.DGE, Profil.VETO, Profil.AGENT, Profil.AUDITEUR)   # l'éleveur : « Mes indicateurs »


def _cohorte(f):
    if not f.programme_poufa:
        return 'hors'
    return str(f.cohorte) if f.cohorte else 'sans'


LIBELLES_COHORTE = {'1': 'Cohorte 1', '2': 'Cohorte 2', 'sans': 'Programme, sans cohorte', 'hors': 'Hors programme'}


def _bandes_de(fermes):
    debut = date.today() - timedelta(days=365)
    ids = [f.id for f in fermes]
    if not ids:
        return []
    return (filtre_perimetre(Bande.query).filter(Bande.ferme_id.in_(ids))
            .filter(db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= debut)).all())


def _ligne(libelle, lien, fermes, bandes=None):
    bandes = bandes if bandes is not None else _bandes_de(fermes)
    return {'libelle': libelle, 'lien': lien, 'fermes': len(fermes), **ind.mortalite_viabilite(bandes),
            'participation': ind.participation(fermes) if fermes else None}


@indicateurs_bp.route('/indicateurs/niveaux')
@profil_requis(*LECTEURS)
def niveaux():
    """C1 + C2 : un niveau et ses sous-niveaux ; un clic descend d'un niveau. Toujours dans le périmètre."""
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    niveau = request.args.get('niveau', 'national' if current_user.est_national else 'province')
    if niveau not in NIVEAUX:
        abort(404)
    province = request.args.get('province', type=int)
    cohorte = request.args.get('cohorte')
    ferme_num = request.args.get('ferme')
    fil = [{'libelle': 'National' if current_user.est_national else 'Mon périmètre', 'lien': url_for('indicateurs.niveaux', niveau='national')}]
    if province:
        fermes = [f for f in fermes if f.province_id == province]
        p = db.session.get(Province, province)
        if p is None:
            abort(404)
        fil.append({'libelle': p.nom, 'lien': url_for('indicateurs.niveaux', niveau='province', province=province)})
    if cohorte:
        fermes = [f for f in fermes if _cohorte(f) == cohorte]
        fil.append({'libelle': LIBELLES_COHORTE.get(cohorte, cohorte),
                    'lien': url_for('indicateurs.niveaux', niveau='cohorte', province=province, cohorte=cohorte)})
    if ferme_num:
        fermes = [f for f in fermes if f.numero == ferme_num]
        if not fermes:
            abort(404)
        fil.append({'libelle': ferme_num, 'lien': url_for('indicateurs.niveaux', niveau='ferme', ferme=ferme_num)})
    total = _ligne(fil[-1]['libelle'], None, fermes)
    lignes = []
    if niveau == 'national':
        for p in Province.query.order_by(Province.ordre):
            fp = [f for f in fermes if f.province_id == p.id]
            if fp:
                lignes.append(_ligne(p.nom, url_for('indicateurs.niveaux', niveau='province', province=p.id), fp))
        enfants = 'Province'
    elif niveau == 'province':
        for c in ('1', '2', 'sans', 'hors'):
            fc = [f for f in fermes if _cohorte(f) == c]
            if fc:
                lignes.append(_ligne(LIBELLES_COHORTE[c], url_for('indicateurs.niveaux', niveau='cohorte',
                                                                   province=province, cohorte=c), fc))
        enfants = 'Cohorte'
    elif niveau == 'cohorte':
        for f in fermes:
            lignes.append(_ligne(f'{f.numero} · {f.nom}', url_for('indicateurs.niveaux', niveau='ferme', ferme=f.numero), [f]))
        enfants = 'Ferme'
    else:
        for b in _bandes_de(fermes):
            lignes.append(_ligne(f'{b.numero} · {b.libelle_type}', url_for('bandes.fiche', numero=b.numero), [], [b]))
            lignes[-1]['participation'] = None
        enfants = 'Bande'
    return render_template('indicateurs/niveaux.html', niveau=niveau, fil=fil, total=total, lignes=lignes,
                           enfants=enfants, financier=current_user.profil != Profil.VETO)


@indicateurs_bp.route('/mes-indicateurs')
@login_required
def mes():
    """C3 : 5 à 8 indicateurs clés du profil, dont 3 courbes hebdomadaires sur 52 semaines (SVG local)."""
    donnees = mes_indicateurs.pour(current_user)
    if donnees is None:
        abort(404)
    return render_template('indicateurs/mes_indicateurs.html', d=donnees)
