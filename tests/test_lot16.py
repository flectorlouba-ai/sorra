"""Lot 16 — écrans de l'agent : Mes fermes par urgence, tournée du jour (gardée sans réseau), fiche
regroupée, nouvel éleveur (mot de passe provisoire montré une fois), inventaire et écart de stock
(seuil sous quatre yeux), commandes d'intrants, biosécurité (score, mesures lues par l'éleveur)."""
import re
from datetime import date, timedelta

from app import db
from app.models import Profil, Utilisateur, Parametre
from app.models.agent import CommandeIntrant, InventaireStock
from app.models.visite import Visite
from app.services import agent as regles, approbations
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, recevoir, bande_ouverte  # noqa: F401


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def _bio(client, numero, reponses, mesures=None):
    data = {f'r{i}': r for i, r in enumerate(reponses)}
    data.update({f'm{i}': m for i, m in (mesures or {}).items()})
    return client.post(f'/fermes/{numero}/biosecurite', data=data, follow_redirects=True)


# ── A, B. Urgence et tournée ────────────────────────────────────────────

def test_mes_fermes_triees_par_urgence(client, monde):
    agent = monde['agent']
    from tests.conftest import creer_ferme
    calme = creer_ferme('Ferme Calme', 'EST', 'Ntoum', agent=agent)
    db.session.add(Visite(ferme_id=monde['f'].id, agent_id=agent.id, objet='Suivi', statut='PREVUE',
                          date_prevue=date.today() - timedelta(days=2)))
    db.session.commit()
    u = regles.urgences([monde['f'], calme])
    assert u[monde['f'].id]['couleur'] == 'orange' and 'pas faite' in u[monde['f'].id]['raisons'][0][1]
    assert u[calme.id] == {'score': 0, 'couleur': 'vert', 'raisons': []}
    connecter(client, 'agent1')
    page = client.get('/fermes/').get_data(as_text=True)
    ordre = re.findall(r'data-ferme-urgence="([^"]+)"', page)
    assert ordre[0] == monde['f'].numero and calme.numero in ordre
    assert 'Visite prévue le' in page and 'data-urgence="orange"' in page
    # La DGE garde la liste habituelle, sans colonne d'urgence
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    changer(client, 'dge')
    assert 'data-ferme-urgence' not in client.get('/fermes/').get_data(as_text=True)


def test_tournee_du_jour_et_pages_gardees(client, monde):
    agent = monde['agent']
    db.session.add(Visite(ferme_id=monde['f'].id, agent_id=agent.id, objet='Vaccination', statut='PREVUE',
                          date_prevue=date.today()))
    db.session.commit()
    connecter(client, 'agent1')
    page = client.get('/tournee').get_data(as_text=True)
    assert f'data-ferme-tournee="{monde["f"].numero}"' in page and 'Visite : vaccination' in page
    assert 'data-garder' in page and f'/fermes/{monde["f"].numero}' in page      # fiches gardées sans réseau
    assert monde['f2'].numero not in page                                       # pas sa ferme
    client.get('/terrain/bureau')                   # lot 19 ter : tuiles de pilotage dans la « Version bureau »
    accueil = client.get('/').get_data(as_text=True)
    assert 'data-tuile-pilotage="tournee"' in accueil and 'data-tuile-pilotage="commandes"' in accueil
    client.get('/terrain/version-terrain')
    changer(client, 'eleveur1')
    assert client.get('/tournee').status_code == 403


# ── C. Fiche ferme ──────────────────────────────────────────────────────

def test_fiche_ferme_regroupee_sans_doublon(client, monde):
    connecter(client, 'agent1')
    page = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    for ident in ('id="biosecurite"', 'id="commandes"', 'id="eleveurs"', 'id="stock"', 'id="visites"'):
        assert page.count(ident) == 1, ident
    assert 'Eleveur1' in page and 'Nouvel éleveur' in page
    # L'agent d'une autre ferme : pas de fiche
    assert client.get(f'/fermes/{monde["f2"].numero}').status_code == 403


# ── D. Nouvel éleveur ───────────────────────────────────────────────────

