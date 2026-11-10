"""Lot T — notifications Web Push (préférences, abonnement, clé d'unicité, qui reçoit quoi, alertes sanitaires
non désactivables, texte sans donnée personnelle, envoi journalisé sans clés), actions de l'agent sur le téléphone
(ligne d'état, encadré, écran, feuille), fiche papier de la semaine (PDF, périmètre)."""
from datetime import date, timedelta

import pytest

from app import db
from app.models import JournalAudit, Profil
from app.models.action import Action
from app.models.notification import AbonnementPush, Notification, PreferenceNotification, TypeNotification as T
from app.services import actions as regles_actions, bandes, notifications
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401

ABONNEMENT = {'endpoint': 'https://push.example/abc', 'keys': {'p256dh': 'P' * 20, 'auth': 'A' * 10}}


def _journal(texte):
    return JournalAudit.query.filter(JournalAudit.detail.contains(texte)).count()


# ── A. Notifications ────────────────────────────────────────────────────

def test_abonnement_et_preferences_depuis_le_telephone(client, monde):
    connecter(client, 'eleveur1')
    r = client.get('/notifications/cle-publique')
    assert r.status_code == 200 and r.json['cle'] is None                    # pas de clé VAPID en test
    assert set(r.json['types']) == set(T.PAR_PROFIL['ELEVEUR'])
    r = client.post('/notifications/abonner', json={'abonnement': ABONNEMENT, 'appareil': 'iPhone'})
    assert r.status_code == 200
    a = AbonnementPush.query.one()
    assert a.utilisateur_id == monde['el'].id and a.actif and a.appareil == 'iPhone'
    assert _journal('Téléphone abonné') == 1
    assert client.post('/notifications/abonner', json={'abonnement': {'endpoint': 'x'}}).status_code == 400
    # Écran « Mes notifications » : interrupteurs par type, heure du rappel, ventes bloquées non désactivable
    page = client.get('/moi/notifications').get_data(as_text=True)
    assert '🔔 Mes notifications' in page and 'name="type_SAISIE_OUBLIEE"' in page and 'name="heure"' in page
    assert 'name="type_VENTES_BLOQUEES" value="1" checked disabled' in page
    assert 'name="type_FEU_ROUGE"' not in page                              # type de l'agent : pas pour l'éleveur
    r = client.post('/moi/notifications', data={'type_PESEE_RETARD': '1', 'heure': '19', 'type_VENTES_BLOQUEES': '0'})
    assert r.status_code == 302
    el = monde['el']
    assert notifications.actif(el, T.SAISIE_OUBLIEE) is False and notifications.actif(el, T.PESEE_RETARD) is True
    assert notifications.actif(el, T.VENTES_BLOQUEES) is True               # jamais coupé
    assert notifications.heure_rappel(el) == 19
    assert _journal('Préférences de notification modifiées') == 1
    client.post('/notifications/desabonner', json={'abonnement': ABONNEMENT})
    assert AbonnementPush.query.one().actif is False
    assert '🔔 Mes notifications' in client.get('/moi').get_data(as_text=True)


def test_notification_unique_texte_court_envoi_journalise_sans_cles(client, monde):
    el = monde['el']
    n = notifications.notifier(el, T.PESEE_RETARD, 'pesee:1:2026-11-10', '⚖️ Pesée en retard', 'Pensez à peser.', '/aller/peser')
    assert n is not None and notifications.notifier(el, T.PESEE_RETARD, 'pesee:1:2026-11-10', 'x', 'y') is None
    assert Notification.query.count() == 1
    notifications.regler(el, T.PESEE_RETARD, False)
    assert notifications.notifier(el, T.PESEE_RETARD, 'pesee:1:autre', 'x', 'y') is None   # coupée : rien
    notifications.regler(el, T.VENTES_BLOQUEES, False)                                     # sans effet
    assert notifications.actif(el, T.VENTES_BLOQUEES)
    assert notifications.envoyer(n) is False and n.resultat == 'sans_abonnement'
    notifications.abonner(el, ABONNEMENT)
    n2 = notifications.notifier(el, T.VACCIN_DEMAIN, 'vaccin:1:2', '💉 Vaccin demain', 'Un vaccin est à faire demain.')
    assert notifications.envoyer(n2) is False and n2.resultat == 'sans_cles' and n2.envoyee_le is not None
    for x in Notification.query:
        assert el.nom not in x.texte and 'eleveur1' not in x.texte and len(x.texte) <= 200
    assert notifications.envoyer_en_attente() == 0


