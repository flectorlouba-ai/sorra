"""Accueils nationaux : chiffres lourds gardés quelques minutes, recalculés par la tâche planifiée."""
from app.models import Profil
from tests.conftest import connecter, creer_utilisateur


def test_accueil_dge_garde_ses_chiffres_et_les_recalcule(app, client):
    from app.services import memoire
    app.config['ACCUEIL_MEMOIRE_SECONDES'] = 300
    dge = creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    page = client.get('/').get_data(as_text=True)
    assert 'data-calcule-le' in page and 'mis à jour toutes les 5 minutes' in page
    assert memoire.lire('DGE_indicateurs') is not None and memoire.lire('DGE_alertes') is not None
    premier = memoire.lire('DGE_indicateurs')[1]
    assert client.get('/').status_code == 200 and memoire.lire('DGE_indicateurs')[1] == premier   # relu, pas recalculé
    r = app.test_cli_runner().invoke(args=['accueil-recalculer'])
    assert r.exit_code == 0 and 'DGE' in r.output and memoire.lire('DGE_indicateurs')[1] > premier
    app.config['ACCUEIL_MEMOIRE_SECONDES'] = 0
    assert 'data-calcule-le' not in client.get('/').get_data(as_text=True)                       # sans mémoire : calcul direct


def test_profils_de_terrain_jamais_en_memoire(app, client):
    from app.services import memoire
    app.config['ACCUEIL_MEMOIRE_SECONDES'] = 300
    veto = creer_utilisateur('veto', Profil.VETO, ['EST'])
    assert not memoire.actif(veto)
    connecter(client, 'veto')
    assert 'data-calcule-le' not in client.get('/').get_data(as_text=True)
    app.config['ACCUEIL_MEMOIRE_SECONDES'] = 0
