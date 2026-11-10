import time

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import MetaData
from config import config

# Noms de contraintes stables : indispensable pour que les migrations
# produisent le même résultat sous SQLite et sous PostgreSQL.
NOMMAGE = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_N_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}

db = SQLAlchemy(metadata=MetaData(naming_convention=NOMMAGE))
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.connexion'
login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
login_manager.login_message_category = 'warning'


def create_app(env='default'):
    app = Flask(__name__)
    app.config.from_object(config[env])
    config[env].verifier()
    if app.config['DERRIERE_PROXY']:
        from app.utils.demo import ProxyDeConfiance
        app.wsgi_app = ProxyDeConfiance(app.wsgi_app)

    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app import models  # noqa: F401  (enregistre les tables)
    from app.services import journal
    journal.installer()

    # ── Blueprints ──
    from app.routes.auth import auth_bp
    from app.routes.accueil import accueil_bp
    from app.routes.utilisateurs import utilisateurs_bp
    from app.routes.referentiel import referentiel_bp
    from app.routes.listes import listes_bp
    from app.routes.parametres import parametres_bp
    from app.routes.journal import journal_bp
    from app.routes.fermes import fermes_bp
    from app.routes.operateurs import operateurs_bp
    from app.routes.livraisons import livraisons_bp
    from app.routes.catalogue import catalogue_bp
    from app.routes.bandes import bandes_bp
    from app.routes.sante import sante_bp
    from app.routes.pilotage import pilotage_bp
    from app.routes.tracabilite import tracabilite_bp, public_bp
    from app.routes.hors_ligne import hors_ligne_bp
    from app.routes.eleveur import eleveur_bp
    from app.routes.entretien import entretien_bp
    from app.routes.argent import argent_bp
    from app.routes.visites import visites_bp
    from app.routes.aides import aides_bp
    from app.routes.controle import controle_bp
    from app.routes.agent import agent_bp
    from app.routes.veto import veto_bp
    from app.routes.dge import dge_bp

    app.register_blueprint(auth_bp,          url_prefix='/auth')
    app.register_blueprint(accueil_bp)
    # Administration
    app.register_blueprint(utilisateurs_bp,  url_prefix='/administration/utilisateurs')
    app.register_blueprint(referentiel_bp,   url_prefix='/administration/provinces')
    app.register_blueprint(listes_bp,        url_prefix='/administration/listes')
    app.register_blueprint(parametres_bp,    url_prefix='/administration/parametres')
    app.register_blueprint(catalogue_bp,     url_prefix='/administration/catalogue')
    # Métier
    app.register_blueprint(fermes_bp,        url_prefix='/fermes')
    app.register_blueprint(operateurs_bp,    url_prefix='/operateurs')
    app.register_blueprint(livraisons_bp,    url_prefix='/livraisons')
    app.register_blueprint(bandes_bp,        url_prefix='/bandes')
    app.register_blueprint(sante_bp,         url_prefix='/sante')
    app.register_blueprint(pilotage_bp,      url_prefix='/pilotage')
    app.register_blueprint(tracabilite_bp,   url_prefix='/tracabilite')
    # Page publique du QR code (sans connexion)
    app.register_blueprint(public_bp)
    # Hors connexion (service worker à la racine, envois après coup)
    app.register_blueprint(hors_ligne_bp)
    # Espace de l'éleveur : accueil en tuiles, saisie du jour, achats, stock (lot 9)
    app.register_blueprint(eleveur_bp)
    # Entretien simple des installations (lot 10)
    app.register_blueprint(entretien_bp)
    app.register_blueprint(argent_bp)
    app.register_blueprint(visites_bp)
    app.register_blueprint(aides_bp)
    app.register_blueprint(controle_bp)
    app.register_blueprint(agent_bp)
    app.register_blueprint(veto_bp)
    app.register_blueprint(dge_bp)
    # Opérateur (abattoir, marché) : scan et réception des lots (lot 19)
    from app.routes.operateur import operateur_bp
    app.register_blueprint(operateur_bp)
    # Espace terrain de l'agent et de l'opérateur (lot 19 ter)
    from app.routes.terrain import terrain_bp
    app.register_blueprint(terrain_bp)
    # Fiches modifiables et archivage (lot A1)
    from app.routes.fiches import fiches_bp
    app.register_blueprint(fiches_bp)
    # Indicateurs : 5 niveaux, « Mes indicateurs » par profil (lot C)
    from app.routes.indicateurs import indicateurs_bp
    app.register_blueprint(indicateurs_bp)
    # Version ordinateur, tous profils (lot R)
    from app.routes.bureau import bureau_bp
    app.register_blueprint(bureau_bp)
    # Plans d'actions et rapports standards (lot D)
    from app.routes.actions import actions_bp
    app.register_blueprint(actions_bp)
    from app.routes.notifications import notifications_bp   # lot T
    app.register_blueprint(notifications_bp)
    # Contrôle
    app.register_blueprint(journal_bp,       url_prefix='/journal')

    # ── CLI ──
    from app.commandes import init_performyl2, rapports_mensuels, demo_exporter, demo_charger, notifications_envoyer
    app.cli.add_command(init_performyl2)
    app.cli.add_command(rapports_mensuels)
    app.cli.add_command(demo_exporter)
    app.cli.add_command(demo_charger)
    app.cli.add_command(notifications_envoyer)

    # ── Globals et filtres Jinja2 ──
    from app.utils.permissions import a_profil
    from app.utils.dates import date_locale
    from app.utils.nombres import quantite
    app.jinja_env.globals['a_profil'] = a_profil
    from app.utils.logo import svg as logo_poulet, poulet
    app.jinja_env.globals['logo_poulet'] = logo_poulet
    app.jinja_env.globals['poulet'] = poulet
    from app.services.fiches import infos as fiches_infos, nombre_archivees
    from app.services.bureau import fonctions_pour as _fonctions_bureau
    from app.routes.accueil import perimetre as _perimetre
    app.jinja_env.globals['fonctions_bureau'] = lambda: _fonctions_bureau(_utilisateur)
    app.jinja_env.globals['perimetre_bureau'] = lambda: _perimetre(_utilisateur)
    from flask_login import current_user as _utilisateur
    app.jinja_env.globals['fiches_infos'] = lambda objets: fiches_infos(objets, _utilisateur)
    app.jinja_env.globals['nombre_archivees'] = nombre_archivees
    app.jinja_env.filters['date_locale'] = date_locale
    app.jinja_env.filters['qte'] = quantite

    from datetime import date as _date

    @app.context_processor
    def _aujourdhui():
        return {'today': _date.today(), 'demo': bool(app.config.get('DEMO'))}

    @app.context_processor
    def _theme():
        # Deux styles (lot 19 ter) : TERRAIN (terrain.css, charte « illustrée douce ») pour l'éleveur, l'agent et
        # l'opérateur ; BUREAU (perform.css seul) pour les autres, et pour l'agent qui a choisi « Version bureau ».
        # `theme_eleveur` reste vrai pour l'éleveur seul : ses mots, ses fêtes, eleveur.js.
        from flask_login import current_user
        from app.models import Profil
        from app.utils import terrain
        eleveur = bool(current_user and current_user.is_authenticated and current_user.profil == Profil.ELEVEUR)
        profil_terrain = terrain.profil_terrain(current_user)

        def bandes_eleveur():
            # Pastilles « autres bâtiments » sur Peser, Sortie, Poulet malade (calculées à la demande)
            from app.routes.eleveur import bandes_en_cours
            return bandes_en_cours() if eleveur else []
        def agent_eleveur():
            # En-tête de l'éleveur (lot 11) : son agent, s'il a un téléphone
            from app.routes.eleveur import _fermes
            return next((f.agent for f in _fermes() if f.agent and f.agent.telephone), None) if eleveur else None
        def visites_nouvelles():
            # Pastille « nouveau » sur 👤 Moi (lot 12) : compte rendu de visite pas encore ouvert
            from app.routes.eleveur import _fermes
            from app.services import visites
            return visites.nouvelles([f.id for f in _fermes()]) if eleveur else 0
        def moi_nouveau():
            # Pastille « nouveau » sur 👤 Moi : compte rendu de visite non lu, ou « Ma banque » sans réponse
            from app.services import bceg
            return eleveur and bool(visites_nouvelles() or bceg.a_repondre(current_user))

        def aide_pour(cle):
            # Bouton « ? » (lot 13, étendu au lot 19 ter) : l'aide de cet écran pour ce profil terrain, si elle
            # est active ; '' sinon. L'éleveur garde ses clés ; l'agent et l'opérateur ont les leurs (ag_, op_).
            return terrain.aide_pour(profil_terrain, cle)

        def aide_active(cle):
            return bool(aide_pour(cle))

        def cloche_agent():
            from app.routes.terrain import cloche
            return cloche(current_user) if profil_terrain == 'agent' else 0
        return {'theme_eleveur': eleveur, 'theme_terrain': bool(profil_terrain), 'profil_terrain': profil_terrain,
                'entete_terrain': lambda: terrain.entete(current_user, profil_terrain),
                'bandes_eleveur': bandes_eleveur, 'agent_eleveur': agent_eleveur,
                'visites_nouvelles': visites_nouvelles, 'moi_nouveau': moi_nouveau, 'aide_active': aide_active,
                'aide_pour': aide_pour, 'cloche_agent': cloche_agent}

    # Lot A : saisies archivées masquées de toutes les requêtes (app/models/base.py)
    from sqlalchemy.orm import Session
    from app.models.base import installer_masquage
    installer_masquage(Session)
    _installer_controles_session(app)
    _installer_erreurs(app)
    from app.services import hors_ligne
    hors_ligne.installer(app)
    from app.utils import statiques
    statiques.installer(app)
    return app