def test_nouvel_eleveur_mot_de_passe_provisoire_une_fois(client, monde):
    connecter(client, 'agent1')
    url = f'/fermes/{monde["f"].numero}/eleveurs/nouveau'
    assert 'Indiquez le téléphone' in client.post(url, data={'nom': 'Ondo'}).get_data(as_text=True)
    page = client.post(url, data={'nom': 'Ondo', 'prenom': 'Jérôme', 'telephone': '077 11 22 33'}).get_data(as_text=True)
    provisoire = re.search(r'data-provisoire>([a-z0-9]{10})<', page).group(1)
    assert 'plus jamais affiché' in page
    u = Utilisateur.query.filter_by(identifiant='jerome.ondo').one()
    assert u.profil == Profil.ELEVEUR and u.doit_changer_mdp and u.check_password(provisoire)
    assert [uf.ferme_id for uf in u.fermes] == [monde['f'].id]
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert provisoire not in fiche and 'mot de passe provisoire' in fiche   # jamais réaffiché
    from app.models import JournalAudit
    ligne = JournalAudit.query.filter_by(table_nom='utilisateur', action='CREATION').order_by(JournalAudit.id.desc()).first()
    assert ligne and provisoire not in str(ligne.__dict__)
    # Première connexion : changer le mot de passe
    changer(client, 'jerome.ondo')
    client.post('/auth/connexion', data={'identifiant': 'jerome.ondo', 'mot_de_passe': provisoire})
    r = client.get('/')
    assert r.status_code == 302 and 'mot-de-passe' in r.location
    # Un autre agent ne peut pas créer d'éleveur sur cette ferme
    changer(client, 'agent2')
    assert client.post(url, data={'nom': 'X', 'telephone': '1'}).status_code == 403


# ── E. Inventaire et écart ──────────────────────────────────────────────

def test_ecart_de_stock_et_seuil_quatre_yeux(client, monde):
    recevoir(monde['f'], [(monde['aliment'], 40, 0)])
    connecter(client, 'agent1')
    url = f'/fermes/{monde["f"].numero}/stock/compter'
    page = client.post(url, data={'produit_id': monde['aliment'].id, 'compte': '39'}, follow_redirects=True)
    assert 'Stock compté ✓' in page.get_data(as_text=True)
    inv = InventaireStock.query.one()
    assert (inv.livre, inv.utilise, inv.compte, inv.ecart, inv.ecart_pct) == (40, 0, 39, 1, 2.5)
    page = client.post(url, data={'produit_id': monde['aliment'].id, 'compte': '30'}, follow_redirects=True)
    assert 'au-delà du seuil de 10 %' in page.get_data(as_text=True)
    u = regles.urgences([monde['f']])[monde['f'].id]
    assert any('Écart de stock' in t for _, t in u['raisons'])          # le dernier comptage seulement
    assert 'data-inventaire' in client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    # Le seuil est sensible : quatre yeux
    assert approbations.sensible('intrants.seuil_ecart_stock_pct')
    admin = creer_utilisateur('admin', Profil.ADMIN)
    p = Parametre.query.filter_by(cle='intrants.seuil_ecart_stock_pct').one()
    prop = approbations.proposer('PARAMETRE', p.cle, p.description, p.valeur, '30', {'valeur': '30'}, 'essai', admin)
    db.session.commit()
    assert regles.seuil_ecart() == 10
    approbations.decider(prop, creer_utilisateur('dge', Profil.DGE), True)
    db.session.commit()
    assert regles.seuil_ecart() == 30 and not regles.urgences([monde['f']])[monde['f'].id]['raisons']
    assert client.post(url, data={'produit_id': monde['aliment'].id, 'compte': '-1'},
                       follow_redirects=True).get_data(as_text=True).count('0 ou plus') == 1


# ── F. Commandes ────────────────────────────────────────────────────────

