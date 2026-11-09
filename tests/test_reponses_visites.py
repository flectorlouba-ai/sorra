"""Lot 12 — réponse du vétérinaire (visible par l'éleveur, pas par l'agent ; états simples ; pastilles) et
visites de l'agent (planifiée, compte rendu sans réseau, affichage chez l'éleveur, pastille « nouveau »)."""
import io
import re
from datetime import timedelta

from app import db
from app.models import JournalAudit, Profil
from app.models.sante import AlerteSanitaire, StatutAlerte as SA, ReponseVeterinaire
from app.models.visite import Visite, StatutVisite
from app.services import sante, visites
from app.services.journal import Action
from tests.conftest import connecter, creer_utilisateur
from tests.test_sante import monde, monde_bandes, declarer, JPEG, AUJ  # noqa: F401
from tests.test_bandes import bande_ouverte
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def repondre(client, a, **data):
    return client.post(f'/sante/alertes/{a.numero}/repondre', data=data, follow_redirects=True)


# ── Réponse du vétérinaire ─────────────────────────────────────────────

def test_reponse_du_veterinaire_etats_simples_et_pastilles(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    declarer(client, b)
    a = AlerteSanitaire.query.one()
    page = client.get('/sante/mes-declarations').get_data(as_text=True)
    assert 'Mes signalements' in page and 'Envoyé ✓' in page
    changer(client, 'veto')
    page = client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    assert "Réponse à l&#39;éleveur" in page.replace("Réponse à l'éleveur", "Réponse à l&#39;éleveur")
    assert 'Isolez les poulets malades' in page                       # conseils types à cocher
    assert 'Cochez un conseil' in repondre(client, a).get_data(as_text=True)
    client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.EN_ANALYSE, 'commentaire': 'je regarde'})
    changer(client, 'eleveur1')
    assert 'Le vétérinaire regarde' in client.get('/sante/mes-declarations').get_data(as_text=True)
    changer(client, 'veto')
    repondre(client, a, conseils=['Isolez les poulets malades', 'Je passe vous voir'], texte='Je viens jeudi.')
    r = ReponseVeterinaire.query.one()
    assert r.veto_id == monde['veto'].id and r.conseils == ['Isolez les poulets malades', 'Je passe vous voir']
    assert JournalAudit.query.filter_by(action=Action.REPONSE_VETO).count() == 1
    # L'éleveur : ligne d'état + pastille 💬, un toucher ouvre la réponse
    changer(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert '💬 Le vétérinaire vous a répondu' in accueil and 'href="/sante/mes-declarations"' in accueil
    assert re.search(r'data-tuile="soins">\s*<span class="pastille bleue">💬</span>', accueil)
    page = client.get('/sante/mes-declarations').get_data(as_text=True)
    assert '💬 Réponse du vétérinaire' in page and 'Isolez les poulets malades' in page and 'Je viens jeudi.' in page
    assert 'nouveau' in page and 'Confirmée' not in page and 'Infirmée' not in page
    db.session.refresh(r)
    assert r.lue_le is not None                                       # lue : plus de pastille
    accueil = client.get('/').get_data(as_text=True)
    assert 'Le vétérinaire vous a répondu' not in accueil and '💬</span>' not in accueil
    # Terminé : jamais « confirmée / infirmée »
    changer(client, 'veto')
    client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.CONFIRMEE, 'commentaire': 'Coccidiose'})
    changer(client, 'eleveur1')
    page = client.get('/sante/mes-declarations').get_data(as_text=True)
    assert 'Terminé' in page and 'Confirmée' not in page and 'Isolez les poulets malades' in page


