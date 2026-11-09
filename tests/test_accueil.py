"""Lot 1 — accueil par modules (maquette A) : onglets et tuiles selon le profil."""
import re

import pytest

from app import db
from app.models import Profil, UtilisateurFerme
from app.services.fermes import ajouter_batiment
from tests.conftest import creer_utilisateur, connecter, creer_ferme


def onglets(page):
    return re.findall(r'data-tab="(\w+)"', page)


def tuiles_disponibles(page):
    return re.findall(r'<a href="[^"]+" class="module-card[^"]*">\s*<i[^>]*></i>\s*'
                      r'<div class="mc-title">([^<]+)</div>', page)


def accueil(client, identifiant, profil, provinces=('EST',)):
    creer_utilisateur(identifiant, profil, list(provinces))
    connecter(client, identifiant)
    return client.get('/').get_data(as_text=True)


def test_admin_tous_les_onglets(client, app):
    page = accueil(client, 'admin', Profil.ADMIN)
    assert onglets(page) == ['config', 'fermes', 'sante', 'tracabilite', 'economie', 'pilotage',
                             'maintenance', 'qhse', 'comptabilite']
    assert tuiles_disponibles(page) == ['Journal des opérations', 'Utilisateurs',
                                        'Provinces et localités', 'Listes', 'Paramètres',
                                        'Catalogue des intrants', 'Formules des indicateurs',
                                        'Tâches d&#39;entretien',
                                        'Fermes', 'Bandes', 'Intrants', 'Indicateurs d&#39;élevage',
                                        'Alertes sanitaires', 'Déclarations', 'Vaccins et traitements',
                                        'Lots et QR codes', 'Opérateurs', 'Tableau de bord national',
                                        'Carte des fermes', 'Rapports']
    assert page.count('tuile-etiquette">Bientôt') == 8
    assert page.count('tuile-etiquette">Option') == 12
    assert '« Recherche amont / aval » arrive bientôt' in page
    assert 'Catalogue des intrants' in page
    assert 'Aucune alerte active' in page and 'Suivi et traçabilité de la filière avicole' in page
    assert 'Bonjour, <strong>ADMIN</strong>' in page   # Prénom NOM
    assert '> Accueil<' not in page   # pas de bouton Accueil sur l'accueil


def test_dge_sans_configuration(client, app):
    page = accueil(client, 'dge', Profil.DGE, ())
    assert onglets(page)[0] == 'fermes' and 'config' not in onglets(page)
    assert len(onglets(page)) == 8
    assert tuiles_disponibles(page) == ['Fermes', 'Bandes', 'Intrants', 'Indicateurs d&#39;élevage',
                                        'Alertes sanitaires', 'Lots et QR codes', 'Opérateurs',
                                        'Tableau de bord national',
                                        'Carte des fermes', 'Rapports']


def test_agent(client, app):
    page = accueil(client, 'agent', Profil.AGENT)
    assert onglets(page) == ['fermes', 'sante', 'tracabilite']
    assert tuiles_disponibles(page) == ['Fermes', 'Bandes', 'Intrants', 'Indicateurs d&#39;élevage',
                                        'Vaccins et traitements', 'Lots et QR codes', 'Opérateurs']
    assert 'Bandes' in page and 'Lots et QR codes' in page


def test_veto(client, app):
    page = accueil(client, 'veto', Profil.VETO)
    assert onglets(page) == ['fermes', 'sante', 'tracabilite']
    assert tuiles_disponibles(page) == ['Fermes', 'Bandes', 'Indicateurs d&#39;élevage', 'Alertes sanitaires',
                                        'Déclarations', 'Vaccins et traitements', 'Lots et QR codes']
    assert 'Recherche amont' not in page   # Traçabilité : la seule tuile utilisable
    assert 'Intrants' not in page   # Fermes et élevage : Fermes et Bandes, en lecture
    assert 'Déclarations' in page


def test_auditeur_journal_seul(client, app):
    page = accueil(client, 'aninf', Profil.AUDITEUR)
    assert onglets(page) == ['config']
    assert tuiles_disponibles(page) == ['Journal des opérations']
    assert 'Utilisateurs' not in page and 'Paramètres' not in page


@pytest.mark.parametrize('profil', [Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR])
def test_espace_bientot(client, app, profil):
    page = accueil(client, 'x', profil)
    assert onglets(page) == [] and 'Votre espace arrive bientôt' in page


def test_eleveur_ma_ferme_et_appel_agent(client, app):
    agent = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    agent.telephone = '+241 77 00 11 22'
    eleveur = creer_utilisateur('eleveur', Profil.ELEVEUR)
    f = creer_ferme('Ferme Obiang', 'EST', 'Ntoum', agent=agent, statut='Opérationnelle')
    ajouter_batiment(f, 1200)
    ajouter_batiment(f, 800)
    eleveur.fermes = [UtilisateurFerme(ferme=f)]
    db.session.commit()
    connecter(client, 'eleveur')
    page = client.get('/').get_data(as_text=True)
    assert onglets(page) == [] and 'href="tel:+24177001122"' in page and 'mon agent' in page
    page = client.get('/mon-stock').get_data(as_text=True)
    assert 'Ma ferme' in page and 'Ferme Obiang' in page
    assert 'EST-001' in page and 'Opérationnelle' in page and '2 000' in page


def test_tuile_bientot_ne_mene_nulle_part(client, app):
    page = accueil(client, 'admin', Profil.ADMIN)
    assert 'Bientôt' in page and '/indicateurs' not in page
