"""Lot 15 — quatre yeux (l'auteur n'approuve pas, ancienne valeur avant approbation, refus), journal chaîné
(intact puis rupture simulée détectée), sessions (fermeture, 30 min pour le pilotage, jamais pour l'éleveur
ni l'agent), double authentification (obligatoire selon le profil, code faux, code de secours à usage unique,
réinitialisation par l'ADMIN)."""
import time

import pytest
from sqlalchemy import text

from app import db
from app.models import Parametre, Profil, JournalAudit, Utilisateur
from app.models.securite import Proposition, SessionUtilisateur
from app.services import approbations, parametres, securite
from app.services.journal import Action, verifier_chaine, enregistrer
from tests.conftest import connecter, creer_utilisateur


def changer(client, identifiant, mdp=None):
    client.post('/auth/deconnexion')
    return connecter(client, identifiant) if mdp is None else connecter(client, identifiant, mdp)


# ── Quatre yeux ─────────────────────────────────────────────────────────

def test_parametre_sensible_quatre_yeux(client, app):
    creer_utilisateur('admin', Profil.ADMIN)
    creer_utilisateur('dge', Profil.DGE)
    p = Parametre.query.filter_by(cle='bandes.seuil_rouge_pct').one()
    connecter(client, 'admin')
    page = client.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': '2'}, follow_redirects=True)
    assert 'Indiquez le motif' in page.get_data(as_text=True)
    client.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': '2', 'motif': 'trop d\'alertes'})
    db.session.refresh(p)
    assert p.valeur == '1'                                           # l'ancienne valeur s'applique
    prop = Proposition.query.one()
    assert (prop.avant, prop.apres, prop.statut) == ('1', '2', 'EN_ATTENTE')
    # L'auteur ne peut pas approuver
    client.post(f'/approbations/{prop.id}', data={'decision': 'approuver'})
    db.session.refresh(prop)
    assert prop.statut == 'EN_ATTENTE'
    assert 'Rien à approuver' in client.get('/approbations').get_data(as_text=True)
    # Une autre personne habilitée approuve
    changer(client, 'dge')
    assert 'trop d&#39;alertes' in client.get('/approbations').get_data(as_text=True)
    client.post(f'/approbations/{prop.id}', data={'decision': 'approuver'})
    db.session.refresh(prop)
    db.session.refresh(p)
    assert prop.statut == 'APPROUVEE' and p.valeur == '2'
    assert JournalAudit.query.filter_by(action=Action.PROPOSITION).count() == 1
    assert JournalAudit.query.filter_by(action=Action.APPROBATION).count() == 1


def test_refus_avec_motif_et_reglage_non_sensible_direct(client, app):
    admin = creer_utilisateur('admin', Profil.ADMIN)
    dge = creer_utilisateur('dge', Profil.DGE)
    p = Parametre.query.filter_by(cle='securite.profils_2fa').one()
    prop = approbations.proposer('PARAMETRE', p.cle, p.description, p.valeur, 'ADMIN', {'valeur': 'ADMIN'}, 'essai', admin)
    db.session.commit()
    with pytest.raises(approbations.RegleApprobation):
        approbations.decider(prop, dge, False, '')                   # refus : motif obligatoire
    approbations.decider(prop, dge, False, 'non')
    db.session.commit()
    assert prop.statut == 'REFUSEE' and Parametre.query.filter_by(cle='securite.profils_2fa').one().valeur != 'ADMIN'
    # Réglage non sensible : direct
    q = Parametre.query.filter_by(cle='securite.mdp_longueur_min').one()
    connecter(client, 'admin')
    client.post(f'/administration/parametres/{q.id}/modifier', data={'valeur': '12'})
    db.session.refresh(q)
    assert q.valeur == '12'


def test_le_veto_decide_seulement_le_sanitaire(client, app):
    admin = creer_utilisateur('admin', Profil.ADMIN)
    veto = creer_utilisateur('veto', Profil.VETO, ['EST'])
    sanitaire = approbations.proposer('PARAMETRE', 'sante.retard_vaccin_jours', 'Retard', '2', '3', {'valeur': '3'}, 'x', admin)
    general = approbations.proposer('PARAMETRE', 'verifications.delai_rouge_heures', 'Délai', '48', '24', {'valeur': '24'}, 'x', admin)
    db.session.commit()
    assert approbations.a_decider(veto) == [sanitaire]
    assert approbations.peut_decider(veto, sanitaire) and not approbations.peut_decider(veto, general)


