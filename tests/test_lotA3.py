"""Lot A3 — programme POUFA, capacité, production théorique et réelle, cible et atteinte, hors programme,
bande de chair ou de ponte, paramètres sous quatre yeux, formulaires de la ferme et de l'opérateur en fenêtre."""
from datetime import timedelta

import pytest

from app import db, indicateurs
from app.models import Ferme, Profil
from app.models.bande import Bande, Sortie
from app.services import bandes as regles, approbations
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_fermes import form, libreville  # noqa: F401


# ── Calculs (une seule source : app/indicateurs.py) ─────────────────────

def test_production_theorique_et_parametres(app):
    assert indicateurs.production_theorique_t(1000, 6) == pytest.approx(12.6)       # 1 000 × 6 × 2,1 kg
    assert indicateurs.production_theorique_t(0, 6) is None
    assert indicateurs.rendement_carcasse() == 0.75 and indicateurs.objectif_national_t() == 100000
    assert indicateurs.couleur_atteinte(85) == 'vert' and indicateurs.couleur_atteinte(80) == 'vert'
    assert indicateurs.couleur_atteinte(60) == 'orange' and indicateurs.couleur_atteinte(49.9) == 'rouge'
    assert indicateurs.couleur_atteinte(None) is None


def test_cible_reelle_atteinte_part_nationale(client, monde):
    f = monde['f']                                     # 2 bâtiments : 1 500 + 800 places, 6 bandes par an
    assert f.capacite == 2300 and f.bandes_par_an == 6
    assert indicateurs.cible_t(f) == pytest.approx(2300 * 6 * 2.1 / 1000)
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=40))
    op = monde['abattoir'] if 'abattoir' in monde else None
    from app.models import Operateur
    op = Operateur.query.filter_by(type='Abattoir').first()
    regles.sortir(b, AUJ, 'Abattoir', op, None, 500, 1050, monde['el'])
    db.session.commit()
    p = indicateurs.production_fermes([f])[f.id]
    assert p['reelle'] == pytest.approx(1.05)
    assert p['atteinte'] == pytest.approx(1.05 * 100 / (2300 * 6 * 2.1 / 1000))
    assert p['couleur'] == 'rouge' and p['carcasse'] == pytest.approx(1.05 * 0.75)
    assert p['part_nationale'] == pytest.approx(1.05 * 100 / 100000)
    # Une sortie de plus de 12 mois ne compte plus
    assert indicateurs.production_reelle_t([f], jour=AUJ + timedelta(days=400)) == {}


def test_hors_programme_pas_de_cible_ni_livraison_ni_commande(client, monde):
    f2 = monde['f2']
    f2.programme_poufa = False
    db.session.commit()
    assert indicateurs.cible_t(f2) is None
    assert indicateurs.production_fermes([f2])[f2.id]['couleur'] is None
    from app.services import agent, dge
    with pytest.raises(agent.RegleAgent, match='hors programme'):
        agent.commander(f2, monde['aliment'], 10, 'bande suivante', monde['agent'])
    with pytest.raises(dge.RegleDge, match='hors programme'):
        dge.prevoir(f2, AUJ, monde['aliment'], 10, None, monde['agent'])


def test_liste_des_fermes_filtre_programme_et_atteinte(client_admin, monde):
    monde['f2'].programme_poufa = False
    db.session.commit()
    page = client_admin.get('/fermes/').get_data(as_text=True)
    assert 'Cible (t/an)' in page and 'Produit 12 mois' in page and 'Hors programme (1)' in page
    assert 'data-atteinte="EST-001"' in page
    page = client_admin.get('/fermes/?programme=hors').get_data(as_text=True)
    assert 'Ferme Deux' in page and 'Ferme Un' not in page
    page = client_admin.get('/fermes/?programme=programme').get_data(as_text=True)
    assert 'Ferme Un' in page and 'Ferme Deux' not in page


def test_tableau_de_bord_et_carte_filtrent_le_programme(client_admin, monde):
    monde['f2'].programme_poufa = False
    db.session.commit()
    page = client_admin.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert 'data-production' in page and "hors programme à part : 1 ferme" in page
    assert client_admin.get('/pilotage/tableau-de-bord?programme=hors').status_code == 200
    assert 'data-filtre-programme' in client_admin.get('/pilotage/carte?programme=programme').get_data(as_text=True)


