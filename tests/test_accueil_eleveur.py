"""Lot 9 — accueil de l'éleveur en tuiles, « Saisie du jour », accès directs, « J'ai acheté »."""
import io
import re
from datetime import timedelta

from app import db
from app.models import Livraison, Profil, Produit, JournalAudit, Parametre
from app.models.bande import SaisieJour, Pesee
from app.models.intrant import StatutLivraison as S, OrigineLivraison
from app.models.sante import CalendrierVaccinal
from app.services import intrants, bandes as regles, pilotage
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer
from tests.test_sante import JPEG


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def tuiles(page):
    return re.findall(r'data-tuile="(\w+)"', page)


def jours(bande, *decalages, morts=0):
    for d in decalages:
        db.session.add(SaisieJour(bande=bande, date=AUJ - timedelta(days=d), morts=morts))
    db.session.commit()


def acheter(client, produit, quantite='10', **extra):
    data = {'produit': produit.id, 'quantite': quantite, **extra}
    return client.post('/j-ai-achete', data=data, content_type='multipart/form-data')


# ── Accueil : tuiles affichées ou cachées ───────────────────────────────

def test_accueil_sans_bande_ni_poussins(client, monde):
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'Aucune bande en cours' in page and 'poulet-dort' in page
    assert 'Saisie du jour' not in page
    assert tuiles(page) == ['livraisons', 'malade', 'achat', 'bandes', 'stock']
    assert 'tuiles impair' in page                       # la dernière tuile prend toute la largeur
    assert 'class="compteur"' not in page and 'bloc-bat' not in page   # plus de tableau de bord


def test_accueil_poussins_en_attente_et_livraisons_a_confirmer(client, monde):
    recevoir(monde['f'], [(monde['poussins'], 1000, 3)])
    liv = intrants.nouvelle_livraison(monde['f'], AUJ, None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'bande' in tuiles(page) and '>997<' in page.replace('\n', '')       # pastille poussins
    assert re.search(r'data-tuile="livraisons">\s*<span class="pastille ">1</span>', page)
    assert 'carte-livraison' not in page                 # plus de grandes cartes de livraison sur l'accueil


def test_accueil_avec_bandes_saisie_pastilles_et_ligne_d_etat(client, monde):
    b1 = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    jours(b1, 2, 1)
    b2 = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=2), bat=1)
    jours(b2, 1)
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert '2 bâtiments · tout va bien' in page and 'B1 jour 3 · B2 jour 2' in page and 'poulet-content' in page
    assert 'B1, B2 à faire · morts et aliment' in page and 'aria-label="2 bâtiment(s) à saisir"' in page
    assert tuiles(page) == ['livraisons', 'peser', 'sortie', 'vaccins', 'malade', 'achat', 'bandes', 'stock']
    assert 'tuiles impair' not in page
    jours(b1, 0)
    jours(b2, 0)
    page = client.get('/').get_data(as_text=True)
    assert "Tout est envoyé aujourd'hui" in page and 'tuile-calme' in page and 'href="/saisie-du-jour"' in page


def test_bandeau_rouge_et_attention(client, monde):
    bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    b2 = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=2), bat=1)
    jours(b2, 1)
    jours(b2, 0, morts=30)                                 # 3,75 % : rouge
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert "⚠️ B2 : beaucoup de morts aujourd'hui → Signaler" in page
    assert f'/sante/declarer?bande={b2.numero}' in page
    assert 'B1, B2 demandent votre attention' in page and 'poulet-malade' in page
    # « Poulet malade » ouvre directement la bande au feu rouge
    r = client.get('/aller/malade')
    assert r.status_code == 302 and f'bande={b2.numero}' in r.location