def test_changement_de_profil_quatre_yeux(client, app):
    creer_utilisateur('admin', Profil.ADMIN)
    dge = creer_utilisateur('dge', Profil.DGE)
    u = creer_utilisateur('agent1', Profil.AGENT, ['EST'])
    connecter(client, 'admin')
    from tests.conftest import province
    client.post(f'/administration/utilisateurs/{u.id}/modifier', data={
        'nom': u.nom, 'profil': 'VETO', 'provinces': [str(province('EST').id)], 'actif': 'on'})
    db.session.refresh(u)
    assert u.profil == Profil.AGENT
    prop = Proposition.query.filter_by(genre='PROFIL').one()
    approbations.decider(prop, dge, True)
    db.session.commit()
    db.session.refresh(u)
    assert u.profil == Profil.VETO


# ── Journal chaîné ──────────────────────────────────────────────────────

def test_journal_chaine_intact_puis_rupture_detectee(client, app):
    creer_utilisateur('admin', Profil.ADMIN)
    creer_utilisateur('audit', Profil.AUDITEUR)
    for i in range(3):
        enregistrer(Action.EXPORT, detail=f'essai {i}')
        db.session.commit()
    intact, n, rompue = verifier_chaine()
    assert intact and n == JournalAudit.query.count() and rompue is None
    connecter(client, 'audit')
    assert '✓ Journal intact' in client.get('/integrite').get_data(as_text=True)
    # Rupture simulée (hors application : la base de test n'a pas le déclencheur de la migration)
    cible = JournalAudit.query.filter_by(detail='essai 1').one()
    db.session.execute(text("UPDATE journal_audit SET detail = 'falsifié' WHERE id = :i"), {'i': cible.id})
    db.session.commit()
    db.session.expire_all()
    intact, _, rompue = verifier_chaine()
    assert not intact and rompue.id == cible.id
    assert f"Rupture à l&#39;entrée n° {cible.id}" in client.get('/integrite').get_data(as_text=True).replace("l'entrée", 'l&#39;entrée')


# ── Sessions ────────────────────────────────────────────────────────────

def test_sessions_enregistrees_et_fermees_par_l_admin(client, app):
    creer_utilisateur('admin', Profil.ADMIN)
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    s = SessionUtilisateur.query.one()
    assert s.fermee_le is None and s.appareil
    assert 'cette session' in client.get('/auth/securite').get_data(as_text=True)   # chacun voit les siennes
    # L'ADMIN la ferme depuis un autre poste (même service que l'écran Sessions) : refusée à la requête suivante
    admin = Utilisateur.query.filter_by(identifiant='admin').one()
    securite.fermer(s.id, admin, 'appareil perdu')
    db.session.commit()
    r = client.get('/')
    assert r.status_code == 302 and '/auth/connexion' in r.location
    assert db.session.get(SessionUtilisateur, s.id).motif_fermeture == 'appareil perdu'
    # L'écran Sessions de l'ADMIN : liste, et « Fermer cette session »
    connecter(client, 'dge')
    sid_dge = SessionUtilisateur.query.filter(SessionUtilisateur.fermee_le.is_(None)).one().id
    changer(client, 'admin')
    page = client.get('/sessions').get_data(as_text=True)
    assert 'Fermer cette session' in page and 'Admin' in page
    autre = SessionUtilisateur(id='autre-appareil', utilisateur_id=Utilisateur.query.filter_by(identifiant='dge').one().id,
                               appareil='Android · Chrome')
    db.session.add(autre)
    db.session.commit()
    assert 'Android · Chrome' in client.get('/sessions').get_data(as_text=True)
    client.post('/auth/sessions/autre-appareil/fermer', data={'motif': 'perdu'})
    assert db.session.get(SessionUtilisateur, 'autre-appareil').fermee_le is not None
    assert sid_dge != 'autre-appareil'


def test_inactivite_30_min_pilotage_jamais_eleveur_ni_agent(client, app):
    assert parametres.obtenir('securite.duree_session_minutes') == 30
    for ident, profil, expire in (('dge', Profil.DGE, True), ('agent', Profil.AGENT, False), ('el', Profil.ELEVEUR, False)):
        creer_utilisateur(ident, profil, ['EST'] if profil == Profil.AGENT else [])
        connecter(client, ident)
        with client.session_transaction() as s:
            s['derniere_activite'] = time.time() - 31 * 60
        r = client.get('/auth/securite')
        assert (r.status_code == 302 and '/auth/connexion' in r.location) is expire, ident
        client.post('/auth/deconnexion')


# ── Double authentification ─────────────────────────────────────────────

@pytest.fixture
def avec_2fa(app):
    app.config['DEUX_FACTEURS'] = True
    yield
    app.config['DEUX_FACTEURS'] = False


