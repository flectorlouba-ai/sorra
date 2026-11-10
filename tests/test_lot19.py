"""Lot 19 — opérateur (abattoir, marché) et traçabilité aval : fonctions 58 (écart à la réception), 63 (contrôles
automatiques), 65 (refus), 66 (indicateurs de traçabilité)."""
import html
import re
from datetime import timedelta

import pytest

from app import db, indicateurs
from app.models import Profil, Operateur, JournalAudit, Parametre, Produit
from app.models.hors_ligne import ConflitHorsLigne
from app.models.sante import AlerteSanitaire, CalendrierVaccinal, Traitement
from app.models.tracabilite import Reception, Scan, EtatReception as E
from app.services import bandes as regles, receptions, tracabilite, veto
from tests.conftest import creer_utilisateur, connecter, province
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def texte(r):
    """Page lue comme l'utilisateur la voit (apostrophes et guillemets décodés)."""
    return html.unescape(r.get_data(as_text=True))


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


@pytest.fixture
def aval(monde):
    """Abattoir de Ntoum (registre du monde de test) + un marché, chacun avec son compte OPÉRATEUR,
    un vétérinaire de l'Estuaire, une bande pesée."""
    abattoir = Operateur.query.filter_by(type='Abattoir').one()
    marche = Operateur(numero='OPE-0003', nom='Marché Mont-Bouët', type='Marché', province=province('EST'))
    db.session.add(marche)
    db.session.flush()
    for ident, op in (('abattoir1', abattoir), ('marche1', marche)):
        u = creer_utilisateur(ident, Profil.OPERATEUR, ['EST'])
        u.operateur_id = op.id
    v = creer_utilisateur('veto1', Profil.VETO, ['EST'])
    v.telephone = '+241 66 00 11 22'
    creer_utilisateur('dge', Profil.DGE)
    b = bande_ouverte(monde)
    regles.peser(b, AUJ, 10, 20, monde['el'])
    db.session.commit()
    return {**monde, 'abattoir': abattoir, 'marche': marche, 'b': b, 'veto': v}


def sortie(m, op=None, nombre=100, b=None):
    op = op or m['abattoir']
    s = regles.sortir(b or m['b'], AUJ, 'Abattoir' if op.type == 'Abattoir' else 'Vente', op, '', nombre,
                      nombre * 2, m['el'])
    db.session.commit()
    return s


def scanner(client, lot=None, numero=None, code=None):
    q = {'code': code or lot.code} if (code or lot) and not numero else {'numero': numero}
    r = client.get('/operateur/lot', query_string=q)
    return texte(r)


def recevoir(client, lot, **champs):
    data = {'numero': lot.numero, 'vivants': '100', 'morts': '0', 'poids': '200', 'choix': 'valider', **champs}
    return client.post('/operateur/recevoir', data=data)


# ── A. Un opérateur ne voit que ses lots ────────────────────────────────

def test_operateur_ne_voit_que_ses_lots(client, aval):
    a = sortie(aval).lot
    m = sortie(aval, aval['marche'], nombre=50).lot
    connecter(client, 'abattoir1')
    accueil = texte(client.get('/'))
    # lot 19 ter : mots de l'espace terrain (Recevoir un lot, Lots qui arrivent, Mes réceptions)
    assert 'Recevoir un lot' in accueil and 'Lots qui arrivent' in accueil and 'Mes réceptions' in accueil
    assert '1 lot arrive cette semaine' in accueil
    attendus = texte(client.get('/operateur/attendus'))
    assert a.numero in attendus and m.numero not in attendus
    from app.models.tracabilite import LotTrace
    from app.utils.permissions import filtre_perimetre
    abattoir1 = db.session.get(type(aval['el']), aval['el'].id).__class__.query.filter_by(identifiant='abattoir1').one()
    assert [l.numero for l in filtre_perimetre(LotTrace.query, utilisateur=abattoir1)] == [a.numero]
    page = scanner(client, m)                                   # le lot du marché : refusé, rien n'est montré
    assert 'data-resultat="ROUGE"' in page and 'Ce lot est pour Marché Mont-Bouët.' in page and 'Ferme Un' not in page
    changer(client, 'marche1')
    recevoir(client, m, vivants='50', poids='100')
    r = Reception.query.one()
    changer(client, 'abattoir1')
    assert client.get(f'/operateur/receptions/{r.id}').status_code == 403
    assert m.numero not in texte(client.get('/operateur/receptions'))
    assert client.get('/fermes/').status_code == 403 and client.get('/journal/scans').status_code == 403


