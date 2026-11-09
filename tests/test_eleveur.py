"""Lot 8 — espace éleveur « illustré doux » : étoiles, série, poulet, « Bien reçu ! »,
plusieurs bandes à la fois, vaccin du jour, conseil, feuille de style réservée."""
from datetime import timedelta

from app import db, indicateurs
from app.models import Parametre, Profil, Produit, UtilisateurFerme
from app.models.bande import SaisieJour, Pesee
from app.models.sante import CalendrierVaccinal, Vaccination
from app.services import ludique, bandes as regles, sante
from app.services.fermes import ajouter_batiment
from app.utils.logo import poulet
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def jours(bande, *decalages, morts=0):
    for d in decalages:
        db.session.add(SaisieJour(bande=bande, date=AUJ - timedelta(days=d), morts=morts))
    db.session.commit()


# ── Étoiles ─────────────────────────────────────────────────────────────

def test_etoiles_regle_de_depart_et_seuils_reglables(app):
    assert ludique.etoiles(2.5, 1.6) == 3
    assert ludique.etoiles(2.5, 1.8) == 2          # indice trop élevé
    assert ludique.etoiles(2.5, None) == 2         # indice inconnu : 2 au plus
    assert ludique.etoiles(4.9, 1.5) == 2
    assert ludique.etoiles(6, 1.5) == 1 and ludique.etoiles(40, 3) == 1   # jamais 0
    assert ludique.etoiles(None, None) == 1
    Parametre.query.filter_by(cle='bandes.etoiles_mortalite_2_pct').one().valeur = '10'
    db.session.commit()
    assert ludique.etoiles(6, 1.5) == 2
    assert [ludique.PHRASES_ETOILES[n] for n in (3, 2, 1)] == [
        'Votre meilleure bande !', 'Bonne bande !', 'La prochaine sera meilleure']


def test_etoiles_gardees_au_bilan_et_dans_mes_bandes(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    jours(b, 2, 1, 0)
    regles.sortir(b, AUJ, 'Vente', None, 'Marché', 997, 2000, monde['el'])
    regles.cloturer(b, monde['el'])
    db.session.commit()
    assert b.bilan['etoiles'] in (1, 2, 3) and b.bilan['serie_record'] == 3 and b.bilan['vendus'] == 997
    connecter(client, 'eleveur1')
    page = client.get(f'/bandes/{b.numero}/bilan').get_data(as_text=True)
    assert 'Bande terminée' in page and 'class="etoiles etoiles-grandes"' in page and 'Voir mes bandes passées' in page
    assert ludique.PHRASES_ETOILES[b.bilan['etoiles']].replace("'", '&#39;') in page and 'série record' in page
    page = client.get('/bandes/mes-bandes').get_data(as_text=True)
    assert b.numero in page and 'class="etoiles"' in page
    changer(client, 'agent1')   # l'agent garde son bilan habituel
    assert 'Sorties par destinataire' in client.get(f'/bandes/{b.numero}/bilan').get_data(as_text=True)
    assert client.get('/bandes/mes-bandes').status_code == 403


# ── Série et record ─────────────────────────────────────────────────────

def test_serie_jours_consecutifs_et_jour_manque(monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=12))
    jours(b, 10, 9, 8, 7, 6, 4, 3, 2, 1)       # un trou à J-5
    assert ludique.serie(b) == 4                # pas encore de saisie aujourd'hui : on compte jusqu'à hier
    jours(b, 0)
    assert ludique.serie(b) == 5 and ludique.plus_longue_serie(b) == 5
    s = ludique.etat_serie(b, [b])
    assert s['n'] == 5 and not s['nouveau_record'] and s['record'] == 5   # égale l'ancienne série de 5
    b2 = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=5), bat=1)
    jours(b2, 4, 3)                              # puis hier et aujourd'hui manqués
    s = ludique.etat_serie(b2, [b, b2])
    assert s['n'] == 0 and s['repart']
    jours(b2, 0)
    s = ludique.etat_serie(b2, [b, b2])
    assert s['n'] == 1 and s['repart']          # « On repart : 1 jour ! »


