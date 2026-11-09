"""Lot 3 — bandes d'élevage."""
from datetime import date, timedelta

import pytest

from app import db, indicateurs
from app.models import (Produit, Profil, JournalAudit, UtilisateurFerme, Operateur, Parametre, Livraison)
from app.models.bande import Bande, SaisieJour, Pesee, Sortie, StatutBande
from app.models.base import maintenant
from app.models.intrant import StatutLivraison as S
from app.services import intrants, bandes as regles
from tests.conftest import creer_utilisateur, connecter, creer_ferme, province

AUJ = date.today()


@pytest.fixture
def monde(app):
    p = {'poussins': Produit(nom='Poussins chair', type='Poussins', unite='têtes'),
         'aliment': Produit(nom='Aliment démarrage', type='Aliment', unite='sacs', poids_sac_kg=25),
         'croissance': Produit(nom='Aliment croissance', type='Aliment', unite='sacs', poids_sac_kg=50)}
    db.session.add_all(p.values())
    agent = creer_utilisateur('agent1', Profil.AGENT, ['EST'])
    agent.prenom = 'Paul'
    autre = creer_utilisateur('agent2', Profil.AGENT, ['EST'])
    f = creer_ferme('Ferme Un', 'EST', 'Ntoum', agent=agent)
    f2 = creer_ferme('Ferme Deux', 'EST', 'Owendo', agent=autre)
    for cap in (1500, 800):
        regles.intrants  # noqa
        from app.services.fermes import ajouter_batiment
        ajouter_batiment(f, cap)
    from app.services.fermes import ajouter_batiment
    ajouter_batiment(f2, 500)
    el = creer_utilisateur('eleveur1', Profil.ELEVEUR)
    el.fermes = [UtilisateurFerme(ferme=f)]
    db.session.add(Operateur(numero='OPE-0001', nom='Abattoir de Ntoum', type='Abattoir', province=province('EST')))
    db.session.add(Operateur(numero='OPE-0002', nom='Super U', type='Distributeur', province=province('EST')))
    db.session.commit()
    return {'f': f, 'f2': f2, 'agent': agent, 'el': el, **p}


def recevoir(ferme, lignes, jour=None):
    liv = intrants.nouvelle_livraison(ferme, jour or AUJ - timedelta(days=1), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': p, 'quantite_livree': q, 'subventionne': False,
                                     'part_subventionnee': None, 'valeur_unitaire': None} for p, q, _ in lignes])
    db.session.flush()
    for l, (_, q, morts) in zip(sorted(liv.lignes, key=lambda x: x.id), lignes):
        l.quantite_recue = q
        l.morts_arrivee = morts if l.produit.type == 'Poussins' else None
    liv.statut = S.RECUE
    db.session.commit()
    return liv


def bande_ouverte(m, effectif=None, jour=None, bat=0):
    jour = jour or AUJ
    morts = 3 if effectif is None else 0
    liv = recevoir(m['f'], [(m['poussins'], max(1000, effectif or 0), morts), (m['aliment'], 40, 0)], jour=jour)
    ligne = next(l for l in liv.lignes if l.produit.type == 'Poussins')
    b = regles.ouvrir(m['f'], m['f'].batiments[bat], ligne, effectif or 997, jour, None, m['el'])
    db.session.commit()
    return b


# ── Ouverture ───────────────────────────────────────────────────────────

def test_ouverture_par_l_eleveur_depuis_les_poussins(client, monde):
    liv = recevoir(monde['f'], [(monde['poussins'], 1000, 3), (monde['aliment'], 40, 0)])
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'Nouveaux poussins' in page and '997' in page and 'Commencer une bande' in page
    page = client.get(f'/bandes/ouvrir?ferme={monde["f"].numero}').get_data(as_text=True)
    assert '997' in page and '1 000 reçus − 3 morts' in page and 'Dans quel bâtiment' in page
    ligne = next(l for l in liv.lignes if l.produit.type == 'Poussins')
    client.post('/bandes/ouvrir', data={'ferme': monde['f'].numero, 'ligne': ligne.id,
                                        'batiment': monde['f'].batiments[0].id, 'effectif': '997'})
    b = Bande.query.one()
    assert b.numero == 'EST-001-B1-01' and b.effectif_initial == 997 and b.poids_initial_g == 40
    assert b.date_fin_prevue == AUJ + timedelta(days=45)
    stock = {s['produit'].nom: s['stock'] for s in intrants.stock_ferme(monde['f'])}
    assert stock['Poussins chair'] == 0   # quittent l'attente de bande
    page = client.get('/').get_data(as_text=True)
    assert 'Nouveaux poussins' not in page and 'Jour 0' in page and '997' in page