def test_compte_operateur_rattache_a_un_etablissement(client, aval, admin):
    connecter(client, 'admin')
    donnees = {'identifiant': 'quai2', 'nom': 'Quai', 'profil': 'OPERATEUR', 'mot_de_passe': 'Provisoire-2026'}
    r = client.post('/administration/utilisateurs/creer', data=donnees, follow_redirects=True)
    assert 'établissement (registre des opérateurs)' in texte(r)
    client.post('/administration/utilisateurs/creer', data={**donnees, 'operateur_id': str(aval['marche'].id)})
    u = type(admin).query.filter_by(identifiant='quai2').one()
    assert u.operateur_id == aval['marche'].id and u.province_ids == [province('EST').id]


# ── B, C. Contrôles automatiques ────────────────────────────────────────

def test_controles_tous_verts_puis_chaque_cas(client, aval):
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    page = scanner(client, lot)
    assert 'data-resultat="VERT"' in page and 'Valider la réception' in page and 'Je les reçois et je les garde à part' not in page
    # lot 19 ter : contrôles en phrases (mêmes contrôles, même ordre)
    for libelle in ('Lot connu, jamais reçu', 'Bien envoyé à votre abattoir', 'Pas de médicament récent',
                    "Le vétérinaire n'a rien bloqué", 'Pesés aujourd', 'Poulets vaccinés'):
        assert libelle in page, libelle
    assert 'Annoncé par la ferme : <strong>100 poulets' in page
    assert page.index('Poulets vaccinés') < page.index('Pas de médicament') < page.index('rien bloqué') < page.index('Pesés')
    # Pesée de plus de 7 jours avant la sortie : orange
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=8)
    db.session.commit()
    page = scanner(client, lot)
    assert 'data-resultat="ORANGE"' in page and 'Je les reçois et je les garde à part' in page and 'Refuser le lot' in page
    assert 'Valider la réception' not in page and re.search(r'class="manque" data-controle="pesee"', page)
    # Vaccin en retard de 2 jours ou plus : orange ; de moins de 2 jours (tolérance) : non
    for p in aval['b'].pesees:
        p.date = AUJ
    vaccin = Produit(nom='Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    db.session.flush()
    aval['b'].date_mise_en_place = AUJ - timedelta(days=10)
    cal = CalendrierVaccinal(age_jours=9, produit=vaccin, mode='Eau de boisson')
    db.session.add(cal)
    db.session.commit()
    assert 'data-resultat="VERT"' in scanner(client, lot)         # prévu hier : dans la tolérance
    cal.age_jours = 8
    db.session.commit()
    page = scanner(client, lot)
    assert 'data-resultat="ORANGE"' in page and re.search(r'class="manque" data-controle="vaccins"', page)
    assert 'Gumboro' in page
    cal.actif = False
    # Traitement en délai d'attente : orange
    med = Produit(nom='Enrofloxacine', type='Médicament', unite='ml', delai_attente_jours=5)
    db.session.add(med)
    db.session.flush()
    db.session.add(Traitement(bande=aval['b'], date_debut=AUJ - timedelta(days=2), date_fin=AUJ - timedelta(days=1),
                              produit=med, motif='Toux', nombre_animaux=100, quantite=1))
    db.session.commit()
    page = scanner(client, lot)
    assert 'data-resultat="ORANGE"' in page and re.search(r'class="manque" data-controle="delai_attente"', page)
    assert "Médicament donné récemment — attendre jusqu'au" in page


def test_abattoir_et_marche(client, aval):
    """Marché : blocage et délai d'attente restent bloquants ; vaccins et pesée pour information."""
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=10)
    db.session.commit()
    lot_a, lot_m = sortie(aval).lot, sortie(aval, aval['marche'], nombre=40).lot
    connecter(client, 'abattoir1')
    assert 'data-resultat="ORANGE"' in scanner(client, lot_a)
    changer(client, 'marche1')
    page = scanner(client, lot_m)
    assert 'data-resultat="VERT"' in page and re.search(r'class="info" data-controle="pesee"', page)
    assert '(pour information)' in page
    med = Produit(nom='Enrofloxacine', type='Médicament', unite='ml', delai_attente_jours=5)
    db.session.add(med)
    db.session.flush()
    db.session.add(Traitement(bande=aval['b'], date_debut=AUJ - timedelta(days=1), date_fin=AUJ,
                              produit=med, motif='Toux', nombre_animaux=10, quantite=1))
    db.session.commit()
    assert 'data-resultat="ORANGE"' in scanner(client, lot_m)
    # Les contrôles sont des paramètres : « NON » retire la ligne, « TOUS » rend la pesée bloquante partout
    Parametre.query.filter_by(cle='reception.controle_delai_attente').one().valeur = 'NON'
    Parametre.query.filter_by(cle='reception.controle_pesee').one().valeur = 'TOUS'
    db.session.commit()
    page = scanner(client, lot_m)
    assert 'data-controle="delai_attente"' not in page and re.search(r'class="manque" data-controle="pesee"', page)