def test_record_personnel_toutes_bandes_confondues(monde):
    ancienne = bande_ouverte(monde, jour=AUJ - timedelta(days=30))
    jours(ancienne, 29, 28, 27)                  # record de 3 jours
    regles.cloturer(ancienne, monde['el'], 'essai')
    db.session.commit()
    b = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=5), bat=1)
    jours(b, 3, 2, 1)
    assert not ludique.etat_serie(b, [ancienne, b])['nouveau_record']    # 3 = 3 : pas battu
    jours(b, 0)
    s = ludique.etat_serie(b, [ancienne, b])
    assert s['n'] == 4 and s['nouveau_record'] and s['record'] == 4


def test_saisie_hors_ligne_compte_a_sa_date(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=6))
    jours(b, 5, 4, 2, 1)                         # trou à J-3
    assert ludique.serie(b) == 2
    connecter(client, 'eleveur1')
    jour = (AUJ - timedelta(days=3)).isoformat()
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '0', 'jour': jour}, il_y_a=timedelta(days=3))
    assert rep['etat'] == 'ok'
    db.session.expire_all()
    assert ludique.serie(b) == 5


# ── Le poulet selon le feu ──────────────────────────────────────────────

def test_expression_du_poulet_selon_le_feu(client, monde):
    for feu, visage in (('vert', 'content'), ('orange', 'inquiet'), ('rouge', 'malade'), ('gris', 'dort')):
        assert f'poulet-{visage}' in poulet(feu)
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert indicateurs.feu(b)[0] == 'orange' and 'poulet-inquiet' in page        # rien envoyé hier
    assert 'poulet-dort' in page                                                   # bâtiment vide
    jours(b, 2, 1)
    assert 'poulet-content' in client.get('/saisie-du-jour').get_data(as_text=True)
    jours(b, 0, morts=20)                                                          # 2 % > 1 %
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'poulet-malade' in page and "Beaucoup de morts aujourd'hui" in page
    assert 'Votre agent et le vétérinaire sont prévenus' in page and 'Signaler un poulet malade' in page
    assert 'Isolez les poulets malades' in page                                   # conseil


def test_conseil_du_feu_rouge_parametrable(client, monde):
    b = bande_ouverte(monde)
    jours(b, 0, morts=30)
    creer_utilisateur('veto1', Profil.VETO, ['EST'])
    db.session.commit()
    connecter(client, 'veto1')
    assert "Conseil affiché à l'éleveur" in client.get('/sante/vaccins').get_data(as_text=True)
    client.post('/sante/conseil', data={'conseil': 'Appelez le vétérinaire avant toute vente.'})
    assert Parametre.query.filter_by(cle='sante.conseil_feu_rouge').one().valeur == 'Appelez le vétérinaire avant toute vente.'
    changer(client, 'eleveur1')
    assert 'Appelez le vétérinaire avant toute vente.' in client.get('/saisie-du-jour').get_data(as_text=True)
    assert client.post('/sante/conseil', data={'conseil': 'x'}).status_code == 403
    changer(client, 'agent1')
    assert client.post('/sante/conseil', data={'conseil': 'x'}).status_code == 403


# ── « Bien reçu ! » ─────────────────────────────────────────────────────

def test_bien_recu_avec_etincelles_seulement_en_vert(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    jours(b, 2, 1)
    connecter(client, 'eleveur1')
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '1'}, follow_redirects=True).get_data(as_text=True)
    assert 'class="bien-recu joie"' in page and 'class="etincelles"' in page and 'Bien reçu !' in page
    assert "3 jours d'affilée" in page and 'Envoyé ✓' not in page
    # Feu rouge : ni saut ni étincelles, seulement « Envoyé ✓ — Votre agent est prévenu »
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '30'}, follow_redirects=True).get_data(as_text=True)
    if 'Ajouter à la saisie' in page or 'déjà' in page.lower():
        page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '30', 'ajouter': '1'},
                           follow_redirects=True).get_data(as_text=True)
    assert indicateurs.feu(b)[0] == 'rouge'
    assert 'class="bien-recu sobre"' in page and 'etincelles' not in page and 'Bien reçu !' not in page
    assert 'Envoyé ✓' in page and 'Votre agent est prévenu' in page


