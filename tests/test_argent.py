"""Lot 11 — « Mon argent » : ventes (montant facultatif, complété plus tard), « J'ai payé » (annulation 10 s,
hors ligne, agent pour l'éleveur), Gagné / Dépensé / Reste par période, répartition entre bandes, bilan
financier, aide de l'État, visibilité (agent oui, DGE agrégé seulement, BCEG non)."""
import io
from datetime import timedelta

from app import db
from app.models import JournalAudit, Livraison, Profil
from app.models.argent import Depense, icone_et_nom
from app.models.bande import Sortie
from app.models.base import maintenant
from app.services import argent, intrants, bandes as regles
from app.services.journal import Action
from tests.conftest import creer_utilisateur, connecter, creer_ferme
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer
from tests.test_sante import JPEG


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def depense(ferme, montant, jour=None, batiment=None, categorie='⚡ Électricité'):
    d = Depense(numero_metier=f'DEP-T-{Depense.query.count() + 1}', ferme_id=ferme.id, categorie=categorie,
                montant_fcfa=montant, date=jour or AUJ, batiment_id=batiment.id if batiment else None)
    db.session.add(d)
    db.session.commit()
    return d


def vendre(bande, nombre=100, montant=None, motif='Vente', jour=None):
    s = Sortie(bande=bande, date=jour or AUJ, motif=motif, destinataire_libre='Marché', nombre=nombre,
               poids_total_kg=nombre * 2, montant_fcfa=montant)
    db.session.add(s)
    db.session.commit()
    return s


def payer(client, **data):
    base = {'categorie': '⚡ Électricité', 'montant': '90 000'}
    return client.post('/j-ai-paye', data={**base, **data}, content_type='multipart/form-data')


# ── Catégories ──────────────────────────────────────────────────────────

def test_categories_de_depart_et_image(client, monde):
    assert [c[2] for c in argent.categories()] == ["Main-d'œuvre", 'Électricité', 'Carburant', 'Transport', 'Eau',
                                                     'Réparation', 'Autre']
    assert icone_et_nom('👷 Main-d\'œuvre') == ('👷', "Main-d'œuvre")
    assert icone_et_nom('Gardiennage') == ('📦', 'Gardiennage')                  # ajoutée sans émoji


# ── Ventes et sorties : montant facultatif, complété plus tard ─────────

def test_sortie_avec_et_sans_montant(client, monde):
    b = bande_ouverte(monde)
    from app.models import Operateur
    abattoir = Operateur.query.filter_by(type='Abattoir').first()
    connecter(client, 'eleveur1')
    page = client.get(f'/bandes/{b.numero}/sortie').get_data(as_text=True)
    assert 'Combien avez-vous reçu ?' in page and 'facultatif' in page
    client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Vente', 'destinataire_libre': 'Marché', 'nombre': '100',
                                                  'poids_total': '200', 'montant': '600 000'})
    client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'operateur': abattoir.id, 'nombre': '50',
                                                  'poids_total': '100', 'montant': ''})
    client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Autre', 'destinataire_libre': 'Don', 'nombre': '5',
                                                  'poids_total': '10', 'montant': '9 999'})
    montants = {s.motif: s.montant_fcfa for s in Sortie.query}
    assert montants == {'Vente': 600000, 'Abattoir': None, 'Autre': None}       # « Autre » : jamais de montant
    page = client.get('/mon-argent?periode=tout').get_data(as_text=True)
    assert 'à compléter →' in page and '+ 600 000' in page


def test_completer_le_montant_une_fois_puis_correction_de_l_agent(client, monde):
    b = bande_ouverte(monde)
    s = vendre(b, montant=None, motif='Vente')
    connecter(client, 'eleveur1')
    client.post(f'/ventes/{s.id}/montant', data={'montant': '450000'})
    db.session.refresh(s)
    assert s.montant_fcfa == 450000
    page = client.post(f'/ventes/{s.id}/montant', data={'montant': '1'}).get_data(as_text=True)
    assert 'demandez une correction à votre agent' in page
    db.session.refresh(s)
    assert s.montant_fcfa == 450000
    changer(client, 'agent1')
    page = client.post(f'/ventes/{s.id}/montant', data={'montant': '480000'}).get_data(as_text=True)
    assert 'Indiquez le motif' in page
    client.post(f'/ventes/{s.id}/montant', data={'montant': '480000', 'motif': 'erreur de saisie'})
    db.session.refresh(s)
    assert s.montant_fcfa == 480000
    j = JournalAudit.query.filter_by(action=Action.CORRECTION, table_nom='sortie').one()
    assert '450000 → 480000' in j.detail and 'erreur de saisie' in j.detail


# ── J'ai payé : annulation 10 s, hors ligne, agent pour l'éleveur ──────