def test_parametres_de_reception_sous_quatre_yeux(aval):
    from app.services import approbations
    assert approbations.sensible('reception.controle_vaccins') and approbations.sensible('reception.seuil_morts_pct')
    assert approbations.domaine('PARAMETRE', 'reception.vaccin_tolerance_jours') == 'SANITAIRE'


def test_case_vide_refusee(client, aval):
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    page = scanner(client, lot)
    assert re.search(r'id="vivants"[^>]*placeholder="—"[^>]*required value=""', page)
    for vide in ({'morts': ''}, {'vivants': ''}, {'poids': ''}):
        r = recevoir(client, lot, **vide)
        assert r.status_code == 400 and Reception.query.count() == 0
    assert "« 0 » s'il n'y a pas de mort" in texte(recevoir(client, lot, morts=''))
    assert recevoir(client, lot).status_code == 302
    assert Reception.query.one().etat == E.VALIDEE and Reception.query.one().morts == 0


# ── D. Écart à la réception ─────────────────────────────────────────────

def test_ecart_explication_alertes_et_chiffres_de_la_ferme_intacts(client, aval):
    s = sortie(aval)
    lot = s.lot
    connecter(client, 'abattoir1')
    r = recevoir(client, lot, vivants='95', morts='4')               # 1 manquant, 4 % de morts
    assert r.status_code == 400 and 'touchez la raison' in texte(r)
    r = recevoir(client, lot, vivants='95', morts='4', motif_ecart='Autre')
    assert r.status_code == 400 and 'expliquez' in texte(r)
    assert Reception.query.count() == 0
    recevoir(client, lot, vivants='95', morts='4', motif_ecart='Erreur de comptage')
    rec = Reception.query.one()
    assert (rec.annonce, rec.vivants, rec.morts, rec.ecart, rec.motif_ecart) == (100, 95, 4, 1, 'Erreur de comptage')
    db.session.refresh(s)
    assert s.nombre == 100 and s.poids_total_kg == 200                # la sortie de la ferme n'est jamais modifiée
    message = ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('Écart à la réception%')).one()
    assert message.ferme_id == aval['f'].id and 'Annoncé 100, reçus vivants 95' in message.detail
    alerte = AlerteSanitaire.query.one()                               # au-delà de 2 % : le vétérinaire, quel que soit le motif
    assert alerte.origine == 'RECEPTION' and alerte.ferme_id == aval['f'].id
    changer(client, 'agent1')                                          # l'agent de la ferme est prévenu
    assert 'Écart à la réception du lot' in texte(client.get('/hors-ligne/a-verifier'))
    changer(client, 'dge')                                             # la DGE aussi (Arbitrages)
    assert 'Écart à la réception du lot' in texte(client.get('/hors-ligne/a-verifier'))
    changer(client, 'veto1')
    assert 'Morts à la réception du lot' in texte(client.get('/sante/alertes'))


