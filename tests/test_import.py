"""Lot 1 — import de la liste POUFA (Excel) en deux temps."""
import io
import os

import pytest
from openpyxl import Workbook, load_workbook

from app import db
from app.models import Ferme, Localite, Profil, JournalAudit
from app.services import import_poufa
from tests.conftest import creer_utilisateur, connecter, province, creer_ferme


def fichier(lignes, entetes=None):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Fermes'
    ws.append(entetes or [c[0] + (' *' if c[2] else '') for c in import_poufa.COLONNES])
    for l in lignes:
        ws.append(l)
    t = io.BytesIO()
    wb.save(t)
    return t.getvalue()


def ligne(nom, tel, province_='Estuaire', localite='Ntoum', ami='', cohorte='', statut='', agent='',
          lat='', lon='', infra='', obs=''):
    return [nom, f'Exploitant {nom}', tel, province_, localite, ami, cohorte, statut, agent, lat, lon, infra, obs]


@pytest.fixture
def preparation(app):
    est = province('EST')
    db.session.add_all([Localite(province=est, nom='Ntoum'), Localite(province=est, nom="N'kok")])
    db.session.commit()
    creer_utilisateur('agent.est', Profil.AGENT, ['EST'])
    creer_ferme('Ferme Existante', 'EST', 'Ntoum', telephone='077999999', reference_ami='AMI-1')


def envoyer(client, contenu):
    return client.post('/fermes/import/verifier', data={'fichier': (io.BytesIO(contenu), 'poufa.xlsx')},
                       content_type='multipart/form-data')


def test_modele_avec_explications(client_admin):
    r = client_admin.get('/fermes/import/modele.xlsx')
    wb = load_workbook(io.BytesIO(r.data))
    assert wb.sheetnames == ['Fermes', 'Explications']
    assert wb['Fermes']['A1'].value == 'Nom de la ferme *'
    assert 'Opérationnelle' in str([c.value for c in wb['Explications']['B']])


def test_apercu_puis_import_des_lignes_valides(client_admin, preparation):
    contenu = fichier([
        ligne('Ferme Bonne', '077100001', ami='AMI-2', cohorte=1, statut='Opérationnelle', agent='agent.est',
              lat='0,39', lon='9,61', infra='Clôture; pédiluve'),
        ligne('Ferme Nkok', '077100002', localite='Nkok'),                 # identique à N'kok
        ligne('Ferme Nkoq', '077100003', localite='Nkoq'),                 # nouvelle, ressemble à N'kok
        ligne('Ferme Bikélé', '077100004', localite='Bikélé'),             # nouvelle
        ligne('Ferme Tel', '+241 07 79 99 999'),                           # doublon téléphone (base)
        ligne('Ferme Ami', '077100005', ami='ami-1'),                      # doublon AMI (base)
        ligne('Ferme Bis', '077100001'),                                   # doublon dans le fichier
        ligne('', '077100006'),                                            # nom vide
        ligne('Ferme Prov', '077100007', province_='Lagune'),              # province inconnue
        ligne('Ferme Agent', '077100008', agent='inconnu'),                # agent inconnu
        ligne('Ferme Infra', '077100009', infra='Piscine'),                # infrastructure inconnue
        ligne('Ferme Loin', '077100010', lat='-1,63', lon='13,58'),        # avertissement position
    ])
    page = envoyer(client_admin, contenu).get_data(as_text=True)
    assert 'Importer les lignes valides (5)' in page
    assert 'Localité nouvelle : « Nkoq » sera créée' in page
    assert '⚠ « Nkoq » ressemble à « N&#39;kok »' in page
    assert 'Ce téléphone est déjà celui de l&#39;exploitant de la ferme EST-001' in page
    assert 'référence AMI ami-1 est déjà celle de la ferme EST-001' in page
    assert 'Doublon dans le fichier : le même téléphone que la ligne 2' in page
    assert 'Province inconnue' in page and 'inconnu' in page and 'Infrastructure inconnue : « Piscine »' in page
    assert 'Position à' in page
    assert Ferme.query.count() == 1   # rien d'importé à l'aperçu

    jeton = [f for f in os.listdir(import_poufa.dossier()) if f.endswith('.xlsx')]
    assert jeton
    r = client_admin.post('/fermes/import/importer')
    page = r.get_data(as_text=True)
    assert '5 ferme(s) importée(s), 7 ligne(s) refusée(s)' in page
    assert Ferme.query.count() == 6
    bonne = Ferme.query.filter_by(nom='Ferme Bonne').one()
    assert bonne.numero == 'EST-002' and bonne.cohorte == 1 and bonne.statut == 'Opérationnelle'
    assert bonne.agent.identifiant == 'agent.est' and bonne.reference_ami == 'AMI-2'
    assert [i.infrastructure for i in bonne.infrastructures] == ['Clôture', 'Pédiluve']
    assert Ferme.query.filter_by(nom='Ferme Nkok').one().localite.nom == "N'kok"
    nouvelles = Localite.query.filter(Localite.nom.in_(['Nkoq', 'Bikélé'])).all()
    assert len(nouvelles) == 2 and not any(l.a_verifier for l in nouvelles)   # créées par l'ADMIN
    imp = JournalAudit.query.filter_by(action='IMPORT').one()
    assert '5 ferme(s) créée(s), 7 ligne(s) refusée(s), 2 localité(s)' in imp.detail
    assert JournalAudit.query.filter_by(action='CREATION', table_nom='ferme').count() == 6

    # Fichier déposé effacé, rapport téléchargeable
    restants = os.listdir(import_poufa.dossier())
    assert not [f for f in restants if f.endswith('.xlsx') and not f.endswith('_rapport.xlsx')]
    lien = page.split('/fermes/import/rapport/')[1].split('"')[0]
    rapport = load_workbook(io.BytesIO(client_admin.get('/fermes/import/rapport/' + lien).data)).active
    resultats = [row[-2] for row in rapport.iter_rows(min_row=2, values_only=True)]
    assert resultats[0] == 'Importée : EST-002' and resultats[4].startswith('Refusée')


def test_mauvais_fichier(client_admin):
    r = client_admin.post('/fermes/import/verifier', data={'fichier': (io.BytesIO(b'pas un excel'), 'x.xlsx')},
                          content_type='multipart/form-data', follow_redirects=True)
    assert 'pas un fichier Excel' in r.get_data(as_text=True)
    r = client_admin.post('/fermes/import/verifier', data={'fichier': (io.BytesIO(fichier([], ['A', 'B'])), 'x.xlsx')},
                          content_type='multipart/form-data', follow_redirects=True)
    assert 'colonnes ne correspondent pas' in r.get_data(as_text=True)


def test_import_sans_apercu_refuse(client_admin):
    r = client_admin.post('/fermes/import/importer', follow_redirects=True)
    assert 'vérifiez-le de nouveau' in r.get_data(as_text=True)


@pytest.mark.parametrize('profil', [Profil.DGE, Profil.AGENT])
def test_import_reserve_a_l_admin(client, app, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/fermes/import').status_code == 403
    assert client.get('/fermes/import/modele.xlsx').status_code == 403
    assert 'Importer la liste POUFA' not in client.get('/fermes/').get_data(as_text=True)
