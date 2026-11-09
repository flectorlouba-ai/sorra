import os

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort,
                   Response, session)
from flask_login import current_user

from app import db
from app.models import Ferme, Province, Localite, Utilisateur, Profil, FermeInfrastructure, Batiment, Livraison
from app.models.intrant import OrigineLivraison
from app.models.base import maintenant
from app.models.ferme import SourcePosition
from app.models.liste_deroulante import ld_choices
from app.services import fermes as regles
from app.services import geo, import_poufa, intrants
from app.services import bandes as regles_bandes
from app.models import Bande
from app.services.journal import enregistrer, Action
from app.utils.permissions import profil_requis, filtre_perimetre, a_profil

fermes_bp = Blueprint('fermes', __name__)

XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
LECTEURS = (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO)
CREATEURS = (Profil.ADMIN, Profil.DGE, Profil.AGENT)


def charger(numero):
    """Ferme du périmètre de l'utilisateur, sinon 404 (inconnue) ou 403 (hors périmètre)."""
    ferme = Ferme.query.filter_by(numero_metier=numero).first()
    if ferme is None:
        abort(404)
    if filtre_perimetre(Ferme.query.filter(Ferme.id == ferme.id)).first() is None:
        abort(403)
    return ferme


def controle_position(ferme):
    """Résultat du contrôle hors province, avec le nom des provinces, ou None."""
    if not ferme.a_une_position:
        return None
    r = geo.verifier(ferme.latitude, ferme.longitude, ferme.province.code)
    if r and r['province_trouvee']:
        r['nom_trouvee'] = Province.query.filter_by(code=r['province_trouvee']).first().nom
    return r


# ── Liste ───────────────────────────────────────────────────────────────

@fermes_bp.route('/')
@profil_requis(*LECTEURS)
def liste():
    base = filtre_perimetre(Ferme.query)
    total = base.count()
    operationnelles = base.filter(Ferme.statut == 'Opérationnelle').count()
    f = {k: request.args.get(k, '').strip() for k in ('province', 'cohorte', 'statut', 'q')}
    q = base
    if f['province'].isdigit():
        q = q.filter(Ferme.province_id == int(f['province']))
    if f['cohorte'] in ('1', '2'):
        q = q.filter(Ferme.cohorte == int(f['cohorte']))
    elif f['cohorte'] == 'aucune':
        q = q.filter(Ferme.cohorte.is_(None))
    if f['statut']:
        q = q.filter(Ferme.statut == f['statut'])
    if f['q']:
        motif = f'%{f["q"]}%'
        q = q.filter(db.or_(Ferme.nom.ilike(motif), Ferme.numero_metier.ilike(motif),
                            Ferme.exploitant_nom.ilike(motif), Ferme.reference_ami.ilike(motif)))
    fermes = q.order_by(Ferme.numero_metier).all()
    provinces = filtre_perimetre(Province.query).order_by(Province.ordre).all() \
        if not current_user.est_national else Province.query.order_by(Province.ordre).all()
    if current_user.profil == Profil.AGENT:
        # L'agent filtre parmi les provinces où il a des fermes ou peut en créer
        ids = {fe.province_id for fe in base} | set(current_user.province_ids)
        provinces = [p for p in Province.query.order_by(Province.ordre) if p.id in ids]
    return render_template('fermes/liste.html', fermes=fermes, total=total,
                           operationnelles=operationnelles, filtre=f, provinces=provinces,
                           statuts=[v for v, _ in ld_choices('statuts_ferme')],
                           peut_creer=regles.peut_creer(current_user))


# ── Fiche ───────────────────────────────────────────────────────────────