def test_j_ai_paye_annuler_dans_les_10_secondes(client, monde):
    connecter(client, 'eleveur1')
    page = client.get('/j-ai-paye').get_data(as_text=True)
    for nom in ('Main-d&#39;œuvre', 'Électricité', 'Carburant', 'Transport', 'Eau', 'Réparation', 'Autre'):
        assert nom in page
    r = payer(client, batiment=str(monde['f'].batiments[1].id), recu=(io.BytesIO(JPEG), 'recu.jpg'))
    assert r.status_code == 302 and r.location.endswith('/mon-argent')
    d = Depense.query.one()
    assert d.montant_fcfa == 90000 and d.batiment_id == monde['f'].batiments[1].id and d.photo_recu
    assert d.numero.startswith(f'DEP-{maintenant().year}-') and not d.saisi_par_agent
    page = client.get('/mon-argent').get_data(as_text=True)
    assert 'Enregistré ✓ — Électricité · 90 000 FCFA' in page and f'/depenses/{d.numero}/annuler' in page
    assert client.get(f'/depenses/{d.numero}/recu').status_code == 200
    client.post(f'/depenses/{d.numero}/annuler')
    db.session.refresh(d)
    assert d.annule
    assert JournalAudit.query.filter_by(action=Action.ANNULATION, table_nom='depense').count() == 1
    assert argent.totaux(argent.mouvements([monde['f'].id]))['depense'] == 0
    # Trop tard : refusé
    payer(client)
    d2 = Depense.query.filter_by(annule=False).one()
    d2.cree_le = maintenant() - timedelta(seconds=40)
    db.session.commit()
    client.post(f'/depenses/{d2.numero}/annuler')
    db.session.refresh(d2)
    assert not d2.annule


def test_j_ai_paye_controles(client, monde):
    connecter(client, 'eleveur1')
    assert 'Touchez ce que vous avez payé' in payer(client, categorie='').get_data(as_text=True)
    assert 'Indiquez le montant' in payer(client, montant='').get_data(as_text=True)
    assert 'trop ancienne' in payer(client, date=(AUJ - timedelta(days=10)).isoformat()).get_data(as_text=True)
    assert Depense.query.count() == 0


def test_j_ai_paye_hors_ligne(client, monde):
    connecter(client, 'eleveur1')
    _, rep = rejouer(client, '/j-ai-paye', {'categorie': '⛽ Carburant', 'montant': '15000'},
                     content_type='multipart/form-data')
    assert rep['etat'] == 'ok'
    d = Depense.query.one()
    assert d.appareil_id == 'tel-1' and d.montant_fcfa == 15000
    assert 'Enregistré ✓ —' not in client.get('/mon-argent').get_data(as_text=True)   # pas de bandeau après coup


def test_agent_saisit_j_ai_paye_pour_l_eleveur(client, monde):
    connecter(client, 'agent1')
    r = payer(client, ferme=monde['f'].numero, categorie="👷 Main-d'œuvre", montant='50000',
              date=(AUJ - timedelta(days=12)).isoformat())       # l'agent peut saisir plus ancien
    assert r.status_code == 302 and '#argent' in r.location
    d = Depense.query.one()
    assert d.saisi_par_agent and d.cree_par == monde['agent'].id
    j = JournalAudit.query.filter_by(action=Action.POUR_ELEVEUR, table_nom='depense').one()
    assert 'pour l\'éleveur' in j.detail
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'id="argent"' in fiche and "Agent pour l&#39;éleveur" in fiche
    changer(client, 'eleveur1')
    assert "Agent pour l'éleveur" in client.get('/mon-argent?periode=tout').get_data(as_text=True)
    # Un autre agent ne saisit pas pour cette ferme
    creer_utilisateur('agent3', Profil.AGENT, ['EST'])
    changer(client, 'agent3')
    payer(client, ferme=monde['f'].numero)
    assert Depense.query.count() == 1


def test_agent_corrige_une_depense_avec_motif(client, monde):
    d = depense(monde['f'], 30000)
    connecter(client, 'agent1')
    assert 'Indiquez le motif' in client.post(f'/depenses/{d.numero}/corriger', data={
        'categorie': '⛽ Carburant', 'montant': '35000', 'date': AUJ.isoformat()}).get_data(as_text=True)
    client.post(f'/depenses/{d.numero}/corriger', data={'categorie': '⛽ Carburant', 'montant': '35000',
                                                        'date': AUJ.isoformat(), 'motif': 'reçu relu'})
    db.session.refresh(d)
    assert d.montant_fcfa == 35000 and d.categorie == '⛽ Carburant'
    assert JournalAudit.query.filter_by(action=Action.CORRECTION, table_nom='depense').count() == 1
    changer(client, 'eleveur1')
    assert client.get(f'/depenses/{d.numero}/corriger').status_code in (302, 403)