def test_repartition_sur_deux_batiments_et_une_bande_par_batiment(monde):
    liv = recevoir(monde['f'], [(monde['poussins'], 2000, 0)])
    ligne = liv.lignes[0]
    b1 = regles.ouvrir(monde['f'], monde['f'].batiments[0], ligne, 1200, AUJ, 42, monde['el'])
    with pytest.raises(regles.RegleBande, match='déjà une bande'):
        regles.ouvrir(monde['f'], monde['f'].batiments[0], ligne, 100, AUJ, None, monde['el'])
    with pytest.raises(regles.RegleBande, match='entre 1 et 800'):
        regles.ouvrir(monde['f'], monde['f'].batiments[1], ligne, 900, AUJ, None, monde['el'])
    b2 = regles.ouvrir(monde['f'], monde['f'].batiments[1], ligne, 800, AUJ, None, monde['el'])
    db.session.commit()
    assert (b1.numero, b2.numero) == ('EST-001-B1-01', 'EST-001-B2-01')
    assert regles.poussins_en_attente(monde['f']) == []
    assert regles.depasse_capacite(b2) is False and b1.poids_initial_g == 42


def test_numero_jamais_reutilise(monde):
    b = bande_ouverte(monde)
    regles.cloturer(b, monde['agent'], 'essai')
    db.session.commit()
    liv = recevoir(monde['f'], [(monde['poussins'], 500, 0)])
    b2 = regles.ouvrir(monde['f'], monde['f'].batiments[0], liv.lignes[0], 500, AUJ, None, monde['el'])
    assert b2.numero == 'EST-001-B1-02'


def test_rattrapage_par_l_agent(client, monde):
    connecter(client, 'agent1')
    client.post('/bandes/rattrapage', data={'ferme': monde['f'].numero, 'batiment': monde['f'].batiments[0].id,
                                            'date': (AUJ - timedelta(days=20)).isoformat(),
                                            'effectif': '1600', 'morts': '30'})
    b = Bande.query.one()
    assert b.rattrapage and b.morts_avant_suivi == 30
    v = indicateurs.calculer(b)
    assert v['age'] == 20 and v['effectif_present'] == 1570 and v['partiels']
    page = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert 'indicateurs partiels' in page and '1 600 poussins mis en place pour 1 500 places' in page
    # Pas de feu orange « pas de saisie hier » le jour de l'ouverture du rattrapage
    assert indicateurs.feu(b)[0] == 'vert'
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    assert client.get(f'/bandes/rattrapage?ferme={monde["f"].numero}').status_code == 403


# ── Saisie du jour ──────────────────────────────────────────────────────

