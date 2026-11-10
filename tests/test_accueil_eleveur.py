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

HUIT = ['saisie', 'ma_bande', 'ventes', 'soins', 'malade', 'produits', 'argent', 'entretien']


def test_accueil_sans_bande_ni_poussins(client, monde):
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'Aucune bande en cours' in page and 'poulet-dort' in page
    assert tuiles(page) == HUIT                          # les 8 tuiles restent, même sans bande
    assert 'aucune bande en cours' in page               # la tuile Saisie du jour le dit
    assert 'class="compteur"' not in page and 'bloc-bat' not in page   # plus de tableau de bord
    # Sans bande : Saisie du jour et Ventes et sorties ouvrent une petite page simple
    for lien in ('/saisie-du-jour', '/aller/sortie', '/aller/peser', '/aller/traitement'):
        page = client.get(lien).get_data(as_text=True)
        assert 'Aucune bande en cours' in page and 'Mes bandes' in page, lien
    assert 'Peser' not in client.get('/ma-bande').get_data(as_text=True)      # pas de bouton inutile


def test_accueil_poussins_en_attente_et_livraisons_a_confirmer(client, monde):
    recevoir(monde['f'], [(monde['poussins'], 1000, 3)])
    liv = intrants.nouvelle_livraison(monde['f'], AUJ, None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert tuiles(page) == HUIT
    assert re.search(r'data-tuile="ma_bande">\s*<span class="pastille ">997</span>', page)   # poussins
    assert re.search(r'data-tuile="produits">\s*<span class="pastille ">1</span>', page)     # à confirmer
    assert 'carte-livraison' not in page
    page = client.get('/ma-bande').get_data(as_text=True)
    assert 'data-case="nouvelle"' in page and '997 poussins en attente' in page
    page = client.get('/mes-produits').get_data(as_text=True)
    assert 'carte-livraison' in page and f'/livraisons/{liv.numero}/tout-recu' in page and 'J&#39;ai reçu moins' not in page
    for case in ('achat', 'stock', 'livraisons'):
        assert f'data-case="{case}"' in page
    # Tout reçu : retour sur « Mes produits » avec « Annuler (10) »
    r = client.post(f'/livraisons/{liv.numero}/tout-recu')
    assert r.location.endswith('/mes-produits')
    assert 'bandeau-annuler' in client.get('/mes-produits').get_data(as_text=True)


def test_accueil_avec_bandes_saisie_pastilles_et_ligne_d_etat(client, monde):
    b1 = bande_ouverte(monde, jour=AUJ - timedelta(days=3))
    jours(b1, 2, 1)
    b2 = bande_ouverte(monde, effectif=800, jour=AUJ - timedelta(days=2), bat=1)
    jours(b2, 1)
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert '2 bâtiments · tout va bien' in page and 'B1 jour 3 · B2 jour 2' in page and 'poulet-content' in page
    assert 'B1, B2 à faire · morts et aliment' in page and 'aria-label="2 bâtiment(s) à saisir"' in page
    assert tuiles(page) == HUIT and 'tuile tuile-large' in page          # Entretien en pleine largeur
    jours(b1, 0)
    jours(b2, 0)
    page = client.get('/').get_data(as_text=True)
    assert "Tout est envoyé aujourd'hui" in page and 'tuile-calme' in page and 'href="/saisie-du-jour"' in page


def test_raccourcis_pesee_et_vaccin_du_jour(client, monde):
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=8, produit=vaccin, mode='Eau de boisson'))
    db.session.commit()
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=7))
    jours(b, *range(1, 7))
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert '⚖️ Pesée prévue dans B1' in page and f'href="/bandes/{b.numero}/pesee"' in page   # 7 jours sans pesée
    assert 'data-raccourci="vaccin"' not in page                        # vaccin demain : pas de raccourci
    assert '>demain</span>' in page                                     # mais la pastille de la tuile
    page = client.get('/vaccins-et-soins').get_data(as_text=True)
    assert 'Vaccin Gumboro · B1' in page and 'demain' in page and "✓ C'est fait" not in page   # rien à l'avance
    db.session.add(Pesee(bande=b, date=AUJ, nombre_pesees=10, poids_total_kg=2, poids_moyen_g=200, poids_attendu_g=180))
    b.date_mise_en_place = AUJ - timedelta(days=8)
    db.session.commit()
    page = client.get('/').get_data(as_text=True)
    assert 'Pesée prévue' not in page and 'data-raccourci="vaccin"' in page and "✓ C'est fait" in page
    # « ✓ C'est fait » depuis l'accueil : 1 toucher, puis « Fait ✓ — Annuler (10) »
    from app.models.sante import Vaccination
    form = re.search(r'<form method="post" action="([^"]+)" class="form-vaccin-fait".*?</form>', page, re.S)
    champs = dict(re.findall(r'name="(\w+)" value="([^"]*)"', form.group(0)))
    r = client.post(form.group(1), data=champs)
    assert r.location.endswith('/')
    v = Vaccination.query.one()
    assert (v.nombre_animaux, v.quantite, v.mode) == (997, 997, 'Eau de boisson') and v.calendrier_id
    page = client.get('/').get_data(as_text=True)
    assert 'Fait ✓ — Vaccin Gumboro · B1' in page and 'data-raccourci="vaccin"' not in page
    client.post(f'/vaccinations/{v.id}/annuler', data={'retour': 'accueil'})
    db.session.refresh(v)
    assert v.annule and 'data-raccourci="vaccin"' in client.get('/').get_data(as_text=True)    # de nouveau à faire
    assert JournalAudit.query.filter_by(action='ANNULATION', table_nom='vaccination').count() == 1
    assert 'Vaccin Gumboro' not in {s['produit'].nom for s in intrants.stock_ferme(monde['f']) if s['stock'] < 0}


