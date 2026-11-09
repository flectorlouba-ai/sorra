"""Lot 18 — écrans de la DGE : planning des livraisons (Prévue → Livrée → Confirmée), « Créer la livraison »
d'une commande validée, arbitrages par province, classement pondéré (quatre yeux, bandes incomplètes
ignorées et signalées), rapports mensuels gardés (e-mail préparé, coupé), agents (charge, réaffectation)."""
import os
import re
from datetime import date, timedelta

from app import db
from app.models import Profil, Livraison, JournalAudit, Parametre
from app.models.agent import CommandeIntrant
from app.models.dge import RapportMensuel
from app.models.intrant import StatutLivraison as S
from app.services import dge as regles, agent, approbations, intrants
from tests.conftest import creer_utilisateur, connecter, creer_ferme
from tests.test_bandes import monde, bande_ouverte  # noqa: F401


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def _dge(client):
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    connecter(client, 'dge')


# ── A. Planning ─────────────────────────────────────────────────────────

def test_planning_prevue_livree_confirmee(client, monde):
    _dge(client)
    demain = (date.today() + timedelta(days=1)).isoformat()
    client.post('/livraisons-etat/prevoir', data={'ferme': monde['f'].numero, 'date': demain,
                                                  'produit_id': monde['aliment'].id, 'quantite': '50',
                                                  'fournisseur': 'SMAG'})
    liv = Livraison.query.one()
    assert liv.statut == S.PREVUE and liv.lignes[0].quantite_livree == 50
    page = client.get('/livraisons-etat/planning').get_data(as_text=True)
    assert re.search(r'data-colonne="PREVUE".*?data-livraison="' + liv.numero, page, re.S)
    # Prévue : invisible de l'éleveur et de l'agent, pas dans le stock
    changer(client, 'eleveur1')
    assert liv.numero not in client.get('/livraisons/mes-livraisons').get_data(as_text=True)
    assert intrants.stock_ferme(monde['f']) == []
    changer(client, 'dge')
    client.post(f'/livraisons-etat/{liv.numero}/livree')
    assert liv.statut == S.A_CONFIRMER and liv.date_livraison == date.today()
    changer(client, 'eleveur1')
    assert liv.numero in client.get('/livraisons/mes-livraisons').get_data(as_text=True)
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    assert liv.statut in S.CONFIRMEES
    changer(client, 'dge')
    page = client.get('/livraisons-etat/planning').get_data(as_text=True)
    assert re.search(r'data-colonne="CONFIRMEE".*?data-livraison="' + liv.numero, page, re.S)
    # Annuler une prévue : motif obligatoire ; une livrée ne s'annule pas ici
    client.post('/livraisons-etat/prevoir', data={'ferme': monde['f'].numero, 'date': demain,
                                                  'produit_id': monde['aliment'].id, 'quantite': '5'})
    autre = Livraison.query.filter_by(statut=S.PREVUE).one()
    assert 'motif' in client.post(f'/livraisons-etat/{autre.numero}/annuler', data={},
                                  follow_redirects=True).get_data(as_text=True)
    client.post(f'/livraisons-etat/{autre.numero}/annuler', data={'motif': 'Camion en panne'})
    assert autre.statut == S.ANNULEE
    assert 'Seule une livraison prévue' in client.post(f'/livraisons-etat/{liv.numero}/livree',
                                                       follow_redirects=True).get_data(as_text=True)
    changer(client, 'agent1')
    assert client.get('/livraisons-etat/planning').status_code == 403


# ── B. Commande → livraison ─────────────────────────────────────────────

def test_creer_la_livraison_d_une_commande_validee(client, monde):
    c = agent.commander(monde['f'], monde['aliment'], 20, 'B2', monde['agent'])
    db.session.commit()
    _dge(client)
    assert 'Créer la livraison' not in client.get('/commandes').get_data(as_text=True)
    assert 'validée' in client.post(f'/commandes/{c.id}/creer-livraison', follow_redirects=True).get_data(as_text=True)
    client.post(f'/commandes/{c.id}/decider', data={'decision': 'valider'})
    assert 'Créer la livraison' in client.get('/commandes').get_data(as_text=True)
    client.post(f'/commandes/{c.id}/creer-livraison')
    liv = Livraison.query.one()
    assert c.statut == 'LIVREE' and c.livraison_id == liv.id and liv.statut == S.PREVUE
    assert liv.date_livraison == date.today() + timedelta(days=7) and liv.lignes[0].quantite_livree == 20
    assert liv.numero in client.get('/commandes').get_data(as_text=True)