def test_trois_jours_de_saisie_et_stock_d_aliment(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    connecter(client, 'eleveur1')
    for i, (morts, sacs) in enumerate([(4, 2), (3, 2), (2, 3)]):
        jour = AUJ - timedelta(days=2 - i)
        client.post(f'/bandes/{b.numero}/saisie', data={'jour': jour.isoformat(), 'morts': morts, 'sacs': sacs,
                                                        'aliment_choisi': monde['aliment'].id})
    db.session.refresh(b)
    assert [s.morts for s in b.saisies] == [4, 3, 2]
    v = indicateurs.calculer(b)
    assert v['effectif_present'] == 988 and v['aliment_kg'] == 175 and v['sacs'] == 7
    stock = {s['produit'].nom: s for s in intrants.stock_ferme(monde['f'])}
    assert stock['Aliment démarrage']['stock'] == 33 and stock['Aliment démarrage']['kg'] == 825
    assert v['regularite'] == 100


def test_seconde_saisie_du_jour_s_ajoute_apres_confirmation(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    data = {'morts': 3, 'sacs': 1, 'aliment_choisi': monde['aliment'].id}
    client.post(f'/bandes/{b.numero}/saisie', data=data)
    page = client.post(f'/bandes/{b.numero}/saisie', data={**data, 'morts': 2}).get_data(as_text=True)
    assert 'Vous avez déjà envoyé' in page and 'Oui, ajouter' in page
    assert SaisieJour.query.one().morts == 3
    client.post(f'/bandes/{b.numero}/saisie', data={**data, 'morts': 2, 'ajouter': '1'})
    s = SaisieJour.query.one()
    assert s.morts == 5 and s.sacs == 2


def test_controles_de_saisie(client, monde):
    b = bande_ouverte(monde, effectif=10)
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/saisie', data={'morts': 11}, follow_redirects=True)
    assert 'entre 0 et 10' in r.get_data(as_text=True) and SaisieJour.query.count() == 0
    r = client.post(f'/bandes/{b.numero}/saisie', data={'morts': 0, 'sacs': 50, 'aliment_choisi': monde['aliment'].id},
                    follow_redirects=True)
    page = r.get_data(as_text=True)
    assert 'Stock insuffisant' in page and SaisieJour.query.one().sacs == 50   # non bloquant


def test_jour_passe_limite_pour_l_eleveur(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/saisie', data={'jour': (AUJ - timedelta(days=5)).isoformat(), 'morts': 1},
                    follow_redirects=True)
    assert 'trop ancien' in r.get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/saisie', data={'jour': (AUJ - timedelta(days=3)).isoformat(), 'morts': 1})
    assert SaisieJour.query.count() == 1
    assert 'Jour oublié' in client.get(f'/bandes/{b.numero}/oublie').get_data(as_text=True)
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    client.post(f'/bandes/{b.numero}/saisie', data={'jour': (AUJ - timedelta(days=8)).isoformat(), 'morts': 1})
    assert SaisieJour.query.count() == 2


def test_saisie_de_l_agent_pour_l_eleveur(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    page = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert "Saisir pour l'éleveur" in page
    assert 'Envoyer' in client.get(f'/bandes/{b.numero}/saisir').get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': 2})
    s = SaisieJour.query.one()
    assert s.saisi_par_agent and s.cree_par == monde['agent'].id
    j = JournalAudit.query.filter_by(action='POUR_ELEVEUR').order_by(JournalAudit.id.desc()).first()
    assert "agent Paul Agent1 pour l'éleveur" in j.detail
    assert 'Agent pour l&#39;éleveur' in client.get(f'/bandes/{b.numero}').get_data(as_text=True)


# ── Pesée, sortie ───────────────────────────────────────────────────────

def test_pesee_et_courbe(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=21))
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '9,8'}, follow_redirects=True)
    assert 'poids moyen 980 g' in r.get_data(as_text=True) and 'dans la courbe' in r.get_data(as_text=True)
    p = Pesee.query.one()
    assert p.poids_moyen_g == 980 and p.poids_attendu_g == 900
    v = indicateurs.calculer(b)
    assert round(v['gmq'], 1) == round((980 - 40) / 21, 1)
    r = client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '7'}, follow_redirects=True)
    assert 'en dessous de la courbe' in r.get_data(as_text=True)


def test_sorties(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.get(f'/bandes/{b.numero}/sortie').get_data(as_text=True)
    assert 'Pour qui ?' in page and 'Il restera 997 poulets' in page
    r = client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'nombre': '500', 'poids_total': '1000'},
                    follow_redirects=True)
    assert 'Choisissez l&#39;abattoir' in r.get_data(as_text=True)
    op2 = Operateur.query.filter_by(type='Distributeur').one()
    r = client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'operateur': op2.id,
                                                        'nombre': '500', 'poids_total': '1000'}, follow_redirects=True)
    assert 'Choisissez l&#39;abattoir' in r.get_data(as_text=True)
    op = Operateur.query.filter_by(type='Abattoir').one()
    r = client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'operateur': op.id,
                                                        'nombre': '515', 'poids_total': '1030'}, follow_redirects=True)
    assert 'Il reste 482 poulets' in r.get_data(as_text=True)
    r = client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Vente', 'nombre': '483', 'poids_total': '900',
                                                        'destinataire_libre': 'Marché'}, follow_redirects=True)
    assert 'entre 1 et 482' in r.get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Vente', 'nombre': '482', 'poids_total': '960',
                                                    'destinataire_libre': 'Marché de Ntoum'})
    page = client.get('/').get_data(as_text=True)
    assert 'Tous les poulets sont sortis' in page   # clôture proposée
    assert Sortie.query.count() == 2


# ── Indicateurs ─────────────────────────────────────────────────────────

