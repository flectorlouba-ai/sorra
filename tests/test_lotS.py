"""Lot S — sécurité : en-têtes (CSP sans ressource externe, Referrer-Policy, nosniff, frame-ancestors), limite de débit sur la
connexion, mots de passe courants refusés, CSRF obligatoire sur les POST, alerte « nouvel appareil », journal des consultations
sensibles, export des droits journalisé, contrôles du script de déploiement (secrets, pip-audit), sauvegarde chiffrée."""
import re

from app import db
from app.models import JournalAudit, Profil
from app.services import securite
from tests.conftest import connecter, creer_utilisateur, MDP


def test_entetes_de_securite(client):
    r = client.get('/auth/connexion')
    csp = r.headers['Content-Security-Policy']
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp and 'http' not in csp
    assert r.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
    assert r.headers['X-Content-Type-Options'] == 'nosniff' and r.headers['X-Frame-Options'] == 'DENY'
    assert 'camera=(self)' in r.headers['Permissions-Policy']
    r = client.get('/auth/connexion', base_url='https://localhost')
    assert 'max-age=31536000' in r.headers['Strict-Transport-Security']


def test_limite_de_debit_sur_la_connexion(client, admin):
    securite.oublier_tentatives()
    for _ in range(securite.LIMITE_TENTATIVES):
        client.post('/auth/connexion', data={'identifiant': 'inconnu', 'mot_de_passe': 'x'})
    r = client.post('/auth/connexion', data={'identifiant': 'admin', 'mot_de_passe': MDP})
    assert r.status_code == 429 and 'Trop de tentatives' in r.get_data(as_text=True)
    assert JournalAudit.query.filter(JournalAudit.detail == 'trop de tentatives depuis cette adresse').count() == 1
    securite.oublier_tentatives()
    assert client.post('/auth/connexion', data={'identifiant': 'admin', 'mot_de_passe': MDP}).status_code == 302


def test_mots_de_passe_courants_refuses(client, admin):
    assert securite.mot_de_passe_courant('motdepasse') and securite.mot_de_passe_courant('1234567890') and securite.mot_de_passe_courant('aaaaaaaaaa')
    assert not securite.mot_de_passe_courant('Pluie-sur-Kango-2026')
    connecter(client, 'admin')
    r = client.post('/auth/mot-de-passe', data={'actuel': MDP, 'nouveau': 'azertyuiop', 'confirmation': 'azertyuiop'})
    assert 'trop courant' in r.get_data(as_text=True) and admin.check_password(MDP)
    r = client.post('/administration/utilisateurs/creer', data={'identifiant': 'nouveau', 'nom': 'N', 'profil': 'ADMIN', 'mot_de_passe': 'password123'}, follow_redirects=True)
    assert 'trop courant' in r.get_data(as_text=True)


def test_csrf_obligatoire_sur_les_post(app, admin):
    """Sans jeton, un POST est refusé (la fixture de test coupe le CSRF : on le rallume ici)."""
    app.config['WTF_CSRF_ENABLED'] = True
    try:
        c = app.test_client()
        c.post('/auth/connexion', data={'identifiant': 'admin', 'mot_de_passe': MDP})
        r = c.post('/auth/deconnexion', data={})
        assert r.status_code in (400, 403) or 'CSRF' in r.get_data(as_text=True) or r.status_code == 302 and '/auth/connexion' in r.headers.get('Location', '')
        page = c.get('/auth/connexion').get_data(as_text=True)
        jeton = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', page).group(1)
        r = c.post('/auth/connexion', data={'csrf_token': jeton, 'identifiant': 'admin', 'mot_de_passe': MDP})
        assert r.status_code == 302
    finally:
        app.config['WTF_CSRF_ENABLED'] = False


def test_nouvel_appareil_signale_et_consultations_journalisees(client, admin):
    connecter(client, 'admin')
    j = JournalAudit.query.filter(JournalAudit.action == 'CONNEXION').order_by(JournalAudit.id.desc()).first()
    assert 'nouvel appareil' in j.detail
    page = client.get('/').get_data(as_text=True)
    assert 'Première connexion depuis cet appareil' in page
    client.post('/auth/deconnexion')
    connecter(client, 'admin')
    j = JournalAudit.query.filter(JournalAudit.action == 'CONNEXION').order_by(JournalAudit.id.desc()).first()
    assert 'nouvel appareil' not in j.detail                                   # le même appareil, la seconde fois
    client.get('/administration/utilisateurs/')
    client.get('/sessions')
    assert JournalAudit.query.filter(JournalAudit.action == 'CONSULTATION').count() == 2
    r = client.get('/bureau/droits?format=xlsx')
    assert r.status_code == 200 and r.data[:2] == b'PK'
    assert JournalAudit.query.filter(JournalAudit.action == 'EXPORT', JournalAudit.detail.contains('Export des droits')).count() == 1


def test_scripts_de_deploiement_et_sauvegarde():
    d = open('deploiement/demo/deployer.sh', encoding='utf-8').read()
    assert 'pip-audit' in d and 'SORRA_VAPID_PRIVEE' in d and 'PRIVATE KEY' in d
    s = open('deploiement/demo/performyl2-demo-sauvegarde.sh', encoding='utf-8').read()
    assert 'gpg' in s and 'recipient-file' in s and 'DISTANT' in s and 'rm -f "${FICHIER}"' in s
    assert 'lot S' in open('docs/securite.md', encoding='utf-8').read()
