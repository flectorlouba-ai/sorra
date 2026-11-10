"""Lot A2 — catalogue des intrants et fournisseurs : article enrichi (référence, fournisseur, conditionnement,
type Matériel), table fournisseur, origine Programme / Externe, stock par article et par origine (Programme
d'abord), écart d'inventaire sur le Programme seulement, saisie du jour sur les articles en stock, droits."""
from datetime import timedelta

from app import db
from app.models import Produit, Profil, Fournisseur
from app.services import intrants, agent as services_agent
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401


def ligne_stock(ferme, produit):
    return next(s for s in intrants.stock_ferme(ferme) if s['produit'].id == produit.id)


def acheter(m, produit, quantite):
    a = intrants.enregistrer_achat(m['f'], produit, quantite, 0, 10000, 'Marché', AUJ - timedelta(days=1), m['el'])
    db.session.commit()
    return a


# ── Stock par origine ───────────────────────────────────────────────────

def test_imputation_programme_d_abord():
    assert intrants.imputer(40, 45) == (40, 5)
    assert intrants.imputer(40, 10) == (10, 0)
    assert intrants.imputer(0, 7) == (0, 7)


def test_stock_par_article_et_par_origine(client, monde):
    b = bande_ouverte(monde)                         # 40 sacs d'aliment de l'État reçus avec les poussins
    acheter(monde, monde['aliment'], 10)             # 10 sacs achetés par l'éleveur
    s = ligne_stock(monde['f'], monde['aliment'])
    assert (s['etat'], s['achat'], s['programme'], s['externe'], s['stock']) == (40, 10, 40, 10, 50)
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0', 'sacs': '45', 'aliment_choisi': str(monde['aliment'].id)})
    s = ligne_stock(monde['f'], monde['aliment'])
    assert (s['programme'], s['externe'], s['stock']) == (0, 5, 5)          # Programme d'abord
    page = client.get('/mon-stock').get_data(as_text=True)
    assert "il reste 0 de l'État · 5 à vous" in page


def test_ecart_d_inventaire_sur_le_programme_seulement(client, monde):
    b = bande_ouverte(monde)
    acheter(monde, monde['aliment'], 10)
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0', 'sacs': '30', 'aliment_choisi': str(monde['aliment'].id)})
    # Il reste 10 sacs Programme + 10 sacs Externe ; l'agent en compte 17 : 3 sacs Programme manquent
    inv = services_agent.compter(monde['f'], monde['aliment'], 17, monde['agent'])
    db.session.commit()
    assert (inv.livre, inv.utilise, inv.externe, inv.compte_programme, inv.ecart) == (40, 30, 10, 7, 3)
    assert inv.ecart_pct == 7.5                                     # 3 sur 40 livrés par le Programme
    inv = services_agent.compter(monde['f'], monde['aliment'], 20, monde['agent'])
    assert inv.ecart == 0                                           # les achats ne cachent pas un manque


def test_ecran_stock_de_l_agent_montre_les_origines(client, monde):
    bande_ouverte(monde)
    acheter(monde, monde['aliment'], 10)
    connecter(client, 'agent1')
    page = client.get(f'/terrain/stock?ferme={monde["f"].numero}').get_data(as_text=True)
    assert 'Programme 40 · Externe 10' in page
    page = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'Programme · Externe' in page and 'data-origines' in page


# ── Saisie du jour : les articles en stock, « Comme hier » ──────────────

