"""Lot 1 — fermes : numéros, doublons, statut, bâtiments, position, localités, cloisonnement."""
import pytest

from app import db
from app.models import Ferme, Localite, Profil, JournalAudit, Utilisateur, Province, Batiment
from app.services import fermes as regles
from tests.conftest import creer_utilisateur, connecter, province, creer_ferme


def form(**champs):
    d = {'nom': 'Ferme Mba', 'exploitant_nom': 'Jean Mba', 'exploitant_telephone': '+241 77 12 34 56',
         'province_id': str(province('EST').id), 'localite_id': ''}
    d.update(champs)
    return d


@pytest.fixture
def libreville(app):
    loc = Localite(province=province('EST'), nom='Libreville')
    db.session.add(loc)
    db.session.commit()
    return loc


# ── Numéros ─────────────────────────────────────────────────────────────

def test_numero_par_province_sur_3_chiffres(app):
    assert creer_ferme('A', 'EST', 'Ntoum').numero == 'EST-001'
    assert creer_ferme('B', 'EST', 'Ntoum').numero == 'EST-002'
    assert creer_ferme('C', 'WNT', 'Oyem').numero == 'WNT-001'


def test_code_province_verrouille_des_qu_une_ferme_existe(client_admin):
    est = province('EST')
    creer_ferme('A', 'EST', 'Ntoum')
    r = client_admin.post(f'/administration/provinces/{est.id}/modifier',
                          data={'code': 'ESTU', 'nom': 'Estuaire', 'actif': 'on'}, follow_redirects=True)
    assert 'ne peut plus changer' in r.get_data(as_text=True)
    assert db.session.get(Province, est.id).code == 'EST'
    # Le nom reste modifiable
    client_admin.post(f'/administration/provinces/{est.id}/modifier',
                      data={'code': 'EST', 'nom': 'Estuaire', 'actif': 'on'})


# ── Création par écran ──────────────────────────────────────────────────

def test_agent_cree_dans_sa_province_et_devient_referent(client, app, libreville):
    agent = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    connecter(client, 'agent')
    page = client.get('/fermes/nouvelle').get_data(as_text=True)
    assert 'champ-fixe' in page and 'Estuaire' in page   # une seule province : préremplie
    r = client.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id), latitude='0,3921',
                                                  longitude='9,6103', gps_precision_m='8', gps_source='GPS'))
    assert r.location.endswith('/fermes/EST-001')
    f = Ferme.query.one()
    assert f.agent_id == agent.id and f.statut == 'En préparation' and f.gps_source == 'GPS'
    assert f.gps_precision_m == 8 and f.gps_date is not None and f.cree_par == agent.id
    assert [h.statut for h in f.historique] == ['En préparation']


def test_agent_ne_cree_pas_hors_de_ses_provinces(client, app):
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    loc = Localite(province=province('HOG'), nom='Franceville')
    db.session.add(loc)
    db.session.commit()
    connecter(client, 'agent')
    r = client.post('/fermes/nouvelle', data=form(province_id=str(province('HOG').id),
                                                  localite_id=str(loc.id)))
    assert 'Choisissez la province' in r.get_data(as_text=True)
    assert Ferme.query.count() == 0


@pytest.mark.parametrize('profil', [Profil.VETO, Profil.ELEVEUR, Profil.BCEG, Profil.AUDITEUR])
def test_creation_refusee(client, app, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/fermes/nouvelle').status_code == 403


def test_dge_choisit_l_agent(client, app, libreville):
    agent = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    client.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id), agent_id=str(agent.id)))
    assert Ferme.query.one().agent_id == agent.id


def test_champs_obligatoires(client_admin, libreville):
    r = client_admin.post('/fermes/nouvelle', data=form(nom='', exploitant_telephone='12',
                                                        localite_id=str(libreville.id)))
    page = r.get_data(as_text=True)
    assert 'nom de la ferme est obligatoire' in page and 'au moins 7 chiffres' in page
    assert 'Jean Mba' in page   # la saisie est conservée


# ── Doublons ────────────────────────────────────────────────────────────

def test_doublon_telephone(client_admin, libreville):
    creer_ferme('Ferme A', 'EST', 'Libreville', telephone='077123456')
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id),
                                                        exploitant_telephone='+241 07 71 23 456'))
    assert 'Ce téléphone est déjà celui de l&#39;exploitant de la ferme EST-001 (Ferme A)' in r.get_data(as_text=True)
    assert Ferme.query.count() == 1


def test_doublon_nom_meme_localite(client_admin, libreville):
    creer_ferme('Ferme Mbâ', 'EST', 'Libreville')
    r = client_admin.post('/fermes/nouvelle', data=form(nom='FERME MBA', localite_id=str(libreville.id)))
    assert 'même nom existe déjà dans cette localité : EST-001' in r.get_data(as_text=True)


