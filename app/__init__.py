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
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

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

    app.register_blueprint(auth_bp,          url_prefix='/auth')
    app.register_blueprint(accueil_bp)
    # Administration
    app.register_blueprint(utilisateurs_bp,  url_prefix='/administration/utilisateurs')
    app.register_blueprint(referentiel_bp,   url_prefix='/administration/provinces')
    app.register_blueprint(listes_bp,        url_prefix='/administration/listes')
    app.register_blueprint(parametres_bp,    url_prefix='/administration/parametres')
    # Contrôle
    app.register_blueprint(journal_bp,       url_prefix='/journal')

    # ── CLI ──
    from app.commandes import init_kimba
    app.cli.add_command(init_kimba)

    # ── Globals et filtres Jinja2 ──
    from app.utils.permissions import a_profil
    from app.utils.dates import date_locale
    app.jinja_env.globals['a_profil'] = a_profil
    app.jinja_env.filters['date_locale'] = date_locale

    _installer_controles_session(app)
    _installer_erreurs(app)
    return app


def _installer_controles_session(app):
    from flask import request, session, redirect, url_for, flash
    from flask_login import current_user, logout_user
    from app.services import parametres
    from app.services.journal import enregistrer, Action

    libres = {'static', 'auth.connexion', 'auth.deconnexion', 'auth.mot_de_passe'}

    @app.before_request
    def controles_session():
        if request.endpoint in (None, 'static') or not current_user.is_authenticated:
            return None
        maintenant = time.time()
        derniere = session.get('derniere_activite')
        duree = parametres.obtenir('securite.duree_session_minutes', 60)
        if derniere and maintenant - derniere > duree * 60:
            enregistrer(Action.DECONNEXION, detail='Fin de session après inactivité')
            from app import db as _db
            _db.session.commit()
            logout_user()
            session.clear()
            flash('Votre session a expiré après une période d\'inactivité.', 'warning')
            return redirect(url_for('auth.connexion'))
        session['derniere_activite'] = maintenant
        if current_user.doit_changer_mdp and request.endpoint not in libres:
            return redirect(url_for('auth.mot_de_passe'))
        return None


def _installer_erreurs(app):
    from flask import render_template, redirect, request, url_for, flash
    from flask_wtf.csrf import CSRFError

    @app.errorhandler(CSRFError)
    def csrf_expire(e):
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
