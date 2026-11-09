"""Hors connexion : service worker, jeton d'envoi, saisies à vérifier par l'agent."""
import os

from flask import Blueprint, render_template, jsonify, redirect, url_for, flash, make_response, current_app, request
from flask_login import current_user
from flask_wtf.csrf import generate_csrf

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.hors_ligne import ConflitHorsLigne
from app.utils import statiques
from app.utils.permissions import profil_requis, filtre_perimetre

hors_ligne_bp = Blueprint('hors_ligne', __name__)


# Fichiers gardés dès l'installation (adresses versionnées par url_for : ?v=<empreinte>)
A_GARDER = ['css/perform.css', 'css/eleveur.css', 'polices/polices.css',
            'vendor/bootstrap-5.3.3/css/bootstrap.min.css', 'vendor/bootstrap-icons-1.11.3/bootstrap-icons.min.css',
            'vendor/bootstrap-5.3.3/js/bootstrap.bundle.min.js', 'js/compteurs.js', 'js/hors_ligne.js',
            'js/eleveur.js', 'manifest.webmanifest', 'icones/icone-192.png',
            'polices/nunito-latin-400-normal.woff2', 'polices/nunito-latin-600-normal.woff2',
            'polices/nunito-latin-700-normal.woff2', 'polices/nunito-latin-800-normal.woff2',
            'polices/space-grotesk-latin-400-normal.woff2', 'polices/space-grotesk-latin-500-normal.woff2',
            'polices/space-grotesk-latin-600-normal.woff2', 'polices/space-grotesk-latin-700-normal.woff2',
            'polices/jetbrains-mono-latin-700-normal.woff2']
# Police d'icônes appelée par bootstrap-icons.min.css avec sa propre empreinte
POLICE_ICONES = '/static/vendor/bootstrap-icons-1.11.3/fonts/bootstrap-icons.woff2?dd67030699838ea613ee6dbda90effa6'


def version():
    """Empreinte de l'application (fichiers statiques et gabarits) : nomme les caches."""
    return statiques.version_application(current_app.static_folder,
                                         os.path.join(current_app.root_path, current_app.template_folder))


@hors_ligne_bp.route('/sw.js')
def service_worker():
    """Servi à la racine pour couvrir tout le site ; jamais gardé en cache par le navigateur."""
    a_garder = [url_for('static', filename=f) for f in A_GARDER] + [POLICE_ICONES]
    r = make_response(render_template('sw.js', version=version(), a_garder=a_garder))
    r.mimetype = 'application/javascript'
    r.headers['Service-Worker-Allowed'] = '/'
    r.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return r


@hors_ligne_bp.route('/hors-ligne/ping')
def ping():
    return '', 204


@hors_ligne_bp.route('/hors-ligne/jeton')
def jeton():
    """Jeton de formulaire frais pour envoyer les saisies gardées sur le téléphone."""
    if not current_user.is_authenticated:
        return jsonify(etat='connexion'), 401
    return jsonify(etat='ok', jeton=generate_csrf(), utilisateur=current_user.identifiant)


# Lot 13 : toutes les pages de l'éleveur sont gardées par le téléphone (service worker) à chaque
# ouverture de l'accueil avec du réseau. Une seule liste, vérifiée par tests/test_pages_hors_ligne.py.
PAGES_ELEVEUR = ['accueil.index', 'eleveur.saisie', 'eleveur.ma_bande', 'eleveur.soins', 'eleveur.produits',
                 'argent.mon_argent', 'argent.payer', 'eleveur.achat', 'eleveur.stock', 'livraisons.mes_livraisons',
                 'bandes.mes_bandes', 'bandes.ouvrir', 'entretien.ecran', 'entretien.panne', 'eleveur.moi',
                 'eleveur.mon_compte', 'visites.mes_visites', 'sante.mes_declarations', 'eleveur.presentation',
                 'aides.liste', 'auth.mot_de_passe']
ALLER = ['peser', 'sortie', 'malade', 'traitement', 'vaccins']


def pages_agent(user):
    """Pages de saisie de l'agent pour ses fermes (lot 16, rendues hors ligne après relecture) : tournée,
    fiche, compte rendu (non planifié et visites prévues), biosécurité, nouvel éleveur, J'ai payé, entretien,
    puis pour chaque bande en cours : fiche, saisie du jour (et jour oublié), pesée, sortie, poulet malade, vaccin, traitement.
    Les décisions (trancher, valider, commander, compter) restent en ligne."""
    from app.models import Ferme, Bande, Livraison
    from app.models.bande import StatutBande
    from app.models.intrant import StatutLivraison
    from app.models.visite import Visite, StatutVisite
    pages = [url_for('accueil.index'), url_for('agent.tournee'), url_for('fermes.liste'), url_for('auth.mot_de_passe')]
    fermes = Ferme.query.filter_by(agent_id=user.id).order_by(Ferme.numero_metier).all()
    for f in fermes:
        n = f.numero
        pages += [url_for('fermes.fiche', numero=n), url_for('visites.compte_rendu', numero=n),
                  url_for('agent.biosecurite', numero=n), url_for('agent.nouvel_eleveur', numero=n),
                  url_for('argent.payer', ferme=n), url_for('entretien.ecran', ferme=n),
                  url_for('entretien.panne', ferme=n)]
    ids = [f.id for f in fermes]
    if ids:
        for v in Visite.query.filter(Visite.ferme_id.in_(ids), Visite.statut == StatutVisite.PREVUE):
            pages.append(url_for('visites.compte_rendu', numero=v.ferme.numero, visite=v.id))
        for b in Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS):
            n = b.numero
            pages += [url_for('bandes.fiche', numero=n), url_for('bandes.saisir', numero=n),
                      url_for('bandes.oublie', numero=n), url_for('bandes.pesee', numero=n),
                      url_for('bandes.sortie', numero=n), url_for('sante.declarer', bande=n),
                      url_for('sante.vacciner', numero=n), url_for('sante.traiter', numero=n)]
        for liv in Livraison.query.filter(Livraison.ferme_id.in_(ids), Livraison.statut == StatutLivraison.A_CONFIRMER):
            pages.append(url_for('livraisons.recu_moins', numero=liv.numero))
    return list(dict.fromkeys(pages))


