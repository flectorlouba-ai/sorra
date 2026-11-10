"""Lot R — version ordinateur : chaque profil voit ses boutons et rien d'autre (403 sinon), périmètre respecté dans
les tableaux, la carte et les alertes, vétérinaire sans aucune donnée financière, Excel conforme et journalisé,
impression journalisée, fenêtres, bascule terrain / ordinateur, anciennes adresses redirigées."""
import io
import json
import re

import pytest
from openpyxl import load_workbook

from app import db
from app.models import JournalAudit, Profil
from app.services.bureau import FONCTIONS
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401


def boutons(page):
    return re.findall(r'data-fonction="(\w+)"', page)


# ── Boutons et droits ───────────────────────────────────────────────────

def test_chaque_profil_voit_ses_boutons_et_rien_d_autre(client, monde):
    for profil, ident in ((Profil.VETO, 'veto'), (Profil.DGE, 'dge'), (Profil.AUDITEUR, 'aninf')):
        creer_utilisateur(ident, profil, ['EST'])
    connecter(client, 'veto')
    page = client.get('/').get_data(as_text=True)
    assert boutons(page) == [f[0] for f in FONCTIONS[Profil.VETO]]
    assert client.get('/administration/utilisateurs/').status_code == 403
    assert client.get('/bureau/droits').status_code == 403
    assert client.get('/bureau/plans-actions').status_code == 403
    client.post('/auth/deconnexion')
    connecter(client, 'aninf')
    assert client.get('/bureau/exports').status_code == 200 and client.get('/bureau/recherche').status_code == 200
    assert client.get('/bureau/visites').status_code == 403 and client.get('/fermes/').status_code in (200, 403)


def test_veterinaire_sans_donnee_financiere(client, monde):
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    bande_ouverte(monde)
    connecter(client, 'veto')
    page = client.get('/').get_data(as_text=True)
    assert 'FCFA' not in page and 'Produit 12 mois' not in page and 'Gagné' not in page
    for lien in re.findall(r'<a class="fb[^"]*" href="([^"]+)"', page):
        contenu = client.get(lien, follow_redirects=True).get_data(as_text=True)
        assert 'FCFA' not in contenu, lien


def test_perimetre_dans_le_tableau_la_carte_et_les_alertes(client, monde):
    from app.models import Ferme
    hog = creer_utilisateur('agent_hog', Profil.AGENT, ['HOG'])
    f_hog = __import__('tests.conftest', fromlist=['creer_ferme']).creer_ferme('Ferme Moanda', 'HOG', 'Moanda', agent=hog)
    f_hog.latitude, f_hog.longitude = -1.5, 13.2
    monde['f'].latitude, monde['f'].longitude = 0.39, 9.76
    db.session.commit()
    bande_ouverte(monde)
    connecter(client, 'agent_hog')
    client.get('/bureau/version-ordinateur')
    page = client.get('/').get_data(as_text=True)
    assert 'Ferme Moanda' in page and 'Ferme Un' not in page and monde['f'].numero not in page
    assert f'data-point-ferme="{f_hog.numero}"' in page and f'data-point-ferme="{monde["f"].numero}"' not in page


# ── Excel et impression journalisés ─────────────────────────────────────

def test_excel_des_lignes_filtrees_journalise(client_admin, monde):
    donnees = {'colonnes': ['N°', 'Ferme', 'Places'], 'lignes': [['EST-001', 'Ferme Un', '2 300'], ['EST-002', 'Ferme Deux', '500']]}
    r = client_admin.post('/bureau/exports/tableau.xlsx', data={'titre': 'Fermes', 'filtres': 'Estuaire', 'donnees': json.dumps(donnees)})
    assert r.status_code == 200 and 'spreadsheetml' in r.mimetype
    ws = load_workbook(io.BytesIO(r.data)).active
    lignes = [[c.value for c in row] for row in ws.iter_rows()]
    assert lignes[0][0] == 'SORRA — Fermes' and 'Estuaire' in lignes[1][0]
    assert lignes[3] == ['N°', 'Ferme', 'Places'] and lignes[4] == ['EST-001', 'Ferme Un', 2300] and lignes[5][2] == 500
    j = JournalAudit.query.filter_by(action='EXPORT', table_nom='tableau').one()
    assert 'Fermes' in j.detail and '2 ligne(s)' in j.detail and 'Estuaire' in j.detail
    assert client_admin.post('/bureau/exports/tableau.xlsx', data={'donnees': 'pas du json'}).status_code == 400


def test_impression_journalisee(client_admin, monde):
    r = client_admin.post('/bureau/exports/impression', json={'titre': 'Élevages', 'lignes': 6})
    assert r.get_json()['etat'] == 'ok'
    j = JournalAudit.query.filter_by(action='EXPORT', table_nom='impression').one()
    assert 'Élevages' in j.detail and '6 ligne(s)' in j.detail


def test_outils_de_tableau_charges_sur_les_pages_de_bureau(client_admin, monde):
    page = client_admin.get('/fermes/').get_data(as_text=True)
    assert 'js/tableaux.js' in page and 'class="bureau"' in page and 'kente-band' not in page
    assert 'Bande en cours' in page and 'Dernière saisie' in page and 'Alerte' in page       # colonnes de la maquette
    connecter(client_admin, 'admin')


# ── Fenêtres et bascule ─────────────────────────────────────────────────

def test_fenetres_vides_et_preremplies_presentes(client_admin, monde):
    page = client_admin.get('/administration/utilisateurs/').get_data(as_text=True)
    assert 'id="fen-user"' in page and 'modal-footer' in page and "ouvrirModification(this)" in page
    page = client_admin.get('/fermes/nouvelle').get_data(as_text=True)
    assert 'id="fen-ferme"' in page and 'data-ouverte' in page
    assert 'max-height:calc(100vh - 32px)' in open('app/static/css/perform.css', encoding='utf-8').read()


def test_bascule_terrain_ordinateur(client, monde):
    connecter(client, 'eleveur1')
    assert 'theme-terrain' in client.get('/').get_data(as_text=True)
    r = client.post('/bureau/bascule-automatique', json={'largeur': 1440})
    assert r.get_json()['etat'] == 'ordinateur'
    page = client.get('/').get_data(as_text=True)
    assert 'class="bureau"' in page and boutons(page) == [f[0] for f in FONCTIONS[Profil.ELEVEUR]]
    client.get('/bureau/version-terrain')
    assert 'theme-terrain' in client.get('/').get_data(as_text=True)
    assert client.post('/bureau/bascule-automatique', json={'largeur': 1440}).get_json()['etat'] == 'inchange'   # choix explicite
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')                               # nouvelle session : téléphone étroit → rien ne change
    assert client.post('/bureau/bascule-automatique', json={'largeur': 390}).get_json()['etat'] == 'inchange'


def test_anciennes_adresses_redirigent(client, monde):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    assert client.get('/bureau/').status_code == 302
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    r = client.get('/terrain/bureau')
    assert r.status_code == 302
    page = client.get('/').get_data(as_text=True)
    assert 'class="bureau"' in page and 'data-fonction="fermes"' in page


@pytest.mark.parametrize('profil, ident', [(Profil.BCEG, 'bceg'), (Profil.MAEDR, 'maedr')])
def test_bceg_et_maedr_ont_le_gabarit(client, monde, profil, ident):
    creer_utilisateur(ident, profil)
    connecter(client, ident)
    page = client.get('/').get_data(as_text=True)
    assert 'class="bureau"' in page and boutons(page) == ['accueil'] and 'lot M' in page