@fermes_bp.route('/<numero>')
@profil_requis(*LECTEURS)
def fiche(numero):
    ferme = charger(numero)
    controle = controle_position(ferme)
    dessin = geo.dessin(ferme.province.code, ferme.latitude, ferme.longitude)
    return render_template('fermes/fiche.html', ferme=ferme, controle=controle, dessin=dessin,
                           peut_modifier=regles.peut_modifier(current_user, ferme),
                           stock=intrants.stock_ferme(ferme),
                           achats=(Livraison.query.filter_by(ferme_id=ferme.id, origine=OrigineLivraison.ACHAT)
                                   .order_by(Livraison.date_livraison.desc(), Livraison.numero_metier.desc()).all()
                                   if current_user.profil in (Profil.AGENT, Profil.DGE, Profil.ADMIN) else None),
                           etats={b.id: regles_bandes.etat_batiment(b) for b in ferme.batiments},
                           bandes=Bande.query.filter_by(ferme_id=ferme.id)
                           .order_by(Bande.date_mise_en_place.desc()).all())


# ── Création / modification ─────────────────────────────────────────────

def _nombre(texte, entier=False):
    texte = (texte or '').strip().replace(',', '.')
    if not texte:
        return None
    return int(texte) if entier else float(texte)


def _agents():
    return (Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True)
            .order_by(Utilisateur.nom, Utilisateur.prenom).all())


def _contexte_formulaire(ferme, provinces, saisie, erreurs, suggestions=None):
    localites = (Localite.query.filter(Localite.province_id.in_([p.id for p in provinces]),
                                       Localite.actif.is_(True))
                 .order_by(Localite.nom).all())
    return dict(ferme=ferme, provinces=provinces, localites=localites, saisie=saisie,
                erreurs=erreurs, suggestions=suggestions or [],
                agents=_agents() if a_profil(Profil.ADMIN, Profil.DGE) else [],
                statuts=[v for v, _ in ld_choices('statuts_ferme')],
                infrastructures=[v for v, _ in ld_choices('types_infrastructures')],
                province_modifiable=ferme is None or a_profil(Profil.ADMIN))


def _lire(f, ferme, provinces):
    """Contrôle la saisie. Renvoie (données, erreurs, suggestions de localité)."""
    d, erreurs = {}, []
    d['nom'] = f.get('nom', '').strip()
    d['exploitant_nom'] = f.get('exploitant_nom', '').strip()
    d['exploitant_telephone'] = f.get('exploitant_telephone', '').strip()
    if not d['nom']:
        erreurs.append('Le nom de la ferme est obligatoire.')
    if not d['exploitant_nom']:
        erreurs.append('Le nom de l\'exploitant est obligatoire.')
    if len(regles.normaliser_telephone(d['exploitant_telephone'])) < 7:
        erreurs.append('Le téléphone de l\'exploitant est obligatoire (au moins 7 chiffres).')

    # Province
    if ferme is not None and not a_profil(Profil.ADMIN):
        province = ferme.province
    else:
        pid = f.get('province_id', '')
        province = next((p for p in provinces if str(p.id) == pid), None)
        if province is None:
            erreurs.append('Choisissez la province.')
    d['province'] = province

    # Localité : existante, choisie dans une suggestion, ou nouvelle
    suggestions, d['localite'], d['localite_nouvelle'] = [], None, None
    choix = f.get('localite_choisie') or f.get('localite_id', '')
    if province is not None:
        if choix == 'nouvelle':
            nom_loc = f.get('localite_nouvelle', '').strip()
            if not nom_loc:
                erreurs.append('Écrivez le nom de la nouvelle localité.')
            else:
                existante = regles.localite_identique(province.id, nom_loc)
                if existante:
                    d['localite'] = existante
                else:
                    suggestions = regles.localites_semblables(province.id, nom_loc)
                    if suggestions and not f.get('confirmer_nouvelle'):
                        erreurs.append('')   # bloque l'enregistrement : question posée à l'écran
                    else:
                        suggestions = []
                        d['localite_nouvelle'] = nom_loc
        elif choix.isdigit():
            d['localite'] = Localite.query.filter_by(id=int(choix), province_id=province.id).first()
            if d['localite'] is None:
                erreurs.append('La localité ne correspond pas à la province.')
        else:
            erreurs.append('Choisissez la localité.')

    # Position
    try:
        lat, lon = _nombre(f.get('latitude')), _nombre(f.get('longitude'))
        precision = _nombre(f.get('gps_precision_m'), entier=True)
    except ValueError:
        lat = lon = precision = None
        erreurs.append('La position doit être écrite en chiffres (ex. 0,3921 et 9,6103).')
    if (lat is None) != (lon is None):
        erreurs.append('Indiquez la latitude et la longitude, ou aucune des deux.')
    elif lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
        erreurs.append('Position impossible : vérifiez la latitude et la longitude.')
    d['latitude'], d['longitude'], d['gps_precision_m'] = lat, lon, precision
    d['gps_source'] = SourcePosition.GPS if f.get('gps_source') == 'GPS' else SourcePosition.MANUELLE

    # Agent référent (choisi par ADMIN et DGE)
    if a_profil(Profil.ADMIN, Profil.DGE):
        aid = f.get('agent_id', '')
        d['agent'] = next((a for a in _agents() if str(a.id) == aid), None)
        if aid and d['agent'] is None:
            erreurs.append('Agent technique inconnu.')

    # Compléments (modification seulement)
    if ferme is not None:
        d['reference_ami'] = f.get('reference_ami', '').strip().upper() or None
        cohorte = f.get('cohorte', '')
        d['cohorte'] = int(cohorte) if cohorte in ('1', '2') else None
        statuts = [v for v, _ in ld_choices('statuts_ferme')] + [ferme.statut]
        d['statut'] = f.get('statut') if f.get('statut') in statuts else ferme.statut
        connues = [v for v, _ in ld_choices('types_infrastructures')] + \
                  [i.infrastructure for i in ferme.infrastructures]
        d['infrastructures'] = sorted({i for i in f.getlist('infrastructures') if i in connues})
        d['observations'] = f.get('observations', '').strip() or None

    if not [e for e in erreurs if e] and '' not in erreurs:
        loc_id = d['localite'].id if d['localite'] else None
        erreurs += regles.doublons(d['nom'], d['exploitant_telephone'], loc_id,
                                   d.get('reference_ami'), sauf_id=ferme.id if ferme else None)
    return d, erreurs, suggestions


