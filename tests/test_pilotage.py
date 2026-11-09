"""Lot 5 — tableaux de bord, carte, rapports, exports, formules."""
import io
from openpyxl import load_workbook

from app import db, indicateurs
from app.models import Profil, JournalAudit, Parametre, Province
from app.services import pilotage, bandes as regles
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, recevoir, bande_ouverte, AUJ  # noqa: F401


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def _journal(action):
    return JournalAudit.query.filter_by(action=action).all()


# ── Tableau de bord ─────────────────────────────────────────────────────

def test_tableau_de_bord_par_profil(client, monde):
    bande_ouverte(monde)
    creer_utilisateur('dge1', Profil.DGE)
    creer_utilisateur('veto1', Profil.VETO, ['HOG'])
    creer_utilisateur('el2', Profil.ELEVEUR)
    db.session.commit()
    connecter(client, 'dge1')
    page = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert 'Tableau de bord national' in page and 'Bandes en cours' in page and '997' in page
    assert 'Mortalité par province' in page   # plusieurs provinces visibles
    page = client.get('/pilotage/tableau-de-bord?cohorte=2').get_data(as_text=True)
    assert 'Bandes en cours' in page
    changer(client, 'agent1')
    page = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert "Indicateurs d" in page and '997' in page and 'Mortalité par province' not in page
    changer(client, 'veto1')   # province sans ferme : rien de l'Estuaire
    page = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert '997' not in page
    changer(client, 'el2')
    assert client.get('/pilotage/tableau-de-bord').status_code == 403


def test_comparaison_avec_la_province_a_partir_de_trois_bandes(monde):
    b = bande_ouverte(monde)
    v = indicateurs.calculer(b)
    assert indicateurs.comparaison_province(b, v) is None   # une seule bande
    bande_ouverte(monde, effectif=800, bat=1)
    liv = recevoir(monde['f2'], [(monde['poussins'], 500, 0)])
    b3 = regles.ouvrir(monde['f2'], monde['f2'].batiments[0], liv.lignes[0], 500, AUJ, None, monde['el'])
    db.session.commit()
    phrase = indicateurs.comparaison_province(b3, indicateurs.calculer(b3))
    assert phrase and "de l'Estuaire" in phrase


# ── Mortalité à l'arrivée ───────────────────────────────────────────────

def test_mortalite_a_l_arrivee_et_alerte_dge(client, monde):
    liv = recevoir(monde['f'], [(monde['poussins'], 1000, 30)])
    liv.fournisseur = 'Couvoir A'
    db.session.commit()
    dge = creer_utilisateur('dge1', Profil.DGE)
    db.session.commit()
    d = pilotage.mortalite_arrivee(dge, {})
    assert d['seuil'] == 2 and d['lignes'][0]['taux'] == 3 and d['lignes'][0]['alerte']
    assert d['fournisseurs'][0]['fournisseur'] == 'Couvoir A'
    connecter(client, 'dge1')
    assert 'au-delà du seuil de mortalité' in client.get('/').get_data(as_text=True)
    Parametre.query.filter_by(cle='intrants.seuil_mortalite_arrivee_pct').one().valeur = '5'
    db.session.commit()
    assert 'au-delà du seuil de mortalité' not in client.get('/').get_data(as_text=True)


# ── Carte ───────────────────────────────────────────────────────────────

def test_carte_des_fermes(client, monde):
    monde['f'].latitude, monde['f'].longitude = 0.4, 9.45
    db.session.commit()
    bande_ouverte(monde)
    dge = creer_utilisateur('dge1', Profil.DGE)
    db.session.commit()
    c = pilotage.carte(dge)
    assert len(c['formes']) == 9 and len(c['points']) == 1 and c['points'][0]['feu'] in ('vert', 'orange', 'rouge')
    connecter(client, 'dge1')
    page = client.get('/pilotage/carte').get_data(as_text=True)
    assert 'point-ferme' in page and monde['f'].numero in page
    autre = Province.query.filter(Province.code != 'EST').first()
    assert monde['f'].numero not in client.get(f'/pilotage/carte?province={autre.id}').get_data(as_text=True)
    changer(client, 'agent1')
    assert client.get('/pilotage/carte').status_code == 403


# ── Rapports PDF ────────────────────────────────────────────────────────

