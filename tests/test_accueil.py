"""Accueil de la version ordinateur (lot R, remplace les tuiles du lot 15) : boutons des fonctionnalités par profil
(aucun bouton mort), périmètre, compteurs ; l'éleveur garde son accueil terrain (lots 9 à 13)."""
import re

import pytest

from app import db
from app.models import Profil, UtilisateurFerme
from app.services.bureau import FONCTIONS
from app.services.fermes import ajouter_batiment
from tests.conftest import creer_utilisateur, connecter, creer_ferme


def boutons(page):
    return re.findall(r'data-fonction="(\w+)"', page)


def liens(page):
    return re.findall(r'<a class="fb[^"]*" href="([^"]+)" data-fonction', page)


def accueil(client, identifiant, profil, provinces=('EST',)):
    creer_utilisateur(identifiant, profil, list(provinces))
    connecter(client, identifiant)
    if profil in (Profil.AGENT, Profil.ELEVEUR, Profil.OPERATEUR):     # lot R : version ordinateur choisie
        client.get('/bureau/version-ordinateur')
    return client.get('/', follow_redirects=True).get_data(as_text=True)


@pytest.mark.parametrize('profil', [Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO, Profil.AUDITEUR, Profil.BCEG,
                                    Profil.MAEDR])
def test_boutons_par_profil_et_aucun_bouton_mort(client, app, profil):
    page = accueil(client, 'u', profil)
    assert boutons(page) == [f[0] for f in FONCTIONS[profil]]
    assert 'kente-band' not in page                             # charte YL.1 sans bande kente
    for lien in liens(page):                                    # chaque bouton ouvre un écran qui existe
        assert client.get(lien, follow_redirects=True).status_code == 200, lien
    assert 'data-tuile-pilotage' not in page                     # plus de tuiles


def test_bouton_actif_et_configuration(client, app):
    page = accueil(client, 'admin', Profil.ADMIN)
    assert re.search(r'class="fb on" href="/bureau/" data-fonction="accueil"', page)
    page = client.get('/administration/utilisateurs/').get_data(as_text=True)
    assert re.search(r'class="fb on" href="[^"]+" data-fonction="utilisateurs"', page)
    page = client.get('/configuration').get_data(as_text=True)
    for titre in ('Provinces et localités', 'Listes', 'Paramètres', 'Catalogue des intrants', 'Formules des indicateurs'):
        assert titre in page


def test_perimetre_en_tete(client, app):
    assert 'Périmètre : <b>National' in accueil(client, 'dge', Profil.DGE)
    client.post('/auth/deconnexion')
    assert 'Périmètre : <b>Estuaire' in accueil(client, 'veto', Profil.VETO)
    client.post('/auth/deconnexion')
    assert 'Périmètre : <b>0 ferme suivie' in accueil(client, 'agent', Profil.AGENT)
    assert 'aria-label="Se déconnecter"' in client.get('/').get_data(as_text=True)      # lot V : icône seule


def test_compteur_a_approuver(client, app):
    admin = creer_utilisateur('admin', Profil.ADMIN)
    from app.models import Parametre
    from app.services import approbations
    p = Parametre.query.filter_by(cle='bandes.seuil_rouge_pct').one()
    approbations.proposer('PARAMETRE', p.cle, p.description, p.valeur, '2', {'valeur': '2'}, 'essai', admin)
    db.session.commit()
    page = accueil(client, 'veto', Profil.VETO)
    assert re.search(r'data-fonction="validations"[^>]*><span class="pa">1</span>', page)
    client.post('/auth/deconnexion')
    connecter(client, 'admin')                                  # l'auteur : rien à approuver
    assert not re.search(r'data-fonction="validations"[^>]*><span class="pa">', client.get('/bureau/').get_data(as_text=True))


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
    assert 'data-tab=' not in page and 'href="tel:+24177001122"' in page and 'data-entete="agent"' in page
    assert 'Ma ferme' not in client.get('/mon-stock').get_data(as_text=True)     # lot 11 : dans « Moi »
    page = client.get('/moi').get_data(as_text=True)
    assert 'Ma ferme' in page and 'Ferme Obiang' in page
    assert 'EST-001' in page and '2 000' in page