def _installer_controles_session(app):
    from flask import request, session, redirect, url_for, flash
    from flask_login import current_user, logout_user
    from app.services import parametres
    from app.services.journal import enregistrer, Action

    libres = {'static', 'auth.connexion', 'auth.deconnexion', 'auth.mot_de_passe', 'auth.mise_en_place',
              'auth.codes_secours', 'auth.deux_facteurs'}

    @app.before_request
    def controles_session():
        if request.endpoint in (None, 'static') or not current_user.is_authenticated:
            return None
        maintenant = time.time()
        from app.services import securite
        from app.models.securite import SessionUtilisateur
        from app import db as _db
        sid = session.get('sid')
        enregistree = _db.session.get(SessionUtilisateur, sid) if sid else None
        if enregistree is not None and enregistree.fermee_le is not None:
            # Lot 15 : session fermée par l'ADMIN (ou depuis un autre appareil)
            logout_user()
            session.clear()
            flash('Votre session a été fermée. Reconnectez-vous.', 'warning')
            return redirect(url_for('auth.connexion'))
        derniere = session.get('derniere_activite')
        duree = parametres.obtenir('securite.duree_session_minutes', 30)
        # Lot 15 : 30 min d'inactivité pour le pilotage ; jamais pour l'éleveur ni l'agent
        if derniere and securite.expire_par_inactivite(current_user) and maintenant - derniere > duree * 60:
            securite.fermer(sid, None, 'Inactivité')
            enregistrer(Action.DECONNEXION, detail='Fin de session après inactivité')
            from app import db as _db
            _db.session.commit()
            logout_user()
            session.clear()
            flash('Votre session a expiré après une période d\'inactivité.', 'warning')
            return redirect(url_for('auth.connexion'))
        if enregistree is not None and (not derniere or maintenant - derniere > 60):
            from app.models.base import maintenant as _maintenant
            enregistree.derniere_activite = _maintenant()
            _db.session.commit()
        session['derniere_activite'] = maintenant
        if current_user.doit_changer_mdp and request.endpoint not in libres and not app.config.get('DEMO'):
            return redirect(url_for('auth.mot_de_passe'))
        return None


def _installer_erreurs(app):
    from flask import render_template, redirect, request, url_for, flash
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_expire(e):
        if 'X-Hors-Ligne-Id' in request.headers:
            from flask import jsonify
            return jsonify(etat='connexion')
        if request.endpoint == 'auth.connexion' or not request.referrer:
            return render_template(
                'auth/connexion.html',
                erreur='Votre session a expiré. Merci de ressaisir vos identifiants.'
            ), 400
        flash('Votre session a expiré, la page a été rechargée. '
              'Merci de refaire votre saisie.', 'warning')
        return redirect(request.referrer or url_for('accueil.index'))

    @app.errorhandler(403)
    def interdit(e):
        return render_template('erreurs/erreur.html', code=403,
                               message="Vous n'avez pas accès à cette page."), 403

    @app.errorhandler(404)
    def introuvable(e):
        return render_template('erreurs/erreur.html', code=404,
                               message='Cette page n\'existe pas.'), 404