def test_ecart_sous_le_seuil_sans_alerte_veterinaire(client, aval):
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    recevoir(client, lot, vivants='98', morts='1', motif_ecart='Poulets échappés')   # 1 % : pas de vétérinaire
    assert Reception.query.one().motif_ecart == 'Poulets échappés'
    assert AlerteSanitaire.query.count() == 0 and ConflitHorsLigne.query.count() == 1
    lot2 = sortie(aval).lot
    recevoir(client, lot2, vivants='100', morts='0')                     # conforme : rien à expliquer
    assert Reception.query.filter_by(lot_id=lot2.id).one().motif_ecart is None and ConflitHorsLigne.query.count() == 1


# ── E. Refus ────────────────────────────────────────────────────────────

def test_chaque_motif_de_refus(client, aval):
    connecter(client, 'abattoir1')
    page = scanner(client, code='CodeQuiNExistePas12345')
    assert 'data-resultat="ROUGE"' in page and "Ce lot n'existe pas." in page and 'Scanner un autre lot' in page
    assert 'Appeler l' not in page                                       # pas de lot : pas d'agent à appeler
    lot = sortie(aval).lot
    tracabilite.annuler(lot, 'erreur de saisie')
    db.session.commit()
    page = scanner(client, lot)
    assert 'La ferme a annulé ce lot.' in page
    lot = sortie(aval).lot
    recevoir(client, lot)
    page = scanner(client, lot)
    assert 'Il a déjà été reçu le' in page and "📞 Appeler l'agent de la ferme" not in page
    aval['agent'].telephone = '+241 77 00 00 01'
    db.session.commit()
    assert 'tel:+24177000001' in scanner(client, lot)
    lot = sortie(aval, aval['marche']).lot
    assert 'Ce lot est pour Marché Mont-Bouët.' in scanner(client, lot)
    lot = sortie(aval).lot
    veto.bloquer(aval['b'], 'Suspicion de Newcastle', aval['veto'])
    db.session.commit()
    page = scanner(client, lot)
    assert 'Le vétérinaire a bloqué la vente de ces poulets.' in page
    r = recevoir(client, lot)                                             # un lot refusé ne se reçoit pas
    assert r.status_code == 400 and Reception.query.filter_by(lot_id=lot.id).count() == 0


def test_alerte_dge_apres_3_refus_du_meme_qr(client, aval):
    lot = sortie(aval, aval['marche']).lot
    connecter(client, 'abattoir1')
    scanner(client, lot)
    scanner(client, lot)
    assert not ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('%refus de scan%')).count()
    scanner(client, numero=lot.numero)                                    # même QR, tapé à la main
    alerte = ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('%refus de scan%')).one()
    assert '3 refus de scan' in alerte.quoi and alerte.ferme_id == aval['f'].id
    scanner(client, lot)                                                  # une seule alerte
    assert ConflitHorsLigne.query.filter(ConflitHorsLigne.quoi.like('%refus de scan%')).count() == 1
    changer(client, 'dge')
    assert '3 refus de scan' in texte(client.get('/hors-ligne/a-verifier'))


# ── F. Sous réserve : décision du vétérinaire seulement ─────────────────

