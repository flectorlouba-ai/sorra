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
    # Lot 15 : double authentification (TOTP). Coupée par défaut en développement et en test ;
    # active par défaut en production ; YL2_2FA=0 pour la démo locale SEULEMENT.
    DEUX_FACTEURS = _oui('YL2_2FA', '0')
    # Démonstration publique (sorra.performyl.com) : données fictives, mot de passe connu de tous.
    # Bandeau sur toutes les pages, comptes protégés, verrouillage par compte + adresse IP.
    DEMO = _oui('YL2_DEMO', '0')
    # Lot L : encadré « Comptes de démonstration » sur la page de connexion (un clic remplit identifiant et mot de
    # passe). Absent = faux : sans ce réglage, aucun identifiant ni mot de passe n'apparaît dans la page.
    DEMO_COMPTES = _oui('SORRA_DEMO_COMPTES', '0')
    DEMO_MOT_DE_PASSE = os.environ.get('SORRA_DEMO_MDP', 'Demo-yl2-2026')   # mot de passe PUBLIC des comptes fictifs
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024   # fichier d'import POUFA

    @classmethod
    def verifier(cls):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    DEUX_FACTEURS = _oui('YL2_2FA', '1')

    @classmethod
    def verifier(cls):
        manquantes = [n for n in ('SECRET_KEY', 'DATABASE_URL') if not os.environ.get(n)]
        if manquantes:
            raise RuntimeError('Variables manquantes dans le .env : ' + ', '.join(manquantes))


class TestingConfig(Config):
    TESTING = True
    ACCUEIL_MEMOIRE_SECONDES = 0          # pas de mémoire des accueils : chaque test voit ses données tout de suite
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('TEST_DATABASE_URL', 'sqlite:///:memory:')
    TEMP_DIR = tempfile.gettempdir()


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'testing':     TestingConfig,
    'default':     DevelopmentConfig,
}
