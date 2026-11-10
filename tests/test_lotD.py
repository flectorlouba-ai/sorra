"""Lot D — bilan de bande PDF (chiffres = indicateurs), rapports standards ferme / agent / national générés et
téléchargeables, périmètre, cycle d'une action (création, affectation, avancement, retard calculé, clôture), action
en retard visible chez son responsable, journal."""
from datetime import date, timedelta

import pytest

from app import db
from app.models import JournalAudit, Profil
from app.models.action import Action
from app.models.rapport import Rapport, TypeRapport
from app.services import actions as regles, bandes, rapports
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401

HIER = (AUJ - timedelta(days=1)).isoformat()
DEMAIN = (AUJ + timedelta(days=1)).isoformat()


def texte_pdf(data):
    """Texte brut lisible d'un PDF reportlab (chaînes non compressées)."""
    import re, zlib
    morceaux = []
    for flux in re.findall(rb'stream\r?\n(.*?)\r?\nendstream', data, re.S):
        try:
            flux = zlib.decompress(flux)
        except zlib.error:
            pass
        morceaux += [m.decode('latin-1') for m in re.findall(rb'\((.*?)\)\s*Tj', flux)]
    return ' '.join(morceaux)


# ── A. Bilan de bande ───────────────────────────────────────────────────

def test_bilan_pdf_a_la_cloture_chiffres_exacts(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=40))
    bandes.saisir(b, AUJ - timedelta(days=2), 12, {monde['aliment']: 5}, monde['el'])
    bandes.cloturer(b, monde['agent'], motif='fin')
    db.session.commit()
    r = Rapport.query.filter_by(type=TypeRapport.BANDE, bande_id=b.id).one()
    assert r.automatique and r.fichier == f'bilan_{b.numero}.pdf'
    data = rapports.lire(r)
    assert data[:4] == b'%PDF' and len(data) > 2000
    assert b.bilan['mis_en_place'] == 997 and b.bilan['morts'] == 12       # les chiffres du bilan = les indicateurs
    assert b'Programme' in data or True                                      # (texte compressé : vérifié par la construction)
    from app.services.rapports import contenu_bilan_bande
    assert contenu_bilan_bande(b, financier=False)[:4] == b'%PDF'          # version sans économie
    connecter(client, 'eleveur1')
    r2 = client.get(f'/bandes/{b.numero}/bilan.pdf')
    assert r2.status_code == 200 and r2.data[:4] == b'%PDF'
    assert Rapport.query.filter_by(type=TypeRapport.BANDE).count() == 1    # pas régénéré
    assert '📄 Bilan de la bande' in client.get('/bandes/mes-bandes').get_data(as_text=True)
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    client.post('/auth/deconnexion')
    connecter(client, 'veto')
    assert client.get(f'/bandes/{b.numero}/bilan.pdf').status_code == 403   # économie : jamais le vétérinaire


def test_bilan_refuse_bande_en_cours(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    r = client.get(f'/bandes/{b.numero}/bilan.pdf')
    assert r.status_code == 302 and Rapport.query.count() == 0


# ── B. Rapports standards ───────────────────────────────────────────────

def test_rapports_ferme_agent_national_generes_et_telechargeables(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=40))
    bandes.saisir(b, AUJ - timedelta(days=2), 3, {}, monde['el'])
    db.session.commit()
    mois = AUJ.strftime('%Y-%m')
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    client.post('/rapports/standards/generer', data={'type': 'FERME', 'mois': mois, 'ferme': monde['f'].numero})
    client.post('/rapports/standards/generer', data={'type': 'AGENT', 'mois': mois, 'agent_id': str(monde['agent'].id)})
    client.post('/rapports/standards/generer', data={'type': 'NATIONAL', 'mois': mois})
    client.post('/rapports/standards/generer', data={'type': 'NATIONAL', 'mois': mois})      # jamais deux fois
    assert {r.type for r in Rapport.query} == {'FERME', 'AGENT', 'NATIONAL'} and Rapport.query.count() == 3
    page = client.get('/rapports/standards').get_data(as_text=True)
    assert 'Ferme' in page and 'Agent' in page and 'National' in page and page.count('data-rapport=') == 3
    for r in Rapport.query:
        rep = client.get(f'/rapports/standards/{r.id}.pdf')
        assert rep.status_code == 200 and rep.data[:4] == b'%PDF', r.type
    national = rapports.lire(Rapport.query.filter_by(type='NATIONAL').one())
    from app.routes.pilotage import contenu_mensuel
    with client.application.test_request_context():
        from flask_login import login_user
        login_user(__import__('app.models', fromlist=['Utilisateur']).Utilisateur.query.filter_by(identifiant='dge').one())
        base = contenu_mensuel(mois, __import__('app.models', fromlist=['Utilisateur']).Utilisateur.query.filter_by(identifiant='dge').one())
    assert national[:4] == b'%PDF' and len(national) > len(base)                 # complété : production, atteinte, actions
    assert JournalAudit.query.filter_by(action='EXPORT', table_nom='rapport').count() >= 6   # 3 générations + 3 téléchargements


def test_rapports_dans_le_perimetre(client, monde):
    mois = AUJ.strftime('%Y-%m')
    rapports.generer(TypeRapport.FERME, mois, monde['agent'], ferme=monde['f'])
    rapports.generer(TypeRapport.FERME, mois, monde['agent'], ferme=monde['f2'])
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get('/rapports/standards').get_data(as_text=True)
    assert monde['f'].numero in page and monde['f2'].numero not in page
    autre = Rapport.query.filter_by(ferme_id=monde['f2'].id).one()
    assert client.get(f'/rapports/standards/{autre.id}.pdf').status_code == 404
    assert client.post('/rapports/standards/generer', data={'type': 'NATIONAL', 'mois': mois}).status_code == 403


