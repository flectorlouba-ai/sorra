"""Lot E-b — nouvelle ferme créée par l'agent sans réseau (numéro provisoire, rattachement des saisies, doublon
sur le téléphone et sur le serveur) ; punaise à glisser pour corriger la position."""
import uuid

from app import db
from app.models import Ferme, Utilisateur
from app.models.argent import Depense
from app.models.hors_ligne import ConflitHorsLigne
from app.models.visite import Visite
from tests.conftest import connecter
from tests.test_bandes import monde, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer

NTOUM = (0.3921, 9.7610)


def formulaire(**extra):
    d = {'ferme_id': str(uuid.uuid4()), 'numero_terrain': 'P-0412', 'eleveur_nom': 'Mebale', 'eleveur_prenom': 'Esther',
         'exploitant_nom': 'Esther Mebale', 'telephone': '077 12 34 56', 'localite': 'Kango', 'nom': "Ferme d'Esther",
         'nb_batiments': '2', 'places': '750', 'bandes_par_an': '6', 'identifiant': 'esther.mebale',
         'provisoire': 'kangxabcde', 'latitude': str(NTOUM[0]), 'longitude': str(NTOUM[1]), 'precision': '7'}
    d.update(extra)
    return d


def test_ecran_nouvelle_ferme_garde_sur_le_telephone(client, monde):
    connecter(client, 'agent1')
    page = client.get('/terrain/nouvelle-ferme').get_data(as_text=True)
    assert 'Pas de réseau : la ferme sera envoyée plus tard' in page and 'Une ferme existe déjà tout près' in page
    assert 'data-retour-garde="/terrain/ferme-provisoire"' in page and 'fermes-connues' in page
    pages = client.get('/hors-ligne/pages').get_json()['pages']
    assert '/terrain/nouvelle-ferme' in pages and '/terrain/ferme-provisoire' in pages
    choix = client.get('/terrain/nouvel-eleveur').get_data(as_text=True)
    assert '/terrain/nouvelle-ferme' in choix and 'Avec du réseau seulement' not in choix


def test_ferme_hors_ligne_numero_provisoire_puis_rattachement(client, monde):
    connecter(client, 'agent1')
    _, rep = rejouer(client, '/terrain/nouvelle-ferme', formulaire())
    assert rep['etat'] == 'ok' and 'P-0412 est devenue' in rep['message']
    f = Ferme.query.filter_by(numero_terrain='P-0412').one()
    assert f.numero.startswith('EST-') and f.numero != 'P-0412' and f.capacite == 1500 and f.agent_id == monde['agent'].id
    assert f.localite.nom == 'Kango' and f.a_une_position
    u = Utilisateur.query.filter_by(identifiant='esther.mebale').one()
    assert u.check_password('kangxabcde') and u.fermes[0].ferme_id == f.id
    # Les saisies faites sur la ferme provisoire, envoyées ensuite, sont rattachées à la vraie ferme
    _, rep = rejouer(client, '/fermes/P-0412/visites/compte-rendu', {'objet': 'Suivi', 'constats': 'Première visite'})
    assert rep['etat'] == 'ok'
    assert Visite.query.one().ferme_id == f.id
    from app.services import argent
    _, rep = rejouer(client, '/j-ai-paye', {'ferme': 'P-0412', 'categorie': argent.categories()[0][0], 'montant': '5000'})
    assert rep['etat'] == 'ok' and Depense.query.one().ferme_id == f.id
    # Le même envoi rejoué n'enregistre pas deux fermes
    _, rep = rejouer(client, '/terrain/nouvelle-ferme', formulaire(ferme_id=str(uuid.uuid4())))
    assert rep['etat'] == 'refuse' and Ferme.query.filter_by(numero_terrain='P-0412').count() == 1


def test_ferme_avec_reseau_affiche_le_compte(client, monde):
    connecter(client, 'agent1')
    page = client.post('/terrain/nouvelle-ferme', data=formulaire(numero_terrain='P-0500')).get_data(as_text=True)
    assert 'esther.mebale' in page and 'kangxabcde' in page


def test_doublon_trouve_par_le_serveur_sur_toutes_les_fermes(client, monde):
    autre = monde['f2']                                  # ferme d'un autre agent : le téléphone ne la connaît pas
    autre.latitude, autre.longitude = NTOUM[0] + 0.0004, NTOUM[1]
    db.session.commit()
    connecter(client, 'agent1')
    assert autre.numero not in client.get('/terrain/nouvelle-ferme').get_data(as_text=True)
    rejouer(client, '/terrain/nouvelle-ferme', formulaire(motif_doublon='Voisin'))
    c = ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('Ferme peut-être en double%')).one()
    assert autre.numero in c.detail and 'P-0412' in c.detail and 'Voisin' in c.detail


def test_doublon_connu_du_telephone(client, monde):
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get('/terrain/nouvelle-ferme').get_data(as_text=True)
    assert f'"numero": "{f.numero}"' in page and 'data-seuil="200"' in page
    assert f'/fermes/{f.numero}/eleveurs/nouveau' in page or f'nouvel-eleveur' in page


def test_creation_incomplete_refusee(client, monde):
    connecter(client, 'agent1')
    page = client.post('/terrain/nouvelle-ferme', data=formulaire(places='0')).get_data(as_text=True)
    assert 'Indiquez le nombre de bâtiments' in page and Ferme.query.filter_by(numero_terrain='P-0412').count() == 0


def test_punaise_sur_la_carte_de_la_province(client, monde):
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get(f'/terrain/fermes/{f.numero}/position').get_data(as_text=True)
    assert 'data-punaise' in page and 'Glissez la punaise' in page and '"echelle"' in page and 'id="punaise"' in page
    # La punaise remplit les mêmes champs que la saisie des coordonnées (même enregistrement)
    client.post(f'/terrain/fermes/{f.numero}/position', data={'action': 'main', 'latitude_main': '0,39300',
                                                             'longitude_main': '9,76150', 'motif': 'Bâtiment déplacé'})
    assert round(db.session.get(Ferme, f.id).latitude, 4) == 0.393


def test_projection_inverse_de_la_carte(app):
    from app.services import geo
    d = geo.dessin('EST', NTOUM[0], NTOUM[1], largeur=320, hauteur=230)
    pr, (x, y) = d['projection'], d['epingle']
    lon = pr['x0'] + (x - pr['dx']) / pr['echelle']
    lat = pr['y1'] - (y - pr['dy']) / pr['echelle']
    assert abs(lon - NTOUM[1]) < 0.01 and abs(lat - NTOUM[0]) < 0.01