# ── C. Arbitrages ───────────────────────────────────────────────────────

def test_arbitrages_par_province(client, monde):
    from app.models.hors_ligne import ConflitHorsLigne
    from app.models.base import maintenant
    f_hog = creer_ferme('Ferme Haut', 'HOG', 'Franceville')
    for f, age in ((monde['f'], 0), (monde['f'], 72), (f_hog, 1)):
        c = ConflitHorsLigne(ferme_id=f.id, quoi='Saisie', detail='x', genre='SAISIE_JOUR', statut='A_VERIFIER',
                             versions=[])
        c.cree_le = maintenant() - timedelta(hours=age)
        db.session.add(c)
    db.session.commit()
    _dge(client)
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert 'data-province-arbitrage="EST"' in page and 'data-province-arbitrage="HOG"' in page
    assert page.index('data-province-arbitrage="EST"') < page.index('data-province-arbitrage="HOG"')   # retard d'abord
    from tests.conftest import province
    filtre = client.get(f'/hors-ligne/a-verifier?province={province("HOG").id}').get_data(as_text=True)
    assert filtre.count('id="verif-') == 1


# ── D. Classement ───────────────────────────────────────────────────────

def _bilan(mortalite, ic, gmq, regularite, incomplet=False):
    return {'mortalite': mortalite, 'indice_consommation': ic, 'gmq': gmq, 'regularite': regularite,
            'incomplet': incomplet}


def test_classement_pondere_et_bandes_incompletes(client, monde):
    from app.services import bandes as regles_bandes
    b1 = bande_ouverte(monde)
    regles_bandes.cloturer(b1, monde['agent'], 'fin')
    b1.bilan = _bilan(2, 1.6, 55, 95)
    b2 = bande_ouverte(monde, effectif=800, bat=1)
    regles_bandes.cloturer(b2, monde['agent'], 'fin')
    b2.bilan = _bilan(1, 1.5, 60, 50)                     # incomplète (50 % des jours saisis) : ignorée
    db.session.commit()
    n = regles.notes(b1.bilan)
    assert (n['mortalite'], round(n['ic']), round(n['gmq']), n['regularite']) == (80, 83, 62, 95)
    _dge(client)
    page = client.get('/classement').get_data(as_text=True)
    assert f'data-ferme="{monde["f"].numero}"' in page and 'data-ignorees' in page and '1 bande incomplète ignorée' in page
    r = regles.classement(creer_utilisateur('dge2', Profil.DGE))
    attendu = round((80 * 35 + n['ic'] * 25 + n['gmq'] * 20 + 95 * 20) / 100, 1)
    assert r['classees'][0]['score'] == attendu and r['ignorees'] == 1
    # Une ferme n'ayant que des bandes incomplètes : « non classée »
    b2.bilan = _bilan(1, 1.5, 60, 50)
    b1.bilan = _bilan(2, 1.6, 55, 40)
    db.session.commit()
    assert 'data-non-classee' in client.get('/classement').get_data(as_text=True)
    # Pondérations : quatre yeux
    assert approbations.sensible('classement.poids_mortalite')
    r = client.get('/classement.csv')
    assert r.status_code == 200 and 'Rang' in r.data.decode('utf-8-sig')
    changer(client, 'agent1')
    assert client.get('/classement').status_code == 403


# ── E. Rapports mensuels gardés ─────────────────────────────────────────

