"""Lot 2 — intrants : catalogue, livraisons, confirmation, stock, alertes, cloisonnement."""
from datetime import date, timedelta

import pytest

from app import db
from app.models import (Produit, Livraison, LivraisonLigne, Profil, JournalAudit, UtilisateurFerme,
                        Parametre)
from app.models.base import maintenant
from app.models.intrant import StatutLivraison as S
from app.services import intrants
from tests.conftest import creer_utilisateur, connecter, creer_ferme, MDP


@pytest.fixture
def catalogue(app):
    produits = {
        'poussins': Produit(nom='Poussins chair', type='Poussins', unite='têtes'),
        'aliment': Produit(nom='Aliment démarrage', type='Aliment', unite='sacs', poids_sac_kg=25),
        'vaccin': Produit(nom='Vaccin Newcastle', type='Vaccin', unite='doses'),
    }
    db.session.add_all(produits.values())
    db.session.commit()
    return produits


@pytest.fixture
def monde(app, catalogue):
    """Deux agents (EST), une ferme chacun, un éleveur rattaché à la ferme de l'agent 1."""
    a1 = creer_utilisateur('agent1', Profil.AGENT, ['EST'])
    a2 = creer_utilisateur('agent2', Profil.AGENT, ['EST'])
    f1 = creer_ferme('Ferme Un', 'EST', 'Ntoum', agent=a1)
    f2 = creer_ferme('Ferme Deux', 'EST', 'Owendo', agent=a2)
    el = creer_utilisateur('eleveur1', Profil.ELEVEUR)
    el.fermes = [UtilisateurFerme(ferme=f1)]
    db.session.commit()
    return {'a1': a1, 'a2': a2, 'f1': f1, 'f2': f2, 'el': el, **catalogue}


def form_livraison(ferme, *lignes, jour=None, fournisseur=''):
    d = {'ferme': ferme.numero, 'date_livraison': (jour or date.today()).isoformat(), 'fournisseur': fournisseur}
    for i, (produit, qte, sub, part, valeur) in enumerate(lignes):
        d.update({f'ligne-{i}-produit': str(produit.id), f'ligne-{i}-quantite': str(qte),
                  f'ligne-{i}-part': str(part or ''), f'ligne-{i}-valeur': str(valeur or '')})
        if sub:
            d[f'ligne-{i}-subventionne'] = 'on'
    return d


def livrer(ferme, lignes, jour=None, statut=S.A_CONFIRMER):
    liv = intrants.nouvelle_livraison(ferme, jour or date.today(), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': p, 'quantite_livree': q, 'subventionne': False,
                                     'part_subventionnee': None, 'valeur_unitaire': None} for p, q in lignes])
    liv.statut = statut
    db.session.commit()
    return liv


# ── Catalogue ───────────────────────────────────────────────────────────

def test_catalogue_admin(client_admin):
    r = client_admin.post('/administration/catalogue/creer',
                          data={'nom': 'Aliment croissance', 'type': 'Aliment', 'unite': 'sacs'}, follow_redirects=True)
    assert 'poids du sac est obligatoire' in r.get_data(as_text=True)
    client_admin.post('/administration/catalogue/creer',
                      data={'nom': 'Aliment croissance', 'type': 'Aliment', 'unite': 'sacs', 'poids_sac_kg': '50'})
    p = Produit.query.one()
    assert p.poids_sac_kg == 50 and p.en_sacs
    r = client_admin.post('/administration/catalogue/creer',
                          data={'nom': 'ALIMENT CROISSANCE', 'type': 'Aliment', 'unite': 'kg'}, follow_redirects=True)
    assert 'existe déjà' in r.get_data(as_text=True)
    client_admin.post(f'/administration/catalogue/{p.id}/modifier',
                      data={'nom': 'Aliment croissance', 'type': 'Aliment', 'unite': 'sacs', 'poids_sac_kg': '50'})
    assert db.session.get(Produit, p.id).actif is False   # désactivé, pas supprimé
    r = client_admin.post('/administration/catalogue/creer', data={'nom': 'X', 'type': 'Pierre', 'unite': 'kg'},
                          follow_redirects=True)
    assert 'Choisissez le type' in r.get_data(as_text=True)
    assert not [r for r in client_admin.application.url_map.iter_rules() if 'catalogue' in r.rule and 'supprimer' in r.rule]


