import os

import pytest

os.environ['KIMBA_ENV'] = 'testing'

from app import create_app, db  # noqa: E402
from app.models import Utilisateur, Profil, Province, Localite, Parametre  # noqa: E402
from app.models.referentiel import PROVINCES_GABON  # noqa: E402
from app.models.parametre import PARAMETRES_DEFAUT  # noqa: E402

MDP = 'MotDePasse-2026'


@pytest.fixture
def app():
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        for i, (code, nom) in enumerate(PROVINCES_GABON, start=1):
            db.session.add(Province(code=code, nom=nom, ordre=i))
        for cle, valeur, type_, description in PARAMETRES_DEFAUT:
            db.session.add(Parametre(cle=cle, valeur=valeur, type=type_, description=description))
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def province(code):
    return Province.query.filter_by(code=code).one()


def creer_utilisateur(identifiant, profil, provinces=(), doit_changer=False, actif=True):
    u = Utilisateur(identifiant=identifiant, nom=identifiant.capitalize(), profil=profil,
                    actif=actif, doit_changer_mdp=doit_changer,
                    provinces=[province(c) for c in provinces])
    u.set_password(MDP)
    db.session.add(u)
    db.session.commit()
    return u


def connecter(client, identifiant, mdp=MDP):
    return client.post('/auth/connexion', data={'identifiant': identifiant, 'mot_de_passe': mdp})


@pytest.fixture
def admin(app):
    return creer_utilisateur('admin', Profil.ADMIN)


@pytest.fixture
def client_admin(client, admin):
    connecter(client, 'admin')
    return client


@pytest.fixture
def localites(app):
    """Deux localités dans l'Estuaire, une dans le Haut-Ogooué."""
    for code, nom in (('EST', 'Libreville'), ('EST', 'Ntoum'), ('HOG', 'Franceville')):
        db.session.add(Localite(province=province(code), nom=nom))
    db.session.commit()
