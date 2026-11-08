from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from app import db
from app.models import Operateur, Province, Localite, Profil
from app.models.liste_deroulante import ld_choices
from app.services.numerotation import generer_numero
from app.utils.permissions import profil_requis, filtre_perimetre

operateurs_bp = Blueprint('operateurs', __name__)

LECTEURS = (Profil.ADMIN, Profil.DGE, Profil.AGENT)
GESTIONNAIRES = (Profil.ADMIN, Profil.DGE)


def charger(numero):
    op = Operateur.query.filter_by(numero=numero).first()
    if op is None:
        abort(404)
    if filtre_perimetre(Operateur.query.filter(Operateur.id == op.id)).first() is None:
        abort(403)
    return op


@operateurs_bp.route('/')
@profil_requis(*LECTEURS)
def liste():
    base = filtre_perimetre(Operateur.query)
    f = {k: request.args.get(k, '').strip() for k in ('type', 'province', 'etat', 'q')}
    q = base
    if f['type']:
        q = q.filter(Operateur.type == f['type'])
    if f['province'].isdigit():
        q = q.filter(Operateur.province_id == int(f['province']))
    if f['etat'] != 'tous':
        q = q.filter(Operateur.actif.is_(f['etat'] != 'inactifs'))
    if f['q']:
        motif = f'%{f["q"]}%'
        q = q.filter(db.or_(Operateur.nom.ilike(motif), Operateur.numero.ilike(motif),
                            Operateur.contact.ilike(motif)))
    return render_template('operateurs/liste.html', operateurs=q.order_by(Operateur.numero).all(),
                           total=base.filter(Operateur.actif.is_(True)).count(), filtre=f,
                           types=[v for v, _ in ld_choices('types_operateurs')],
                           provinces=filtre_perimetre(Province.query).order_by(Province.ordre).all())


@operateurs_bp.route('/<numero>')
@profil_requis(*LECTEURS)
def fiche(numero):
    return render_template('operateurs/fiche.html', op=charger(numero))


def _contexte(op, saisie, erreurs):
    return dict(op=op, saisie=saisie, erreurs=erreurs,
                provinces=Province.query.filter_by(actif=True).order_by(Province.ordre).all(),
                localites=Localite.query.filter_by(actif=True).order_by(Localite.nom).all(),
                types=[v for v, _ in ld_choices('types_operateurs')])


def _lire(f, op):
    d, erreurs = {}, []
    d['nom'] = f.get('nom', '').strip()
    if not d['nom']:
        erreurs.append('Le nom est obligatoire.')
    types = [v for v, _ in ld_choices('types_operateurs')] + ([op.type] if op else [])
    d['type'] = f.get('type') if f.get('type') in types else None
    if d['type'] is None:
        erreurs.append('Choisissez le type.')
    pid = f.get('province_id', '')
    d['province'] = db.session.get(Province, int(pid)) if pid.isdigit() else None
    if d['province'] is None:
        erreurs.append('Choisissez la province.')
    lid = f.get('localite_id', '')
    d['localite'] = None
    if lid.isdigit() and d['province']:
        d['localite'] = Localite.query.filter_by(id=int(lid), province_id=d['province'].id).first()
        if d['localite'] is None:
            erreurs.append('La localité ne correspond pas à la province.')
    d['contact'] = f.get('contact', '').strip() or None
    d['telephone'] = f.get('telephone', '').strip() or None
    d['convention'] = f.get('convention') == 'on'
    d['convention_date'] = None
    if d['convention'] and f.get('convention_date'):
        try:
            d['convention_date'] = date.fromisoformat(f['convention_date'])
        except ValueError:
            erreurs.append('Date de convention invalide.')
    if op is not None:
        d['actif'] = f.get('actif') == 'on'
    return d, erreurs


@operateurs_bp.route('/nouveau', methods=['GET', 'POST'])
@profil_requis(*GESTIONNAIRES)
def nouveau():
    if request.method == 'GET':
        return render_template('operateurs/formulaire.html', **_contexte(None, {}, []))
    d, erreurs = _lire(request.form, None)
    if erreurs:
        return render_template('operateurs/formulaire.html',
                               **_contexte(None, request.form, erreurs))
    op = Operateur(numero=generer_numero('OPERATEUR', 'OPE', largeur=4), actif=True, **d)
    db.session.add(op)
    db.session.commit()
    flash(f'Opérateur {op.numero} créé.', 'success')
    return redirect(url_for('operateurs.fiche', numero=op.numero))


@operateurs_bp.route('/<numero>/modifier', methods=['GET', 'POST'])
@profil_requis(*GESTIONNAIRES)
def modifier(numero):
    op = charger(numero)
    if request.method == 'GET':
        return render_template('operateurs/formulaire.html', **_contexte(op, {}, []))
    d, erreurs = _lire(request.form, op)
    if erreurs:
        return render_template('operateurs/formulaire.html', **_contexte(op, request.form, erreurs))
    for cle, valeur in d.items():
        setattr(op, cle, valeur)
    db.session.commit()
    flash(f'Opérateur {op.numero} enregistré.', 'success')
    return redirect(url_for('operateurs.fiche', numero=op.numero))