# ── Gagné / Dépensé / Reste par période ────────────────────────────────

def test_totaux_par_periode(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=60))
    vendre(b, montant=500000, jour=AUJ)
    vendre(b, montant=200000, jour=AUJ - timedelta(days=45))
    depense(monde['f'], 100000, jour=AUJ)
    depense(monde['f'], 40000, jour=AUJ - timedelta(days=45))
    tous = argent.mouvements([monde['f'].id])
    mois = argent.filtrer(tous, 'mois', jour=AUJ)
    if (AUJ - timedelta(days=45)).month != AUJ.month:
        assert argent.totaux(mois) == {'gagne': 500000, 'depense': 100000, 'reste': 400000}
    assert argent.totaux(tous) == {'gagne': 700000, 'depense': 140000, 'reste': 560000}
    t = argent.totaux(argent.filtrer(tous, 'bande', b), b.id)
    assert t == {'gagne': 700000, 'depense': 140000, 'reste': 560000}     # une seule bande : tout pour elle
    connecter(client, 'eleveur1')
    page = client.get('/mon-argent?periode=tout').get_data(as_text=True)
    assert '700 000' in page and '140 000' in page and '560 000' in page
    page = client.get('/mon-argent?periode=bande').get_data(as_text=True)
    assert 'class="periode active" href="/mon-argent?periode=bande"' in page
    # Reste négatif : en rouge
    depense(monde['f'], 1000000)
    assert 'reste negatif' in client.get('/mon-argent?periode=tout').get_data(as_text=True)


# ── Répartition entre bandes ───────────────────────────────────────────

def test_partage_exact_au_prorata():
    assert argent.partager(100, {'a': 1, 'b': 1, 'c': 1}) == {'a': 34, 'b': 33, 'c': 33}
    assert sum(argent.partager(90001, {'a': 997, 'b': 500}).values()) == 90001
    assert argent.partager(90000, {'a': 1000, 'b': 500}) == {'a': 60000, 'b': 30000}
    assert argent.partager(10, {'a': 0, 'b': 0}) == {'a': 5, 'b': 5}
    assert argent.partager(10, {}) == {}


def test_repartition_batiment_prorata_hors_bande_et_poussins(client, monde):
    f = monde['f']
    b1 = bande_ouverte(monde, effectif=1000, jour=AUJ - timedelta(days=10))
    b2 = bande_ouverte(monde, effectif=500, jour=AUJ - timedelta(days=10), bat=1)
    sans = depense(f, 90000)                                   # sans bâtiment : au prorata 1000 / 500
    avec = depense(f, 20000, batiment=f.batiments[1])          # avec bâtiment : tout à B2
    avant = depense(f, 7000, jour=AUJ - timedelta(days=20))    # aucune bande ce jour-là : hors bande
    mvts = {m['objet'].id: m for m in argent.mouvements([f.id])}
    assert mvts[sans.id]['parts'] == {b1.id: 60000, b2.id: 30000}
    assert mvts[avec.id]['parts'] == {b2.id: 20000}
    assert mvts[avant.id]['parts'] == {} and mvts[avant.id]['hors_bande']
    # Poussins achetés : à la bande qui les a reçus, jamais en partage
    regles.cloturer(b2, monde['el'], 'essai')
    db.session.commit()
    connecter(client, 'eleveur1')
    client.post('/j-ai-achete', data={'produit': monde['poussins'].id, 'quantite': '300', 'morts': '0', 'prix': '150000'},
                content_type='multipart/form-data')
    achat = Livraison.query.filter_by(origine='ACHAT').one()
    ligne = achat.lignes[0]
    b3 = regles.ouvrir(f, f.batiments[1], ligne, 300, AUJ, None, monde['el'])
    db.session.commit()
    m = next(m for m in argent.mouvements([f.id]) if m['objet'].id == achat.id)
    assert m['parts'] == {b3.id: 150000}
    # Un achat d'aliment pour B1 : à B1
    client.post('/j-ai-achete', data={'produit': monde['aliment'].id, 'quantite': '10', 'prix': '90000',
                                      'batiment': str(f.batiments[0].id)}, content_type='multipart/form-data')
    a2 = Livraison.query.filter_by(origine='ACHAT').order_by(Livraison.numero_metier.desc()).first()
    assert a2.batiment_id == f.batiments[0].id
    m = next(m for m in argent.mouvements([f.id]) if m['objet'].id == a2.id)
    assert m['parts'] == {b1.id: 90000}
    page = client.get(f'/mon-argent?periode=bande&bande={b1.numero}').get_data(as_text=True)
    assert 'votre part : 50 000' in page            # B1 1 000, B2 500 (terminée ce jour), B3 300


# ── Bilan financier, aide de l'État ────────────────────────────────────

