"""Démonstration publique (YL2_DEMO=1, sorra.performyl.com) : le mot de passe est connu de tous.
Bandeau sur toutes les pages ; mot de passe, téléphone et 2FA bloqués ; verrouillage par compte + adresse IP
(celui qui se trompe est bloqué, pas les autres) ; X-Forwarded-For lu seulement depuis 127.0.0.1."""
import pytest

from app import db
from app.models import Profil, Utilisateur, UtilisateurFerme, JournalAudit
from tests.conftest import creer_utilisateur, connecter, creer_ferme, MDP

A, B = '10.0.0.1', '10.0.0.2'


@pytest.fixture
def demo(app):
    app.config['DEMO'] = True
    yield app
    app.config['DEMO'] = False


def essai(client, ident, mdp, ip):
    return client.post('/auth/connexion', data={'identifiant': ident, 'mot_de_passe': mdp},
                       environ_base={'REMOTE_ADDR': ip})


def test_bandeau_sur_toutes_les_pages(client, demo):
    assert 'DÉMONSTRATION — données fictives' in client.get('/auth/connexion').get_data(as_text=True)
    creer_utilisateur('dge', Profil.DGE)
    el = creer_utilisateur('eleveur', Profil.ELEVEUR)
    el.fermes = [UtilisateurFerme(ferme=creer_ferme('Ferme Un', 'EST', 'Ntoum'))]
    db.session.commit()
    connecter(client, 'dge')
    for page in ('/', '/fermes/', '/auth/securite'):
        assert 'data-demo' in client.get(page).get_data(as_text=True), page
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur')
    for page in ('/', '/moi', '/mon-compte'):
        assert 'data-demo' in client.get(page).get_data(as_text=True), page


def test_pas_de_bandeau_hors_demonstration(client, app):
    assert 'data-demo' not in client.get('/auth/connexion').get_data(as_text=True)


def test_mot_de_passe_telephone_et_2fa_bloques(client, demo):
    el = creer_utilisateur('eleveur', Profil.ELEVEUR)
    el.telephone = '+241 77 00 00 01'
    el.fermes = [UtilisateurFerme(ferme=creer_ferme('Ferme Un', 'EST', 'Ntoum'))]
    db.session.commit()
    connecter(client, 'eleveur')
    page = client.get('/auth/mot-de-passe').get_data(as_text=True)
    assert 'Désactivé en démonstration' in page and 'name="nouveau"' not in page
    page = client.post('/auth/mot-de-passe', data={'actuel': MDP, 'nouveau': 'Autre-mdp-2026',
                                                   'confirmation': 'Autre-mdp-2026'}).get_data(as_text=True)
    assert 'Désactivé en démonstration' in page
    db.session.refresh(el)
    assert el.check_password(MDP)
    page = client.post('/mon-compte', data={'telephone': '+241 66 66 66 66'}).get_data(as_text=True)
    assert 'Désactivé en démonstration' in page and el.telephone == '+241 77 00 00 01'
    client.post('/auth/deconnexion')
    creer_utilisateur('veto', Profil.VETO, ['EST'])                    # 2FA facultative pour le vétérinaire
    db.session.commit()
    connecter(client, 'veto')
    assert 'Activer la double authentification' not in client.get('/auth/securite').get_data(as_text=True)
    r = client.get('/auth/2fa/mise-en-place', follow_redirects=True)
    assert 'Désactivé en démonstration' in r.get_data(as_text=True)
    assert not Utilisateur.query.filter_by(identifiant='veto').one().totp_active


def test_l_admin_ne_peut_ni_changer_un_mot_de_passe_ni_desactiver(client, demo):
    creer_utilisateur('admin', Profil.ADMIN)
    dge = creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    connecter(client, 'admin')
    base = {'nom': 'Dge', 'profil': 'DGE', 'actif': 'on'}
    page = client.post(f'/administration/utilisateurs/{dge.id}/modifier', data={**base, 'mot_de_passe': 'Piege-2026-xx'},
                       follow_redirects=True).get_data(as_text=True)
    assert 'Désactivé en démonstration' in page
    client.post(f'/administration/utilisateurs/{dge.id}/modifier', data={'nom': 'Dge', 'profil': 'DGE'})
    db.session.refresh(dge)
    assert dge.actif and dge.check_password(MDP) and not dge.doit_changer_mdp
    client.post(f'/administration/utilisateurs/{dge.id}/modifier', data={**base, 'nom': 'Direction'})
    db.session.refresh(dge)
    assert dge.nom == 'Direction'                                     # le reste se modifie normalement


def test_verrouillage_par_compte_et_adresse(client, demo):
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    for _ in range(5):
        essai(client, 'dge', 'mauvais', A)
    page = essai(client, 'dge', MDP, A).get_data(as_text=True)          # A, même avec le bon mot de passe : bloqué
    assert 'Trop d' in page and 'cet appareil' in page
    r = essai(client, 'dge', MDP, B)                                    # un autre visiteur se connecte
    assert r.status_code == 302 and '/auth/connexion' not in r.location
    u = Utilisateur.query.filter_by(identifiant='dge').one()
    assert u.bloque_jusqu_a is None and u.echecs_connexion == 0         # le compte n'est jamais bloqué pour tous
    assert JournalAudit.query.filter(JournalAudit.action == 'BLOCAGE', JournalAudit.adresse_ip == A).count() == 1


def test_hors_demonstration_le_compte_reste_bloque_pour_tous(client, app):
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    for _ in range(5):
        essai(client, 'dge', 'mauvais', A)
    assert 'bloqué' in essai(client, 'dge', MDP, B).get_data(as_text=True)


def test_adresse_reelle_seulement_derriere_nginx(app):
    """X-Forwarded-For : cru depuis 127.0.0.1 (nginx), ignoré depuis une autre adresse."""
    from flask import request
    from app.utils.demo import ProxyDeConfiance
    vues = []

    @app.route('/_adresse')
    def _adresse():
        vues.append(request.remote_addr)
        return 'ok'
    app.wsgi_app = ProxyDeConfiance(app.wsgi_app)
    c = app.test_client()
    c.get('/_adresse', headers={'X-Forwarded-For': '41.158.1.2'}, environ_base={'REMOTE_ADDR': '127.0.0.1'})
    c.get('/_adresse', headers={'X-Forwarded-For': '41.158.1.2'}, environ_base={'REMOTE_ADDR': '10.9.9.9'})
    assert vues == ['41.158.1.2', '10.9.9.9']


def test_page_publique_du_qr_avec_bandeau(client, demo):
    assert 'data-demo' in client.get('/q/code-inconnu').get_data(as_text=True)