def test_evenements_eleveur_et_agent_selon_le_profil(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=20))
    el, agent = monde['el'], monde['agent']
    # 1. Rappel du soir : à 18 h sans saisie du jour → notification ; avant l'heure : rien
    from datetime import datetime
    tot = datetime.combine(AUJ, datetime.min.time()).replace(hour=9)
    notifications.calculer(tot)
    assert Notification.query.filter_by(utilisateur_id=el.id, type=T.SAISIE_OUBLIEE).count() == 0
    soir = tot.replace(hour=18)
    notifications.calculer(soir)
    assert Notification.query.filter_by(utilisateur_id=el.id, type=T.SAISIE_OUBLIEE).count() == 1
    notifications.calculer(soir)                                                               # même jour : pas deux fois
    assert Notification.query.filter_by(utilisateur_id=el.id, type=T.SAISIE_OUBLIEE).count() == 1
    # 2. Pesée en retard pour l'éleveur ; l'agent n'a aucune notification « éleveur »
    assert Notification.query.filter_by(utilisateur_id=el.id, type=T.PESEE_RETARD).count() == 1
    assert Notification.query.filter(Notification.utilisateur_id == agent.id,
                                     Notification.type.in_(T.PAR_PROFIL['ELEVEUR'])).count() == 0
    # 3. Ferme sans saisie depuis 2 jours → l'agent
    assert Notification.query.filter_by(utilisateur_id=agent.id, type=T.FERME_SANS_SAISIE).count() == 1
    # 4. Action en retard → l'agent responsable, pas l'autre agent
    a = regles_actions.creer(agent, 'Vérifier l\'abreuvoir', AUJ - timedelta(days=2), ferme=monde['f'])
    db.session.commit()
    notifications.calculer(soir)
    assert Notification.query.filter_by(utilisateur_id=agent.id, type=T.ACTION_RETARD).count() == 1
    autre = next(u for u in [creer_utilisateur('agent3', Profil.AGENT, ['EST'])])
    notifications.calculer(soir)
    assert Notification.query.filter_by(utilisateur_id=autre.id).count() == 0
    # 5. Les types reçus par chacun sont ceux de son profil
    for n in Notification.query:
        assert n.type in T.PAR_PROFIL[n.utilisateur.profil.value]


