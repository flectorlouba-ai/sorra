"""Lot 12 — « case vide ≠ zéro » : les morts et l'aliment démarrent à « — » ; « Aucun mort » et « Pas d'aliment
donné » valent 0, explicitement ; « Comme hier (N sacs) » d'un toucher ; « — » refusé à l'envoi ; un jour non
saisi n'est jamais compté zéro (régularité, mortalité et IC « incomplets »)."""
import re
from datetime import timedelta

from app import db, indicateurs
from app.models.bande import SaisieJour, SaisieAliment
from app.services import bandes as regles
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def test_les_cases_demarrent_a_tiret(client, monde):
    bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert re.search(r'name="morts" value="" placeholder="—"', page)
    assert re.search(r'name="sacs" value="" placeholder="—"', page)
    assert '✓ Aucun mort' in page and "Pas d'aliment donné" in page
    assert 'data-vide="morts"' in page and 'data-vide="aliment"' in page
    # Le contrôle se fait aussi sur le téléphone, avant l'envoi (même sans réseau)
    js = client.get('/static/js/compteurs.js').get_data(as_text=True)
    assert "window.addEventListener('submit'" in js and 'stopImmediatePropagation' in js
    assert "Touchez « Aucun mort »" in js


def test_tiret_refuse_a_l_envoi(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '', 'sacs': '0'}, follow_redirects=True)
    assert "Touchez « Aucun mort » s&#39;il n&#39;y a pas eu de mort." in page.get_data(as_text=True)
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0', 'sacs': ''}, follow_redirects=True)
    assert "Pas d&#39;aliment donné" in page.get_data(as_text=True)
    assert SaisieJour.query.count() == 0
    # Sans réseau aussi : refusé, jamais enregistré comme 0
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '', 'sacs': '0'})
    assert rep['etat'] == 'refuse' and SaisieJour.query.count() == 0


def test_aucun_mort_et_pas_d_aliment_valent_zero(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0', 'sacs': '0'})
    s = SaisieJour.query.one()
    assert s.morts == 0 and s.sacs == 0


def test_comme_hier_un_toucher_valeur_explicite_et_2_clics(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    hier = SaisieJour(bande=b, date=AUJ - timedelta(days=1), morts=1)
    hier.aliments.append(SaisieAliment(produit=monde['aliment'], sacs=3, kg=75))
    db.session.add(hier)
    db.session.commit()
    connecter(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert 'href="/saisie-du-jour"' in accueil                     # clic 1 : la tuile
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    bouton = re.search(r'<button type="button" class="case-rapide" data-mettre="([^"]+)" data-aliment="(\d+)">'
                       r'Comme hier \(3 sacs\)</button>', page)
    assert bouton and bouton.group(1) == '3' and bouton.group(2) == str(monde['aliment'].id)
    # Jamais pré-rempli : la case reste à « — » tant qu'on n'a pas touché
    assert re.search(r'name="sacs" value="" placeholder="—"', page)
    # Un toucher (dans l'écran, ne compte pas) puis Envoyer (clic 2) : 3 sacs
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0', 'sacs': bouton.group(1),
                                                  'aliment_choisi': bouton.group(2)})
    s = SaisieJour.query.filter_by(date=AUJ).one()
    assert s.sacs == 3 and s.aliments[0].produit_id == monde['aliment'].id
    # Pas d'aliment la veille (bande du jour) : pas de bouton « Comme hier »
    assert b.aliment_veille(AUJ - timedelta(days=2)) is None


def test_jour_non_saisi_jamais_compte_zero_ic_incomplet(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=5))
    for d in (4, 3, 1):                                           # 2 jours oubliés (J-5 et J-2)
        db.session.add(SaisieJour(bande=b, date=AUJ - timedelta(days=d), morts=2))
    db.session.commit()
    v = indicateurs.calculer(b)
    assert v['jours_saisis'] == 3 and v['jours_non_saisis'] == 2 and v['incomplet']
    assert v['morts_cumules'] == 6                                 # les jours manquants ne sont pas des zéros…
    assert v['regularite'] < 100                                    # … ils sont « non saisis »
    connecter(client, 'agent1')
    fiche = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert 'incomplet : 2 jours non saisis' in fiche
    from tests.conftest import creer_utilisateur
    from app.models import Profil
    creer_utilisateur('dge1', Profil.DGE, [])
    db.session.commit()
    client.post('/auth/deconnexion')
    connecter(client, 'dge1')
    tableau = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert 'Jours non saisis' in tableau and 'jamais comptés comme 0' in tableau
    # Bilan figé : « incomplet » gardé ; le rapport PDF le dit aussi
    regles.cloturer(b, monde['el'], 'essai')
    db.session.commit()
    assert b.bilan['incomplet'] and b.bilan['jours_non_saisis'] >= 2
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert 'incomplet' in client.get(f'/bandes/{b.numero}/bilan').get_data(as_text=True)


def test_saisie_complete_pas_incomplet(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    for d in (2, 1):
        db.session.add(SaisieJour(bande=b, date=AUJ - timedelta(days=d), morts=0))
    db.session.commit()
    assert not indicateurs.calculer(b)['incomplet']