def test_vaccins_et_soins_c_est_fait_hors_ligne_et_signalements(client, monde):
    vaccin = Produit(nom='Vaccin Newcastle', type='Vaccin', unite='flacons')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=0, produit=vaccin, mode='Eau de boisson'))
    db.session.commit()
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.get('/vaccins-et-soins').get_data(as_text=True)
    assert 'data-case="traitement"' in page and 'Mes signalements' in page
    form = re.search(r'<form method="post" action="([^"]+)" class="form-vaccin-fait".*?</form>', page, re.S)
    champs = dict(re.findall(r'name="(\w+)" value="([^"]*)"', form.group(0)))
    assert champs['quantite'] == '1' and champs['depuis'] == 'soins'       # flacons : 1, comme l'écran du vaccin
    _, rep = rejouer(client, form.group(1), champs)                        # sans réseau : rejoué plus tard
    assert rep['etat'] == 'ok'
    page = client.get('/vaccins-et-soins').get_data(as_text=True)
    assert 'Fait ✓ —' not in page and 'Aucun vaccin à faire' in page
    assert client.get('/aller/traitement').location.endswith(f'/sante/traiter/{b.numero}')
    page = client.get('/sante/mes-declarations').get_data(as_text=True)
    assert 'Mes signalements' in page and 'Mes déclarations' not in page


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


def test_entete_agent_et_moi(client, monde):
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'data-entete="agent"' not in page and 'data-entete="moi"' in page     # l'agent n'a pas de téléphone
    assert '/auth/mot-de-passe' not in page                               # le mot de passe est dans « Moi »
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    for lien in ('/', '/mes-produits', '/mon-argent'):
        page = client.get(lien).get_data(as_text=True)
        assert 'href="tel:+24177123456"' in page and '📞 Paul' in page and '👤 Moi' in page, lien
    assert 'Appeler Paul' not in client.get('/').get_data(as_text=True)  # plus de tuile « Appeler »
    page = client.get('/moi').get_data(as_text=True)
    assert 'Ma ferme' in page and 'Ferme Un' in page and '2 300 places' in page
    for cle in ('visites', 'compte', 'aide', 'presentation', 'quitter'):
        assert f'data-moi="{cle}"' in page
    assert 'data-moi="banque"' not in page                              # ferme non financée : rien (lot 13)
    # 👤 Moi → Se déconnecter : 2
    client.post('/auth/deconnexion')
    assert client.get('/moi').status_code == 302


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
    r = client.post(f'/bandes/{b1.numero}/saisie', data={'sacs': '0', 'morts': '1', 'ajouter': '1'})
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
    assert r.status_code == 302 and r.location.endswith('/mes-produits')
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
    assert 'data-case="nouvelle"' in client.get('/ma-bande').get_data(as_text=True)
    client.post('/bandes/ouvrir', data={'ferme': monde['f'].numero, 'ligne': a.lignes[0].id,
                                        'batiment': monde['f'].batiments[0].id, 'effectif': '496'})
    assert regles.poussins_en_attente(monde['f']) == []
    # Poussins déjà mis en bande : l'achat ne s'annule plus
    assert not intrants.achat_annulable(a, monde['el'])


def test_achat_annuler_dans_les_10_secondes(client, monde):
    connecter(client, 'eleveur1')
    acheter(client, monde['aliment'], '5')
    a = Livraison.query.filter_by(origine=OrigineLivraison.ACHAT).one()
    page = client.get('/mes-produits').get_data(as_text=True)
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
    assert 'bandeau-annuler' not in client.get('/mes-produits').get_data(as_text=True)
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