def test_rapports_pdf(client, monde):
    b = bande_ouverte(monde)
    creer_utilisateur('dge1', Profil.DGE)
    db.session.commit()
    connecter(client, 'dge1')
    assert 'Rapport hebdomadaire' in client.get('/pilotage/rapports').get_data(as_text=True)
    for url in ('/pilotage/rapports/hebdomadaire.pdf', f'/pilotage/rapports/hebdomadaire.pdf?province={monde["f"].province_id}',
                f'/pilotage/rapports/mensuel.pdf?mois={AUJ:%Y-%m}'):
        r = client.get(url)
        assert r.status_code == 200 and r.data[:4] == b'%PDF', url
    assert client.get('/pilotage/rapports/mensuel.pdf?mois=n-importe').status_code == 400
    # fin de bande : seulement après la clôture
    assert client.get(f'/pilotage/rapports/bande/{b.numero}.pdf').status_code == 302
    regles.cloturer(b, monde['agent'], 'essai')
    db.session.commit()
    r = client.get(f'/pilotage/rapports/bande/{b.numero}.pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert len([j for j in _journal('EXPORT') if j.table_nom == 'rapport']) == 4


# ── Exports ─────────────────────────────────────────────────────────────

def test_exports_selon_les_droits_et_journalises(client, monde):
    bande_ouverte(monde)
    connecter(client, 'agent1')
    r = client.get('/pilotage/exports/fermes.csv')
    texte = r.data.decode('utf-8-sig')
    assert r.status_code == 200 and 'Ferme Un' in texte and 'Ferme Deux' not in texte   # périmètre de l'agent
    r = client.get('/pilotage/exports/bandes.xlsx')
    ws = load_workbook(io.BytesIO(r.data)).active
    assert ws['A1'].value == 'N°' and ws['A2'].value == 'EST-001-B1-01'
    assert client.get('/pilotage/exports/livraisons.csv').status_code == 200
    assert client.get('/pilotage/exports/autre.csv').status_code == 404
    assert len(_journal('EXPORT')) == 3
    creer_utilisateur('veto1', Profil.VETO, ['EST'])
    db.session.commit()
    changer(client, 'veto1')
    assert client.get('/pilotage/exports/livraisons.csv').status_code == 403
    changer(client, 'eleveur1')
    assert client.get('/pilotage/exports/fermes.csv').status_code == 403


# ── Formules ────────────────────────────────────────────────────────────

def test_moteur_de_formules_sans_eval():
    autorisees = {'a', 'b'}
    assert indicateurs.evaluer('(a + b) * 2 / 4', {'a': 1, 'b': 3}) == 2
    for mauvaise in ('__import__("os")', 'a ** 2', 'open(a)', 'a.b', 'c + 1', 'a +', '[a]', 'a if b else 1'):
        try:
            indicateurs.analyser(mauvaise, autorisees)
            assert False, mauvaise
        except indicateurs.FormuleInvalide:
            pass
    assert indicateurs.evaluer('a / b', {'a': 1, 'b': 0}) is None


def test_formules_tester_enregistrer_revenir(client, client_admin, monde):
    page = client.get('/pilotage/formules').get_data(as_text=True)
    assert 'Tester la formule' in page and 'morts_cumules / mis_en_place * 100' in page
    page = client.post('/pilotage/formules', data={'nom': 'mortalite', 'action': 'tester',
                                                   'formule': 'morts_cumules / mis_en_place * 1000'}).get_data(as_text=True)
    assert 'Avec l' in page and '30' in page
    assert Parametre.query.filter_by(cle='formule.mortalite').first() is None   # tester n'enregistre rien
    page = client.post('/pilotage/formules', data={'nom': 'mortalite', 'action': 'enregistrer', 'formule': 'open(1)'},
                       follow_redirects=True).get_data(as_text=True)
    assert Parametre.query.filter_by(cle='formule.mortalite').first() is None
    client.post('/pilotage/formules', data={'nom': 'mortalite', 'action': 'enregistrer', 'motif': 'pour mille',
                                            'formule': 'morts_cumules / mis_en_place * 1000'})
    assert indicateurs.formule('mortalite') == 'morts_cumules / mis_en_place * 100'   # lot 15 : quatre yeux
    from app.models import Profil
    from app.models.securite import Proposition
    from app.services import approbations
    from tests.conftest import creer_utilisateur
    dge = creer_utilisateur('dge', Profil.DGE)
    approbations.decider(Proposition.query.filter_by(statut='EN_ATTENTE').one(), dge, True)
    db.session.commit()
    assert indicateurs.formule('mortalite') == 'morts_cumules / mis_en_place * 1000'
    b = bande_ouverte(monde)
    assert indicateurs.calculer(b)['mortalite'] == 0
    page = client.get('/pilotage/formules').get_data(as_text=True)
    assert "Revenir à la formule d" in page
    client.post('/pilotage/formules', data={'nom': 'mortalite', 'action': 'origine', 'formule': ''})
    approbations.decider(Proposition.query.filter_by(statut='EN_ATTENTE').one(), dge, True)
    db.session.commit()
    assert indicateurs.formule('mortalite') == 'morts_cumules / mis_en_place * 100'
    assert JournalAudit.query.filter_by(table_nom='parametre').count() >= 2
    changer(client, 'agent1')
    assert client.get('/pilotage/formules').status_code == 403