def _position_changee(ferme, d):
    return ferme is None or (ferme.latitude, ferme.longitude) != (d['latitude'], d['longitude'])


def _avertir_position(ferme):
    c = controle_position(ferme)
    if c and not c['ok']:
        ou = f' (elle semble dans la province {c["nom_trouvee"]})' if c.get('nom_trouvee') else \
            ' (elle semble hors du Gabon)'
        flash(f'Attention : la position est à {c["distance_km"]} km de la province '
              f'{ferme.province.nom}{ou}. Vérifiez-la.', 'warning')


@fermes_bp.route('/nouvelle', methods=['GET', 'POST'])
@profil_requis(*CREATEURS)
def nouvelle():
    provinces = regles.provinces_de_creation(current_user, Province.query.filter_by(actif=True)
                                             .order_by(Province.ordre).all())
    if not provinces:
        flash('Aucune province ne vous est attribuée : demandez à l\'administrateur.', 'warning')
        return redirect(url_for('fermes.liste'))
    if request.method == 'GET':
        return render_template('fermes/formulaire.html',
                               **_contexte_formulaire(None, provinces, {}, []))

    d, erreurs, suggestions = _lire(request.form, None, provinces)
    if erreurs:
        return render_template('fermes/formulaire.html', **_contexte_formulaire(
            None, provinces, request.form, [e for e in erreurs if e], suggestions))
    if d['localite_nouvelle']:
        d['localite'] = regles.creer_localite(d['province'].id, d['localite_nouvelle'],
                                              par_admin=a_profil(Profil.ADMIN))
    agent = current_user if current_user.profil == Profil.AGENT else d.get('agent')
    ferme = regles.creer_ferme(
        d['province'], current_user, nom=d['nom'], exploitant_nom=d['exploitant_nom'],
        exploitant_telephone=d['exploitant_telephone'], localite=d['localite'],
        agent_id=agent.id if agent else None, latitude=d['latitude'], longitude=d['longitude'],
        gps_precision_m=d['gps_precision_m'] if d['latitude'] is not None else None,
        gps_source=d['gps_source'] if d['latitude'] is not None else None,
        gps_date=maintenant() if d['latitude'] is not None else None)
    db.session.commit()
    flash(f'Ferme {ferme.numero} créée.', 'success')
    _avertir_position(ferme)
    return redirect(url_for('fermes.fiche', numero=ferme.numero))


