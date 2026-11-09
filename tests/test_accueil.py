"""Lot 15 — accueil du pilotage en tuiles par profil (aucune tuile morte, compteurs, périmètre) ;
l'éleveur garde son accueil (lot 9 à 13)."""
import re

import pytest

from app import db
from app.models import Profil, UtilisateurFerme
from app.routes.accueil import TUILES_PROFIL
from app.services.fermes import ajouter_batiment
from tests.conftest import creer_utilisateur, connecter, creer_ferme


def onglets(page):
    return re.findall(r'data-tab="(\w+)"', page)


def tuiles(page):
    return re.findall(r'data-tuile-pilotage="(\w+)"', page)


def liens(page):
    return re.findall(r'<a href="([^"]+)" class="module-card[^"]*" data-tuile-pilotage', page)


def accueil(client, identifiant, profil, provinces=('EST',)):
    creer_utilisateur(identifiant, profil, list(provinces))
    connecter(client, identifiant)
    return client.get('/').get_data(as_text=True)


@pytest.mark.parametrize('profil', [Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO, Profil.AUDITEUR])
def test_tuiles_par_profil_et_aucune_tuile_morte(client, app, profil):
    page = accueil(client, 'u', profil)
    assert tuiles(page) == TUILES_PROFIL[profil]
    assert 'Bientôt' not in page and 'tuile-bientot' not in page.split('<script')[0]
    for lien in liens(page):                                   # chaque tuile ouvre un écran qui existe
        assert client.get(lien).status_code == 200, lien
    assert onglets(page) == []                                  # un seul panneau : plus d'onglets


def test_tuiles_visees_dans_l_ordre(client, app):
    assert accueil(client, 'admin', Profil.ADMIN).count('data-tuile-pilotage') == len(TUILES_PROFIL[Profil.ADMIN])
    assert TUILES_PROFIL[Profil.ADMIN][:6] == ['utilisateurs', 'configuration', 'a_approuver', 'sessions', 'journal',
                                               'integrite']
    assert TUILES_PROFIL[Profil.DGE][:5] == ['tableau', 'carte', 'livraisons_etat', 'arbitrages', 'rapports']
    assert TUILES_PROFIL[Profil.AUDITEUR] == ['journal', 'integrite']
    page = client.get('/configuration').get_data(as_text=True)
    for titre in ('Provinces et localités', 'Listes', 'Paramètres', 'Catalogue des intrants', 'Formules des indicateurs'):
        assert titre in page


@pytest.mark.parametrize('profil', [Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR])
def test_profils_sans_ecran(client, app, profil):
    page = accueil(client, 'x', profil)
    assert tuiles(page) == [] and 'Vos écrans arrivent bientôt' in page


def test_perimetre_en_tete(client, app):
    assert 'data-perimetre>· National' in accueil(client, 'dge', Profil.DGE)
    client.post('/auth/deconnexion')
    assert 'data-perimetre>· Estuaire' in accueil(client, 'veto', Profil.VETO)
    client.post('/auth/deconnexion')
    assert 'data-perimetre>· 0 ferme suivie' in accueil(client, 'agent', Profil.AGENT)
    assert 'href="/auth/securite"' in client.get('/').get_data(as_text=True)


def test_compteur_a_approuver(client, app):
    admin = creer_utilisateur('admin', Profil.ADMIN)
    from app.models import Parametre
    from app.services import approbations
    p = Parametre.query.filter_by(cle='bandes.seuil_rouge_pct').one()
    approbations.proposer('PARAMETRE', p.cle, p.description, p.valeur, '2', {'valeur': '2'}, 'essai', admin)
    db.session.commit()
    page = accueil(client, 'dge', Profil.DGE)
    assert re.search(r'data-tuile-pilotage="a_approuver">\s*<span class="tuile-compteur"[^>]*>1</span>', page)
    client.post('/auth/deconnexion')
    connecter(client, 'admin')                                 # l'auteur : rien à approuver
    assert not re.search(r'data-tuile-pilotage="a_approuver">\s*<span class="tuile-compteur"',
                         client.get('/').get_data(as_text=True))


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
    assert onglets(page) == [] and 'href="tel:+24177001122"' in page and 'data-entete="agent"' in page
    assert 'Ma ferme' not in client.get('/mon-stock').get_data(as_text=True)     # lot 11 : dans « Moi »
    page = client.get('/moi').get_data(as_text=True)
    assert 'Ma ferme' in page and 'Ferme Obiang' in page
    assert 'EST-001' in page and '2 000' in page