def test_meme_nom_autre_localite_accepte(client_admin, libreville):
    creer_ferme('Ferme Mba', 'EST', 'Ntoum')
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id)))
    assert r.status_code == 302 and Ferme.query.count() == 2


def test_doublon_reference_ami(client_admin, libreville):
    creer_ferme('Ferme A', 'EST', 'Libreville', reference_ami='AMI-12')
    f = creer_ferme('Ferme B', 'EST', 'Libreville')
    r = client_admin.post(f'/fermes/{f.numero}/modifier', data=form(
        nom='Ferme B', exploitant_telephone=f.exploitant_telephone, localite_id=str(f.localite_id),
        reference_ami='ami-12', statut='En préparation'))
    assert 'référence AMI AMI-12 est déjà celle de la ferme EST-001' in r.get_data(as_text=True)


def test_normalisations():
    assert regles.normaliser_telephone('+241 77 12 34 56') == regles.normaliser_telephone('077123456')
    assert regles.normaliser_nom("N'kok") == regles.normaliser_nom('Nkok')
    assert regles.se_ressemblent('Ntoum', 'Ntoun') and not regles.se_ressemblent('Oyem', 'Owendo')


# ── Modification, statut, suspension ────────────────────────────────────

def test_statut_historique_et_pas_de_suppression(client_admin, admin):
    f = creer_ferme('Ferme A', 'EST', 'Libreville')
    base = form(nom='Ferme A', exploitant_telephone=f.exploitant_telephone, localite_id=str(f.localite_id))
    client_admin.post(f'/fermes/{f.numero}/modifier', data={**base, 'statut': 'Opérationnelle', 'cohorte': '1',
                                                            'infrastructures': ['Clôture', 'Pédiluve']})
    client_admin.post(f'/fermes/{f.numero}/modifier', data={**base, 'statut': 'Suspendue', 'cohorte': '1',
                                                            'infrastructures': ['Clôture', 'Pédiluve']})
    db.session.refresh(f)
    assert [h.statut for h in f.historique] == ['Suspendue', 'Opérationnelle', 'En préparation']
    assert f.cohorte == 1 and [i.infrastructure for i in f.infrastructures] == ['Clôture', 'Pédiluve']
    page = client_admin.get(f'/fermes/{f.numero}').get_data(as_text=True)
    assert 'Historique du statut' in page and 'Suspendue' in page and 'Clôture, Pédiluve' in page
    assert not [r for r in client_admin.application.url_map.iter_rules()
                if r.rule.startswith('/fermes') and 'supprimer' in r.rule]
    modif = JournalAudit.query.filter_by(action='MODIFICATION', table_nom='ferme').all()[-1]
    assert modif.avant['statut'] == 'Opérationnelle' and modif.apres['statut'] == 'Suspendue'


def test_seul_admin_change_la_province_numero_inchange(client, app):
    f = creer_ferme('Ferme A', 'EST', 'Libreville')
    hog = Localite(province=province('HOG'), nom='Moanda')
    db.session.add(hog)
    db.session.commit()
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    data = form(nom='Ferme A', exploitant_telephone=f.exploitant_telephone, province_id=str(province('HOG').id),
                localite_id=str(hog.id), statut='En préparation')
    r = client.post(f'/fermes/{f.numero}/modifier', data=data)
    assert 'ne correspond pas à la province' in r.get_data(as_text=True)   # province ignorée pour la DGE
    client.post('/auth/deconnexion')
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    client.post(f'/fermes/{f.numero}/modifier', data=data)
    db.session.refresh(f)
    assert f.province.code == 'HOG' and f.numero == 'EST-001'
    modif = JournalAudit.query.filter_by(action='MODIFICATION', table_nom='ferme').all()[-1]
    assert 'province_id' in modif.apres


# ── Bâtiments ───────────────────────────────────────────────────────────

def test_batiments_codes_et_capacite(client_admin):
    f = creer_ferme('Ferme A', 'EST', 'Libreville')
    client_admin.post(f'/fermes/{f.numero}/batiments/ajouter', data={'capacite': '500'})
    client_admin.post(f'/fermes/{f.numero}/batiments/ajouter', data={'capacite': '300', 'nom': 'Poulailler 2'})
    r = client_admin.post(f'/fermes/{f.numero}/batiments/ajouter', data={'capacite': '-3'}, follow_redirects=True)
    assert 'nombre de poulets' in r.get_data(as_text=True)
    db.session.refresh(f)
    assert [b.code for b in f.batiments] == ['B1', 'B2'] and f.capacite == 800
    b1 = f.batiments[0]
    client_admin.post(f'/fermes/{f.numero}/batiments/{b1.id}/modifier', data={'archiver': '1'})  # lot A1 : archivé
    db.session.refresh(f)
    assert f.capacite == 300
    client_admin.post(f'/fermes/{f.numero}/batiments/ajouter', data={'capacite': '100'})
    assert Batiment.query.order_by(Batiment.id.desc()).first().code == 'B3'   # jamais réutilisé
    page = client_admin.get(f'/fermes/{f.numero}').get_data(as_text=True)
    assert 'Bande en cours' in page and 'Total' in page


