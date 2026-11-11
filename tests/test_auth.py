import time

from app.models import JournalAudit, Profil
from tests.conftest import creer_utilisateur, connecter, MDP


def actions():
    return [l.action for l in JournalAudit.query.order_by(JournalAudit.id).all()]


def test_connexion_reussie_journalisee(client, admin):
    r = connecter(client, 'admin')
    assert r.status_code == 302 and r.location.endswith('/')
    assert 'CONNEXION' in actions()
    assert client.get('/').status_code == 200


def test_identifiant_insensible_a_la_casse(client, admin):
    assert connecter(client, ' ADMIN ').location.endswith('/')


def test_echec_connexion_journalise(client, admin):
    r = connecter(client, 'admin', 'faux')
    assert r.status_code == 200
    assert 'Identifiant ou mot de passe incorrect' in r.get_data(as_text=True)
    ligne = JournalAudit.query.filter_by(action='ECHEC_CONNEXION').one()
    assert ligne.identifiant == 'admin' and ligne.utilisateur_id is None


def test_compte_desactive_refuse(client, app):
    creer_utilisateur('ancien', Profil.AGENT, ['EST'], actif=False)
    r = connecter(client, 'ancien')
    assert 'incorrect' in r.get_data(as_text=True)
    assert JournalAudit.query.filter_by(action='ECHEC_CONNEXION').one().detail == 'compte désactivé'


def test_premiere_connexion_impose_changement(client, app):
    creer_utilisateur('nouveau', Profil.AGENT, ['EST'], doit_changer=True)
    r = connecter(client, 'nouveau')
    assert r.location.endswith('/auth/mot-de-passe')
    # Toute autre page renvoie vers le changement de mot de passe
    assert client.get('/').location.endswith('/auth/mot-de-passe')
    r = client.post('/auth/mot-de-passe', data={'actuel': MDP, 'nouveau': 'Nouveau-mdp-2026',
                                                 'confirmation': 'Nouveau-mdp-2026'})
    assert r.location.endswith('/')
    assert client.get('/').status_code == 200
    assert 'CHANGEMENT_MDP' in actions()


def test_changement_mdp_controles(client, admin):
    connecter(client, 'admin')
    def essai(actuel, nouveau, conf):
        return client.post('/auth/mot-de-passe', data={'actuel': actuel, 'nouveau': nouveau,
                                                        'confirmation': conf}).get_data(as_text=True)
    assert 'actuel est incorrect' in essai('faux', 'Abcdefghijk1', 'Abcdefghijk1')
    assert 'au moins 10' in essai(MDP, 'court', 'court')
    assert 'ne correspond pas' in essai(MDP, 'Abcdefghijk1', 'Abcdefghijk2')


def test_deconnexion_en_post_seulement(client_admin):
    r = client_admin.get('/auth/deconnexion')                  # GET : ne déconnecte pas (pas de jeton CSRF), ramène à l'accueil
    assert r.status_code == 302 and client_admin.get('/').status_code == 200
    r = client_admin.post('/auth/deconnexion')
    assert r.location.endswith('/auth/connexion')
    assert client_admin.get('/').status_code == 302
    assert 'DECONNEXION' in actions()


def test_fin_de_session_apres_inactivite(client_admin):
    with client_admin.session_transaction() as s:
        s['derniere_activite'] = time.time() - 61 * 60
    r = client_admin.get('/')
    assert r.location.endswith('/auth/connexion')
    assert JournalAudit.query.filter_by(action='DECONNEXION').one().detail.startswith('Fin de session')


def test_compte_desactive_perd_sa_session(client, app):
    u = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    connecter(client, 'agent')
    assert client.get('/').status_code == 200
    u.actif = False
    from app import db
    from flask import g
    db.session.commit()
    # Le banc garde un même contexte entre requêtes : on oublie l'utilisateur
    # mémorisé, comme le fait chaque nouvelle requête en vrai.
    g.pop('_login_user', None)
    assert client.get('/').status_code == 302


def test_redirection_next_interne_seulement(client, admin):
    r = client.post('/auth/connexion?next=//exemple.com', data={'identifiant': 'admin', 'mot_de_passe': MDP})
    assert r.location.endswith('/')
