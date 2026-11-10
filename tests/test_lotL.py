"""Lot L — comptes de démonstration en un clic sur la page de connexion : présents seulement avec le réglage
SORRA_DEMO_COMPTES (et la démo), absents sinon (aucun mot de passe dans la page) ; comptes lus en base, jamais
inventés ; connexion réussie pour chacun ; protections de la démo inchangées."""
import pytest

from app.models import Profil, Utilisateur
from tests.conftest import creer_utilisateur, MDP


@pytest.fixture
def comptes(app):
    app.config['DEMO'], app.config['DEMO_COMPTES'], app.config['DEMO_MOT_DE_PASSE'] = True, True, MDP
    creer_utilisateur('dge', Profil.DGE)
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    creer_utilisateur('agent.est', Profil.AGENT, ['EST'])
    creer_utilisateur('eleveur', Profil.ELEVEUR)
    creer_utilisateur('aninf', Profil.AUDITEUR)
    creer_utilisateur('ancien', Profil.AGENT, ['EST'], actif=False)
    yield app
    app.config['DEMO'] = app.config['DEMO_COMPTES'] = False


def test_encadre_present_avec_le_reglage(client, comptes):
    page = client.get('/auth/connexion').get_data(as_text=True)
    assert 'Comptes de démonstration' in page and f'data-mdp="{MDP}"' in page
    assert '>Pilotage<' in page and '>Terrain<' in page
    assert 'data-identifiant="dge"' in page and 'DGE (POUFA)' in page and 'Auditeur ANINF' in page
    assert 'data-identifiant="agent.est"' in page and 'data-identifiant="eleveur"' in page
    assert 'data-identifiant="ancien"' not in page                           # compte archivé : pas listé
    assert page.index('data-identifiant="dge"') < page.index('data-identifiant="eleveur"')   # pilotage avant terrain


def test_absent_sans_le_reglage_et_aucun_mot_de_passe(client, comptes):
    comptes.config['DEMO_COMPTES'] = False
    page = client.get('/auth/connexion').get_data(as_text=True)
    assert 'Comptes de démonstration' not in page and MDP not in page and 'data-identifiant' not in page
    comptes.config['DEMO_COMPTES'], comptes.config['DEMO'] = True, False     # le réglage seul ne suffit pas hors démo
    page = client.get('/auth/connexion').get_data(as_text=True)
    assert 'Comptes de démonstration' not in page and MDP not in page


def test_tous_les_comptes_listes_existent_et_se_connectent(client, comptes):
    import re
    page = client.get('/auth/connexion').get_data(as_text=True)
    listes = re.findall(r'data-identifiant="([^"]+)"', page)
    assert listes and set(listes) <= {u.identifiant for u in Utilisateur.query.filter_by(actif=True)}
    for ident in listes:
        r = client.post('/auth/connexion', data={'identifiant': ident, 'mot_de_passe': MDP})
        assert r.status_code == 302 and '/auth/connexion' not in (r.location or ''), ident
        client.post('/auth/deconnexion')


def test_le_clic_remplit_les_deux_champs_sans_se_connecter(client, comptes):
    page = client.get('/auth/connexion').get_data(as_text=True)
    assert "document.getElementById('identifiant').value = b.dataset.identifiant" in page
    assert "document.getElementById('mot_de_passe').value = zone.dataset.mdp" in page
    assert 'requestSubmit' not in page.split('data-comptes-demo')[1]
    assert 'cdn.' not in page and 'https://' not in page.split('<body')[1]


def test_protections_de_la_demo_inchangees(client, comptes):
    from tests.test_demo import essai, A
    for _ in range(6):
        essai(client, 'dge', 'faux', A)
    r = essai(client, 'dge', MDP, A)
    assert r.status_code == 200 and 'Trop d' in r.get_data(as_text=True)      # verrouillage par compte + adresse