def test_sous_reserve_puis_decision_du_veterinaire_seulement(client, aval, admin):
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=9)
    db.session.commit()
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    recevoir(client, lot, choix='valider')                                # orange : jamais « validée »
    r = Reception.query.one()
    assert r.etat == E.SOUS_RESERVE
    accueil = texte(client.get('/'))
    assert '1 lot attend le vétérinaire' in accueil                     # lot 19 ter : ligne d'état
    assert 'déjà été reçu' in scanner(client, lot)
    # Personne d'autre que le vétérinaire ne décide
    for ident in ('abattoir1', 'dge', 'admin', 'agent1'):
        changer(client, ident)
        res = client.post(f'/operateur/receptions/{r.id}/decider', data={'choix': 'liberer', 'motif': 'ok'})
        assert res.status_code == 403, ident
    autre = creer_utilisateur('veto2', Profil.VETO, ['HOG'])
    changer(client, 'veto2')
    assert client.post(f'/operateur/receptions/{r.id}/decider', data={'choix': 'liberer', 'motif': 'ok'}).status_code == 403
    db.session.refresh(r)
    assert r.etat == E.SOUS_RESERVE and autre
    changer(client, 'veto1')
    page = texte(client.get('/sante/alertes'))
    assert 'Lots retenus à la réception (1)' in page and lot.numero in page and 'Pesée récente' in page
    assert re.search(r'data-fonction="signalements"[^>]*><span class="pa">1</span>', texte(client.get('/')))
    client.post(f'/operateur/receptions/{r.id}/decider', data={'choix': 'liberer', 'motif': ''})
    db.session.refresh(r)
    assert r.etat == E.SOUS_RESERVE                                       # motif obligatoire
    assert texte(client.get(f'/q/{lot.code}')).count('data-etape-reception') == 0
    client.post(f'/operateur/receptions/{r.id}/decider', data={'choix': 'liberer', 'motif': 'Pesée faite au quai, conforme'})
    db.session.refresh(r)
    assert r.etat == E.VALIDEE and r.decision_motif == 'Pesée faite au quai, conforme'
    assert JournalAudit.query.filter_by(action='DECISION_RECEPT').one().detail.endswith('Pesée faite au quai, conforme')
    changer(client, 'abattoir1')
    assert 'Le vétérinaire a donné son accord (1 lot)' in texte(client.get('/'))
    client.get(f'/operateur/receptions/{r.id}')                           # vu : quitte la ligne d'état
    assert 'donné son accord' not in texte(client.get('/'))


def test_refus_par_le_veterinaire_et_refus_au_quai(client, aval):
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=9)
    db.session.commit()
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    recevoir(client, lot, choix='reserve')
    r = Reception.query.one()
    changer(client, 'veto1')
    client.post(f'/operateur/receptions/{r.id}/decider', data={'choix': 'refuser', 'motif': 'Poulets trop maigres'})
    db.session.refresh(r)
    assert r.etat == E.REFUSEE
    changer(client, 'abattoir1')
    assert 'Le vétérinaire a refusé ces poulets.' in scanner(client, lot)  # lot clos
    lot2 = sortie(aval).lot
    recevoir(client, lot2, choix='refuser', vivants='', morts='', poids='')
    r2 = Reception.query.filter_by(lot_id=lot2.id).one()
    assert r2.etat == E.REFUSEE and r2.motif_refus.startswith('Refusé au quai : Pesée récente')
    assert 'data-resultat="ORANGE"' in scanner(client, lot2)              # refus au quai : le lot reste à recevoir


# ── G. Sans réseau ──────────────────────────────────────────────────────

