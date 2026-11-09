"""Lot 12 — règle des conflits : même personne, les saisies s'additionnent ; deux personnes, deux versions
gardées (celle de l'éleveur compte), « à vérifier », décision avec motif et recalcul ; doublon possible de
sortie (mis de côté, rouge après 48 h, DGE) ; écart de confirmation de livraison visible de la DGE."""
from datetime import timedelta

from app import db, indicateurs
from app.models import JournalAudit, Livraison, Profil, Operateur
from app.models.bande import SaisieJour, Sortie
from app.models.hors_ligne import ConflitHorsLigne, StatutVerification as SV, GenreVerification as G
from app.models.intrant import StatutLivraison as S
from app.models.base import maintenant
from app.services import intrants, argent
from app.services.journal import Action
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def saisir(client, b, morts, sacs='0', **extra):
    return client.post(f'/bandes/{b.numero}/saisie', data={'morts': str(morts), 'sacs': sacs, **extra})


def rejouer_saisie(client, b, morts, sacs='0', **kw):
    return rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': str(morts), 'sacs': sacs, 'jour': AUJ.isoformat()}, **kw)


# ── Saisie du jour : deux personnes, deux versions ─────────────────────

def test_agent_puis_eleveur_hors_ligne_deux_versions_celle_de_l_eleveur_compte(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    saisir(client, b, 6)                                        # l'agent, en ligne, en visite
    changer(client, 'eleveur1')
    _, rep = rejouer_saisie(client, b, 4, il_y_a=timedelta(hours=3))   # l'éleveur, sans réseau, plus tôt
    assert rep['etat'] == 'conflit'
    s = SaisieJour.query.one()
    assert s.morts == 4 and s.a_verifier                        # la version de l'éleveur compte
    c = ConflitHorsLigne.query.one()
    assert c.genre == G.SAISIE_JOUR and c.statut == SV.A_VERIFIER
    assert [(v['profil'], v['valeurs']['morts']) for v in c.versions] == [('ELEVEUR', 4), ('AGENT', 6)]
    assert indicateurs.calculer(b)['morts_cumules'] == 4
    # L'éleveur voit « ◷ À vérifier par votre agent », jamais un message d'erreur
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert '◷ À vérifier par votre agent' in page and 'erreur' not in page.lower()


def test_eleveur_puis_agent_en_ligne_mes_chiffres_sont_differents(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    saisir(client, b, 2)
    changer(client, 'agent1')
    page = saisir(client, b, 5).get_data(as_text=True)          # « Déjà envoyé » : deux choix
    assert 'Une saisie existe déjà' in page and 'Mes chiffres sont différents' in page and 'Ajouter' in page
    saisir(client, b, 5, differente='1')
    s = SaisieJour.query.one()
    assert s.morts == 2 and s.a_verifier                        # la version de l'éleveur compte toujours
    assert len(ConflitHorsLigne.query.one().versions) == 2
    # « Ajouter » reste possible (des morts de plus dans la journée) : il s'additionne
    saisir(client, b, 1, ajouter='1')
    assert SaisieJour.query.one().morts == 3


def test_meme_personne_additionne_toujours(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    saisir(client, b, 2)
    rejouer_saisie(client, b, 1)
    s = SaisieJour.query.one()
    assert s.morts == 3 and not s.a_verifier and ConflitHorsLigne.query.count() == 0


def test_decision_avec_motif_journal_et_recalcul(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    saisir(client, b, 6)
    changer(client, 'eleveur1')
    rejouer_saisie(client, b, 4)
    c = ConflitHorsLigne.query.one()
    changer(client, 'agent1')
    accueil = client.get('/').get_data(as_text=True)
    assert '1 saisie à vérifier' in accueil
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert 'Retenir cette version' in page and '4 morts' in page and '6 morts' in page
    # Motif obligatoire
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': '1', 'motif': ''})
    db.session.refresh(c)
    assert c.statut == SV.A_VERIFIER
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': '1', 'motif': 'compté avec l\'éleveur'})
    db.session.refresh(c)
    s = SaisieJour.query.one()
    assert c.statut == SV.TRANCHE and c.retenue == '1' and s.morts == 6 and not s.a_verifier
    assert indicateurs.calculer(b)['morts_cumules'] == 6         # recalcul
    j = JournalAudit.query.filter_by(action=Action.VERIFICATION).one()
    assert 'version de' in j.detail and "compté avec l'éleveur" in j.detail
    assert 'saisie à vérifier' not in client.get('/').get_data(as_text=True)
    # L'éleveur ne tranche jamais
    changer(client, 'eleveur1')
    assert client.get('/hors-ligne/a-verifier').status_code == 403


# ── Doublon possible de sortie ─────────────────────────────────────────

def _sortir(client, b, nombre=50, acheteur='Marché de Ntoum'):
    return client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Vente', 'destinataire_libre': acheteur,
                                                           'nombre': str(nombre), 'poids_total': '100'})