def test_commande_envoyee_validee_refusee_livree(client, monde):
    connecter(client, 'agent1')
    client.post('/commandes/nouvelle', data={'ferme': monde['f'].numero, 'produit_id': monde['aliment'].id,
                                             'quantite': '20', 'motif': 'Bande B2'})
    client.post('/commandes/nouvelle', data={'ferme': monde['f'].numero, 'produit_id': monde['croissance'].id,
                                             'quantite': '10'})
    assert client.post('/commandes/nouvelle', data={'ferme': monde['f2'].numero, 'produit_id': monde['aliment'].id,
                                                    'quantite': '5'}).status_code == 404     # pas sa ferme
    c1, c2 = CommandeIntrant.query.order_by(CommandeIntrant.id).all()
    assert c1.statut == c2.statut == 'ENVOYEE'
    assert client.post(f'/commandes/{c1.id}/decider', data={'decision': 'valider'}).status_code == 403
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    changer(client, 'dge')
    assert re.search(r'data-tuile-pilotage="commandes">\s*<span class="tuile-compteur"[^>]*>2<', client.get('/').get_data(as_text=True))
    client.post(f'/commandes/{c1.id}/decider', data={'decision': 'valider'})
    assert 'motif du refus' in client.post(f'/commandes/{c2.id}/decider', data={'decision': 'refuser'},
                                           follow_redirects=True).get_data(as_text=True)
    client.post(f'/commandes/{c2.id}/decider', data={'decision': 'refuser', 'motif': 'Stock national épuisé'})
    assert (c1.statut, c2.statut, c2.motif_refus) == ('VALIDEE', 'REFUSEE', 'Stock national épuisé')
    # L'agent voit le refus (ferme en orange) jusqu'à ce qu'il l'ait lu
    assert any('Commande refusée' in t for _, t in regles.urgences([monde['f']])[monde['f'].id]['raisons'])
    changer(client, 'agent1')
    assert 'Stock national épuisé' in client.get('/commandes').get_data(as_text=True)
    assert not any('Commande refusée' in t for _, t in regles.urgences([monde['f']])[monde['f'].id]['raisons'])
    # Livrée : quand la livraison liée est créée (lot 18 B)
    liv = recevoir(monde['f'], [(monde['aliment'], 20, 0)])
    regles.marquer_livree(c1, liv)
    db.session.commit()
    assert c1.statut == 'LIVREE' and c1.livraison_id == liv.id
    try:
        regles.marquer_livree(c2, liv)
        assert False
    except regles.RegleAgent:
        pass


# ── G. Biosécurité ──────────────────────────────────────────────────────

def test_biosecurite_score_mesures_et_eleveur(client, monde):
    points = regles.grille()
    assert len(points) == 10
    assert regles.score({'a': 'oui', 'b': 'non', 'c': 'so'}) == 50 and regles.score({'a': 'so'}) is None
    connecter(client, 'agent1')
    numero = monde['f'].numero
    assert 'Répondez à chaque point' in _bio(client, numero, ['oui'] * 9).get_data(as_text=True)
    reponses = ['oui'] * 3 + ['non'] * 5 + ['so'] * 2
    assert 'mesure corrective pour chaque' in _bio(client, numero, reponses).get_data(as_text=True)
    mesures = {i: f'Corriger le point {i}' for i in range(3, 8)}
    page = _bio(client, numero, reponses, mesures).get_data(as_text=True)
    assert 'Biosécurité enregistrée ✓ : 38 %' in page and 'data-score-bio' in page
    v = Visite.query.filter_by(objet='Biosécurité').one()
    assert v.score_biosecurite == 38 and len(v.mesures_correctives) == 5 and v.statut == 'FAITE'
    assert any('Biosécurité 38 %' in t for _, t in regles.urgences([monde['f']])[monde['f'].id]['raisons'])
    # L'éleveur voit le score et les mesures, pas la grille
    changer(client, 'eleveur1')
    page = client.get('/mes-visites').get_data(as_text=True)
    assert 'Biosécurité : 38 %' in page and 'Corriger le point 3' in page and points[0] not in page
    assert client.get(f'/fermes/{numero}/biosecurite').status_code == 403


def test_profils_2fa_modifiable_par_proposition(client, app):
    """Correctif du lot 15 : le réglage texte « securite.profils_2fa » se propose (quatre yeux)."""
    from app.models.securite import Proposition
    admin = creer_utilisateur('admin', Profil.ADMIN)
    db.session.commit()
    connecter(client, 'admin')
    p = Parametre.query.filter_by(cle='securite.profils_2fa').one()
    client.post(f'/administration/parametres/{p.id}/modifier', data={'valeur': 'ADMIN,DGE', 'motif': 'essai'})
    assert Proposition.query.filter_by(cle='securite.profils_2fa', statut='EN_ATTENTE').one().apres == 'ADMIN,DGE'