def test_reception_sans_reseau_controlee_a_l_arrivee(client, aval):
    lot_ok = sortie(aval).lot
    lot_autre = sortie(aval, aval['marche']).lot
    connecter(client, 'abattoir1')
    _, rep = rejouer(client, '/operateur/recevoir', {'code': lot_ok.code, 'vivants': '100', 'morts': '0', 'poids': '200'})
    assert rep['etat'] == 'ok'
    r = Reception.query.filter_by(lot_id=lot_ok.id).one()
    assert r.etat == E.VALIDEE and r.hors_ligne
    scan = Scan.query.filter_by(lot_id=lot_ok.id).one()
    assert scan.source == 'HORS_LIGNE' and scan.resultat == 'VERT'
    # Destiné à un autre opérateur : la réception passe d'elle-même « refusée », l'opérateur est prévenu
    _, rep = rejouer(client, '/operateur/recevoir', {'code': lot_autre.code, 'vivants': '50', 'morts': '0', 'poids': '90'})
    r2 = Reception.query.filter_by(lot_id=lot_autre.id).one()
    assert r2.etat == E.REFUSEE and 'destiné à Marché Mont-Bouët' in r2.motif_refus
    accueil = texte(client.get('/'))
    assert '1 réception à revoir' in accueil                             # lot 19 ter : ligne d'état
    assert 'Ne pouvait pas être reçu' in texte(client.get('/operateur/receptions'))
    # Contrôle bloquant manquant à l'arrivée : sous réserve d'elle-même ; écart sans raison : à expliquer
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=9)
    db.session.commit()
    lot3 = sortie(aval).lot
    _, rep = rejouer(client, '/operateur/recevoir', {'numero': lot3.numero, 'vivants': '90', 'morts': '5', 'poids': '180'})
    r3 = Reception.query.filter_by(lot_id=lot3.id).one()
    assert r3.etat == E.SOUS_RESERVE and r3.motif_ecart is None and receptions.explication_manquante(r3)
    page = texte(client.get(f'/operateur/receptions/{r3.id}'))
    assert 'data-expliquer' in page
    client.post(f'/operateur/receptions/{r3.id}/expliquer', data={'motif_ecart': 'Morts au transport'})
    db.session.refresh(r3)
    assert r3.motif_ecart == 'Morts au transport' and not receptions.explication_manquante(r3)
    assert AlerteSanitaire.query.filter_by(origine='RECEPTION').count() == 1   # 5 % > 2 % : vétérinaire prévenu
    # Les pages de l'opérateur sont gardées par le téléphone
    pages = client.get('/hors-ligne/pages').get_json()['pages']
    assert {'/', '/operateur/scanner', '/operateur/attendus', '/operateur/receptions'} <= set(pages)
    scanner_page = texte(client.get('/operateur/scanner'))
    assert "data-hors-ligne=\"Réception d'un lot\"" in scanner_page


# ── H. Indicateurs de traçabilité ───────────────────────────────────────

def test_indicateurs_de_tracabilite(client, aval):
    s1 = sortie(aval)                                                     # abattoir : reçu, écart 2 sur 100
    s2 = sortie(aval, aval['marche'], nombre=50)                          # marché : pas encore reçu
    regles.sortir(aval['b'], AUJ, 'Vente', None, 'Voisin', 10, 20, aval['el'])   # vente sans opérateur : QR, pas scannable
    regles.sortir(aval['b'], AUJ, 'Autre', None, '', 5, 10, aval['el'])   # « Autre » : hors indicateurs
    db.session.commit()
    connecter(client, 'abattoir1')
    recevoir(client, s1.lot, vivants='97', morts='1', motif_ecart='Poulets échappés')
    scanner(client, s2.lot)                                               # refus de scan
    from app.models.bande import Sortie
    t = indicateurs.tracabilite(Sortie.query.all(), Reception.query.all(), 1, 2.0)
    assert (t['lots_sortis'], t['lots_qr'], t['lots_qr_pct']) == (3, 3, 100)
    assert (t['ventes'], t['ventes_lot'], t['ventes_lot_pct']) == (2, 2, 100)
    assert (t['destines'], t['recus'], round(t['recus_pct'], 1)) == (2, 1, 50.0)
    assert t['ecart_moyen_pct'] == 2.0 and t['ecarts_hors_seuil'] == 1 and t['refus'] == 1
    changer(client, 'dge')
    page = texte(client.get('/pilotage/tableau-de-bord'))
    assert 'Traçabilité aval' in page and 'Lots reçus et scannés' in page and '1 sur 2 lots destinés' in page
    assert 'Journal des scans' in page
    from app.services import pilotage
    from app.models import Utilisateur
    d = pilotage.tableau(Utilisateur.query.filter_by(identifiant='dge').one(), {})
    assert d['tracabilite']['refus'] == 1 and d['par_province'][0]['tracabilite']['recus'] == 1


def test_indicateurs_dans_le_rapport_mensuel(aval, monkeypatch):
    from app.services import rapports_pdf
    vu = {}
    original = rapports_pdf._table

    def espion(lignes, largeurs=None):
        vu.setdefault('lignes', []).extend(lignes)
        return original(lignes, largeurs)
    monkeypatch.setattr(rapports_pdf, '_table', espion)
    from app.routes.pilotage import contenu_mensuel
    from app.models import Utilisateur
    sortie(aval)
    contenu_mensuel(AUJ.strftime('%Y-%m'), Utilisateur.query.filter_by(identifiant='dge').one())
    assert ['Lots sortis avec QR', 'Ventes rattachées à un lot', 'Lots reçus et scannés',
            'Écart moyen à la réception'] in vu['lignes']