# ── Position ────────────────────────────────────────────────────────────

def test_position_hors_province_avertit_sans_bloquer(client_admin, libreville):
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id),
                                                        latitude='-1,6333', longitude='13,5833'),
                          follow_redirects=True)
    page = r.get_data(as_text=True)
    assert 'créée' in page and 'semble hors de la province Estuaire' in page and 'Haut-Ogooué' in page
    assert Ferme.query.one().gps_source == 'MANUELLE'


def test_position_dans_la_province(client_admin, libreville):
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id),
                                                        latitude='0.3921', longitude='9.6103'),
                          follow_redirects=True)
    page = r.get_data(as_text=True)
    assert 'Dans la province Estuaire' in page and 'carte-province' in page


def test_position_incomplete_refusee(client_admin, libreville):
    r = client_admin.post('/fermes/nouvelle', data=form(localite_id=str(libreville.id), latitude='0,39'))
    assert 'aucune des deux' in r.get_data(as_text=True)


def test_formulaire_prevoit_le_cas_sans_gps(client_admin, libreville):
    page = client_admin.get('/fermes/nouvelle').get_data(as_text=True)
    assert 'Prendre la position' in page and 'Saisir à la main' in page
    assert 'Position automatique indisponible, saisissez-la à la main' in page
    assert 'Le numéro est donné automatiquement' in page


# ── Localité nouvelle saisie sur le terrain ─────────────────────────────

def test_localite_nouvelle_ressemblante_puis_choix(client, app):
    agent = creer_utilisateur('agent', Profil.AGENT, ['EST'])
    nkok = Localite(province=province('EST'), nom="N'kok")
    db.session.add(nkok)
    db.session.commit()
    connecter(client, 'agent')
    data = form(localite_id='nouvelle', localite_nouvelle='Nkoq')
    page = client.post('/fermes/nouvelle', data=data).get_data(as_text=True)
    assert 'Vouliez-vous dire' in page and 'N&#39;kok' in page and Ferme.query.count() == 0
    # « Oui, N'kok »
    client.post('/fermes/nouvelle', data={**data, 'localite_choisie': str(nkok.id)})
    assert Ferme.query.one().localite_id == nkok.id
    assert Localite.query.count() == 1


def test_localite_nouvelle_confirmee_a_verifier(client, app):
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    db.session.add(Localite(province=province('EST'), nom="N'kok"))
    db.session.commit()
    connecter(client, 'agent')
    client.post('/fermes/nouvelle', data=form(localite_id='nouvelle', localite_nouvelle='Nkoq',
                                              confirmer_nouvelle='1'))
    loc = Localite.query.filter_by(nom='Nkoq').one()
    assert loc.a_verifier and Ferme.query.one().localite_id == loc.id


def test_localite_identique_reutilisee(client_admin):
    nkok = Localite(province=province('EST'), nom="N'kok")
    db.session.add(nkok)
    db.session.commit()
    client_admin.post('/fermes/nouvelle', data=form(localite_id='nouvelle', localite_nouvelle='NKOK'))
    assert Ferme.query.one().localite_id == nkok.id and Localite.query.count() == 1


def test_admin_valide_et_fusionne(client_admin):
    est = province('EST')
    bonne = Localite(province=est, nom="N'kok")
    a_valider = Localite(province=est, nom='Bikélé', a_verifier=True)
    doublon = Localite(province=est, nom='Nkoq', a_verifier=True)
    db.session.add_all([bonne, a_valider, doublon])
    db.session.commit()
    f = creer_ferme('Ferme A', 'EST', 'Nkoq')
    page = client_admin.get('/administration/provinces/?a_verifier=1').get_data(as_text=True)
    assert 'Bikélé' in page and 'Nkoq' in page and "N&#39;kok" not in page.split('<tbody>')[1].split('</tbody>')[0]
    client_admin.post(f'/administration/provinces/localites/{a_valider.id}/valider')
    assert db.session.get(Localite, a_valider.id).a_verifier is False
    client_admin.post(f'/administration/provinces/localites/{doublon.id}/fusionner',
                      data={'cible_id': str(bonne.id)})
    db.session.refresh(f)
    assert f.localite_id == bonne.id and db.session.get(Localite, doublon.id) is None
    fusion = JournalAudit.query.filter_by(action='FUSION').one()
    assert 'Nkoq' in fusion.detail and "N'kok" in fusion.detail and 'EST-001' in fusion.detail


