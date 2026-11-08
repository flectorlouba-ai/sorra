import os

import pytest

os.environ['YL2_ENV'] = 'testing'

from app import create_app, db  # noqa: E402
from app.models import Utilisateur, Profil, Province, Localite, Parametre, ListeDeroulante  # noqa: E402
from app.models.referentiel import PROVINCES_GABON  # noqa: E402
from app.models.parametre import PARAMETRES_DEFAUT  # noqa: E402

MDP = 'MotDePasse-2026'


def _listes_de_depart():
    """Valeurs de départ des listes, lues dans la migration du lot 1 (mêmes valeurs qu'en base)."""
    import importlib.util
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / 'migrations' / 'versions' / '0003_fermes_et_operateurs.py'
    spec = importlib.util.spec_from_file_location('migration_0003', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.LISTES


@pytest.fixture
def app(tmp_path):
    app = create_app('testing')
    app.instance_path = str(tmp_path)   # fichiers d'import : jamais dans le dossier du projet
    with app.app_context():
        db.create_all()
        for i, (code, nom) in enumerate(PROVINCES_GABON, start=1):
            db.session.add(Province(code=code, nom=nom, ordre=i))
        for cle, valeur, type_, description in PARAMETRES_DEFAUT:
            db.session.add(Parametre(cle=cle, valeur=valeur, type=type_, description=description))
        for categorie, valeurs in _listes_de_depart().items():
            for i, v in enumerate(valeurs):
                db.session.add(ListeDeroulante(categorie=categorie, valeur=v, ordre=i))
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


def creer_ferme(nom, code_province, localite, agent=None, telephone=None, **champs):
    """Ferme de test, créée comme par l'écran (numéro, historique du statut)."""
    from app.services import fermes as regles
    p = province(code_province)
    loc = Localite.query.filter_by(province_id=p.id, nom=localite).first() \
        or Localite(province=p, nom=localite)
    db.session.add(loc)
    f = regles.creer_ferme(p, None, nom=nom, exploitant_nom=f'Exploitant {nom}',
                           exploitant_telephone=telephone or f'07{abs(hash(nom)) % 10**6:06d}',
                           localite=loc, agent_id=agent.id if agent else None, **champs)
    db.session.commit()
    return f