def test_saisie_du_jour_propose_les_articles_en_stock(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Aliment démarrage' in page and 'Aliment croissance' not in page   # pas en stock
    acheter(monde, monde['croissance'], 5)
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Aliment croissance' in page
    # « Comme hier » reprend l'article et la quantité de la veille
    from app.services import bandes as regles
    regles.saisir(b, AUJ - timedelta(days=1), 0, {monde['croissance']: 3}, monde['el'])
    db.session.commit()
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert f'data-aliment="{monde["croissance"].id}"' in page and 'Comme hier (3 sacs)' in page


# ── Catalogue et fournisseurs ───────────────────────────────────────────

def test_catalogue_article_enrichi_par_la_dge(client, app):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    client.post('/administration/catalogue/fournisseurs/creer',
                data={'nom': 'SMAG Aliments', 'type': 'Aliment', 'ville': 'Libreville', 'telephone': '011 00 00 00'})
    fo = Fournisseur.query.one()
    client.post('/administration/catalogue/creer', data={
        'nom': 'Aliment finition', 'type': 'Aliment', 'unite': 'sacs', 'poids_sac_kg': '50',
        'reference': 'SMAG-FIN-50', 'conditionnement': 'sac de 50 kg', 'fournisseur_id': str(fo.id)})
    client.post('/administration/catalogue/creer', data={'nom': 'Abreuvoir 10 L', 'type': 'Matériel', 'unite': 'unités'})
    p = Produit.query.filter_by(nom='Aliment finition').one()
    assert (p.reference, p.conditionnement, p.fournisseur.nom) == ('SMAG-FIN-50', 'sac de 50 kg', 'SMAG Aliments')
    assert Produit.query.filter_by(nom='Abreuvoir 10 L').one().type == 'Matériel'
    page = client.get('/administration/catalogue/').get_data(as_text=True)
    assert 'SMAG-FIN-50' in page and 'fournisseur à préciser' in page          # l'abreuvoir n'a pas de fournisseur
    page = client.get(f'/administration/catalogue/?fournisseur={fo.id}').get_data(as_text=True)
    assert 'Aliment finition' in page and 'Abreuvoir' not in page
    r = client.post('/administration/catalogue/fournisseurs/creer', data={'nom': 'smag aliments', 'type': 'Aliment'},
                    follow_redirects=True)
    assert 'existe déjà' in r.get_data(as_text=True) and Fournisseur.query.count() == 1


def test_fournisseur_archive_et_restaure(client_admin, app):
    client_admin.post('/administration/catalogue/fournisseurs/creer', data={'nom': 'Couvoir du Komo', 'type': 'Couvoir'})
    fo = Fournisseur.query.one()
    client_admin.post(f'/administration/catalogue/fournisseurs/{fo.id}/modifier', data={'archiver': '1'})
    fo = db.session.get(Fournisseur, fo.id)
    assert not fo.actif and fo.archive_le is not None
    assert f'data-fournisseur="{fo.id}"' not in client_admin.get('/administration/catalogue/fournisseurs').get_data(as_text=True)
    assert 'Couvoir du Komo' in client_admin.get('/administration/catalogue/fournisseurs?etat=archives').get_data(as_text=True)
    client_admin.post(f'/administration/catalogue/fournisseurs/{fo.id}/modifier', data={'restaurer': '1'})
    assert db.session.get(Fournisseur, fo.id).actif


def test_droits_lecture_agent_ecriture_admin_dge(client, monde):
    connecter(client, 'agent1')
    page = client.get('/administration/catalogue/').get_data(as_text=True)
    assert 'Aliment démarrage' in page and 'onclick="ouvrirProduit()"' not in page
    assert client.get('/administration/catalogue/fournisseurs').status_code == 200
    assert client.post('/administration/catalogue/creer', data={'nom': 'X', 'type': 'Autre', 'unite': 'kg'}).status_code == 403
    assert client.post('/administration/catalogue/fournisseurs/creer', data={'nom': 'X', 'type': 'Autre'}).status_code == 403
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    assert client.get('/administration/catalogue/').status_code == 403


def test_livraison_propose_les_fournisseurs_du_catalogue(client_admin, app):
    db.session.add(Fournisseur(nom='Pharmavet Gabon', type='Pharmacie vétérinaire'))
    db.session.commit()
    from app.routes.livraisons import noms_fournisseurs
    assert 'Pharmavet Gabon' in noms_fournisseurs()