def test_2fa_obligatoire_mise_en_place_code_faux_et_secours(client, app, avec_2fa):
    u = creer_utilisateur('dge', Profil.DGE)
    r = client.post('/auth/connexion', data={'identifiant': 'dge', 'mot_de_passe': 'MotDePasse-2026'})
    assert r.location.endswith('/auth/2fa/mise-en-place')            # obligatoire pour la DGE
    assert client.get('/').status_code == 302                        # pas encore connecté
    page = client.get('/auth/2fa/mise-en-place').get_data(as_text=True)
    assert 'data:image/svg+xml;base64,' in page and 'otpauth' not in page
    with client.session_transaction() as s:
        secret = s['2fa_secret']
    assert 'Code incorrect' in client.post('/auth/2fa/mise-en-place', data={'code': '000000'}).get_data(as_text=True)
    r = client.post('/auth/2fa/mise-en-place', data={'code': securite.code_actuel(secret)})
    assert r.location.endswith('/auth/2fa/codes-de-secours')
    page = client.get('/auth/2fa/codes-de-secours').get_data(as_text=True)
    import re
    codes = re.findall(r'<code class="mono">(\d{4}-\d{4})</code>', page)
    assert len(codes) == 8
    assert client.get('/auth/2fa/codes-de-secours').status_code == 302   # affichés une seule fois
    db.session.refresh(u)
    assert u.totp_active and len(u.codes_secours) == 8 and codes[0] not in str(u.codes_secours)   # hachés
    # Connexion suivante : code faux refusé, code de secours à usage unique
    client.post('/auth/deconnexion')
    client.post('/auth/connexion', data={'identifiant': 'dge', 'mot_de_passe': 'MotDePasse-2026'})
    assert 'Code incorrect' in client.post('/auth/2fa', data={'code': '123456'}).get_data(as_text=True)
    r = client.post('/auth/2fa', data={'code': codes[0]})
    assert r.location.endswith('/') and client.get('/').status_code == 200
    client.post('/auth/deconnexion')
    client.post('/auth/connexion', data={'identifiant': 'dge', 'mot_de_passe': 'MotDePasse-2026'})
    assert 'Code incorrect' in client.post('/auth/2fa', data={'code': codes[0]}).get_data(as_text=True)
    r = client.post('/auth/2fa', data={'code': securite.code_actuel(secret)})
    assert client.get('/').status_code == 200


def test_2fa_facultative_jamais_eleveur_et_reinitialisation(client, app, avec_2fa):
    creer_utilisateur('admin', Profil.ADMIN)
    agent = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    el = creer_utilisateur('el', Profil.ELEVEUR)
    assert not securite.a_demander(agent) and not securite.a_demander(el)          # facultative ; jamais
    el.totp_active, el.totp_secret = True, securite.nouveau_secret()
    assert not securite.a_demander(el)
    r = client.post('/auth/connexion', data={'identifiant': 'agent', 'mot_de_passe': 'MotDePasse-2026'})
    assert r.location.endswith('/')                                                # pas de second facteur
    # L'agent l'active lui-même, puis l'ADMIN la réinitialise avec motif
    client.get('/auth/2fa/mise-en-place')
    with client.session_transaction() as s:
        secret = s['2fa_secret']
    client.post('/auth/2fa/mise-en-place', data={'code': securite.code_actuel(secret)})
    db.session.refresh(agent)
    assert agent.totp_active and securite.a_demander(agent)
    # (2FA obligatoire pour l'ADMIN : on la coupe le temps de cette partie d'administration)
    app.config['DEUX_FACTEURS'] = False
    changer(client, 'admin')
    assert 'Indiquez le motif' in client.post(f'/administration/utilisateurs/{agent.id}/reinitialiser-2fa',
                                                data={'motif': ''}, follow_redirects=True).get_data(as_text=True)
    client.post(f'/administration/utilisateurs/{agent.id}/reinitialiser-2fa', data={'motif': 'téléphone perdu'})
    db.session.refresh(agent)
    assert not agent.totp_active and agent.totp_secret is None
    assert 'téléphone perdu' in JournalAudit.query.filter(JournalAudit.detail.like('%réinitialisée%')).one().detail


def test_totp_conforme_rfc6238():
    # Vecteur de test de la RFC 6238 (SHA-1, 8 chiffres ramenés à 6) : secret « 12345678901234567890 »
    import base64
    secret = base64.b32encode(b'12345678901234567890').decode()
    assert securite.code_actuel(secret, 59) == '287082'
    assert securite.verifier_code(secret, '287082', 59) and not securite.verifier_code(secret, '287083', 59)