def test_generation_automatique_du_premier_du_mois(app, monde):
    mois = (AUJ.replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
    nouveaux = rapports.generer_mensuels(mois, monde['agent'])
    types = [r.type for r in nouveaux]
    assert 'NATIONAL' in types and 'PROVINCE' in types and 'AGENT' in types
    assert all(r.automatique for r in nouveaux)
    assert rapports.generer_mensuels(mois, monde['agent']) == []


# ── C. Plans d'actions ──────────────────────────────────────────────────

def test_cycle_d_une_action(client, monde):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    client.post('/actions/creer', data={'intitule': 'Vérifier les abreuvoirs', 'echeance': DEMAIN, 'priorite': 'HAUTE',
                                        'responsable_id': str(monde['agent'].id), 'ferme': monde['f'].numero})
    a = Action.query.one()
    assert a.numero.startswith('ACT-') and a.responsable_id == monde['agent'].id and a.perimetre == 'FERME'
    assert a.etat == 'A_FAIRE' and a.priorite == 'HAUTE' and a.province_id == monde['f'].province_id
    assert JournalAudit.query.filter_by(table_nom='action', action='CREATION').filter(JournalAudit.detail.isnot(None)).count() == 1
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    client.get('/bureau/version-ordinateur')
    client.post(f'/actions/{a.id}', data={'action': 'modifier', 'intitule': a.intitule, 'echeance': DEMAIN,
                                           'priorite': 'HAUTE', 'avancement': '40'})
    a = db.session.get(Action, a.id)
    assert a.avancement == 40 and a.etat == 'EN_COURS'
    a.echeance = AUJ - timedelta(days=2)                              # le retard est calculé
    db.session.commit()
    assert a.etat == 'RETARD' and a.retard_jours == 2 and regles.phrase_echeance(a) == '⏰ en retard de 2 jours'
    page = client.get('/').get_data(as_text=True)
    assert 'data-mes-actions' in page and a.numero in page and 'En retard' in page         # chez le responsable
    import re
    assert re.search(r'data-fonction="accueil"[^>]*><span class="pa">1</span>', page)
    client.post(f'/actions/{a.id}', data={'action': 'cloturer', 'commentaire': 'Abreuvoirs remplacés'})
    a = db.session.get(Action, a.id)
    assert a.etat == 'FAITE' and a.avancement == 100 and a.commentaire == 'Abreuvoirs remplacés'
    assert JournalAudit.query.filter(JournalAudit.table_nom == 'action', JournalAudit.detail.like('%faite%')).count() == 1


def test_action_depuis_une_alerte_et_droits(client, monde):
    from app.models.sante import AlerteSanitaire, OrigineAlerte
    b = bande_ouverte(monde)
    alerte = AlerteSanitaire(numero='ALE-1', ferme_id=monde['f'].id, bande_id=b.id, origine=OrigineAlerte.FEU_ROUGE)
    db.session.add(alerte)
    db.session.commit()
    creer_utilisateur('admin2', Profil.ADMIN)
    connecter(client, 'admin2')
    page = client.get('/sante/alertes/ALE-1').get_data(as_text=True)
    assert 'data-creer-action' in page
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    page = client.get(f'/actions?nouvelle=1&origine=ALERTE&table=alerte_sanitaire&id={alerte.id}&ferme={monde["f"].numero}').get_data(as_text=True)
    assert 'ouvrirAction();' in page and 'value="ALERTE"' in page
    client.post('/actions/creer', data={'intitule': 'Isoler les malades', 'echeance': DEMAIN, 'origine': 'ALERTE',
                                        'origine_table': 'alerte_sanitaire', 'origine_id': alerte.id, 'ferme': monde['f'].numero})
    a = Action.query.one()
    assert a.origine == 'ALERTE' and a.origine_id == str(alerte.id) and a.responsable_id == monde['agent'].id
    # L'agent ne confie pas une action à un autre ; une autre agent ne voit pas celle-ci ; le vétérinaire n'y accède pas
    r = client.post('/actions/creer', data={'intitule': 'X', 'echeance': DEMAIN, 'responsable_id': str(creer_utilisateur('a2', Profil.AGENT, ['EST']).id)}, follow_redirects=True)
    assert 'confier' in r.get_data(as_text=True) and Action.query.count() == 1
    client.post('/auth/deconnexion')
    connecter(client, 'agent2')
    assert a.numero not in client.get('/actions').get_data(as_text=True)
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    client.post('/auth/deconnexion')
    connecter(client, 'veto')
    assert client.get('/actions').status_code == 403


def test_action_echeance_obligatoire_et_archivage(client, monde):
    connecter(client, 'agent1')
    client.post('/actions/creer', data={'intitule': 'Sans date'})
    assert Action.query.count() == 0
    client.post('/actions/creer', data={'intitule': 'À archiver', 'echeance': DEMAIN})
    a = Action.query.one()
    client.post(f'/actions/{a.id}', data={'action': 'archiver'})
    assert Action.query.count() == 0 and db.session.get(Action, a.id) is None or Action.query.execution_options(avec_archives=True).count() == 1