def test_deux_sorties_differentes_ne_sont_pas_un_doublon(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    _sortir(client, b, 50)
    changer(client, 'agent1')
    _sortir(client, b, 30)                                       # autre nombre : deux ventes
    _sortir(client, b, 50, acheteur='Restaurant')                # autre acheteur : deux ventes
    assert ConflitHorsLigne.query.count() == 0 and not any(s.mise_de_cote for s in Sortie.query)
    assert indicateurs.calculer(b)['sorties'] == 130


def test_doublon_possible_mis_de_cote_et_decision(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    _sortir(client, b, 50)
    changer(client, 'agent1')
    _sortir(client, b, 50)                                       # même nombre, même acheteur, autre personne
    el, ag = sorted(Sortie.query.all(), key=lambda s: s.cree_par != monde['el'].id)
    assert not el.mise_de_cote and ag.mise_de_cote and el.a_verifier and ag.a_verifier
    assert ag.lot is None and el.lot is not None                 # pas de lot QR pour la sortie mise de côté
    assert indicateurs.calculer(b)['sorties'] == 50              # seule celle de l'éleveur compte
    c = ConflitHorsLigne.query.one()
    assert c.genre == G.SORTIE
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert 'doublon possible' in page and 'Ce sont deux sorties différentes' in page
    # L'éleveur voit « ◷ À vérifier par votre agent » sur la sortie
    changer(client, 'eleveur1')
    assert '◷ À vérifier par votre agent' in client.get('/saisie-du-jour').get_data(as_text=True)
    # Décision : deux sorties différentes → les deux comptent, le lot est créé
    changer(client, 'agent1')
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': 'deux', 'motif': 'deux camions'})
    db.session.expire_all()
    ag = db.session.get(Sortie, ag.id)
    assert not ag.mise_de_cote and not ag.a_verifier and ag.lot is not None
    assert indicateurs.calculer(b)['sorties'] == 100


def test_doublon_garder_celle_de_l_agent(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    _sortir(client, b, 40)
    changer(client, 'eleveur1')
    _sortir(client, b, 40)                                       # l'éleveur en second : la sienne compte
    ag, el = sorted(Sortie.query.all(), key=lambda s: s.cree_par != monde['agent'].id)
    assert ag.mise_de_cote and ag.lot.annule and not el.mise_de_cote
    c = ConflitHorsLigne.query.one()
    changer(client, 'agent1')
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': 'autre', 'motif': 'pesée de l\'agent'})
    db.session.expire_all()
    ag, el = db.session.get(Sortie, ag.id), db.session.get(Sortie, el.id)
    assert not ag.mise_de_cote and not ag.lot.annule and el.mise_de_cote and el.lot.annule
    assert indicateurs.calculer(b)['sorties'] == 40
    assert sum(m['montant'] or 0 for m in argent.mouvements([monde['f'].id])) == 0


def test_doublon_non_tranche_sous_48h_rouge_et_dge(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    _sortir(client, b, 50)
    changer(client, 'agent1')
    _sortir(client, b, 50)
    c = ConflitHorsLigne.query.one()
    creer_utilisateur('dge1', Profil.DGE, [])
    db.session.commit()
    accueil = client.get('/').get_data(as_text=True)
    assert '1 saisie à vérifier' in accueil and 'depuis plus de 48 h' not in accueil
    changer(client, 'dge1')
    assert 'doublon' not in client.get('/').get_data(as_text=True)          # pas encore 48 h
    c.cree_le = maintenant() - timedelta(hours=49)
    db.session.commit()
    accueil = client.get('/').get_data(as_text=True)
    assert '1 doublon de sortie non tranché depuis plus de 48 h' in accueil
    assert 'verif-rouge' in client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    changer(client, 'agent1')
    accueil = client.get('/').get_data(as_text=True)
    assert 'dont 1 doublon de sortie depuis plus de 48 h' in accueil
    # En rouge : niveau « urgence » dans l'encadré Alertes
    from app.routes.accueil import _alertes
    with client.application.test_request_context():
        from flask_login import login_user
        login_user(monde['agent'])
        ligne = next(a for a in _alertes(monde['agent']) if 'à vérifier' in a['texte'])
    assert ligne['niveau'] == 'urgence'


# ── Confirmation de livraison : deux versions, visibles de la DGE ──────

def test_ecart_de_livraison_deux_versions_visible_de_la_dge(client, monde):
    liv = intrants.nouvelle_livraison(monde['f'], AUJ - timedelta(days=1), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': True,
                                     'part_subventionnee': 100, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'agent1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')           # l'agent confirme « tout reçu »
    changer(client, 'eleveur1')
    ligne = liv.lignes[0]
    _, rep = rejouer(client, f'/livraisons/{liv.numero}/recu-moins',
                     {f'recue-{ligne.id}': '30', f'motif-{ligne.id}': 'Sacs abîmés'}, il_y_a=timedelta(hours=3))
    assert rep['etat'] == 'conflit'
    db.session.expire_all()
    liv = db.session.get(Livraison, liv.id)
    assert liv.statut == S.RECUE_ECART and liv.lignes[0].quantite_recue == 30   # la version de l'éleveur compte
    c = ConflitHorsLigne.query.one()
    assert c.genre == G.LIVRAISON and [v['profil'] for v in c.versions] == ['ELEVEUR', 'AGENT']
    creer_utilisateur('dge1', Profil.DGE, [])
    db.session.commit()
    changer(client, 'dge1')
    accueil = client.get('/').get_data(as_text=True)
    assert "1 écart de confirmation de livraison de l'État à vérifier" in accueil.replace('&#39;', "'")
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert liv.numero in page and 'Retenir cette version' in page
    # La DGE peut trancher : la version de l'agent (40 reçus) est retenue
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': '1', 'motif': 'bon de livraison signé'})
    db.session.expire_all()
    liv = db.session.get(Livraison, liv.id)
    assert liv.statut == S.RECUE and liv.lignes[0].quantite_recue == 40


def test_meme_personne_confirmation_sans_conflit(client, monde):
    liv = intrants.nouvelle_livraison(monde['f'], AUJ - timedelta(days=1), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': False,
                                     'part_subventionnee': None, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'eleveur1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    _, rep = rejouer(client, f'/livraisons/{liv.numero}/tout-recu', {})
    assert rep['etat'] == 'ok' and ConflitHorsLigne.query.count() == 0
