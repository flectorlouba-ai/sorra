"""Saisies de l'agent sans réseau (relecture des lots 15-18) : pages gardées sur son téléphone, puis envoi
après coup avec le mécanisme du lot 7 (identifiant unique, file d'attente) et la règle des conflits du lot 12.
Saisie pour l'éleveur, compte rendu de visite, biosécurité, nouvel éleveur. Les décisions restent en ligne."""
import re
from datetime import date, timedelta

from app import db
from app.models import Profil, Utilisateur
from app.models.bande import SaisieJour, Pesee
from app.models.hors_ligne import ConflitHorsLigne, EnvoiHorsLigne, GenreVerification as G
from app.models.sante import Vaccination, Traitement
from app.models.visite import Visite
from app.services import agent as regles
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


# ── Pages gardées sur le téléphone de l'agent ───────────────────────────

def test_pages_de_saisie_de_l_agent_gardees_et_marquees_hors_ligne(client, monde):
    b = bande_ouverte(monde)
    db.session.add(Visite(ferme_id=monde['f'].id, agent_id=monde['agent'].id, objet='Suivi', statut='PREVUE',
                          date_prevue=AUJ))
    db.session.commit()
    connecter(client, 'agent1')
    assert 'data-pages-hors-ligne' in client.get('/').get_data(as_text=True)
    pages = client.get('/hors-ligne/pages').get_json()['pages']
    n = monde['f'].numero
    for attendu in ('/tournee', f'/fermes/{n}', f'/fermes/{n}/visites/compte-rendu', f'/fermes/{n}/biosecurite',
                    f'/fermes/{n}/eleveurs/nouveau', f'/bandes/{b.numero}/saisir', f'/bandes/{b.numero}/pesee',
                    f'/sante/vacciner/{b.numero}', f'/sante/traiter/{b.numero}'):
        assert attendu in pages, attendu
    assert any('visite=' in p for p in pages)                         # les visites prévues aussi
    assert monde['f2'].numero not in ' '.join(pages)                  # pas les fermes d'un autre agent
    # Chaque page gardée s'ouvre, et chaque page de saisie a son formulaire « hors ligne »
    for p in pages:
        r = client.get(p)
        assert r.status_code == 200, p
    for p in (f'/fermes/{n}/visites/compte-rendu', f'/fermes/{n}/biosecurite', f'/fermes/{n}/eleveurs/nouveau',
              f'/bandes/{b.numero}/saisir', f'/bandes/{b.numero}/pesee', f'/sante/vacciner/{b.numero}',
              f'/sante/traiter/{b.numero}'):
        assert 'data-hors-ligne=' in client.get(p).get_data(as_text=True), p
    # La DGE n'a pas de pages à garder
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    changer(client, 'dge')
    assert client.get('/hors-ligne/pages').status_code == 403
    assert 'data-pages-hors-ligne' not in client.get('/').get_data(as_text=True)


# ── Saisie pour l'éleveur ───────────────────────────────────────────────

def test_saisie_pour_l_eleveur_sans_reseau(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '5', 'sacs': '0', 'jour': AUJ.isoformat()})
    assert rep['etat'] == 'ok' and SaisieJour.query.one().morts == 5
    _, rep = rejouer(client, f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4,1'})
    assert rep['etat'] == 'ok' and Pesee.query.count() == 1
    vaccin = __import__('app.models', fromlist=['Produit']).Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    medoc = __import__('app.models', fromlist=['Produit']).Produit(nom='Anticoccidien', type='Médicament', unite='litres')
    db.session.add_all([vaccin, medoc])
    db.session.commit()
    ident, rep = rejouer(client, f'/sante/vacciner/{b.numero}', {'date': AUJ.isoformat(), 'produit_id': vaccin.id,
                                                                'mode': 'Eau de boisson', 'nombre': '990', 'quantite': '1000'})
    assert rep['etat'] == 'ok' and Vaccination.query.one().saisi_par_agent
    _, rep = rejouer(client, f'/sante/vacciner/{b.numero}', {'date': AUJ.isoformat(), 'produit_id': vaccin.id,
                                                            'mode': 'Eau de boisson', 'nombre': '990'}, ident=ident)
    assert rep['etat'] == 'deja' and Vaccination.query.count() == 1    # même identifiant : jamais deux fois
    _, rep = rejouer(client, f'/sante/traiter/{b.numero}', {'date_debut': AUJ.isoformat(), 'date_fin': AUJ.isoformat(),
                                                           'produit_id': medoc.id, 'motif': 'Coccidiose',
                                                           'nombre': '990', 'quantite': '1'})
    assert rep['etat'] == 'ok' and Traitement.query.one().saisi_par_agent
    assert EnvoiHorsLigne.query.count() == 4
    # Règle du lot 12 : l'éleveur avait saisi autre chose, sans réseau → deux versions, la sienne compte
    changer(client, 'eleveur1')
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '3', 'sacs': '0', 'jour': AUJ.isoformat()},
                     il_y_a=timedelta(hours=2))
    assert rep['etat'] == 'conflit'
    c = ConflitHorsLigne.query.filter_by(genre=G.SAISIE_JOUR).one()
    assert sorted(v['profil'] for v in c.versions) == ['AGENT', 'ELEVEUR'] and SaisieJour.query.one().morts == 3