@pytest.mark.parametrize('profil', [Profil.DGE, Profil.AGENT, Profil.ELEVEUR])
def test_catalogue_reserve_admin(client, app, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/administration/catalogue/').status_code == 403


# ── Livraisons ──────────────────────────────────────────────────────────

def test_agent_cree_une_livraison(client, monde):
    db.session.add(__import__('app.models', fromlist=['ListeDeroulante']).ListeDeroulante(
        categorie='fournisseurs', valeur='Couvoir SIAT', ordre=0))
    db.session.commit()
    connecter(client, 'agent1')
    r = client.post('/livraisons/nouvelle', data=form_livraison(
        monde['f1'], (monde['poussins'], 1000, True, 50, 450), (monde['aliment'], 40, False, None, 12000),
        fournisseur='Couvoir SIAT'))
    annee = date.today().year
    assert r.location.endswith(f'/livraisons/LIV-{annee}-000001')
    liv = Livraison.query.one()
    assert liv.statut == S.A_CONFIRMER and liv.fournisseur == 'Couvoir SIAT' and liv.cree_par == monde['a1'].id
    l = {x.produit.nom: x for x in liv.lignes}
    assert l['Poussins chair'].quantite_livree == 1000 and l['Poussins chair'].part_subventionnee == 50
    assert l['Aliment démarrage'].subventionne is False and l['Aliment démarrage'].valeur_unitaire == 12000
    page = client.get('/livraisons/').get_data(as_text=True)
    assert '1 000 têtes Poussins chair, 40 sacs Aliment démarrage' in page and 'À confirmer' in page


def test_controles_du_formulaire(client, monde):
    connecter(client, 'agent1')
    demain = date.today() + timedelta(days=1)
    page = client.post('/livraisons/nouvelle', data=form_livraison(
        monde['f1'], (monde['poussins'], 10.5, True, 0, None), (monde['poussins'], 5, False, None, None),
        jour=demain)).get_data(as_text=True)
    assert 'dans le futur' in page and 'nombre entier' in page and 'entre 1 et 100' in page
    assert 'figure deux fois' in page
    page = client.post('/livraisons/nouvelle', data={'ferme': monde['f1'].numero,
                                                     'date_livraison': date.today().isoformat()}).get_data(as_text=True)
    assert 'Ajoutez au moins un produit' in page
    assert Livraison.query.count() == 0


def test_agent_ne_livre_pas_hors_de_ses_fermes(client, monde):
    connecter(client, 'agent1')
    page = client.post('/livraisons/nouvelle', data=form_livraison(monde['f2'], (monde['vaccin'], 100, False, None, None))
                       ).get_data(as_text=True)
    assert 'Choisissez la ferme' in page and Livraison.query.count() == 0


def test_cloisonnement_des_livraisons(client, monde):
    l1 = livrer(monde['f1'], [(monde['vaccin'], 100)])
    l2 = livrer(monde['f2'], [(monde['vaccin'], 200)])
    connecter(client, 'agent1')
    page = client.get('/livraisons/').get_data(as_text=True)
    assert l1.numero in page and l2.numero not in page
    assert client.get(f'/livraisons/{l2.numero}').status_code == 403
    assert client.post(f'/livraisons/{l2.numero}/tout-recu').status_code == 403


@pytest.mark.parametrize('profil', [Profil.VETO, Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR, Profil.AUDITEUR])
def test_pas_d_acces(client, monde, profil):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/livraisons/').status_code == 403
    assert client.get(f'/livraisons/{liv.numero}').status_code == 403
    assert client.post(f'/livraisons/{liv.numero}/tout-recu').status_code == 403


def test_modification_tant_qu_a_confirmer(client, monde):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    connecter(client, 'agent1')
    client.post(f'/livraisons/{liv.numero}/modifier', data=form_livraison(
        monde['f1'], (monde['vaccin'], 150, False, None, None), (monde['aliment'], 10, False, None, None)))
    db.session.refresh(liv)
    assert sorted(l.quantite_livree for l in liv.lignes) == [10, 150]
    liv.statut = S.RECUE
    db.session.commit()
    assert client.get(f'/livraisons/{liv.numero}/modifier').status_code == 403


# ── Confirmation par l'éleveur ──────────────────────────────────────────

def test_eleveur_tout_recu_avec_morts_et_annulation(client, monde):
    liv = livrer(monde['f1'], [(monde['poussins'], 1000), (monde['aliment'], 40)])
    autre = livrer(monde['f2'], [(monde['vaccin'], 10)])
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'Livraison à confirmer' in page and 'Tout reçu' in page and "J'ai reçu moins" in page
    assert "Morts à l'arrivée" in page and autre.numero not in page
    lp = next(l for l in liv.lignes if l.produit.type == 'Poussins')
    r = client.post(f'/livraisons/{liv.numero}/tout-recu', data={f'morts-{lp.id}': '12'})
    assert r.location.endswith('/')
    db.session.refresh(liv)
    assert liv.statut == S.RECUE and lp.morts_arrivee == 12 and liv.confirmee_par == monde['el'].id
    assert not liv.confirmee_par_agent
    page = client.get('/').get_data(as_text=True)
    assert 'Reçue ✓' in page and 'Annuler' in page and 'Livraison à confirmer' not in page
    conf = JournalAudit.query.filter_by(action='CONFIRMATION').one()
    assert 'tout reçu' in conf.detail and "par l'éleveur Eleveur1" in conf.detail
    # « Annuler » dans les 10 secondes : de nouveau à confirmer
    client.post(f'/livraisons/{liv.numero}/annuler-confirmation')
    db.session.refresh(liv)
    assert liv.statut == S.A_CONFIRMER and lp.quantite_recue is None and lp.morts_arrivee is None
    assert JournalAudit.query.filter_by(action='CONF_ANNULEE').count() == 1


def test_annulation_impossible_apres_le_delai(client, monde):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    connecter(client, 'eleveur1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    liv.confirmee_le = maintenant() - timedelta(minutes=2)
    db.session.commit()
    assert 'Annuler' not in client.get('/').get_data(as_text=True).split('ma-ferme-zone')[1][:400]
    r = client.post(f'/livraisons/{liv.numero}/annuler-confirmation', follow_redirects=True)
    assert 'délai pour annuler est passé' in r.get_data(as_text=True)
    assert db.session.get(Livraison, liv.id).statut == S.RECUE


def test_annulation_reservee_a_celui_qui_a_confirme(client, monde):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    connecter(client, 'eleveur1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    client.post(f'/livraisons/{liv.numero}/annuler-confirmation')
    assert db.session.get(Livraison, liv.id).statut == S.RECUE


def test_eleveur_recu_moins(client, monde):
    liv = livrer(monde['f1'], [(monde['poussins'], 1000), (monde['aliment'], 40)])
    lp, la = sorted(liv.lignes, key=lambda l: l.produit.type != 'Poussins')
    connecter(client, 'eleveur1')
    page = client.get(f'/livraisons/{liv.numero}/recu-moins').get_data(as_text=True)
    assert 'value="1000"' in page and 'value="40"' in page   # préremplis
    page = client.post(f'/livraisons/{liv.numero}/recu-moins', data={
        f'recue-{lp.id}': '1000', f'recue-{la.id}': '38', f'morts-{lp.id}': '5'}).get_data(as_text=True)
    assert 'choisissez le motif' in page
    page = client.post(f'/livraisons/{liv.numero}/recu-moins', data={
        f'recue-{lp.id}': '1200', f'recue-{la.id}': '38', f'motif-{la.id}': 'Abîmé'}).get_data(as_text=True)
    assert 'ne peut pas dépasser' in page
    client.post(f'/livraisons/{liv.numero}/recu-moins', data={
        f'recue-{lp.id}': '1000', f'recue-{la.id}': '38', f'motif-{la.id}': 'Abîmé', f'morts-{lp.id}': '5'})
    db.session.refresh(liv)
    assert liv.statut == S.RECUE_ECART and la.quantite_recue == 38 and la.motif_ecart == 'Abîmé'
    assert lp.morts_arrivee == 5 and lp.motif_ecart is None
    # Confirmée : plus modifiable ni reconfirmable
    r = client.post(f'/livraisons/{liv.numero}/tout-recu', follow_redirects=True)
    assert 'plus à confirmer' in r.get_data(as_text=True)


def test_agent_confirme_pour_l_eleveur(client, monde):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    monde['a1'].prenom = 'Paul'
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get(f'/livraisons/{liv.numero}').get_data(as_text=True)
    assert "Confirmer pour l'éleveur" in page
    assert 'Tout reçu' in client.get(f'/livraisons/{liv.numero}/confirmer').get_data(as_text=True)
    r = client.post(f'/livraisons/{liv.numero}/tout-recu')
    assert r.location.endswith(f'/livraisons/{liv.numero}')
    db.session.refresh(liv)
    assert liv.confirmee_par_agent and liv.confirmee_par == monde['a1'].id
    page = client.get(f'/livraisons/{liv.numero}').get_data(as_text=True)
    assert "confirmé par l'agent Paul Agent1 pour l'éleveur" in page
    conf = JournalAudit.query.filter_by(action='CONFIRMATION').one()
    assert "confirmé par l'agent Paul Agent1 pour l'éleveur" in conf.detail


@pytest.mark.parametrize('identifiant,profil', [('admin', Profil.ADMIN), ('dge', Profil.DGE)])
def test_admin_et_dge_ne_confirment_pas(client, monde, identifiant, profil):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    creer_utilisateur(identifiant, profil)
    connecter(client, identifiant)
    assert client.post(f'/livraisons/{liv.numero}/tout-recu').status_code == 403
    assert 'Confirmer pour' not in client.get(f'/livraisons/{liv.numero}').get_data(as_text=True)


# ── Annulation, correction ──────────────────────────────────────────────

def test_annulation_par_la_dge(client, monde):
    liv = livrer(monde['f1'], [(monde['vaccin'], 100)])
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    r = client.post(f'/livraisons/{liv.numero}/annuler', data={'motif': ''}, follow_redirects=True)
    assert 'motif' in r.get_data(as_text=True) and db.session.get(Livraison, liv.id).statut == S.A_CONFIRMER
    client.post(f'/livraisons/{liv.numero}/annuler', data={'motif': 'Doublon de saisie'})
    db.session.refresh(liv)
    assert liv.statut == S.ANNULEE and liv.motif_annulation == 'Doublon de saisie'
    assert JournalAudit.query.filter_by(action='ANNULATION', table_nom='livraison').count() == 1
    recue = livrer(monde['f1'], [(monde['vaccin'], 100)], statut=S.RECUE)
    client.post(f'/livraisons/{recue.numero}/annuler', data={'motif': 'x'})
    assert db.session.get(Livraison, recue.id).statut == S.RECUE   # trop tard : correction


def test_correction_avec_motif(client, monde):
    liv = livrer(monde['f1'], [(monde['aliment'], 40)])
    connecter(client, 'eleveur1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    l = liv.lignes[0]
    page = client.post(f'/livraisons/{liv.numero}/corriger', data={f'recue-{l.id}': '36', f'motif-{l.id}': 'Manquant'}
                       ).get_data(as_text=True)
    assert 'motif de la correction' in page
    client.post(f'/livraisons/{liv.numero}/corriger', data={
        f'recue-{l.id}': '36', f'motif-{l.id}': 'Manquant', 'motif_correction': 'Recompté avec l\'éleveur'})
    db.session.refresh(liv)
    assert liv.statut == S.RECUE_ECART and l.quantite_recue == 36
    corr = JournalAudit.query.filter_by(action='CORRECTION').one()
    assert "Recompté avec l'éleveur" in corr.detail
    creer_utilisateur('dge', Profil.DGE)
    client.post('/auth/deconnexion')
    connecter(client, 'dge')
    assert client.get(f'/livraisons/{liv.numero}/corriger').status_code == 403


# ── Stock ───────────────────────────────────────────────────────────────

def test_stock_sacs_kg_et_poussins_en_attente(client, monde):
    f1 = monde['f1']
    l1 = livrer(f1, [(monde['poussins'], 1000), (monde['aliment'], 40)])
    for l in l1.lignes:
        l.quantite_recue = l.quantite_livree
        l.morts_arrivee = 12 if l.produit.type == 'Poussins' else None
    l1.statut = S.RECUE
    l2 = livrer(f1, [(monde['aliment'], 10)])
    l2.lignes[0].quantite_recue = 8
    l2.statut = S.RECUE_ECART
    livrer(f1, [(monde['aliment'], 100)])                          # à confirmer : pas en stock
    livrer(f1, [(monde['aliment'], 100)], statut=S.ANNULEE)        # annulée : jamais en stock
    db.session.commit()
    stock = {s['produit'].nom: s for s in intrants.stock_ferme(f1)}
    assert stock['Poussins chair']['stock'] == 988
    assert stock['Aliment démarrage']['stock'] == 48 and stock['Aliment démarrage']['kg'] == 1200
    connecter(client, 'agent1')
    page = client.get(f'/fermes/{f1.numero}').get_data(as_text=True)
    assert "Stock d'intrants" in page and '988' in page and 'en attente de bande' in page
    assert '48' in page and '1 200 kg' in page


def test_utilisations_prevues_pour_le_lot_bandes(monde):
    assert intrants.quantites_utilisees(monde['f1']) == {}


# ── Alertes ─────────────────────────────────────────────────────────────

def test_alertes_retard_et_ecart(client, monde):
    vieille = livrer(monde['f1'], [(monde['vaccin'], 100)], jour=date.today() - timedelta(days=5))
    livrer(monde['f1'], [(monde['vaccin'], 100)], jour=date.today() - timedelta(days=1))      # dans le délai
    livrer(monde['f2'], [(monde['vaccin'], 100)], jour=date.today() - timedelta(days=9))      # autre agent
    ecart = livrer(monde['f1'], [(monde['vaccin'], 100)], statut=S.RECUE_ECART)
    ecart.confirmee_le = maintenant()
    ancienne = livrer(monde['f1'], [(monde['vaccin'], 100)], statut=S.RECUE_ECART)
    ancienne.confirmee_le = maintenant() - timedelta(days=40)                                  # hors 30 jours
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get('/').get_data(as_text=True)
    assert '1 livraison non confirmée depuis plus de 3 jours' in page
    assert '1 livraison reçue avec écart' in page
    assert 'class="alertes-badge ">2</span>' in page   # compteur de l'encadré : 1 + 1
    liste = client.get('/livraisons/?alerte=retard').get_data(as_text=True)
    assert vieille.numero in liste and ecart.numero not in liste
    assert ecart.numero in client.get('/livraisons/?alerte=ecart').get_data(as_text=True)
    # Le délai se règle dans les Paramètres
    Parametre.query.filter_by(cle='intrants.delai_confirmation_jours').one().valeur = '0'
    db.session.commit()
    assert '2 livraisons non confirmées depuis plus de 0 jour' in client.get('/').get_data(as_text=True)


def test_pas_d_alerte_pour_l_eleveur(client, monde):
    livrer(monde['f1'], [(monde['vaccin'], 100)], jour=date.today() - timedelta(days=9))
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'non confirmée depuis' not in page and 'Livraison à confirmer' in page


def test_mes_livraisons(client, monde):
    livrer(monde['f1'], [(monde['vaccin'], 100)])
    livrer(monde['f2'], [(monde['vaccin'], 7)])
    connecter(client, 'eleveur1')
    page = client.get('/livraisons/mes-livraisons').get_data(as_text=True)
    assert 'Vaccin Newcastle' in page and '>7<' not in page
    assert client.get('/livraisons/').status_code == 403