@fermes_bp.route('/<numero>/modifier', methods=['GET', 'POST'])
@profil_requis(*CREATEURS)
def modifier(numero):
    ferme = charger(numero)
    if not regles.peut_modifier(current_user, ferme):
        abort(403)
    provinces = Province.query.filter_by(actif=True).order_by(Province.ordre).all() \
        if a_profil(Profil.ADMIN) else [ferme.province]
    if request.method == 'GET':
        return render_template('fermes/formulaire.html',
                               **_contexte_formulaire(ferme, provinces, {}, []))

    d, erreurs, suggestions = _lire(request.form, ferme, provinces)
    if erreurs:
        return render_template('fermes/formulaire.html', **_contexte_formulaire(
            ferme, provinces, request.form, [e for e in erreurs if e], suggestions))
    if d['localite_nouvelle']:
        d['localite'] = regles.creer_localite(d['province'].id, d['localite_nouvelle'],
                                              par_admin=a_profil(Profil.ADMIN))
    if _position_changee(ferme, d):
        ferme.gps_date = maintenant() if d['latitude'] is not None else None
        ferme.gps_source = d['gps_source'] if d['latitude'] is not None else None
        ferme.gps_precision_m = d['gps_precision_m'] if d['latitude'] is not None else None
    ferme.latitude, ferme.longitude = d['latitude'], d['longitude']
    for champ in ('nom', 'exploitant_nom', 'exploitant_telephone', 'reference_ami', 'cohorte',
                  'observations'):
        setattr(ferme, champ, d[champ])
    ferme.telephone_normalise = regles.normaliser_telephone(ferme.exploitant_telephone)
    ferme.province, ferme.localite = d['province'], d['localite']
    if a_profil(Profil.ADMIN, Profil.DGE):
        ferme.agent_id = d['agent'].id if d.get('agent') else None
    regles.changer_statut(ferme, d['statut'], current_user)
    actuelles = {i.infrastructure for i in ferme.infrastructures}
    if set(d['infrastructures']) != actuelles:
        ferme.infrastructures = [FermeInfrastructure(infrastructure=i) for i in d['infrastructures']]
    db.session.commit()
    flash(f'Ferme {ferme.numero} enregistrée.', 'success')
    _avertir_position(ferme)
    return redirect(url_for('fermes.fiche', numero=ferme.numero))


# ── Bâtiments ───────────────────────────────────────────────────────────

def _capacite(texte):
    try:
        n = int((texte or '').strip())
    except ValueError:
        return None
    return n if n >= 0 else None


@fermes_bp.route('/<numero>/batiments/ajouter', methods=['POST'])
@profil_requis(*CREATEURS)
def ajouter_batiment(numero):
    ferme = charger(numero)
    if not regles.peut_modifier(current_user, ferme):
        abort(403)
    capacite = _capacite(request.form.get('capacite'))
    if capacite is None:
        flash('La capacité doit être un nombre de poulets (0 ou plus).', 'danger')
    else:
        b = regles.ajouter_batiment(ferme, capacite, request.form.get('nom', '').strip())
        db.session.commit()
        flash(f'Bâtiment {b.code} ajouté.', 'success')
    return redirect(url_for('fermes.fiche', numero=numero) + '#batiments')


