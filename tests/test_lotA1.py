"""Lot A1 — règle des formulaires : fiche préremplie (« Enregistrer la modification » · « 🗄️ Archiver » · ✕),
archiver au lieu de supprimer (masqué, exclu des calculs, conservé, restauré par un profil habilité, journal),
droits de modification (ses saisies, bande ouverte ; bande terminée : 🔒 et correction de l'agent avec motif),
corrections entre personnes (deux versions pour la saisie du jour, message « À vérifier » ailleurs), hors ligne."""
from datetime import timedelta

from app import db, indicateurs
from app.models import JournalAudit, Operateur
from app.models.argent import Depense
from app.models.base import AVEC_ARCHIVES
from app.models.bande import SaisieJour, Pesee, Sortie, StatutBande
from app.models.hors_ligne import ConflitHorsLigne, GenreVerification as G
from app.models.tracabilite import LotTrace, Reception
from app.services import bandes as regles, fiches, intrants
from app.services.journal import Action
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def saisie_eleveur(client, b, morts=2):
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': str(morts), 'sacs': '0'})
    return SaisieJour.query.one()


def pesee_eleveur(client, b):
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '4,2'})
    return Pesee.query.one()


def fiche(client, genre, o, **data):
    return client.post(f'/fiches/{genre}/{o.id}', data={'retour': '/ma-bande', **data})


def toutes(modele):
    return modele.query.execution_options(**{AVEC_ARCHIVES: True})


# ── Modifier sa propre saisie ───────────────────────────────────────────

def test_l_eleveur_modifie_sa_pesee_journal_et_compteur(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    r = fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='5,0')
    assert r.status_code == 302 and r.location.endswith('/ma-bande')
    p = Pesee.query.one()
    assert p.poids_total_kg == 5.0 and p.poids_moyen_g == 500
    ligne = JournalAudit.query.filter_by(table_nom='pesee', action=Action.MODIFICATION).filter(
        JournalAudit.detail.isnot(None)).one()
    assert 'modifiée par' in ligne.detail
    assert fiches.nombres_modifications([p]) == {str(p.id): 1}
    # La ligne affiche ✏️ et « modifiée 1 fois »
    page = client.get(f'/bandes/{b.numero}/pesee').get_data(as_text=True)
    assert 'modifiée 1 fois' in page and 'ligne-modifiee' in page


def test_valeurs_invalides_refusees(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='0', poids_total_kg='5')
    assert Pesee.query.one().poids_total_kg == 4.2
    assert 'positif' in client.get('/ma-bande').get_data(as_text=True)


# ── Archiver ────────────────────────────────────────────────────────────

def test_archiver_masque_exclut_conserve_et_journalise(client, monde):
    b = bande_ouverte(monde)
    s = saisie_eleveur(client, b, morts=7)
    assert indicateurs.calculer(b)['morts_cumules'] == 7
    fiche(client, 'saisie', s, action='archiver')
    db.session.expire_all()
    assert SaisieJour.query.count() == 0 and toutes(SaisieJour).count() == 1        # masquée, conservée
    assert indicateurs.calculer(db.session.get(type(b), b.id))['morts_cumules'] == 0   # exclue des calculs
    j = JournalAudit.query.filter_by(table_nom='saisie_jour', action=Action.ARCHIVAGE).one()
    assert j.avant['archive_le'] is None and j.apres['archive_le'] and 'archivée par' in j.detail
    # « Voir les archivées (1) », puis restauration réservée à l'agent de la ferme
    page = client.get(f'/fiches/saisie/archivees?bande={b.numero}').get_data(as_text=True)
    assert 'Saisie du' in page and 'Restaurer' not in page
    s = toutes(SaisieJour).one()
    fiche(client, 'saisie', s, action='restaurer')
    assert SaisieJour.query.count() == 0
    changer(client, 'agent1')
    page = client.get(f'/fiches/saisie/archivees?bande={b.numero}').get_data(as_text=True)
    assert 'Restaurer' in page
    fiche(client, 'saisie', s, action='restaurer', motif='archivée par erreur')
    assert SaisieJour.query.count() == 1
    j = JournalAudit.query.filter_by(table_nom='saisie_jour', action=Action.RESTAURATION).one()
    assert 'archivée par erreur' in j.detail


