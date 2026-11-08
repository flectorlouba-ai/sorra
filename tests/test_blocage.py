"""Blocage d'un compte après des échecs de connexion consécutifs."""
from datetime import timedelta

from app import db
from app.models import JournalAudit, Profil, Parametre, Utilisateur
from app.models.base import maintenant
from tests.conftest import creer_utilisateur, connecter


def echouer(client, identifiant, fois):
    for _ in range(fois):
        r = connecter(client, identifiant, 'mauvais')
    return r.get_data(as_text=True)


def actions(action):
    return JournalAudit.query.filter_by(action=action).order_by(JournalAudit.id).all()


def test_bloque_apres_5_echecs(client, app):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    assert 'bloqué' not in echouer(client, 'agent', 4)
    page = echouer(client, 'agent', 1)
    assert 'bloqué pendant encore 15 minutes' in page
    blocage = actions('BLOCAGE')[-1]
    assert blocage.identifiant == 'agent' and '5 échecs' in blocage.detail
    assert blocage.table_nom == 'utilisateur' and blocage.enregistrement_id == str(u.id)
    # Même le bon mot de passe est refusé pendant le blocage
    r = connecter(client, 'agent')
    assert 'bloqué' in r.get_data(as_text=True)
    assert client.get('/').status_code == 302


def test_reussite_remet_le_compteur_a_zero(client, app):
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    echouer(client, 'agent', 4)
    connecter(client, 'agent')
    client.post('/auth/deconnexion')
    assert 'bloqué' not in echouer(client, 'agent', 4)
    assert actions('BLOCAGE') == []


def test_deblocage_automatique_apres_le_delai(client, app):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    echouer(client, 'agent', 5)
    u.bloque_jusqu_a = maintenant() - timedelta(minutes=1)
    db.session.commit()
    assert connecter(client, 'agent').location.endswith('/')
    deblocage = actions('DEBLOCAGE')[-1]
    assert 'Fin du délai' in deblocage.detail and deblocage.identifiant == 'agent'


def test_admin_debloque(client, app, admin):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    echouer(client, 'agent', 5)
    connecter(client, 'admin')
    page = client.get('/administration/utilisateurs/').get_data(as_text=True)
    assert 'Bloqué' in page and 'Débloquer' in page
    r = client.post(f'/administration/utilisateurs/{u.id}/debloquer', follow_redirects=True)
    assert 'débloqué' in r.get_data(as_text=True)
    assert db.session.get(Utilisateur, u.id).bloque_jusqu_a is None
    deblocage = actions('DEBLOCAGE')[-1]
    assert deblocage.identifiant == 'admin' and "par l'administrateur" in deblocage.detail
    client.post('/auth/deconnexion')
    assert connecter(client, 'agent').location.endswith('/')


def test_debloquer_reserve_a_l_admin(client, app):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    assert client.post(f'/administration/utilisateurs/{u.id}/debloquer').status_code == 403


def test_reglages_pris_en_compte(client, app):
    Parametre.query.filter_by(cle='securite.echecs_avant_blocage').one().valeur = '2'
    Parametre.query.filter_by(cle='securite.blocage_minutes').one().valeur = '30'
    db.session.commit()
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    assert 'bloqué pendant encore 30 minutes' in echouer(client, 'agent', 2)


def test_blocage_ne_cree_pas_de_modification_de_fiche(client, app):
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    echouer(client, 'agent', 5)
    assert actions('MODIFICATION') == []


def test_identifiant_inconnu_jamais_bloque(client, app):
    assert 'bloqué' not in echouer(client, 'personne', 8)
