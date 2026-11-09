import pytest

from app import db
from app.models import Utilisateur, Profil, Province, Localite, ListeDeroulante, Parametre
from app.routes import listes as module_listes
from tests.conftest import province, creer_utilisateur


def creer(client, **champs):
    donnees = {'identifiant': 'agent1', 'nom': 'Mba', 'profil': 'AGENT',
               'provinces': [str(province('EST').id)], 'mot_de_passe': 'Provisoire-2026'}
    donnees.update(champs)
    return client.post('/administration/utilisateurs/creer', data=donnees, follow_redirects=True)


def test_creer_utilisateur(client_admin):
    r = creer(client_admin, identifiant='Agent.Un')
    assert 'créé' in r.get_data(as_text=True)
    u = Utilisateur.query.filter_by(identifiant='agent.un').one()
    assert u.doit_changer_mdp and u.actif and u.province_ids == [province('EST').id]


@pytest.mark.parametrize('champs,message', [
    ({'identifiant': 'admin'}, 'déjà utilisé'),
    ({'identifiant': 'a b'}, 'identifiant doit'),
    ({'provinces': []}, 'au moins une province'),
    ({'mot_de_passe': 'court'}, 'au moins 10'),
    ({'nom': ''}, 'nom est obligatoire'),
    ({'profil': 'PIRATE'}, 'Choisissez un profil'),
])
def test_creer_utilisateur_refus(client_admin, champs, message):
    r = creer(client_admin, **champs)
    assert message in r.get_data(as_text=True)


def test_profil_national_sans_province(client_admin):
    creer(client_admin, profil='DGE')
    assert Utilisateur.query.filter_by(identifiant='agent1').one().provinces == []


def test_desactiver_et_nouveau_mot_de_passe(client_admin):
    creer(client_admin)
    u = Utilisateur.query.filter_by(identifiant='agent1').one()
    u.doit_changer_mdp = False
    db.session.commit()
    client_admin.post(f'/administration/utilisateurs/{u.id}/modifier', data={
        'nom': 'Mba', 'profil': 'AGENT', 'provinces': [str(province('EST').id)],
        'mot_de_passe': 'Autre-mdp-2026'})
    db.session.refresh(u)
    assert u.actif is False and u.doit_changer_mdp is True and u.check_password('Autre-mdp-2026')


def test_admin_ne_se_desactive_pas(client_admin, admin):
    r = client_admin.post(f'/administration/utilisateurs/{admin.id}/modifier',
                          data={'nom': 'Admin', 'profil': 'ADMIN'}, follow_redirects=True)
    assert 'votre propre compte' in r.get_data(as_text=True)


def test_dernier_admin_garde_son_profil(client_admin, admin):
    r = client_admin.post(f'/administration/utilisateurs/{admin.id}/modifier',
                          data={'nom': 'Admin', 'profil': 'DGE', 'actif': 'on'}, follow_redirects=True)
    assert 'au moins un administrateur' in r.get_data(as_text=True)
    assert db.session.get(Utilisateur, admin.id).profil == Profil.ADMIN


def test_liste_et_filtres(client_admin):
    creer(client_admin)
    creer_utilisateur('veto1', Profil.VETO, ['HOG'])
    page = client_admin.get(f'/administration/utilisateurs/?province={province("HOG").id}').get_data(as_text=True)
    assert 'veto1' in page and 'agent1' not in page
    page = client_admin.get('/administration/utilisateurs/?profil=AGENT').get_data(as_text=True)
    assert 'agent1' in page and 'veto1' not in page


def test_localites(client_admin):
    est = province('EST')
    client_admin.post(f'/administration/provinces/{est.id}/localites/creer', data={'nom': 'Owendo'})
    r = client_admin.post(f'/administration/provinces/{est.id}/localites/creer', data={'nom': 'owendo'},
                          follow_redirects=True)
    assert 'existe déjà' in r.get_data(as_text=True)
    loc = Localite.query.filter_by(nom='Owendo').one()
    client_admin.post(f'/administration/provinces/localites/{loc.id}/modifier', data={'nom': 'Owendo'})
    assert db.session.get(Localite, loc.id).actif is False
    page = client_admin.get(f'/administration/provinces/?province={est.id}').get_data(as_text=True)
    assert 'Owendo' in page