# ── Capacité ────────────────────────────────────────────────────────────

def test_creation_capacite_obligatoire_et_batiments_crees(client_admin, libreville):
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id), places=''))
    assert 'Indiquez la capacité' in r.get_data(as_text=True) and Ferme.query.count() == 0
    client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id), nb_batiments='2', places='750',
                                                    bandes_par_an='5', programme_poufa='non'))
    f = Ferme.query.one()
    assert [b.code for b in f.batiments] == ['B1', 'B2'] and f.capacite == 1500
    assert f.bandes_par_an == 5 and not f.programme_poufa and not f.capacite_a_completer


def test_formulaire_en_fenetre_avec_production_en_direct(client_admin, libreville):
    page = client_admin.get('/fermes/nouvelle').get_data(as_text=True)
    assert 'id="fen-ferme"' in page and 'data-ouverte' in page and 'production-directe' in page
    assert 'Membre du programme POUFA' in page and 'Bandes par an' in page
    page = client_admin.get('/operateurs/nouveau').get_data(as_text=True)
    assert 'id="fen-operateur"' in page and 'data-ouverte' in page


def test_cohorte_seulement_au_programme(client_admin, monde):
    f = monde['f']
    f.cohorte = 1
    db.session.commit()
    client_admin.post(f'/fermes/{f.numero}/modifier', data={
        **form(nom=f.nom, exploitant_nom=f.exploitant_nom, exploitant_telephone=f.exploitant_telephone,
               localite_id=str(f.localite_id), province_id=str(f.province_id)),
        'programme_poufa': 'non', 'cohorte': '1', 'statut': f.statut, 'bandes_par_an': '6'})
    f = db.session.get(Ferme, f.id)
    assert not f.programme_poufa and f.cohorte is None


def test_capacite_a_completer_chez_l_agent(client, monde):
    f2 = monde['f2']
    f2.bandes_par_an = None
    db.session.commit()
    assert f2.capacite_a_completer
    connecter(client, 'agent2')
    page = client.get(f'/terrain/fermes/{f2.numero}').get_data(as_text=True)
    assert 'Capacité à compléter' in page
    assert 'data-capacite-a-completer' in client.get('/terrain/fermes').get_data(as_text=True)


# ── Paramètres sous quatre yeux ─────────────────────────────────────────

@pytest.mark.parametrize('cle', ['production.poids_sortie_kg', 'production.rendement_carcasse_pct',
                                 'production.objectif_national_t'])
def test_parametres_de_production_sous_quatre_yeux(app, cle):
    assert approbations.sensible(cle)


# ── Bande de chair ou de ponte ──────────────────────────────────────────

def test_bande_de_ponte_indicateurs_sans_objet(client, monde):
    liv = recevoir(monde['f'], [(monde['poussins'], 500, 0), (monde['aliment'], 20, 0)])
    ligne = next(l for l in liv.lignes if l.produit.type == 'Poussins')
    connecter(client, 'eleveur1')
    page = client.get(f'/bandes/ouvrir?ferme={monde["f"].numero}').get_data(as_text=True)
    assert 'Quelle production ?' in page and 'Ponte' in page and 'ISA Brown' in page
    client.post('/bandes/ouvrir', data={'ferme': monde['f'].numero, 'ligne': ligne.id, 'batiment': monde['f'].batiments[0].id,
                                        'effectif': '500', 'type_production': 'PONTE', 'souche': 'ISA Brown'})
    b = Bande.query.one()
    assert b.ponte and b.souche == 'ISA Brown' and b.origine_poussins == 'Programme'
    assert (b.date_fin_prevue - b.date_mise_en_place).days == 504
    v = indicateurs.calculer(b)
    assert v['ponte'] and v['gmq'] is None and v['indice_consommation'] is None
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    page = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert '🥚 Ponte' in page and 'sans objet' in page
    # La sortie de ponte se fait comme le chair, sans cible : elle ne compte pas dans la production de chair
    from app.models import Operateur
    regles.sortir(b, AUJ, 'Vente', Operateur.query.filter_by(type='Distributeur').first(), None, 100, 180, monde['el'])
    db.session.commit()
    assert indicateurs.production_reelle_t([monde['f']]) == {}


def test_bande_de_chair_par_defaut(client, monde):
    b = bande_ouverte(monde)
    assert b.type_production == 'CHAIR' and not b.ponte and b.origine_poussins == 'Programme'
