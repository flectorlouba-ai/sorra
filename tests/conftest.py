import os

import pytest
from freezegun import freeze_time

os.environ['YL2_ENV'] = 'testing'

# Horloge des tests : date fixe, à midi, qui avance normalement (tick). Démarrée avant
# l'import des fichiers de test, pour que leurs « aujourd'hui » (AUJ…) soient cette
# date-là : aucun test ne dépend du jour ni de l'heure où la suite est lancée, et la
# suite ne peut pas passer minuit en cours de route.
JOUR_DES_TESTS = os.environ.get('YL2_JOUR_DES_TESTS', '2026-06-15 12:00:00')
_horloge = freeze_time(JOUR_DES_TESTS, tick=True)
_horloge.start()

from app import create_app, db  # noqa: E402
from app.models import Utilisateur, Profil, Province, Localite, Parametre, ListeDeroulante  # noqa: E402
from app.models.referentiel import PROVINCES_GABON  # noqa: E402
from app.models.parametre import PARAMETRES_DEFAUT  # noqa: E402
from app.models.entretien import TacheEntretien  # noqa: E402
from app.models.aide import Aide  # noqa: E402

MDP = 'MotDePasse-2026'


def _taches_de_depart():
    """Liste de départ des tâches d'entretien, lue dans la migration du lot 10."""
    import importlib.util
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / 'migrations' / 'versions' / '0012_entretien.py'
    spec = importlib.util.spec_from_file_location('migration_0012', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.TACHES


def _aides_de_depart():
    """Aides « Comment faire ? » de départ, lues dans la migration du lot 13."""
    import importlib.util
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / 'migrations' / 'versions' / '0015_tutoriel_aides_compte_bceg.py'
    spec = importlib.util.spec_from_file_location('migration_0015', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    aides = list(module.AIDES)
    spec = importlib.util.spec_from_file_location('migration_0022', chemin.with_name('0022_espace_terrain.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return aides + list(module.AIDES)       # lot 19 ter : aides de l'agent et de l'opérateur


def _listes_de_depart():
    """Valeurs de départ des listes, lues dans la migration du lot 1 (mêmes valeurs qu'en base)."""
    import importlib.util
    from pathlib import Path
    chemin = Path(__file__).resolve().parent.parent / 'migrations' / 'versions' / '0003_fermes_et_operateurs.py'
    spec = importlib.util.spec_from_file_location('migration_0003', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes = dict(module.LISTES)
    chemin = chemin.with_name('0004_intrants.py')
    spec = importlib.util.spec_from_file_location('migration_0004', chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes['motifs_ecart'] = module.MOTIFS_ECART
    spec = importlib.util.spec_from_file_location('migration_0006', chemin.with_name('0006_sante.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    spec = importlib.util.spec_from_file_location('migration_0013', chemin.with_name('0013_argent.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes['categories_depenses'] = module.CATEGORIES_DEPENSES
    spec = importlib.util.spec_from_file_location('migration_0014',
                                                  chemin.with_name('0014_reponses_visites_verifications.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    spec = importlib.util.spec_from_file_location('migration_0017', chemin.with_name('0017_ecrans_agent.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    spec = importlib.util.spec_from_file_location('migration_0018', chemin.with_name('0018_ecrans_veterinaire.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    spec = importlib.util.spec_from_file_location('migration_0021', chemin.with_name('0021_reception_operateur.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    listes['types_operateurs'] = list(listes['types_operateurs']) + [module.TYPE_MARCHE]
    spec = importlib.util.spec_from_file_location('migration_0022', chemin.with_name('0022_espace_terrain.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    listes.update(module.LISTES)
    return listes


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
        for k, (nom, icone, frequence, portee, infra) in enumerate(_taches_de_depart()):
            db.session.add(TacheEntretien(nom=nom, icone=icone, frequence=frequence, portee=portee,
                                          infrastructure=infra, ordre=k))
        for i, (cle, groupe, titre, etapes) in enumerate(_aides_de_depart()):
            db.session.add(Aide(cle=cle, groupe=groupe, titre=titre, ordre=i,
                                etapes=[{'texte': t, 'capture': k} for t, k in etapes]))
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
    if profil in (Profil.ELEVEUR, Profil.AGENT, Profil.OPERATEUR):
        from app.models.base import maintenant
        u.presentation_vue_le = maintenant()     # tutoriel déjà vu (tests du tutoriel : remis à None ; lot 19 ter : agent, opérateur)
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