def test_fusion_refusee_vers_autre_province(client_admin):
    est, hog = province('EST'), province('HOG')
    a = Localite(province=est, nom='Nkoq', a_verifier=True)
    b = Localite(province=hog, nom='Moanda')
    db.session.add_all([a, b])
    db.session.commit()
    r = client_admin.post(f'/administration/provinces/localites/{a.id}/fusionner',
                          data={'cible_id': str(b.id)}, follow_redirects=True)
    assert 'même province' in r.get_data(as_text=True) and db.session.get(Localite, a.id)


# ── Cloisonnement ───────────────────────────────────────────────────────

@pytest.fixture
def deux_agents(app):
    a1 = creer_utilisateur('agent1', Profil.AGENT, ['EST'])
    a2 = creer_utilisateur('agent2', Profil.AGENT, ['EST'])
    f1 = creer_ferme('Ferme Un', 'EST', 'Libreville', agent=a1)
    f2 = creer_ferme('Ferme Deux', 'EST', 'Ntoum', agent=a2)
    f3 = creer_ferme('Ferme Trois', 'HOG', 'Franceville')
    return a1, a2, f1, f2, f3


def test_agent_ne_voit_que_ses_fermes(client, deux_agents):
    a1, a2, f1, f2, f3 = deux_agents
    connecter(client, 'agent1')
    page = client.get('/fermes/').get_data(as_text=True)
    assert 'Ferme Un' in page and 'Ferme Deux' not in page and 'Ferme Trois' not in page
    assert '1 ferme ·' in page
    assert client.get(f'/fermes/{f2.numero}').status_code == 403
    assert client.get(f'/fermes/{f2.numero}/modifier').status_code == 403
    assert client.post(f'/fermes/{f2.numero}/batiments/ajouter', data={'capacite': '1'}).status_code == 403
    assert client.get(f'/fermes/{f1.numero}/modifier').status_code == 200


def test_veto_lit_les_fermes_de_ses_provinces(client, deux_agents):
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    connecter(client, 'veto')
    page = client.get('/fermes/').get_data(as_text=True)
    assert 'Ferme Un' in page and 'Ferme Deux' in page and 'Ferme Trois' not in page
    assert 'Nouvelle ferme' not in page
    fiche = client.get(f'/fermes/{deux_agents[2].numero}').get_data(as_text=True)
    assert 'Modifier' not in fiche and 'Bâtiment' in fiche and 'btn-edit' not in fiche
    assert client.get(f'/fermes/{deux_agents[2].numero}/modifier').status_code == 403


@pytest.mark.parametrize('profil', [Profil.ELEVEUR, Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR, Profil.AUDITEUR])
def test_pas_d_acces_aux_fermes(client, deux_agents, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/fermes/').status_code == 403
    assert client.get(f'/fermes/{deux_agents[2].numero}').status_code == 403


def test_eleveur_rattache_depuis_utilisateurs_ne_voit_que_sa_ferme(client, deux_agents):
    f1, f2 = deux_agents[2], deux_agents[3]
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    r = client.post('/administration/utilisateurs/creer', data={
        'identifiant': 'eleveur1', 'nom': 'Obiang', 'profil': 'ELEVEUR', 'mot_de_passe': 'Provisoire-2026'},
        follow_redirects=True)
    assert 'au moins une ferme' in r.get_data(as_text=True)
    client.post('/administration/utilisateurs/creer', data={
        'identifiant': 'eleveur1', 'nom': 'Obiang', 'profil': 'ELEVEUR', 'mot_de_passe': 'Provisoire-2026',
        'fermes': [str(f1.id)]})
    u = Utilisateur.query.filter_by(identifiant='eleveur1').one()
    assert u.ferme_ids == [f1.id] and u.provinces == []
    creation = JournalAudit.query.filter_by(action='CREATION', table_nom='utilisateur').all()[-1]
    assert creation.apres['fermes'] == [f1.numero]
    u.doit_changer_mdp = False
    db.session.commit()
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1', 'Provisoire-2026')
    page = client.get('/').get_data(as_text=True)
    assert 'class="tab-btn' not in page and 'data-entete="agent"' not in page   # agent sans téléphone
    page = client.get('/moi').get_data(as_text=True)
    assert 'Ferme Un' in page and 'Ferme Deux' not in page
    assert client.get(f'/fermes/{f2.numero}').status_code == 403