def test_indicateurs_et_bilan(monde):
    b = bande_ouverte(monde, effectif=1000, jour=AUJ - timedelta(days=42))
    b.poids_initial_g = 40
    for i in range(1, 43):
        db.session.add(SaisieJour(bande=b, date=b.date_mise_en_place + timedelta(days=i), morts=1 if i <= 30 else 0))
    db.session.add(Pesee(bande=b, date=AUJ, nombre_pesees=10, poids_total_kg=25, poids_moyen_g=2500))
    db.session.add(Sortie(bande=b, date=AUJ, motif='Abattoir', operateur=Operateur.query.first(), nombre=500,
                          poids_total_kg=1250))
    db.session.flush()
    from app.models.bande import SaisieAliment
    db.session.add(SaisieAliment(saisie=b.saisies[0], produit=monde['aliment'], sacs=168, kg=4200))
    db.session.commit()
    v = indicateurs.calculer(b)
    assert v['morts_cumules'] == 30 and v['effectif_present'] == 470 and v['mortalite'] == 3.0
    assert v['viabilite'] == 97.0
    # Poids vif produit = 1250 + 470 × 2,5 − 1000 × 0,04 = 2385 kg ; IC = 4200 / 2385
    assert round(v['poids_vif_produit'], 1) == 2385.0 and round(v['indice_consommation'], 3) == round(4200 / 2385, 3)
    assert round(v['gmq'], 2) == round((2500 - 40) / 42, 2)
    regles.cloturer(b, monde['agent'], 'fin anticipée')
    db.session.commit()
    assert b.bilan['mortalite'] == 3.0 and b.bilan['duree_jours'] == 42 and b.bilan['poids_moyen_sortie_kg'] == 2.5
    assert b.bilan['sorties_par_destinataire'][0]['destinataire'] == 'Abattoir de Ntoum'
    # Le bilan est figé : changer un seuil ou une formule ne le modifie pas
    Parametre.query.filter_by(cle='bandes.seuil_rouge_pct').one().valeur = '9'
    db.session.commit()
    assert db.session.get(Bande, b.id).bilan['mortalite'] == 3.0


def test_moteur_de_formules_sur():
    assert indicateurs.evaluer('(a + b) * 2 / c', {'a': 1, 'b': 2, 'c': 3}) == 2.0
    assert indicateurs.evaluer('a / b', {'a': 1, 'b': 0}) is None
    for mauvaise in ('__import__("os")', 'a.b', 'a ** 2', 'open', '[a]', 'a if b else c', 'lambda: 1'):
        with pytest.raises(indicateurs.FormuleInvalide):
            indicateurs.analyser(mauvaise, {'a', 'b', 'c'})


def test_courbe_parametrable(client_admin):
    p = Parametre.query.filter_by(cle='bandes.courbe_poids').one()
    r = client_admin.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': 'n importe quoi'},
                          follow_redirects=True)
    assert 'âge:poids' in r.get_data(as_text=True)
    assert 'à valider par les vétérinaires' in client_admin.get('/administration/parametres/').get_data(as_text=True)
    assert indicateurs.poids_attendu(21) == 900 and indicateurs.poids_attendu(24) == 900 + (1450 - 900) * 3 / 7


# ── Feu tricolore et alertes ────────────────────────────────────────────

def test_feu_orange_puis_rouge_et_alertes(client, monde):
    b = bande_ouverte(monde, effectif=1000, jour=AUJ - timedelta(days=5))
    for i in range(1, 5):
        db.session.add(SaisieJour(bande=b, date=b.date_mise_en_place + timedelta(days=i), morts=1))
    db.session.commit()
    assert indicateurs.feu(b)[0] == 'vert'
    db.session.add(SaisieJour(bande=b, date=AUJ, morts=6))   # 0,6 % > 0,5 %
    db.session.commit()
    assert indicateurs.feu(b) == ('orange', 'mortalite')
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'Plus de morts que d&#39;habitude' in page and '6 morts' in page and 'Votre agent Paul a été prévenu' in page
    assert 'Signaler un poulet malade' in page
    SaisieJour.query.filter_by(date=AUJ).one().morts = 15                       # 1,5 % > 1 %
    db.session.commit()
    assert indicateurs.feu(b)[0] == 'rouge'
    client.post('/auth/deconnexion')
    for ident, profil, provinces in (('agent1', None, None), ('dge', Profil.DGE, []), ('veto', Profil.VETO, ['EST'])):
        if profil:
            creer_utilisateur(ident, profil, provinces)
        connecter(client, ident)
        assert f'{b.numero} · Plus de morts que d&#39;habitude' in client.get('/').get_data(as_text=True), ident
        client.post('/auth/deconnexion')
    for ident, profil, provinces in (('admin', Profil.ADMIN, []), ('agent2', None, None), ('veto2', Profil.VETO, ['HOG'])):
        if profil:
            creer_utilisateur(ident, profil, provinces)
        connecter(client, ident)
        assert b.numero not in client.get('/').get_data(as_text=True), ident
        client.post('/auth/deconnexion')