def test_bien_recu_en_orange_sans_etincelles(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=3))   # rien envoyé hier : orange
    connecter(client, 'eleveur1')
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '0'}, follow_redirects=True).get_data(as_text=True)
    assert 'class="bien-recu sobre"' in page and 'etincelles' not in page and 'Votre agent est prévenu' in page


def test_l_agent_ne_voit_pas_bien_recu(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    page = client.post(f'/bandes/{b.numero}/saisie', data={'morts': '1'}, follow_redirects=True).get_data(as_text=True)
    assert 'bien-recu' not in page


# ── Plusieurs bandes à la fois ──────────────────────────────────────────

def test_un_seul_batiment_sans_pastilles(client, monde):
    el2 = creer_utilisateur('eleveur2', Profil.ELEVEUR)
    el2.fermes = [UtilisateurFerme(ferme=monde['f2'])]
    db.session.commit()
    liv = recevoir(monde['f2'], [(monde['poussins'], 500, 0)])
    regles.ouvrir(monde['f2'], monde['f2'].batiments[0], liv.lignes[0], 500, AUJ, None, el2)
    db.session.commit()
    connecter(client, 'eleveur2')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'pastilles-bat' not in page and 'Envoyer ✓' in page and 'poulet-content' in page


def test_deux_batiments_point_orange_et_il_reste_b2(client, monde):
    b1 = bande_ouverte(monde)
    b2 = bande_ouverte(monde, effectif=800, bat=1)
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert page.count('class="pastille-bat') == 2 and page.count('class="point-a-saisir"') == 2
    assert 'B1 · J0' in page and 'B2 · J0' in page
    page = client.post(f'/bandes/{b1.numero}/saisie', data={'morts': '1'}, follow_redirects=True).get_data(as_text=True)
    assert 'Il reste B2 à saisir →' in page and 'data-cible="bat-EST-001-B2"' in page
    assert page.count('class="point-a-saisir"') == 1                 # le point de B1 a disparu
    assert '✓ Saisie du jour envoyée' in page and 'Ajouter à la saisie du jour' in page
    page = client.post(f'/bandes/{b2.numero}/saisie', data={'morts': '0'}, follow_redirects=True).get_data(as_text=True)
    assert 'Il reste' not in page and 'point-a-saisir' not in page
    assert SaisieJour.query.filter_by(bande_id=b1.id).one().morts == 1   # saisies séparées par bande
    assert SaisieJour.query.filter_by(bande_id=b2.id).one().morts == 0
    # Ajouter à une saisie déjà envoyée : la confirmation du lot 3
    page = client.post(f'/bandes/{b1.numero}/saisie', data={'morts': '2'}, follow_redirects=True).get_data(as_text=True)
    assert 'ajouter' in page.lower() and SaisieJour.query.filter_by(bande_id=b1.id).one().morts == 1


def test_quatre_batiments_ordre_et_a_faire_commun(client, monde):
    ajouter_batiment(monde['f'], 600)
    ajouter_batiment(monde['f'], 400)
    db.session.commit()
    b1 = bande_ouverte(monde)
    bande_ouverte(monde, effectif=800, bat=1)
    bande_ouverte(monde, effectif=600, bat=2)
    jours(b1, 0)                                   # B1 déjà saisie aujourd'hui
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    ordre = [page.index(f'{code} · ') for code in ('B2', 'B3', 'B1', 'B4')]
    assert ordre == sorted(ordre)                   # à saisir d'abord, puis saisie, puis vide
    assert 'B4 · vide' in page and page.count('class="point-a-saisir"') == 2
    assert '<strong>B2 :</strong>' in page and '<strong>B3 :</strong>' in page   # « À faire » commun préfixé
    assert 'data-cible="bat-EST-001-B3"' in page


def test_batiment_vide_etoiles_et_ouvrir_ici(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    jours(b, 1, 0)
    regles.cloturer(b, monde['el'], 'essai')
    db.session.commit()
    bande_ouverte(monde, effectif=800, bat=1)             # une bande en cours ailleurs (lot 11)
    recevoir(monde['f'], [(monde['poussins'], 500, 0)])   # poussins en attente
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Dernière bande · ' + b.numero in page and 'class="etoiles"' in page
    assert '🐣 Ouvrir une bande ici' in page and f'batiment={monde["f"].batiments[0].id}' in page
    page = client.get(f'/bandes/ouvrir?ferme={monde["f"].numero}&batiment={monde["f"].batiments[0].id}').get_data(as_text=True)
    assert f'value="{monde["f"].batiments[0].id}" data-numero="EST-001-B1"  checked' in page or \
        f'value="{monde["f"].batiments[0].id}" data-numero="EST-001-B1" ' in page


# ── Vaccin du jour ──────────────────────────────────────────────────────

def test_vaccin_pas_encore_fait_puis_en_retard(client, monde):
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=14, produit=vaccin, mode='Eau de boisson'))
    db.session.commit()
    recevoir(monde['f'], [(vaccin, 2000, 0)])
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=14))
    jours(b, *range(1, 14))
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Vaccin du jour' in page and '/sante/vacciner/' in page
    entree = CalendrierVaccinal.query.one()
    page = client.get(f'/sante/vacciner/{b.numero}?calendrier={entree.id}').get_data(as_text=True)
    assert 'Vaccin Gumboro' in page and "✓ C'est fait" in page and 'Pas encore fait' in page
    assert 'Stock à la ferme : 2 000 doses' in page
    assert Vaccination.query.count() == 0           # « Pas encore fait » : rien d'enregistré
    assert 'Vaccin du jour' in client.get('/saisie-du-jour').get_data(as_text=True)   # toujours à faire
    # Passé la date prévue + 2 jours : « en retard », l'agent est prévenu
    b.date_mise_en_place = AUJ - timedelta(days=17)
    db.session.commit()
    assert sante.vaccins_en_retard(type(b).query)
    changer(client, 'agent1')
    assert 'vaccin en retard' in client.get('/').get_data(as_text=True)


