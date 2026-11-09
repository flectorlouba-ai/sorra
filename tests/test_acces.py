import pytest

from app.models import Profil, Localite, Province, Utilisateur
from app.utils.permissions import filtre_perimetre
from tests.conftest import creer_utilisateur, connecter

PAGES_ADMIN = ['/administration/utilisateurs/', '/administration/provinces/',
               '/administration/listes/', '/administration/parametres/']


@pytest.mark.parametrize('profil', [p for p in Profil if p != Profil.ADMIN])
def test_administration_refusee_aux_autres_profils(client, app, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    for page in PAGES_ADMIN:
        assert client.get(page).status_code == 403, (profil, page)


@pytest.mark.parametrize('profil,code', [(Profil.ADMIN, 200), (Profil.AUDITEUR, 200),
                                         (Profil.DGE, 403), (Profil.AGENT, 403)])
def test_journal_admin_et_auditeur(client, app, profil, code):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/journal/').status_code == code
    assert client.get('/journal/export.csv').status_code == code


def test_pages_protegees_sans_connexion(client, app):
    for page in PAGES_ADMIN + ['/', '/journal/']:
        r = client.get(page)
        assert r.status_code == 302 and '/auth/connexion' in r.location


def test_accueil_sans_tuile_inutile(client, app):
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    connecter(client, 'agent')
    page = client.get('/').get_data(as_text=True)
    assert 'Administration' not in page and 'Journal' not in page
    creer_utilisateur('aninf', Profil.AUDITEUR, ['EST'])
    client.post('/auth/deconnexion')
    connecter(client, 'aninf')
    page = client.get('/').get_data(as_text=True)
    assert 'data-tuile-pilotage="journal"' in page and 'Utilisateurs' not in page      # lot 15 : tuiles


def test_aucune_route_ne_modifie_le_journal(app):
    for regle in app.url_map.iter_rules():
        if regle.rule.startswith('/journal'):
            assert regle.methods <= {'GET', 'HEAD', 'OPTIONS'}, regle


# ── Cloisonnement par province ──────────────────────────────────────────

def test_filtre_perimetre_requetes(app, localites):
    u = creer_utilisateur('veto', Profil.VETO, ['HOG', 'WNT'])
    noms = [l.nom for l in filtre_perimetre(Localite.query, utilisateur=u).all()]
    assert noms == ['Franceville']
    codes = sorted(p.code for p in filtre_perimetre(Province.query, utilisateur=u).all())
    assert codes == ['HOG', 'WNT']
    from sqlalchemy import select
    from app import db
    res = db.session.execute(filtre_perimetre(select(Localite), utilisateur=u)).scalars().all()
    assert [l.nom for l in res] == ['Franceville']


def test_sans_province_ne_voit_rien(app, localites):
    u = creer_utilisateur('isole', Profil.BCEG)
    assert filtre_perimetre(Localite.query, utilisateur=u).count() == 0


def test_modele_sans_perimetre_refuse(app):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    with pytest.raises(TypeError):
        filtre_perimetre(Utilisateur.query, utilisateur=u)