# ── Compte rendu de visite ──────────────────────────────────────────────

def test_compte_rendu_sans_reseau_et_deux_comptes_rendus(client, monde):
    v = Visite(ferme_id=monde['f'].id, agent_id=monde['agent'].id, objet='Vaccination', statut='PREVUE', date_prevue=AUJ)
    db.session.add(v)
    db.session.commit()
    connecter(client, 'agent1')
    url = f'/fermes/{monde["f"].numero}/visites/compte-rendu'
    _, rep = rejouer(client, url, {'visite': str(v.id), 'constats': 'Litière humide',
                                  'recommandations': ['Changez la litière humide']}, il_y_a=timedelta(days=1))
    assert rep['etat'] == 'ok' and v.statut == 'FAITE' and v.faite_le == AUJ - timedelta(days=1)
    # Un second compte rendu de la même visite, saisi sans réseau, arrive après : gardé aussi, agent prévenu
    _, rep = rejouer(client, url, {'visite': str(v.id), 'constats': 'Abreuvoirs sales'})
    assert rep['etat'] == 'ok' and Visite.query.filter_by(statut='FAITE').count() == 2
    assert ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('Deux comptes rendus%')).count() == 1
    # En ligne, le refus reste : on voit tout de suite que la visite est faite
    assert 'déjà son compte rendu' in client.post(url, data={'visite': str(v.id), 'constats': 'x'}).get_data(as_text=True)


# ── Biosécurité ─────────────────────────────────────────────────────────

def test_biosecurite_sans_reseau(client, monde):
    connecter(client, 'agent1')
    points = regles.grille()
    data = {f'r{i}': ('non' if i == 0 else 'oui') for i in range(len(points))}
    data['m0'] = 'Remplir le pédiluve'
    _, rep = rejouer(client, f'/fermes/{monde["f"].numero}/biosecurite', data, il_y_a=timedelta(days=2))
    v = Visite.query.filter_by(objet='Biosécurité').one()
    assert rep['etat'] == 'ok' and v.score_biosecurite == 90 and v.faite_le == AUJ - timedelta(days=2)
    # Grille incomplète : refusée, et l'agent le voit dans « Saisies à vérifier »
    _, rep = rejouer(client, f'/fermes/{monde["f"].numero}/biosecurite', {'r0': 'oui'})
    assert rep['etat'] == 'refuse' and 'Répondez à chaque point' in rep['message']
    assert ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('Envoi refusé%')).count() == 1


# ── Nouvel éleveur ──────────────────────────────────────────────────────

def test_nouvel_eleveur_sans_reseau(client, monde):
    connecter(client, 'agent1')
    url = f'/fermes/{monde["f"].numero}/eleveurs/nouveau'
    page = client.get(url).get_data(as_text=True)
    assert 'data-hors-ligne=' in page and 'name="provisoire"' in page and 'getRandomValues' in page
    # Le téléphone a préparé identifiant et mot de passe, montrés à l'agent avant l'envoi
    _, rep = rejouer(client, url, {'nom': 'Ndong', 'prenom': 'Rose', 'telephone': '066 11 22 33',
                                  'identifiant': 'rose.ndong', 'provisoire': 'k7mq2wpa9x'})
    u = Utilisateur.query.filter_by(identifiant='rose.ndong').one()
    assert rep['etat'] == 'ok' and u.check_password('k7mq2wpa9x') and u.doit_changer_mdp
    assert 'k7mq2wpa9x' not in rep['message']
    # Identifiant déjà pris : un chiffre est ajouté, le mot de passe noté reste valable, l'agent est prévenu
    _, rep = rejouer(client, url, {'nom': 'Ndong', 'prenom': 'Rose', 'telephone': '077 99 88 77',
                                  'identifiant': 'rose.ndong', 'provisoire': 'abcdefgh23'})
    u2 = Utilisateur.query.filter_by(identifiant='rose.ndong2').one()
    assert rep['etat'] == 'ok' and u2.check_password('abcdefgh23')
    assert ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('Identifiant changé : rose.ndong2')).count() == 1
    # Même éleveur inscrit deux fois (deux agents sans réseau) : le second est refusé, signalé
    _, rep = rejouer(client, url, {'nom': 'Ndong', 'prenom': 'Rose', 'telephone': '+241 66 11 22 33',
                                  'identifiant': 'rose.ndong', 'provisoire': 'zzzzzzzzzz'})
    assert rep['etat'] == 'refuse' and 'déjà un compte' in rep['message']
    assert Utilisateur.query.filter(Utilisateur.identifiant.like('rose.ndong%')).count() == 2
    # Première connexion avec le mot de passe noté : il faut le changer
    changer(client, 'rose.ndong')
    client.post('/auth/connexion', data={'identifiant': 'rose.ndong', 'mot_de_passe': 'k7mq2wpa9x'})
    r = client.get('/')
    assert r.status_code == 302 and 'mot-de-passe' in r.location