def _livraison_etat(monde, valeur):
    liv = intrants.nouvelle_livraison(monde['f'], AUJ - timedelta(days=5), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': valeur}])
    db.session.flush()
    liv.lignes[0].quantite_recue = 40
    from app.models.intrant import StatutLivraison
    liv.statut = StatutLivraison.RECUE
    db.session.commit()
    return liv


def test_bilan_financier_a_la_cloture_et_aide_de_l_etat(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    vendre(b, nombre=500, montant=1000000)
    vendre(b, nombre=100, montant=None, motif='Vente')
    depense(monde['f'], 300000)
    liv = _livraison_etat(monde, None)                          # valeur non renseignée : pas de phrase
    assert argent.aide_etat(b) is None
    regles.cloturer(b, monde['el'], 'essai')
    db.session.commit()
    assert b.bilan['chiffre_affaires'] == 1000000 and b.bilan['depenses'] == 300000 and b.bilan['marge'] == 700000
    assert b.bilan['aide_etat'] is None and b.bilan['ventes_a_completer'] == 1
    connecter(client, 'eleveur1')
    page = client.get(f'/bandes/{b.numero}/bilan').get_data(as_text=True)
    assert "chiffre d'affaires" in page and '700 000' in page and "Sans l'aide de l'État" not in page
    assert '1 vente sans montant' in page
    # La valeur est renseignée : la phrase apparaît (40 sacs × 12 500 FCFA)
    liv.lignes[0].valeur_unitaire = 12500
    db.session.commit()
    assert argent.aide_etat(b) == 500000
    s = Sortie.query.filter(Sortie.montant_fcfa.is_(None)).one()
    client.post(f'/ventes/{s.id}/montant', data={'montant': '200000'})     # complétée après la clôture
    db.session.refresh(b)
    assert b.bilan['chiffre_affaires'] == 1200000 and b.bilan['marge'] == 900000 and b.bilan['aide_etat'] == 500000
    page = client.get(f'/bandes/{b.numero}/bilan').get_data(as_text=True)
    assert "Sans l'aide de l'État, cette bande vous aurait coûté <strong>500 000 FCFA</strong> de plus." in page
    page = client.get(f'/mon-argent?periode=bande&bande={b.numero}').get_data(as_text=True)
    assert '500 000 FCFA</strong> de plus' in page


def test_aide_de_l_etat_partielle_jamais_affichee(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    _livraison_etat(monde, 12500)
    assert argent.aide_etat(b) == 500000
    _livraison_etat(monde, None)                                # une ligne sans valeur : rien
    assert argent.aide_etat(b) is None


# ── Visibilité ─────────────────────────────────────────────────────────

def test_visibilite_agent_dge_bceg(client, monde):
    b = bande_ouverte(monde)
    vendre(b, montant=600000)
    depense(monde['f'], 50000)
    # Agent : la carte de la fiche ferme
    connecter(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert "Argent de l'éleveur" in fiche and '600 000' in fiche
    assert client.get('/mon-argent').status_code in (302, 403)
    # DGE : pas de carte par ferme ; des totaux par province, cachés sous 3 fermes
    creer_utilisateur('dge', Profil.DGE, ['EST'])
    changer(client, 'dge')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'id="argent"' not in fiche
    tableau = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    assert 'id="argent-eleveurs"' in tableau and '600 000' not in tableau
    for i in (3, 4):
        f = creer_ferme(f'Ferme {i}', 'EST', 'Ntoum', agent=monde['agent'])
        from app.services.fermes import ajouter_batiment
        ajouter_batiment(f, 500)
        db.session.commit()
        depense(f, 10000 * i)
    tableau = client.get('/pilotage/tableau-de-bord').get_data(as_text=True)
    lignes = argent.agregats(type(monde['f']).query.all())
    assert lignes[0]['fermes'] == 3 and lignes[0]['ca'] == 600000 and lignes[0]['depenses'] == 120000
    assert '600 000' in tableau and '120 000' in tableau
    # BCEG, VETO : rien
    for ident, profil in (('bceg', Profil.BCEG), ('veto', Profil.VETO)):
        creer_utilisateur(ident, profil, ['EST'])
        changer(client, ident)
        assert client.get('/mon-argent').status_code in (302, 403)
        assert client.get('/j-ai-paye').status_code in (302, 403)
        assert 'argent-eleveurs' not in client.get('/pilotage/tableau-de-bord').get_data(as_text=True)


def test_mouvements_de_l_eleveur_seulement(client, monde):
    autre = depense(monde['f2'], 999000)
    connecter(client, 'eleveur1')
    assert '999 000' not in client.get('/mon-argent?periode=tout').get_data(as_text=True)
    assert client.get(f'/depenses/{autre.numero}/recu').status_code == 404