def test_province_code(client_admin):
    est = province('EST')
    r = client_admin.post(f'/administration/provinces/{est.id}/modifier',
                          data={'code': 'HOG', 'nom': 'Estuaire', 'actif': 'on'}, follow_redirects=True)
    assert 'déjà pris' in r.get_data(as_text=True)
    r = client_admin.post(f'/administration/provinces/{est.id}/modifier',
                          data={'code': 'e1', 'nom': 'Estuaire', 'actif': 'on'}, follow_redirects=True)
    assert 'lettres majuscules' in r.get_data(as_text=True)
    assert Province.query.filter_by(code='EST').count() == 1


def test_parametres(client_admin, admin):
    p = Parametre.query.filter_by(cle='securite.mdp_longueur_min').one()
    r = client_admin.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': 'douze'},
                          follow_redirects=True)
    assert 'nombre entier' in r.get_data(as_text=True)
    client_admin.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': '12'})
    db.session.refresh(p)
    assert p.valeur == '12' and p.modifie_par == admin.id
    page = client_admin.get('/administration/parametres/').get_data(as_text=True)
    assert 'securite.' not in page   # pas de nom technique à l'écran


def test_listes_comme_yl1(client_admin, monkeypatch):
    monkeypatch.setattr(module_listes, 'CATEGORIES', {'essai': 'Liste d\'essai'})
    client_admin.post('/administration/listes/ajouter', data={'categorie': 'essai', 'valeur': 'Poussin'})
    client_admin.post('/administration/listes/ajouter', data={'categorie': 'essai', 'valeur': 'Aliment'})
    r = client_admin.post('/administration/listes/ajouter', data={'categorie': 'essai', 'valeur': 'poussin'},
                          follow_redirects=True)
    assert 'existe déjà' in r.get_data(as_text=True)
    r = client_admin.post('/administration/listes/ajouter', data={'categorie': 'autre', 'valeur': 'x'},
                          follow_redirects=True)
    assert 'Données invalides' in r.get_data(as_text=True)
    essai = ListeDeroulante.query.filter_by(categorie='essai')
    poussin, aliment = essai.order_by(ListeDeroulante.ordre).all()
    client_admin.post('/administration/listes/reordonner', json={'ids': [aliment.id, poussin.id]})
    assert [v.valeur for v in essai.order_by(ListeDeroulante.ordre)] == ['Aliment', 'Poussin']
    client_admin.post(f'/administration/listes/modifier/{poussin.id}', data={'valeur': 'Poussins', 'actif': '0'})
    assert db.session.get(ListeDeroulante, poussin.id).actif is False
    client_admin.post(f'/administration/listes/modifier/{poussin.id}', data={'valeur': 'Poussins', 'actif': '1'})
    assert db.session.get(ListeDeroulante, poussin.id).actif is True
    # Pas de suppression : ni route, ni bouton
    assert client_admin.post(f'/administration/listes/supprimer/{aliment.id}').status_code == 404
    assert essai.count() == 2
    page = client_admin.get('/administration/listes/').get_data(as_text=True)
    assert 'Poussins' in page and 'btn-del' not in page and 'trash' not in page


def test_parametres_securite_au_moins_1(client_admin):
    p = Parametre.query.filter_by(cle='securite.echecs_avant_blocage').one()
    r = client_admin.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': '0'},
                          follow_redirects=True)
    assert 'au moins 1' in r.get_data(as_text=True)
    assert db.session.get(Parametre, p.id).valeur == '5'


def test_listes_du_lot_1_avec_valeurs_de_depart(client_admin):
    assert 'Valeurs des listes' in client_admin.get('/configuration').get_data(as_text=True)
    page = client_admin.get('/administration/listes/').get_data(as_text=True)
    for titre in ('Statuts de ferme', 'Types d&#39;infrastructures', 'Types d&#39;opérateurs'):
        assert titre in page
    assert 'Opérationnelle' in page and 'Pédiluve' in page and 'Abattoir' in page
    assert 'Bâtiment d&#39;élevage' not in page