def test_tuiles_peser_vaccins_et_agent(client, monde):
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=8, produit=vaccin, mode='Eau de boisson'))
    db.session.commit()
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=7))
    jours(b, *range(1, 7))
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'B1 : pesée prévue aujourd&#39;hui' in page                       # 7 jours sans pesée
    assert '>demain</span>' in page                                     # vaccin à J8
    assert 'mon agent' not in page                                      # l'agent n'a pas de téléphone
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.add(Pesee(bande=b, date=AUJ, nombre_pesees=10, poids_total_kg=2, poids_moyen_g=200, poids_attendu_g=180))
    db.session.commit()
    page = client.get('/').get_data(as_text=True)
    assert 'prochaine : B1 le' in page and 'href="tel:+24177123456"' in page and 'Appeler Paul, mon agent' in page
    r = client.get('/aller/vaccins')
    assert r.status_code == 200 and 'Enregistrer un traitement' in r.get_data(as_text=True)
    b.date_mise_en_place = AUJ - timedelta(days=8)
    db.session.commit()
    assert 'aujourd&#39;hui</span>' in client.get('/').get_data(as_text=True)
    r = client.get('/aller/vaccins')
    assert r.status_code == 302 and f'/sante/vacciner/{b.numero}' in r.location


# ── Saisie du jour : ouverte sur le premier bâtiment à faire ────────────

def test_saisie_du_jour_s_ouvre_sur_le_premier_batiment_a_saisir(client, monde):
    b1 = bande_ouverte(monde)
    bande_ouverte(monde, effectif=800, bat=1)
    jours(b1, 0)                                               # B1 déjà saisie
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    blocs = re.findall(r'<section class="bloc-bat" id="([^"]+)"', page)
    assert blocs[0] == 'bat-EST-001-B2' and 'pastilles-bat' in page and '‹ Accueil' in page
    # Après l'envoi : retour sur la saisie du jour, « Il reste … » si besoin
    r = client.post(f'/bandes/{b1.numero}/saisie', data={'morts': '1', 'ajouter': '1'})
    assert r.location.endswith('/saisie-du-jour#bat-EST-001-B1')


def test_acces_directs_peser_et_sortie(client, monde):
    jeune = bande_ouverte(monde, jour=AUJ - timedelta(days=2))
    vieille = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=20), bat=1)
    db.session.add(Pesee(bande=vieille, date=AUJ, nombre_pesees=10, poids_total_kg=8, poids_moyen_g=800,
                         poids_attendu_g=800))
    db.session.commit()
    connecter(client, 'eleveur1')
    assert client.get('/aller/peser').location.endswith(f'/bandes/{jeune.numero}/pesee')   # pesée la plus proche
    assert client.get('/aller/sortie').location.endswith(f'/bandes/{vieille.numero}/sortie')  # la plus âgée
    page = client.get(f'/bandes/{jeune.numero}/pesee').get_data(as_text=True)
    assert f'/bandes/{vieille.numero}/pesee' in page and '‹ Accueil' in page          # changer de bâtiment
    assert 'class="btn-top"><i class="bi bi-house-door"></i> Accueil' not in page


# ── J'ai acheté ─────────────────────────────────────────────────────────

def test_achat_stock_source_et_hors_controle_de_l_etat(client, monde):
    recevoir(monde['f'], [(monde['croissance'], 30, 0)])          # livraison de l'État
    db.session.add_all([Produit(nom=f'Produit {i}', type='Autre', unite='unités') for i in range(6)])
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/j-ai-achete').get_data(as_text=True)
    assert 'Aliment croissance' in page and 'Autre produit' in page and 'data-hors-ligne="Achat' in page
    r = acheter(client, monde['croissance'], '10', prix='175 000', lieu='Marché de Ntoum',
                recu=(io.BytesIO(JPEG), 'recu.jpg'))
    assert r.status_code == 302 and r.location.endswith('/')
    a = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT).one()
    assert a.numero.startswith('ACH-') and a.statut == S.RECUE and a.prix_paye_fcfa == 175000 and a.photo_recu
    assert not a.lignes[0].subventionne and a.lignes[0].valeur_unitaire == 17500
    stock = {s['produit'].nom: s for s in intrants.stock_ferme(monde['f'])}['Aliment croissance']
    assert (stock['stock'], stock['etat'], stock['achat'], stock['kg']) == (40, 30, 10, 2000)
    page = client.get('/mon-stock').get_data(as_text=True)
    assert "reçu en tout : 30 de l'État · 10 achetés" in page
    assert 'Mes derniers achats' in page and '175 000 FCFA' in page
    # Hors des contrôles des intrants de l'État (et du futur recoupement)
    assert intrants.livraisons_de_l_etat(Livraison.query).filter_by(id=a.id).count() == 0
    assert a.numero not in client.get('/livraisons/mes-livraisons').get_data(as_text=True)
    changer(client, 'agent1')
    assert a.numero not in client.get('/livraisons/').get_data(as_text=True)
    assert a.numero not in client.get('/pilotage/exports/livraisons.csv').get_data(as_text=True)
    assert all(x['ligne'].livraison.origine == 'ETAT' for x in pilotage.mortalite_arrivee(monde['agent'], {})['lignes'])