def test_alerte_sanitaire_immediate_agent_veto_dge(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    veto = creer_utilisateur('veto', Profil.VETO, ['EST'])
    dge = creer_utilisateur('dge', Profil.DGE)
    autre_veto = creer_utilisateur('veto_nord', Profil.VETO, ['WNT'])
    from app.services import sante
    db.session.commit()
    sante._nouvelle_alerte(monde['f'], b, 'FEU_ROUGE', commentaire='essai')
    db.session.commit()
    assert Notification.query.filter_by(utilisateur_id=monde['agent'].id, type=T.FEU_ROUGE).count() == 1
    assert Notification.query.filter_by(utilisateur_id=veto.id, type=T.ALERTE_SANITAIRE).count() == 1
    assert Notification.query.filter_by(utilisateur_id=dge.id, type=T.ALERTE_SANITAIRE).count() == 1
    assert Notification.query.filter_by(utilisateur_id=autre_veto.id).count() == 0        # hors province
    n = Notification.query.filter_by(utilisateur_id=veto.id).one()
    assert n.envoyee_le is not None and n.resultat == 'sans_abonnement'                     # tentative immédiate
    assert 'eleveur1' not in n.texte and monde['el'].nom not in n.texte


def test_commande_notifications_envoyer(app, monde):
    runner = app.test_cli_runner()
    r = runner.invoke(args=['notifications-envoyer'])
    assert r.exit_code == 0 and 'clés VAPID absentes' in r.output


# ── B. Actions de l'agent sur le téléphone ──────────────────────────────

def test_actions_agent_telephone_ligne_etat_encadre_feuille(client, monde):
    agent = monde['agent']
    a = regles_actions.creer(agent, 'Réparer la clôture', AUJ - timedelta(days=3), ferme=monde['f'])
    a2 = regles_actions.creer(agent, 'Appeler le fournisseur', AUJ + timedelta(days=4))
    db.session.commit()
    connecter(client, 'agent1')
    accueil = client.get('/').get_data(as_text=True)
    assert '🎯 1 action en retard' in accueil and 'data-mes-actions' in accueil and '🎯 Mes actions (2)' in accueil
    assert accueil.count('class="tuile') >= 7                                   # les tuiles sont toujours là
    page = client.get('/terrain/actions').get_data(as_text=True)
    assert page.index('Réparer la clôture') < page.index('Appeler le fournisseur')   # la plus urgente d'abord
    assert 'en retard de 3 jours' in page and 'pour le' in page and f'fiche-action-{a.id}' in page
    assert 'data-hors-ligne="Action ' in page and '＋ Nouvelle action' in page
    r = client.post(f'/terrain/actions/{a.id}', data={'etat': 'en_cours', 'commentaire': 'Poteaux achetés'})
    assert r.status_code == 302 and a.avancement > 0 and a.etat == 'RETARD'
    r = client.post(f'/terrain/actions/{a.id}', data={'etat': 'fait', 'commentaire': 'Clôture réparée'})
    assert a.etat == 'FAITE' and a.commentaire == 'Clôture réparée'
    assert '🎯 Mes actions (1)' in client.get('/').get_data(as_text=True)
    assert '🎯 Mes actions' in client.get('/terrain/moi').get_data(as_text=True)
    # L'autre agent ne voit pas ces actions, ni ne peut les modifier
    client.post('/auth/deconnexion')
    connecter(client, 'agent2')
    assert 'Réparer la clôture' not in client.get('/terrain/actions').get_data(as_text=True)
    assert client.post(f'/terrain/actions/{a2.id}', data={'etat': 'fait'}).status_code == 404
    # Création depuis le téléphone (formulaire du lot D, retour à l'écran terrain)
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    r = client.post('/actions/creer', data={'intitule': 'Livrer l\'aliment', 'echeance': (AUJ + timedelta(days=2)).isoformat(),
                                            'ferme': monde['f'].numero, 'retour': '/terrain/actions'})
    assert r.status_code == 302 and r.headers['Location'].endswith('/terrain/actions')
    assert Action.query.filter_by(intitule="Livrer l'aliment").one().responsable_id == agent.id


def test_actions_terrain_reservees_a_l_agent_et_hors_ligne(client, monde):
    connecter(client, 'eleveur1')
    assert client.get('/terrain/actions').status_code in (403, 404)
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    pages = client.get('/hors-ligne/pages').json
    assert '/terrain/actions' in pages['pages'] and '/moi/notifications' in pages['pages']


# ── C. Fiche papier de la semaine ───────────────────────────────────────

def test_fiche_papier_semaine_pdf(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=15))
    bandes.saisir(b, AUJ, 2, {monde['aliment']: 3}, monde['el'])
    db.session.commit()
    connecter(client, 'eleveur1')
    assert f'data-fiche-semaine="{b.numero}"' in client.get('/ma-bande').get_data(as_text=True)
    r = client.get(f'/bandes/{b.numero}/fiche-semaine.pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF' and len(r.data) > 2500
    assert r.headers['Content-Disposition'].startswith('inline')
    assert _journal('Fiche papier de la semaine imprimée') == 1
    from app.services import fiche_semaine
    assert len(fiche_semaine.semaine_de(AUJ)) == 7 and fiche_semaine.semaine_de(AUJ)[0].weekday() == 0
    vide = fiche_semaine.fiche_pdf(bande_ouverte(monde, jour=AUJ - timedelta(days=1), bat=1))
    assert vide[:4] == b'%PDF' and len(vide) != len(r.data)                     # contenu propre à la bande
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert f'data-fiche-semaine="{b.numero}"' in client.get(f'/terrain/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert client.get(f'/bandes/{b.numero}/fiche-semaine.pdf').status_code == 200
    client.post('/auth/deconnexion')
    connecter(client, 'agent2')                                                  # hors périmètre
    assert client.get(f'/bandes/{b.numero}/fiche-semaine.pdf').status_code == 403
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    client.post('/auth/deconnexion')
    connecter(client, 'veto')
    assert client.get(f'/bandes/{b.numero}/fiche-semaine.pdf').status_code == 403


def test_service_worker_push(client, monde):
    sw = client.get('/sw.js').get_data(as_text=True)
    assert "addEventListener('push'" in sw and "addEventListener('notificationclick'" in sw