# ── Messages vivants ────────────────────────────────────────────────────

def test_pesee_plus_n_grammes_seulement_en_vert(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=9))
    jours(b, *range(1, 9))
    db.session.add(Pesee(bande=b, date=AUJ - timedelta(days=7), nombre_pesees=10, poids_total_kg=1.5,
                         poids_moyen_g=150, poids_attendu_g=150))
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '3,6'},
                       follow_redirects=True).get_data(as_text=True)
    assert '💪 +210 g en 7 jours !' in page
    jours(b, 0, morts=30)                           # feu rouge : pas de message joyeux
    page = client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '4'},
                       follow_redirects=True).get_data(as_text=True)
    assert '💪' not in page


# ── Feuille de style réservée ───────────────────────────────────────────

def test_feuille_eleveur_seulement_pour_l_eleveur_et_la_page_publique(client, monde):
    b = bande_ouverte(monde)
    css = 'css/eleveur.css'
    assert css in client.get('/auth/connexion').get_data(as_text=True)    # connexion : pour tous (écart 1)
    connecter(client, 'eleveur1')
    for url in ('/', f'/bandes/{b.numero}/pesee', f'/bandes/{b.numero}/sortie', '/bandes/mes-bandes'):
        page = client.get(url).get_data(as_text=True)
        assert css in page and 'theme-eleveur' in page and 'Bonjour' in page, url
    changer(client, 'agent1')
    for url in ('/', f'/bandes/{b.numero}/pesee', f'/bandes/{b}'.replace(str(b), b.numero)):
        page = client.get(url).get_data(as_text=True)
        assert css not in page and 'theme-eleveur' not in page, url
    lot = regles.sortir(b, AUJ, 'Vente', None, 'Marché', 10, 20, monde['el']).lot
    db.session.commit()
    client.post('/auth/deconnexion')
    page = client.get(f'/q/{lot.code}').get_data(as_text=True)
    assert css in page and 'poulet-content' in page and 'Élevé par' in page and lot.numero in page
    assert css in client.get('/q/inconnu-0000').get_data(as_text=True)