# ── I. Journal des scans ────────────────────────────────────────────────

def test_journal_des_scans(client, aval, admin):
    lot = sortie(aval).lot
    connecter(client, 'abattoir1')
    scanner(client, lot)
    scanner(client, code='Inconnu1234567890')
    assert Scan.query.count() == 2
    lignes = JournalAudit.query.filter_by(action='SCAN').order_by(JournalAudit.id).all()
    assert len(lignes) == 2 and 'Accepté' in lignes[0].detail and 'Refusé' in lignes[1].detail
    assert 'QR inconnu' in lignes[1].detail and lignes[0].identifiant == 'abattoir1'
    assert all(lot.code not in (l.detail or '') for l in JournalAudit.query)   # jamais le code en clair
    for ident in ('dge', 'admin'):
        changer(client, ident)
        page = texte(client.get('/journal/scans'))
        assert lot.numero in page and 'QR inconnu' in page
    page = texte(client.get('/journal/scans', query_string={'resultat': 'ROUGE'}))
    assert lot.numero not in page and 'QR inconnu' in page
    page = texte(client.get('/journal/scans', query_string={'operateur': str(aval['marche'].id)}))
    assert 'Aucun scan' in page
    creer_utilisateur('audit1', Profil.AUDITEUR)
    changer(client, 'audit1')
    r = client.get('/journal/scans.csv')
    assert r.status_code == 200 and 'Abattoir de Ntoum' in texte(r)
    assert 'journal des scans' in JournalAudit.query.filter_by(action='EXPORT').one().detail
    changer(client, 'veto1')
    assert client.get('/journal/scans').status_code == 403


# ── J, K. Éleveur et page publique ──────────────────────────────────────

def test_affichage_eleveur_et_page_publique(client, aval):
    s = sortie(aval)
    connecter(client, 'eleveur1')
    page = texte(client.get(f'/bandes/{aval["b"].numero}/sortie'))
    assert 'Sorties de cette bande' in page and '✓ Partis' in page and 'Reçus par' not in page
    changer(client, 'abattoir1')
    recevoir(client, s.lot, vivants='98', morts='2', motif_ecart='Morts au transport')
    assert 'Reçus à l&#39;abattoir' in texte(client.get(f'/q/{s.lot.code}')) or \
        "Reçus à l'abattoir" in texte(client.get(f'/q/{s.lot.code}'))
    changer(client, 'eleveur1')
    page = texte(client.get(f'/bandes/{aval["b"].numero}/sortie'))
    assert "Reçus par l'abattoir" in page
    assert "a compté 98 vivants et 2 morts au transport" in page
    for interdit in ('sous réserve', 'événement vérifiable', 'Sous réserve'):
        assert interdit not in page
    # Sous réserve : « En attente du vétérinaire », jamais le mot « réserve »
    for p in aval['b'].pesees:
        p.date = AUJ - timedelta(days=9)
    db.session.commit()
    s2 = sortie(aval)
    changer(client, 'abattoir1')
    recevoir(client, s2.lot, choix='reserve')
    changer(client, 'eleveur1')
    page = texte(client.get(f'/bandes/{aval["b"].numero}/sortie'))
    assert '◷ En attente du vétérinaire' in page and 'réserve' not in page
    public = texte(client.get(f'/q/{s2.lot.code}'))
    assert 'data-etape-reception' not in public                            # reçu mais pas validé
    public = texte(client.get(f'/q/{s.lot.code}'))
    assert 'Abattoir de Ntoum' in public and 'contrôle validé' in public
    for interdit in ('Exploitant', 'eleveur1', 'abattoir1'):
        assert interdit not in public


def test_type_marche_dans_la_liste(aval):
    from app.models.liste_deroulante import ld_choices
    assert 'Marché' in [v for v, _ in ld_choices('types_operateurs')]
    assert receptions.motifs_ecart() == ['Erreur de comptage', 'Morts au transport', 'Poulets échappés', 'Autre']