def pages_a_garder(user):
    """Adresses des pages de l'éleveur : fixes, puis celles de ses bandes, livraisons et aides."""
    if user.profil == Profil.AGENT:
        return pages_agent(user)
    from app.models import Livraison
    from app.models.aide import Aide
    from app.models.intrant import StatutLivraison
    from app.routes.eleveur import bandes_en_cours
    from app.services import bceg
    pages = [url_for(e) for e in PAGES_ELEVEUR] + [url_for('eleveur.aller', quoi=q) for q in ALLER]
    if bceg.fermes_du_responsable(user):
        pages.append(url_for('eleveur.ma_banque'))
    for b in bandes_en_cours():
        pages += [url_for('bandes.pesee', numero=b.numero), url_for('bandes.sortie', numero=b.numero),
                  url_for('sante.declarer', bande=b.numero), url_for('sante.traiter', numero=b.numero),
                  url_for('bandes.oublie', numero=b.numero)]
    for liv in filtre_perimetre(Livraison.query).filter(Livraison.statut == StatutLivraison.A_CONFIRMER):
        pages.append(url_for('livraisons.recu_moins', numero=liv.numero))
    pages += [url_for('aides.aide', cle=a.cle) for a in Aide.query.filter_by(actif=True)]
    return list(dict.fromkeys(pages))


@hors_ligne_bp.route('/hors-ligne/pages')
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def pages():
    return jsonify(pages=pages_a_garder(current_user))


VERIFICATEURS = (Profil.AGENT, Profil.DGE, Profil.ADMIN)


def conflits_a_voir(user):
    """Refus à marquer « vus » et versions à trancher (lot 12)."""
    from sqlalchemy import or_, and_
    from app.models.hors_ligne import GenreVerification as G, StatutVerification as SV
    return (filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)
            .filter(or_(and_(ConflitHorsLigne.genre == G.MESSAGE, ConflitHorsLigne.vu_le.is_(None)),
                        and_(ConflitHorsLigne.genre != G.MESSAGE, ConflitHorsLigne.statut == SV.A_VERIFIER))))


@hors_ligne_bp.route('/hors-ligne/a-verifier')
@profil_requis(*VERIFICATEURS)
def conflits():
    from app.models.hors_ligne import GenreVerification as G
    from app.services import verifications
    tous = filtre_perimetre(ConflitHorsLigne.query)
    par_province, province = None, request.args.get('province', type=int)
    if current_user.profil in (Profil.DGE, Profil.ADMIN):     # lot 18 : arbitrages au niveau national
        from app.services import dge
        par_province = dge.arbitrages_par_province(current_user)
        if province:
            tous = tous.filter(ConflitHorsLigne.ferme.has(province_id=province))
    a_trancher = (verifications.a_trancher(tous).order_by(ConflitHorsLigne.cree_le).all())
    from sqlalchemy import or_
    from app.models.hors_ligne import StatutVerification as SV
    autres = (tous.filter(or_(ConflitHorsLigne.statut.is_(None), ConflitHorsLigne.statut != SV.A_VERIFIER))
              .order_by(ConflitHorsLigne.cree_le.desc()).limit(100).all())
    return render_template('hors_ligne/conflits.html', a_trancher=a_trancher, conflits=autres, G=G,
                           par_province=par_province, province=province,
                           en_retard=verifications.en_retard, choix_sortie=verifications.CHOIX_SORTIE)


@hors_ligne_bp.route('/hors-ligne/a-verifier/<int:ident>/trancher', methods=['POST'])
@profil_requis(*VERIFICATEURS)
def trancher(ident):
    from app.services import verifications
    c = filtre_perimetre(ConflitHorsLigne.query.filter_by(id=ident)).first_or_404()
    try:
        verifications.trancher(c, request.form.get('choix'), request.form.get('motif', ''), current_user)
        db.session.commit()
        flash('Décision enregistrée (inscrite au journal) : les chiffres sont recalculés.', 'success')
    except verifications.RegleVerification as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('hors_ligne.conflits') + f'#verif-{ident}')


@hors_ligne_bp.route('/hors-ligne/a-verifier/<int:ident>/vu', methods=['POST'])
@profil_requis(*VERIFICATEURS)
def vu(ident):
    c = filtre_perimetre(ConflitHorsLigne.query.filter_by(id=ident)).first_or_404()
    if c.vu_le is None:
        c.vu_le, c.vu_par = maintenant(), current_user.id
        db.session.commit()
        flash('Marqué comme vu.', 'success')
    return redirect(url_for('hors_ligne.conflits'))