def test_poussins_achetes_en_attente_de_bande(client, monde):
    connecter(client, 'eleveur1')
    acheter(client, monde['poussins'], '500', morts='4')
    a = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT).one()
    assert a.lignes[0].morts_arrivee == 4
    attente = regles.poussins_en_attente(monde['f'])
    assert [(l.livraison.numero, d) for l, d in attente] == [(a.numero, 496)]
    assert 'data-tuile="bande"' in client.get('/').get_data(as_text=True)
    client.post('/bandes/ouvrir', data={'ferme': monde['f'].numero, 'ligne': a.lignes[0].id,
                                        'batiment': monde['f'].batiments[0].id, 'effectif': '496'})
    assert regles.poussins_en_attente(monde['f']) == []
    # Poussins déjà mis en bande : l'achat ne s'annule plus
    assert not intrants.achat_annulable(a, monde['el'])


def test_achat_annuler_dans_les_10_secondes(client, monde):
    connecter(client, 'eleveur1')
    acheter(client, monde['aliment'], '5')
    a = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT).one()
    page = client.get('/').get_data(as_text=True)
    assert 'Enregistré ✓ — Aliment démarrage' in page and f'/achats/{a.numero}/annuler' in page
    client.post(f'/achats/{a.numero}/annuler')
    db.session.refresh(a)
    assert a.statut == S.ANNULEE
    assert 'Aliment démarrage' not in {s['produit'].nom for s in intrants.stock_ferme(monde['f'])}
    assert JournalAudit.query.filter_by(action='ANNULATION', table_nom='livraison').count() == 1
    # Passé le délai : seule l'agent peut corriger
    acheter(client, monde['aliment'], '5')
    b = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT, statut=S.RECUE).one()
    from app.models.base import maintenant
    b.confirmee_le = maintenant() - timedelta(minutes=2)
    db.session.commit()
    assert 'bandeau-annuler' not in client.get('/').get_data(as_text=True)
    r = client.post(f'/achats/{b.numero}/annuler', follow_redirects=True)
    assert 'délai pour annuler est passé' in r.get_data(as_text=True) and db.session.get(Livraison, b.id).statut == S.RECUE


def test_achat_correction_par_l_agent_et_lecture(client, monde):
    connecter(client, 'eleveur1')
    acheter(client, monde['poussins'], '200', morts='2', prix='100000')
    a = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT).one()
    assert client.get(f'/achats/{a.numero}/corriger').status_code == 403      # pas l'éleveur
    changer(client, 'agent1')
    page = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert "Achats de l'éleveur" in page and a.numero in page and 'Corriger' in page
    client.post(f'/achats/{a.numero}/corriger', data={'quantite': '210', 'morts': '3', 'prix': '105000',
                                                      'lieu': 'Couvoir', 'date': AUJ.isoformat(), 'motif': ''})
    assert db.session.get(Livraison, a.id).lignes[0].quantite_recue == 200      # motif obligatoire
    client.post(f'/achats/{a.numero}/corriger', data={'quantite': '210', 'morts': '3', 'prix': '105000',
                                                      'lieu': 'Couvoir', 'date': AUJ.isoformat(),
                                                      'motif': 'Erreur de comptage'})
    db.session.expire_all()
    l = db.session.get(Livraison, a.id).lignes[0]
    assert (l.quantite_recue, l.morts_arrivee) == (210, 3)
    assert JournalAudit.query.filter_by(action='CORRECTION', table_nom='livraison').count() == 1
    for ident, profil, provinces, voit, corrige in (('dge1', Profil.DGE, [], True, False),
                                                   ('veto1', Profil.VETO, ['EST'], False, False)):
        creer_utilisateur(ident, profil, provinces)
        db.session.commit()
        changer(client, ident)
        page = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
        assert ("Achats de l'éleveur" in page) is voit and ('/corriger' in page) is corrige, ident


