import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def _oui(nom, defaut='0'):
    return os.environ.get(nom, defaut).strip().lower() in ('1', 'true', 'oui', 'yes')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'performyl2-dev-cle-a-changer')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f'sqlite:///{os.path.join(BASE_DIR, "performyl2_dev.db")}')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    # Jeton valable le temps de la session (repris de YL.1) : évite le
    # « CSRF token has expired » sur un onglet resté ouvert.
    WTF_CSRF_TIME_LIMIT = None

    # Cookies de session. SECURE seulement derrière HTTPS : en HTTP simple
    # (cas actuel, port 5021 sans HTTPS) le navigateur ne renverrait plus le cookie.
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = _oui('COOKIE_SECURE')
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Derrière nginx : lire la vraie adresse du visiteur (X-Forwarded-For) pour
    # le journal. Ne l'activer que si l'application n'est joignable que par nginx.
    DERRIERE_PROXY = _oui('DERRIERE_PROXY')

    JOURNAL_PAR_PAGE = 50

    @classmethod
    def verifier(cls):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False

    @classmethod
    def verifier(cls):
        manquantes = [n for n in ('SECRET_KEY', 'DATABASE_URL') if not os.environ.get(n)]
        if manquantes:
            raise RuntimeError('Variables manquantes dans le .env : ' + ', '.join(manquantes))


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    TEMP_DIR = tempfile.gettempdir()


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