def test_rapport_mensuel_produit_garde_et_email_coupe(client, monde, app):
    bande_ouverte(monde)
    Parametre.query.filter_by(cle='rapports.email_destinataires').one().valeur = 'dge@exemple.ga, sg@exemple.ga'
    db.session.commit()
    _dge(client)
    page = client.get('/pilotage/rapports').get_data(as_text=True)
    mois = regles.mois_termines(1)[0]
    r = RapportMensuel.query.one()
    assert r.mois == mois and f'data-rapport-garde="{mois}"' in page and 'coupé' in page
    chemin = os.path.join(app.instance_path, 'rapports', r.fichier)
    assert open(chemin, 'rb').read(4) == b'%PDF'
    assert r.email_prepare_le is not None and r.email_envoye_le is None
    assert JournalAudit.query.filter(JournalAudit.detail.like('%préparé, non envoyé%')).count() == 1
    client.get('/pilotage/rapports')
    assert RapportMensuel.query.count() == 1                       # jamais régénéré
    rep = client.get(f'/rapports/mensuels/{mois}.pdf')
    assert rep.status_code == 200 and rep.data[:4] == b'%PDF'
    # La commande du cron : rien de plus à produire
    res = app.test_cli_runner().invoke(args=['rapports-mensuels'])
    assert 'Rien à produire' in res.output


# ── F. Agents ───────────────────────────────────────────────────────────

def test_agents_charge_et_reaffectation(client, monde):
    _dge(client)
    page = client.get('/agents').get_data(as_text=True)
    assert 'data-agent="agent1"' in page and 'data-charge="vert"' in page
    autre_hog = creer_utilisateur('agent_hog', Profil.AGENT, ['HOG'])
    db.session.commit()
    f = monde['f']
    assert 'ne travaille pas dans la province' in client.post(
        '/agents/reaffecter', data={'ferme': f.numero, 'agent': str(autre_hog.id), 'motif': 'x'},
        follow_redirects=True).get_data(as_text=True)
    agent2 = monde['f2'].agent
    assert 'motif' in client.post('/agents/reaffecter', data={'ferme': f.numero, 'agent': str(agent2.id)},
                                  follow_redirects=True).get_data(as_text=True)
    client.post('/agents/reaffecter', data={'ferme': f.numero, 'agent': str(agent2.id), 'motif': 'Congé de Paul'})
    assert f.agent_id == agent2.id
    assert JournalAudit.query.filter(JournalAudit.detail.like('%Congé de Paul%')).count() == 1
    changer(client, 'agent2')
    assert f.numero in client.get('/fermes/').get_data(as_text=True)
    assert client.get('/agents').status_code == 403


def test_ponderations_et_bareme_reglables_sous_quatre_yeux(client, monde):
    """Pondérations, barème des notes et seuil « incomplète » : paramètres classement.*, quatre yeux.
    Seuls les seuils des étoiles (bandes.etoiles_*) sont hors du classement."""
    from app.services import bandes as regles_bandes
    b = bande_ouverte(monde)
    regles_bandes.cloturer(b, monde['agent'], 'fin')
    b.bilan = _bilan(2, 1.6, 55, 95)
    admin, dge = creer_utilisateur('admin', Profil.ADMIN), creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    cles = [p.cle for p in Parametre.query.filter(Parametre.cle.like('classement.%'))]
    assert len(cles) == 10 and all(approbations.sensible(c) for c in cles)
    avant = regles.classement(dge)['classees'][0]['score']
    for cle, valeur in (('classement.poids_mortalite', '80'), ('classement.mortalite_note_zero_pct', '4'),
                        ('classement.seuil_complet_pct', '96')):
        p = Parametre.query.filter_by(cle=cle).one()
        approbations.proposer('PARAMETRE', cle, p.description, p.valeur, valeur, {'valeur': valeur}, 'essai', admin)
    db.session.commit()
    assert regles.classement(dge)['classees'][0]['score'] == avant            # rien avant l'approbation
    from app.models.securite import Proposition
    for prop in Proposition.query.filter_by(statut='EN_ATTENTE').all():
        assert not approbations.peut_decider(admin, prop)                  # jamais l'auteur
        approbations.decider(prop, dge, True)
    db.session.commit()
    r = regles.classement(dge)
    assert r['poids']['mortalite'] == 80 and r['bareme']['mortalite_zero'] == 4 and r['seuil'] == 96
    assert r['classees'] == [] and r['ignorees'] == 1                      # 95 % < 96 % : bande incomplète
