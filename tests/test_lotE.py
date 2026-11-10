"""Lot E (partie a) — positions des fermes : précision exigée, contrôle de province, correction à la main et quatre
yeux, historique sans rien écraser ; visites : distance recalculée par le serveur et explication ; tournée ;
carte (indicateur, infobulle, à localiser, à vérifier) ; contrôle des visites de la DGE ; page publique."""
import pytest

from app import db
from app.models import Ferme, Profil, PositionFerme
from app.models.visite import Visite
from app.services import positions, approbations
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer

NTOUM = (0.3921, 9.7610)          # Estuaire
FRANCEVILLE = (-1.6333, 13.5833)  # Haut-Ogooué


def releve(client, f, lat, lon, precision='8', **extra):
    return client.post(f'/terrain/fermes/{f.numero}/position',
                       data={'latitude': str(lat), 'longitude': str(lon), 'precision': precision, **extra})


# ── Calculs ─────────────────────────────────────────────────────────────

def test_distance_haversine(app):
    assert positions.distance_m(0, 9, 0, 9) == 0
    assert positions.distance_m(0.0, 9.0, 0.0, 9.01) == pytest.approx(1112, rel=0.01)
    assert positions.texte_distance(120) == '120 m' and positions.texte_distance(4200) == '4,2 km'


# ── Relevé sur place (E1–E3, E5) ────────────────────────────────────────