def test_achat_date_limitee_et_hors_ligne(client, monde):
    connecter(client, 'eleveur1')
    page = acheter(client, monde['aliment'], '5', date=(AUJ - timedelta(days=5)).isoformat()).get_data(as_text=True)
    assert 'trop ancien' in page and Livraison.query.count() == 0
    ident, rep = rejouer(client, '/j-ai-achete', {'produit': monde['aliment'].id, 'quantite': '7'},
                         content_type='multipart/form-data')
    assert rep['etat'] == 'ok' and Livraison.query.one().lignes[0].quantite_recue == 7
    _, rep = rejouer(client, '/j-ai-achete', {'produit': monde['aliment'].id, 'quantite': '7'}, ident=ident,
                     content_type='multipart/form-data')
    assert rep['etat'] == 'deja' and Livraison.query.count() == 1


# ── Tableau des clics (depuis l'accueil) ────────────────────────────────

def test_tableau_des_clics(client, monde):
    """Chaque action : la tuile de l'accueil mène directement à l'écran où se trouve le geste final."""
    recevoir(monde['f'], [(monde['poussins'], 500, 0)])
    liv = intrants.nouvelle_livraison(monde['f'], AUJ, None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=0, produit=vaccin, mode='Eau de boisson'))
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    b = bande_ouverte(monde, effectif=800, bat=1)
    connecter(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)

    def ouvrir(lien):   # clic 1 : la tuile
        assert f'href="{lien}"' in accueil, lien
        r = client.get(lien)
        return client.get(r.location) if r.status_code == 302 else r

    # Saisie du jour → Envoyer : 2
    assert 'Envoyer ✓' in ouvrir('/saisie-du-jour').get_data(as_text=True)
    # Livraisons → Tout reçu : 2
    assert f'/livraisons/{liv.numero}/tout-recu' in ouvrir('/livraisons/mes-livraisons').get_data(as_text=True)
    # Nouvelle bande → bâtiment → Commencer : 3 (le seul bâtiment libre est déjà choisi : 2)
    page = ouvrir('/bandes/ouvrir').get_data(as_text=True)
    assert 'name="batiment"' in page and 'Commencer la bande' in page
    # Peser → Enregistrer : 2
    assert 'Enregistrer la pesée' in ouvrir('/aller/peser').get_data(as_text=True)
    # Sortie → type → Enregistrer : 3
    page = ouvrir('/aller/sortie').get_data(as_text=True)
    assert 'name="motif"' in page and 'Enregistrer la sortie' in page
    # Vaccins → C'est fait : 2
    assert "✓ C'est fait" in ouvrir('/aller/vaccins').get_data(as_text=True)
    # Poulet malade → signes → Envoyer : 3 (photo facultative)
    page = ouvrir('/aller/malade').get_data(as_text=True)
    assert 'name="signes"' in page and 'Envoyer au vétérinaire' in page
    # J'ai acheté → produit → Enregistrer : 3
    page = ouvrir('/j-ai-achete').get_data(as_text=True)
    assert 'name="produit"' in page and '>Enregistrer</button>' in page
    # Mes bandes, Mon stock, Appeler mon agent : 1
    assert b.numero in ouvrir('/bandes/mes-bandes').get_data(as_text=True)
    assert 'Aliment démarrage' in ouvrir('/mon-stock').get_data(as_text=True)
    assert 'href="tel:+24177123456"' in accueil