@fermes_bp.route('/<numero>/batiments/<int:batiment_id>/modifier', methods=['POST'])
@profil_requis(*CREATEURS)
def modifier_batiment(numero, batiment_id):
    ferme = charger(numero)
    if not regles.peut_modifier(current_user, ferme):
        abort(403)
    b = Batiment.query.filter_by(id=batiment_id, ferme_id=ferme.id).first_or_404()
    capacite = _capacite(request.form.get('capacite'))
    if capacite is None:
        flash('La capacité doit être un nombre de poulets (0 ou plus).', 'danger')
    else:
        b.nom = request.form.get('nom', '').strip() or None
        b.capacite = capacite
        b.actif = request.form.get('actif') == 'on'
        db.session.commit()
        flash(f'Bâtiment {b.code} enregistré.', 'success')
    return redirect(url_for('fermes.fiche', numero=numero) + '#batiments')


# ── Import de la liste POUFA (ADMIN) ────────────────────────────────────

@fermes_bp.route('/import')
@profil_requis(Profil.ADMIN)
def import_page():
    return render_template('fermes/import.html', resultats=None)


@fermes_bp.route('/import/modele.xlsx')
@profil_requis(Profil.ADMIN)
def import_modele():
    return Response(import_poufa.modele(), mimetype=XLSX,
                    headers={'Content-Disposition': 'attachment; filename=modele_fermes_poufa.xlsx'})


def _resume(resultats):
    return {'total': len(resultats), 'ok': sum(r['ok'] for r in resultats),
            'refusees': sum(not r['ok'] for r in resultats),
            'nouvelles': len({r['v']['localite_nouvelle'] for r in resultats
                              if r['ok'] and r['v'].get('localite_nouvelle')})}


@fermes_bp.route('/import/verifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def import_verifier():
    fichier = request.files.get('fichier')
    contenu = fichier.read() if fichier else b''
    if not contenu:
        flash('Choisissez le fichier Excel à vérifier.', 'danger')
        return redirect(url_for('fermes.import_page'))
    try:
        lignes = import_poufa.lire(contenu)
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('fermes.import_page'))
    jeton = import_poufa.nouveau_jeton()
    import_poufa.ecrire(import_poufa.chemin(jeton, '.xlsx'), contenu)
    session['import_poufa'] = jeton
    resultats = import_poufa.verifier(lignes)
    return render_template('fermes/import.html', resultats=resultats, resume=_resume(resultats))


@fermes_bp.route('/import/importer', methods=['POST'])
@profil_requis(Profil.ADMIN)
def import_importer():
    jeton = session.pop('import_poufa', None)
    try:
        source = import_poufa.chemin(jeton, '.xlsx')
        with open(source, 'rb') as f:
            contenu = f.read()
    except (ValueError, OSError, TypeError):
        flash('Le fichier vérifié n\'est plus disponible : vérifiez-le de nouveau.', 'warning')
        return redirect(url_for('fermes.import_page'))
    # On revérifie : des fermes ont pu être créées entre l'aperçu et l'import
    resultats = import_poufa.verifier(import_poufa.lire(contenu))
    creees, localites = import_poufa.importer(resultats, current_user)
    refusees = sum(not r['ok'] for r in resultats)
    enregistrer(Action.IMPORT, table='ferme',
                detail=f'Import de la liste POUFA : {creees} ferme(s) créée(s), {refusees} ligne(s) '
                       f'refusée(s), {localites} localité(s) créée(s).')
    db.session.commit()
    os.remove(source)
    import_poufa.ecrire(import_poufa.chemin(jeton, '_rapport.xlsx'), import_poufa.rapport(resultats))
    flash(f'{creees} ferme(s) importée(s), {refusees} ligne(s) refusée(s).', 'success')
    return render_template('fermes/import_termine.html', creees=creees, refusees=refusees,
                           localites=localites, jeton=jeton)


@fermes_bp.route('/import/rapport/<jeton>.xlsx')
@profil_requis(Profil.ADMIN)
def import_rapport(jeton):
    try:
        with open(import_poufa.chemin(jeton, '_rapport.xlsx'), 'rb') as f:
            contenu = f.read()
    except (ValueError, OSError):
        abort(404)
    return Response(contenu, mimetype=XLSX,
                    headers={'Content-Disposition': 'attachment; filename=rapport_import_poufa.xlsx'})