def test_aucune_suppression_physique(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    fiche(client, 'pesee', p, action='archiver')
    assert JournalAudit.query.filter_by(action=Action.SUPPRESSION).count() == 0
    assert toutes(Pesee).count() == 1


def test_archiver_un_vaccin_rend_le_stock(client, monde):
    from app.models import Produit
    from app.services import sante
    b = bande_ouverte(monde)
    vaccin = Produit(nom='Gumboro', type='Vaccin', unite='doses')
    db.session.add(vaccin)
    recevoir(monde['f'], [(vaccin, 1000, 0)])
    connecter(client, 'eleveur1')
    v = sante.vacciner(b, AUJ, vaccin, 'Eau de boisson', 900, 900, None, monde['el'])
    v.cree_par = monde['el'].id
    db.session.commit()
    stock = lambda: next(s['stock'] for s in intrants.stock_ferme(monde['f']) if s['produit'].id == vaccin.id)
    assert stock() == 100
    fiche(client, 'vaccin', v, action='archiver')
    assert stock() == 1000
    assert toutes(type(v)).one().annule                 # ancien état tenu à jour


# ── Bande terminée : lecture seule, correction de l'agent avec motif ────

def test_bande_terminee_verrou_et_correction_de_l_agent(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    b.statut, b.date_cloture = StatutBande.CLOTUREE, AUJ
    db.session.commit()
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='6')
    assert Pesee.query.one().poids_total_kg == 4.2
    info = fiches.infos([p], monde['el'])[p.id]
    assert info.mode is None and info.message == '🔒 Cette bande est terminée. Pour corriger, appelez votre agent.'
    changer(client, 'agent1')
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='6')     # sans motif
    assert Pesee.query.one().poids_total_kg == 4.2
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='6', motif='erreur de balance')
    assert Pesee.query.one().poids_total_kg == 6.0
    j = JournalAudit.query.filter_by(table_nom='pesee', action=Action.CORRECTION).one()
    assert 'erreur de balance' in j.detail
    m = ConflitHorsLigne.query.filter_by(genre=G.MESSAGE).one()
    assert 'Votre agent a corrigé' in m.detail


# ── Corrections entre personnes ─────────────────────────────────────────

def test_l_agent_modifie_la_saisie_de_l_eleveur_deux_versions(client, monde):
    b = bande_ouverte(monde)
    s = saisie_eleveur(client, b, morts=2)
    changer(client, 'agent1')
    fiche(client, 'saisie', s, action='modifier', morts='5', motif='recompté')
    s = SaisieJour.query.one()
    assert s.morts == 2 and s.a_verifier                    # la version de l'éleveur compte (lot 12)
    c = ConflitHorsLigne.query.filter_by(genre=G.SAISIE_JOUR).one()
    assert [v['valeurs']['morts'] for v in c.versions] == [2, 5]


def test_l_agent_corrige_une_depense_avec_motif_et_message(client, monde):
    connecter(client, 'eleveur1')
    from app.services import argent
    categorie = argent.categories()[0][0]
    client.post('/j-ai-paye', data={'categorie': categorie, 'montant': '5000'})
    d = Depense.query.one()
    changer(client, 'agent1')
    fiche(client, 'depense', d, action='modifier', categorie=d.categorie, montant_fcfa='4000', date=d.date.isoformat())
    assert Depense.query.one().montant_fcfa == 5000                       # motif obligatoire
    fiche(client, 'depense', d, action='modifier', categorie=d.categorie, montant_fcfa='4000',
          date=d.date.isoformat(), motif='reçu relu')
    assert Depense.query.one().montant_fcfa == 4000
    assert 'Votre agent a corrigé' in ConflitHorsLigne.query.filter_by(genre=G.MESSAGE).one().detail