def test_pas_de_saisie_hier(monde):
    b = bande_ouverte(monde, jour=AUJ)
    assert indicateurs.feu(b)[0] == 'vert'                                   # jour de la mise en place
    assert indicateurs.feu(b, AUJ + timedelta(days=1))[0] == 'vert'          # le lendemain
    assert indicateurs.feu(b, AUJ + timedelta(days=2)) == ('orange', 'saisie')
    assert "Vous n'avez pas envoyé hier" == indicateurs.phrase(b, 'orange', 'saisie', indicateurs.calculer(b))


def test_a_faire_aujourd_hui(monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=7))
    taches = indicateurs.a_faire(b)
    assert 'Peser 10 poulets' in taches and any('aujourd' in t for t in taches)
    b.date_fin_prevue = AUJ + timedelta(days=2)
    assert any('Fin de bande prévue' in t for t in indicateurs.a_faire(b))


# ── Clôture, correction ─────────────────────────────────────────────────

def test_cloture_par_l_eleveur_a_zero_et_lecture_seule(client, monde):
    b = bande_ouverte(monde, effectif=10)
    op = Operateur.query.filter_by(type='Abattoir').one()
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/cloturer')
    assert r.status_code == 403                                    # il reste des poulets
    client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'operateur': op.id, 'nombre': '10',
                                                    'poids_total': '22'})
    client.post(f'/bandes/{b.numero}/cloturer')
    db.session.refresh(b)
    assert b.statut == StatutBande.CLOTUREE and b.bilan['sortis'] == 10
    page = client.get('/').get_data(as_text=True)
    assert 'vide depuis 0 jour' in page and 'Dernière bande' in page and 'poulet-dort' in page
    assert client.post(f'/bandes/{b.numero}/saisie', data={'morts': 1}).status_code == 403
    assert client.get(f'/bandes/{b.numero}/bilan').status_code == 200


def test_cloture_par_l_agent_avec_motif_et_correction(client, monde):
    b = bande_ouverte(monde)
    db.session.add(SaisieJour(bande=b, date=AUJ, morts=50))
    db.session.commit()
    connecter(client, 'agent1')
    r = client.post(f'/bandes/{b.numero}/corriger/saisie/{AUJ.isoformat()}', data={'morts': '5'})
    assert 'motif' in r.get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/corriger/saisie/{AUJ.isoformat()}', data={'morts': '5', 'motif': 'faute de frappe'})
    assert SaisieJour.query.one().morts == 5
    assert JournalAudit.query.filter_by(action='CORRECTION').count() == 1
    r = client.post(f'/bandes/{b.numero}/cloturer', follow_redirects=True)
    assert 'indiquez le motif' in r.get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/cloturer', data={'motif': 'Poulets vendus hors application'})
    db.session.refresh(b)
    assert not b.en_cours
    assert client.get(f'/bandes/{b.numero}/corriger/saisie/{AUJ.isoformat()}').status_code == 403   # agent : non
    client.post('/auth/deconnexion')
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    client.post(f'/bandes/{b.numero}/corriger/saisie/{AUJ.isoformat()}', data={'morts': '7', 'motif': 'recompté'})
    db.session.refresh(b)
    assert b.bilan['morts'] == 7   # bilan recalculé après la correction de l'ADMIN


# ── Cloisonnement ───────────────────────────────────────────────────────

def test_cloisonnement(client, monde):
    b = bande_ouverte(monde)
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    connecter(client, 'veto')
    assert b.numero in client.get('/bandes/').get_data(as_text=True)
    fiche = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert 'Clôturer' not in fiche and 'Saisir pour' not in fiche
    assert client.post(f'/bandes/{b.numero}/saisie', data={'morts': 1}).status_code == 403
    client.post('/auth/deconnexion')
    connecter(client, 'agent2')
    assert client.get(f'/bandes/{b.numero}').status_code == 403
    assert b.numero not in client.get('/bandes/').get_data(as_text=True)
    client.post('/auth/deconnexion')
    for profil in (Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR, Profil.AUDITEUR):
        ident = profil.value.lower()
        creer_utilisateur(ident, profil, ['EST'])
        connecter(client, ident)
        assert client.get('/bandes/').status_code == 403
        assert client.get(f'/bandes/{b.numero}').status_code == 403
        client.post('/auth/deconnexion')
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    fiche = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert 'Clôturer' not in fiche and client.post(f'/bandes/{b.numero}/saisie', data={'morts': 1}).status_code == 403