# ── Tableau des clics (lot 11) ──────────────────────────────────────────
# Comptent : ouvrir un écran et valider. Ne comptent pas : les choix dans le même écran
# (bâtiment, produit, signe, catégorie, type de sortie) et les + / − des compteurs.

def test_tableau_des_clics(client, monde):
    recevoir(monde['f'], [(monde['poussins'], 500, 0)])
    liv = intrants.nouvelle_livraison(monde['f'], AUJ, None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=0, produit=vaccin, mode='Eau de boisson'))
    db.session.add(Produit(nom='Amoxicilline', type='Médicament', unite='sachets'))
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    b = bande_ouverte(monde, effectif=800, bat=1)
    connecter(client, 'eleveur1')

    def ouvrir(lien, depuis='/'):     # un clic : le lien est sur l'écran de départ
        page = client.get(depuis).get_data(as_text=True)
        assert f'href="{lien}"' in page, (depuis, lien)
        r = client.get(lien)
        return (client.get(r.location) if r.status_code == 302 else r).get_data(as_text=True)

    # Saisie du jour → Envoyer : 2
    assert 'Envoyer ✓' in ouvrir('/saisie-du-jour')
    # Ventes et sorties → Enregistrer : 2 (le type de sortie est un choix)
    page = ouvrir('/aller/sortie')
    assert 'name="motif"' in page and 'Enregistrer la sortie' in page
    # Vaccins et soins → C'est fait : 2
    assert 'class="tache-bouton">✓ C&#39;est fait' in ouvrir('/vaccins-et-soins').replace("C'est", 'C&#39;est')
    # Poulet malade → Envoyer : 2 (les signes sont des choix)
    page = ouvrir('/aller/malade')
    assert 'name="signes"' in page and 'Envoyer au vétérinaire' in page
    # Mes produits → Tout reçu : 2
    assert f'/livraisons/{liv.numero}/tout-recu' in ouvrir('/mes-produits')
    # Ma bande → Nouvelle bande → Commencer : 3
    ouvrir('/ma-bande')
    page = ouvrir('/bandes/ouvrir', depuis='/ma-bande')
    assert 'Ouvrir la bande' in page          # lot K4 : libellé de la maquette la plus récente (lot A)
    # Ma bande → Peser → Enregistrer : 3
    assert 'Enregistrer la pesée' in ouvrir('/aller/peser', depuis='/ma-bande')
    # Mes produits → J'ai acheté → Enregistrer : 3
    page = ouvrir('/j-ai-achete', depuis='/mes-produits')
    assert 'name="produit"' in page and '>Enregistrer</button>' in page
    # Mon argent → J'ai payé → Enregistrer : 3
    ouvrir('/mon-argent')
    page = ouvrir('/j-ai-paye', depuis='/mon-argent')
    assert 'name="categorie"' in page and '>Enregistrer</button>' in page
    # Vaccins et soins → Traitement → Enregistrer : 3
    page = ouvrir('/aller/traitement', depuis='/vaccins-et-soins')
    assert b.numero in page and 'name="produit_id"' in page
    # Entretien → Fait ✓ : 2 (inchangé)
    assert 'class="tache-bouton">Fait ✓' in ouvrir('/entretien')
    # 📞 : 1
    assert 'href="tel:+24177123456"' in client.get('/').get_data(as_text=True)
    # 👤 Moi → Se déconnecter : 2
    assert 'data-moi="quitter"' in ouvrir('/moi')


# ── Ordre fixe des 8 tuiles ─────────────────────────────────────────────

def test_ordre_des_tuiles_fixe(client, monde):
    """Saisie du jour · Ma bande · Ventes et sorties · Vaccins et soins · Poulet malade · Mes produits ·
    Mon argent · Entretien — quelles que soient les pastilles, avec ou sans bande."""
    vaccin = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.add(CalendrierVaccinal(age_jours=1, produit=vaccin, mode='Eau de boisson'))
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    b = bande_ouverte(monde)
    recevoir(monde['f'], [(monde['poussins'], 300, 0)])
    liv = intrants.nouvelle_livraison(monde['f'], AUJ, None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'eleveur1')
    assert tuiles(client.get('/').get_data(as_text=True)) == HUIT
    jours(b, 0)
    b.date_mise_en_place = AUJ - timedelta(days=5)
    liv.statut = S.ANNULEE
    db.session.commit()
    page = client.get('/').get_data(as_text=True)
    assert 'tuile-calme' in page and 'en retard' in page and tuiles(page) == HUIT
    monde['agent'].telephone = None
    regles.cloturer(b, monde['el'], 'essai')
    db.session.commit()
    assert tuiles(client.get('/').get_data(as_text=True)) == HUIT       # les tuiles ne disparaissent plus