def test_fiche_sans_position_propose_le_releve(client, monde):
    connecter(client, 'agent1')
    page = client.get(f'/terrain/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'Position pas encore relevée' in page and 'Relever la position ici' in page
    page = client.get(f'/terrain/fermes/{monde["f"].numero}/position').get_data(as_text=True)
    assert '✓ Garder cette position' in page and 'disabled' in page and '± 30 m' in page


def test_precision_insuffisante_refusee(client, monde):
    connecter(client, 'agent1')
    page = releve(client, monde['f'], *NTOUM, precision='85').get_data(as_text=True)
    assert '± 85 m' in page and db.session.get(Ferme, monde['f'].id).latitude is None


def test_releve_dans_la_province_garde_et_historique(client, monde):
    connecter(client, 'agent1')
    releve(client, monde['f'], *NTOUM, precision='7')
    f = db.session.get(Ferme, monde['f'].id)
    assert (round(f.latitude, 4), f.gps_precision_m, f.position_a_verifier) == (0.3921, 7, False)
    releve(client, monde['f'], 0.3925, 9.7612, precision='5')
    pos = PositionFerme.query.filter_by(ferme_id=f.id).order_by(PositionFerme.id).all()
    assert len(pos) == 2 and [p.en_vigueur for p in pos] == [False, True]          # aucune n'est écrasée
    assert pos[1].origine == 'GPS' and pos[1].auteur_id == monde['agent'].id


def test_hors_province_relever_a_nouveau_ou_garder_quand_meme(client, monde):
    connecter(client, 'agent1')
    page = releve(client, monde['f'], *FRANCEVILLE).get_data(as_text=True)
    assert '⚠️ Cette position est dans la province Haut-Ogooué' in page and 'Garder quand même' in page
    assert 'appelez la DGE' in page and PositionFerme.query.count() == 0
    releve(client, monde['f'], *FRANCEVILLE, garder='1')                              # motif obligatoire
    assert PositionFerme.query.count() == 0
    releve(client, monde['f'], *FRANCEVILLE, garder='1', motif='Province mal notée sur la fiche')
    f = db.session.get(Ferme, monde['f'].id)
    assert f.position_a_verifier and f.province.code == 'EST'                          # la province ne change pas
    assert PositionFerme.query.one().a_verifier


def test_releve_sans_reseau_garde_et_marque_a_verifier(client, monde):
    connecter(client, 'agent1')
    _, rep = rejouer(client, f'/terrain/fermes/{monde["f"].numero}/position',
                     {'latitude': str(FRANCEVILLE[0]), 'longitude': str(FRANCEVILLE[1]), 'precision': '9'})
    assert rep['etat'] == 'ok'
    pos = PositionFerme.query.one()
    assert pos.hors_ligne and pos.a_verifier


# ── Correction à la main (E4) ───────────────────────────────────────────

def test_correction_a_la_main_proche_puis_loin_aux_quatre_yeux(client, monde):
    connecter(client, 'agent1')
    releve(client, monde['f'], *NTOUM)
    client.post(f'/terrain/fermes/{monde["f"].numero}/position', data={
        'action': 'main', 'latitude_main': '0,3930', 'longitude_main': '9,7615', 'motif': 'Bâtiment loin de la route'})
    f = db.session.get(Ferme, monde['f'].id)
    assert round(f.latitude, 4) == 0.393 and PositionFerme.query.filter_by(origine='MANUELLE').count() == 1
    # À plus de 1 km : proposition aux quatre yeux, la position ne change pas encore
    client.post(f'/terrain/fermes/{monde["f"].numero}/position', data={
        'action': 'main', 'latitude_main': '0,45', 'longitude_main': '9,80', 'motif': 'GPS du téléphone imprécis'})
    f = db.session.get(Ferme, monde['f'].id)
    assert round(f.latitude, 4) == 0.393
    from app.models.securite import Proposition
    p = Proposition.query.filter_by(genre='POSITION').one()
    dge = creer_utilisateur('dge', Profil.DGE)
    approbations.decider(p, dge, True)
    db.session.commit()
    f = db.session.get(Ferme, monde['f'].id)
    assert round(f.latitude, 2) == 0.45 and PositionFerme.query.count() == 3


def test_correction_sans_motif_refusee(client, monde):
    connecter(client, 'agent1')
    client.post(f'/terrain/fermes/{monde["f"].numero}/position', data={
        'action': 'main', 'latitude_main': '0,3930', 'longitude_main': '9,7615'})
    assert PositionFerme.query.count() == 0


# ── Visite : distance à la ferme (E6) ───────────────────────────────────

def test_visite_distance_recalculee_par_le_serveur(client, monde):
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get(f'/fermes/{f.numero}/visites/compte-rendu').get_data(as_text=True)
    assert 'data-distance-max="1000.0"' in page and 'Pourquoi si loin' in page
    client.post(f'/fermes/{f.numero}/visites/compte-rendu', data={
        'objet': 'Suivi', 'constats': 'RAS', 'latitude': '0.3930', 'longitude': '9.7610', 'precision': '12'})
    v = Visite.query.one()
    assert v.distance_m == pytest.approx(100, abs=5) and v.precision_m == 12 and positions.etat_visite(v) == 'confirmee'
    client.post(f'/fermes/{f.numero}/visites/compte-rendu', data={
        'objet': 'Suivi', 'constats': 'Vu au village', 'latitude': '0.43', 'longitude': '9.76',
        'motif_distance': 'Rencontre au village'})
    v = Visite.query.order_by(Visite.cree_le.desc()).first()
    assert v.distance_m > 4000 and v.motif_distance == 'Rencontre au village' and positions.etat_visite(v) == 'eloignee'


# ── Tournée, éleveur, carte, DGE, page publique ─────────────────────────

def test_tournee_itineraire_et_ferme_a_relever(client, monde):
    from app.models.visite import StatutVisite
    db.session.add(Visite(ferme_id=monde['f'].id, agent_id=monde['agent'].id, objet='Suivi', date_prevue=AUJ,
                          statut=StatutVisite.PREVUE))
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get('/terrain/tournee').get_data(as_text=True)
    assert 'à relever sur place' in page and 'Itinéraire complet' in page and 'google.com/maps/dir' in page


def test_eleveur_mon_compte_position(client, monde):
    connecter(client, 'eleveur1')
    assert 'Votre agent relèvera la position à sa prochaine visite' in client.get('/mon-compte').get_data(as_text=True)
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    from app.models.base import maintenant
    f.gps_date = maintenant()
    db.session.commit()
    assert '📍 Position relevée ✓ le' in client.get('/mon-compte').get_data(as_text=True)


def test_carte_indicateur_infobulle_et_encadres(client_admin, monde):
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    bande_ouverte(monde)
    page = client_admin.get('/pilotage/carte?indicateur=mortalite').get_data(as_text=True)
    assert 'data-indicateur-carte' in page and 'Mortalité :' in page and 'Dernière saisie' in page
    assert 'À localiser (1)' in page and 'Position à vérifier (0)' in page and 'data-province-carte="EST"' in page
    from app.models import Province
    page = client_admin.get(f'/pilotage/carte?province={Province.query.filter_by(code="EST").one().id}').get_data(as_text=True)
    assert 'class="etiquette-ferme"' in page and '← Tout le Gabon' in page


def test_controle_des_visites_de_la_dge(client, monde):
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    connecter(client, 'agent1')
    client.post(f'/fermes/{f.numero}/visites/compte-rendu', data={'objet': 'Suivi', 'constats': 'RAS',
                                                                 'latitude': '0.43', 'longitude': '9.76',
                                                                 'motif_distance': 'Route coupée'})
    client.post('/auth/deconnexion')
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    page = client.get('/agents?controle=eloignee').get_data(as_text=True)
    assert 'Contrôle des visites' in page and 'Route coupée' in page and 'data-visite-etat="eloignee"' in page
    assert '0/1 confirmées' in page
    assert 'data-visite-etat' not in client.get('/agents?controle=sans_position').get_data(as_text=True)


def test_page_publique_sans_point_exact(client, monde):
    from app.models import Operateur
    from app.services import bandes as regles
    f = monde['f']
    f.latitude, f.longitude = NTOUM
    db.session.commit()
    b = bande_ouverte(monde)
    s = regles.sortir(b, AUJ, 'Abattoir', Operateur.query.filter_by(type='Abattoir').one(), None, 10, 21, monde['el'])
    db.session.commit()
    page = client.get(f'/q/{s.lot.code}').get_data(as_text=True)
    assert 'Ntoum' in page and 'Estuaire' in page
    assert '0.3921' not in page and '9.761' not in page and '0,3921' not in page