def test_l_agent_voit_qu_une_reponse_a_ete_donnee_pas_le_contenu(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    declarer(client, b)
    a = AlerteSanitaire.query.one()
    changer(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'pas encore de réponse' in fiche
    assert client.post(f'/sante/alertes/{a.numero}/repondre', data={'conseils': ['x']}).status_code in (302, 403)
    changer(client, 'veto')
    repondre(client, a, conseils=['Ne vendez pas avant ma visite'], texte='Secret médical')
    changer(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'le vétérinaire a répondu le' in fiche
    assert 'Ne vendez pas avant ma visite' not in fiche and 'Secret médical' not in fiche
    assert 'Diarrhée' not in fiche                                    # ni les signes de la déclaration
    assert client.get(f'/sante/alertes/{a.numero}').status_code == 403


def test_reponse_sur_une_alerte_du_feu_rouge(client, monde):
    b = bande_ouverte(monde)
    a = sante._nouvelle_alerte(b.ferme, b, 'FEU_ROUGE')
    db.session.commit()
    connecter(client, 'veto')
    repondre(client, a, conseils=['Augmentez la ventilation'])
    changer(client, 'eleveur1')
    page = client.get('/sante/mes-declarations').get_data(as_text=True)
    assert 'beaucoup de morts' in page and 'Augmentez la ventilation' in page


# ── Visites de l'agent ─────────────────────────────────────────────────

def test_visite_planifiee_compte_rendu_hors_ligne_et_eleveur(client, monde):
    connecter(client, 'agent1')
    numero = monde['f'].numero
    demain = AUJ + timedelta(days=1)
    page = client.get(f'/fermes/{numero}/visites/planifier').get_data(as_text=True)
    for objet in ('Suivi', 'Vaccination', 'Contrôle', 'Panne', 'Autre'):
        assert objet in page
    client.post(f'/fermes/{numero}/visites/planifier', data={'date': demain.isoformat(), 'objet': 'Suivi'})
    v = Visite.query.one()
    assert v.statut == StatutVisite.PREVUE and v.date_prevue == demain and v.agent_id == monde['agent'].id
    # L'éleveur voit la prochaine visite dans la ligne d'état
    changer(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert '📅 Visite de Paul demain' in accueil
    # Compte rendu, envoyé sans réseau (position et photo comprises)
    changer(client, 'agent1')
    page = client.get(f'/fermes/{numero}/visites/compte-rendu?visite={v.id}').get_data(as_text=True)
    assert 'Changez la litière humide' in page and 'data-hors-ligne="Compte rendu de visite' in page
    assert 'navigator.geolocation' in page
    _, rep = rejouer(client, f'/fermes/{numero}/visites/compte-rendu',
                     {'visite': str(v.id), 'constats': 'Litière mouillée en B2',
                      'recommandations': ['Changez la litière humide', 'Notez les morts chaque jour'],
                      'recommandation_libre': 'Réparez la fuite', 'latitude': '0.3901', 'longitude': '9.4544',
                      'photo': (io.BytesIO(JPEG), 'v.jpg')}, content_type='multipart/form-data')
    assert rep['etat'] == 'ok'
    db.session.refresh(v)
    assert v.statut == StatutVisite.FAITE and v.latitude == 0.3901 and v.photo
    assert v.toutes_recommandations == ['Changez la litière humide', 'Notez les morts chaque jour', 'Réparez la fuite']
    # L'éleveur : pastille « nouveau » sur 👤 Moi, recommandations en gros, puis lu
    changer(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert re.search(r'data-entete="moi">👤 Moi <span class="pastille-nouveau">nouveau</span>', accueil)
    assert 'Visite de Paul' not in accueil                            # plus de visite prévue
    assert 'data-moi="visites"' in client.get('/moi').get_data(as_text=True)
    page = client.get('/mes-visites').get_data(as_text=True)
    assert 'Changez la litière humide' in page and 'Réparez la fuite' in page and 'nouveau' in page
    db.session.refresh(v)
    assert v.vue_par_eleveur_le is not None
    assert 'pastille-nouveau' not in client.get('/').get_data(as_text=True)
    assert client.get(f'/visites/{v.id}/photo').status_code == 200


def test_visite_non_planifiee_annulation_et_alerte_de_l_agent(client, monde):
    connecter(client, 'agent1')
    numero = monde['f'].numero
    r = client.post(f'/fermes/{numero}/visites/compte-rendu', data={'objet': 'Contrôle', 'constats': 'RAS'})
    assert r.status_code == 302
    assert Visite.query.one().statut == StatutVisite.FAITE and Visite.query.one().date_prevue is None
    assert 'Écrivez un constat' in client.post(f'/fermes/{numero}/visites/compte-rendu',
                                                data={'objet': 'Contrôle'}).get_data(as_text=True)
    # Visite prévue aujourd'hui : dans l'encadré Alertes de l'agent
    v = visites.planifier(monde['f'], AUJ, 'Vaccination', monde['agent'])
    db.session.commit()
    assert 'Visite prévue aujourd’hui : Ferme Un' in client.get('/').get_data(as_text=True)
    assert 'Indiquez le motif' in client.post(f'/visites/{v.id}/annuler', data={'motif': ''},
                                               follow_redirects=True).get_data(as_text=True)
    client.post(f'/visites/{v.id}/annuler', data={'motif': 'pluie'})
    db.session.refresh(v)
    assert v.statut == StatutVisite.ANNULEE
    assert JournalAudit.query.filter_by(action=Action.ANNULATION, table_nom='visite').count() == 1
    # Une visite passée et non faite n'est plus montrée à l'éleveur ; « en retard » chez l'agent
    v2 = Visite(ferme_id=monde['f'].id, agent_id=monde['agent'].id, date_prevue=AUJ - timedelta(days=2), objet='Suivi')
    db.session.add(v2)
    db.session.commit()
    assert visites.prochaine([monde['f'].id]) is None
    assert 'Visite en retard' in client.get('/').get_data(as_text=True)
    # Un autre agent ne voit pas cette ferme
    creer_utilisateur('agent9', Profil.AGENT, ['EST'])
    db.session.commit()
    changer(client, 'agent9')
    assert client.get(f'/fermes/{numero}/visites/planifier').status_code == 404


def test_quand_jours_simples():
    assert visites.quand(AUJ) == "aujourd'hui" and visites.quand(AUJ + timedelta(days=1)) == 'demain'
    j = AUJ + timedelta(days=3)
    assert visites.quand(j) == f'{visites.JOURS[j.weekday()]} {j.day}'
    assert visites.quand(AUJ + timedelta(days=30)) == f'le {(AUJ + timedelta(days=30)).strftime("%d/%m")}'