def test_un_autre_eleveur_ou_une_autre_ferme_ne_touche_pas(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    changer(client, 'agent2')                                 # agent d'une autre ferme
    assert fiche(client, 'pesee', p, action='archiver').status_code == 404
    assert Pesee.query.count() == 1


# ── Sortie et lot (point 4 validé) ──────────────────────────────────────

def _sortie_abattoir(monde, b):
    op = Operateur.query.filter_by(type='Abattoir').one()
    s = regles.sortir(b, AUJ, 'Abattoir', op, None, 100, 210, monde['el'])
    db.session.commit()
    return s


def test_archiver_une_sortie_annule_son_lot(client, monde):
    b = bande_ouverte(monde)
    s = _sortie_abattoir(monde, b)
    s.cree_par = monde['el'].id
    db.session.commit()
    connecter(client, 'eleveur1')
    fiche(client, 'sortie', s, action='archiver')
    lot = LotTrace.query.one()
    assert lot.annule and 'Sortie archivée' in lot.motif_annulation
    assert Sortie.query.filter(Sortie.archive_le.is_(None)).count() == 0
    assert indicateurs.calculer(b)['effectif_present'] == b.effectif_initial
    changer(client, 'agent1')
    fiche(client, 'sortie', toutes(Sortie).one(), action='restaurer')
    assert not LotTrace.query.one().annule


def test_archiver_une_sortie_dont_le_lot_est_recu_est_refuse(client, monde):
    from app.models.base import maintenant
    b = bande_ouverte(monde)
    s = _sortie_abattoir(monde, b)
    s.cree_par = monde['el'].id
    lot = LotTrace.query.one()
    db.session.add(Reception(lot_id=lot.id, ferme_id=b.ferme_id, operateur_id=s.operateur_id, recu_le=maintenant(),
                             etat='VALIDEE', vivants=100, morts=0))
    db.session.commit()
    connecter(client, 'eleveur1')
    fiche(client, 'sortie', s, action='archiver')
    assert Sortie.query.filter(Sortie.archive_le.is_(None)).count() == 1
    assert not LotTrace.query.one().annule
    assert 'déjà été reçu' in client.get('/ma-bande').get_data(as_text=True)


# ── Hors ligne : modification et archivage partent dans la file d'attente ──

def test_archivage_rejoue_apres_coup(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    ident, rep = rejouer(client, f'/fiches/pesee/{p.id}', {'action': 'archiver', 'retour': '/ma-bande'})
    assert rep['etat'] == 'ok'
    assert Pesee.query.count() == 0
    _, rep = rejouer(client, f'/fiches/pesee/{p.id}', {'action': 'archiver'}, ident=ident)
    assert rep['etat'] == 'deja'


def test_modification_refusee_apres_coup_signalee(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    b.statut, b.date_cloture = StatutBande.CLOTUREE, AUJ
    db.session.commit()
    _, rep = rejouer(client, f'/fiches/pesee/{p.id}', {'action': 'modifier', 'nombre_pesees': '10',
                                                       'poids_total_kg': '6'})
    assert rep['etat'] == 'refuse' and '🔒' in rep['message']


# ── Achats ──────────────────────────────────────────────────────────────

def test_achat_de_poussins_deja_en_bande_non_archivable(client, monde):
    connecter(client, 'eleveur1')
    achat = intrants.enregistrer_achat(monde['f'], monde['poussins'], 500, 0, 100000, 'Marché',
                                       AUJ - timedelta(days=1), monde['el'])
    achat.cree_par = monde['el'].id
    db.session.commit()
    ligne = achat.lignes[0]
    regles.ouvrir(monde['f'], monde['f'].batiments[1], ligne, 500, AUJ, None, monde['el'])
    db.session.commit()
    fiche(client, 'achat', achat, action='archiver')
    assert db.session.get(type(achat), achat.id).archive_le is None


# ── Écrans de bureau : « Archiver » remplace « Désactiver » (point 6) ──

def test_bureau_archiver_et_restaurer_produit_utilisateur_liste(client_admin, monde):
    from app.models import Produit, Utilisateur
    from app.models.liste_deroulante import ListeDeroulante
    p = monde['croissance']
    client_admin.post(f'/administration/catalogue/{p.id}/modifier', data={'archiver': '1'})
    p = db.session.get(Produit, p.id)
    assert not p.actif and p.archive_le is not None
    assert JournalAudit.query.filter_by(table_nom='produit', action=Action.ARCHIVAGE).count() == 1
    page = client_admin.get('/administration/catalogue/?etat=archives').get_data(as_text=True)
    assert 'Archivés (1)' in page and 'Aliment croissance' in page
    client_admin.post(f'/administration/catalogue/{p.id}/modifier', data={'restaurer': '1'})
    p = db.session.get(Produit, p.id)
    assert p.actif and p.archive_le is None
    assert JournalAudit.query.filter_by(table_nom='produit', action=Action.RESTAURATION).count() == 1
    # Utilisateur : archivé, il ne se connecte plus ; journal ARCHIVAGE
    u = Utilisateur.query.filter_by(identifiant='agent2').one()
    client_admin.post(f'/administration/utilisateurs/{u.id}/modifier', data={'archiver': '1'})
    assert db.session.get(Utilisateur, u.id).actif is False
    assert JournalAudit.query.filter_by(table_nom='utilisateur', action=Action.ARCHIVAGE).count() == 1
    page = client_admin.get('/administration/utilisateurs/?statut=inactifs').get_data(as_text=True)
    assert '🗄️ Archivé' in page and 'Désactivé' not in page
    # Valeur de liste
    v = ListeDeroulante.query.first()
    client_admin.post(f'/administration/listes/modifier/{v.id}', data={'archiver': '1'})
    assert db.session.get(ListeDeroulante, v.id).actif is False
    client_admin.post(f'/administration/listes/modifier/{v.id}', data={'restaurer': '1'})
    assert db.session.get(ListeDeroulante, v.id).actif is True
    # Plus de case « actif » à décocher dans les fenêtres
    assert 'Produit actif' not in client_admin.get('/administration/catalogue/').get_data(as_text=True)
    assert 'Compte actif' not in client_admin.get('/administration/utilisateurs/').get_data(as_text=True)


def test_bureau_batiment_avec_bande_en_cours_non_archivable(client_admin, monde):
    b = bande_ouverte(monde)
    bat = b.batiment
    client_admin.post(f'/fermes/{monde["f"].numero}/batiments/{bat.id}/modifier', data={'archiver': '1'})
    assert db.session.get(type(bat), bat.id).actif is True


def test_ferme_et_bande_vides_archivees_par_l_admin(client_admin, monde):
    from app.models import Ferme, Bande
    f2 = monde['f2']
    r = client_admin.post(f'/fiches/entite/ferme/{f2.numero}', data={'motif': ''})
    assert db.session.get(Ferme, f2.id) is not None                       # motif obligatoire
    client_admin.post(f'/fiches/entite/ferme/{f2.numero}', data={'motif': 'créée en double'})
    assert Ferme.query.filter_by(id=f2.id).first() is None                # masquée
    assert toutes(Ferme).filter_by(id=f2.id).one().archive_le is not None  # conservée
    assert 'Ferme Deux' not in client_admin.get('/fermes/').get_data(as_text=True)
    assert f2.numero in client_admin.get('/fiches/entite/ferme/archivees').get_data(as_text=True)
    client_admin.post(f'/fiches/entite/ferme/{f2.numero}', data={'action': 'restaurer'})
    assert Ferme.query.filter_by(id=f2.id).first() is not None
    # Une ferme qui a des bandes ne s'archive pas ; une bande vide oui, et ses poussins reviennent au stock
    b = bande_ouverte(monde)
    client_admin.post(f'/fiches/entite/ferme/{monde["f"].numero}', data={'motif': 'essai'})
    assert Ferme.query.filter_by(id=monde['f'].id).first() is not None
    attente = regles.poussins_en_attente(monde['f'])
    client_admin.post(f'/fiches/entite/bande/{b.numero}', data={'motif': 'ouverte par erreur'})
    assert Bande.query.filter_by(id=b.id).first() is None
    assert regles.poussins_en_attente(monde['f']) != attente


def test_l_agent_n_archive_pas_une_ferme(client, monde):
    connecter(client, 'agent1')
    assert client.post(f'/fiches/entite/ferme/{monde["f2"].numero}', data={'motif': 'x'}).status_code == 403


# ── Les 5 petits défauts du dossier ─────────────────────────────────────

def test_cinq_petits_defauts(client, monde):
    import re
    css = open('app/static/css/terrain.css', encoding='utf-8').read()
    regle = re.search(r'\n\.pastille-bat\{[^}]*\}', css).group(0)
    assert 'min-height:44px' in regle                                              # 1. pastilles à 44 px
    assert '.theme-terrain .case-choix small{font-size:.8rem;}' in css             # 2. numéro de ferme ≥ 12 px
    assert '.theme-terrain .btn-new{font-size:.85rem;min-height:44px;}' in css     # 3. « Retour à l'accueil »
    assert '.theme-terrain .coche-envoye{margin-left:auto;color:var(--e-prairie-fonce)' in css   # 4. ✓ envoyé lisible
    gabarit = open('app/templates/terrain/agent/a_verifier.html', encoding='utf-8').read()
    assert 'c.quoi|lower' not in gabarit                                           # 5. numéro de bande en majuscules
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '2', 'sacs': '0'})
    changer(client, 'agent1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '5', 'sacs': '0', 'differente': '1'})
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert b.numero in page and b.numero.lower() not in page


def test_saisie_reprise_sans_auteur_reste_a_l_eleveur(client, monde):
    b = bande_ouverte(monde)
    p = pesee_eleveur(client, b)
    p.cree_par = None                                     # données reprises (import, démo)
    db.session.commit()
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='5')
    assert Pesee.query.one().poids_total_kg == 5.0
    changer(client, 'agent1')                             # l'agent corrige : motif obligatoire
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='6')
    assert Pesee.query.one().poids_total_kg == 5.0
    fiche(client, 'pesee', p, action='modifier', nombre_pesees='10', poids_total_kg='6', motif='balance')
    assert Pesee.query.one().poids_total_kg == 6.0
