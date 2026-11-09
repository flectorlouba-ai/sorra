"""Lot 10 — entretien : tâches regroupées par période et par bâtiment, retard (semaine et mois seulement),
désinfection à la clôture, pannes, annulation 10 s, hors ligne, fiche de l'agent, liste des tâches (ADMIN)."""
import io
import re
from datetime import timedelta, datetime, timezone

from freezegun import freeze_time

from app import db
from app.models import JournalAudit
from app.models.bande import Bande
from app.models.ferme import FermeInfrastructure
from app.models.entretien import TacheEntretien, EntretienFait, Panne, StatutPanne, Frequence
from app.models.base import maintenant
from app.services import entretien, bandes as regles
from app.services.journal import Action
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer
from tests.test_sante import JPEG


def tache(nom):
    return TacheEntretien.query.filter(TacheEntretien.nom.like(f'{nom}%')).one()


def carte(ferme, nom, jour=None):
    return next((c for c in entretien.cartes(ferme, jour) if c['tache'].nom.startswith(nom)), None)


def vieillir(monde, jours=60):
    """Ferme créée il y a longtemps : les tâches de la semaine et du mois existaient déjà avant."""
    monde['f'].cree_le = datetime.now(timezone.utc) - timedelta(days=jours)
    db.session.commit()


def fait(client, monde, nom, **extra):
    return client.post('/entretien/fait', data={'tache': tache(nom).id, **extra})


def vider(bande, monde):
    """Clôture de la bande (le motif couvre les poulets restants)."""
    regles.cloturer(bande, monde['el'], 'essai')
    db.session.commit()


# ── Tâches : période, bâtiment, regroupement, infrastructure ───────────

def test_taches_de_depart_par_bande_et_regroupees(client, monde):
    f = monde['f']
    assert carte(f, 'Laver les abreuvoirs') is None                 # pas de bande : pas de tâche de bande
    bande_ouverte(monde)
    c = carte(f, 'Laver les abreuvoirs')
    assert c['sous'] == 'B1 · chaque jour' and not c['faite']
    bande_ouverte(monde, bat=1)
    c = carte(f, 'Laver les abreuvoirs')
    assert c['sous'] == 'B1 et B2 · chaque jour'                    # une seule carte pour les deux bâtiments
    connecter(client, 'eleveur1')
    page = client.get('/entretien').get_data(as_text=True)
    assert page.count('<strong>Laver les abreuvoirs</strong>') == 1 and 'B1 et B2 · chaque jour' in page
    assert 'Vérifier la litière' in page and 'chaque semaine' in page
    # Un seul « Fait ✓ » coche les deux bâtiments
    fait(client, monde, 'Laver les abreuvoirs')
    lignes = EntretienFait.query.filter_by(tache_id=tache('Laver les abreuvoirs').id).all()
    assert len(lignes) == 2 and {l.periode for l in lignes} == {AUJ}
    assert carte(f, 'Laver les abreuvoirs')['faite']
    page = client.get('/entretien').get_data(as_text=True)
    assert '✓ fait' in page and 'Fait ✓ — Laver les abreuvoirs' in page   # grisé + bandeau Annuler (10)
    # Demain, la tâche quotidienne revient ; la semaine reste faite jusqu'à lundi
    fait(client, monde, 'Vérifier la litière')
    demain = AUJ + timedelta(days=1)
    assert not carte(f, 'Laver les abreuvoirs', demain)['faite']
    lundi = entretien.debut_periode(Frequence.SEMAINE, AUJ) + timedelta(days=7)
    assert carte(f, 'Vérifier la litière', lundi - timedelta(days=1))['faite']
    assert not carte(f, 'Vérifier la litière', lundi)['faite']


def test_periodes():
    from datetime import date
    mercredi = date(2026, 6, 17)
    assert entretien.debut_periode(Frequence.JOUR, mercredi) == mercredi
    assert entretien.debut_periode(Frequence.SEMAINE, mercredi) == date(2026, 6, 15)
    assert entretien.debut_periode(Frequence.MOIS, mercredi) == date(2026, 6, 1)
    assert entretien.periode_precedente(Frequence.MOIS, date(2026, 1, 1)) == date(2025, 12, 1)
    assert entretien.periode_precedente(Frequence.SEMAINE, date(2026, 6, 15)) == date(2026, 6, 8)


def test_taches_selon_les_infrastructures(client, monde):
    f = monde['f']
    assert carte(f, "Changer l'eau du pédiluve") is None and carte(f, 'Vérifier le groupe') is None
    f.infrastructures.append(FermeInfrastructure(infrastructure='Pédiluve'))
    f.infrastructures.append(FermeInfrastructure(infrastructure='Groupe électrogène'))
    db.session.commit()
    c = carte(f, "Changer l'eau du pédiluve")
    assert c['sous'] == 'toute la ferme · chaque semaine'          # tâche de la ferme, même sans bande
    assert carte(f, 'Vérifier le groupe')['sous'] == 'toute la ferme · chaque mois'
    assert carte(f, 'Vérifier la pompe') is None


# ── Retard : semaine et mois seulement ──────────────────────────────────

def test_pas_de_retard_pour_les_taches_du_jour(client, monde):
    vieillir(monde)
    bande_ouverte(monde, jour=AUJ - timedelta(days=20))
    c = carte(monde['f'], 'Laver les abreuvoirs')
    assert c['retard'] is None                                       # rien hier, mais pas de « pas fait hier »
    connecter(client, 'eleveur1')
    page = client.get('/entretien').get_data(as_text=True)
    assert 'hier' not in page


def test_retard_semaine_et_mois(client, monde):
    vieillir(monde)
    monde['f'].infrastructures.append(FermeInfrastructure(infrastructure='Groupe électrogène'))
    db.session.commit()
    bande_ouverte(monde, jour=AUJ - timedelta(days=20))
    assert carte(monde['f'], 'Vérifier la litière')['retard'] == 'pas fait la semaine dernière'
    assert carte(monde['f'], 'Vérifier le groupe')['retard'] == 'pas fait le mois dernier'
    # Les tâches en retard viennent en tête
    assert entretien.cartes(monde['f'])[0]['retard']
    connecter(client, 'eleveur1')
    assert 'pas fait la semaine dernière' in client.get('/entretien').get_data(as_text=True)
    # Faite la semaine dernière : plus de retard
    t = tache('Vérifier la litière')
    prec = entretien.periode_precedente(Frequence.SEMAINE, entretien.debut_periode(Frequence.SEMAINE, AUJ))
    db.session.add(EntretienFait(ferme_id=monde['f'].id, batiment_id=monde['f'].batiments[0].id, tache_id=t.id,
                                 periode=prec, fait_le=prec))
    db.session.commit()
    assert carte(monde['f'], 'Vérifier la litière')['retard'] is None


def test_pas_de_retard_pour_une_bande_qui_vient_de_commencer(client, monde):
    vieillir(monde)
    bande_ouverte(monde)                                             # commencée aujourd'hui
    assert carte(monde['f'], 'Vérifier la litière')['retard'] is None


# ── Vide sanitaire : désinfection à la clôture, avertissement à l'ouverture ─

def test_desinfection_apparait_a_la_cloture(client, monde):
    b = bande_ouverte(monde)
    assert carte(monde['f'], 'Nettoyer et désinfecter') is None
    vider(b, monde)
    c = carte(monde['f'], 'Nettoyer et désinfecter')
    assert c and not c['faite'] and c['sous'].startswith('B1 · vide sanitaire depuis')
    assert entretien.desinfection_a_faire(monde['f'].batiments[0]) == b
    assert carte(monde['f'], 'Laver les abreuvoirs') is None         # plus de bande : plus de tâche de bande
    connecter(client, 'eleveur1')
    fait(client, monde, 'Nettoyer et désinfecter')
    f = EntretienFait.query.filter_by(tache_id=tache('Nettoyer et désinfecter').id).one()
    assert f.bande_id == b.id and f.batiment_id == monde['f'].batiments[0].id
    assert entretien.desinfection_a_faire(monde['f'].batiments[0]) is None
    assert carte(monde['f'], 'Nettoyer et désinfecter')['faite']


def _ouvrir(client, monde, **extra):
    liv = recevoir(monde['f'], [(monde['poussins'], 500, 0)])
    ligne = liv.lignes[0]
    return client.post('/bandes/ouvrir', data={'ferme': monde['f'].numero, 'ligne': ligne.id,
                                               'batiment': monde['f'].batiments[0].id, 'effectif': '500', **extra})


def test_avertissement_a_l_ouverture_sans_desinfection(client, monde):
    b = bande_ouverte(monde)
    vider(b, monde)
    connecter(client, 'eleveur1')
    page = _ouvrir(client, monde).get_data(as_text=True)
    assert 'avertissement-desinfection' in page and 'Je nettoie d' in page and 'name="continuer"' in page
    assert Bande.query.count() == 1                                  # rien d'ouvert : l'éleveur choisit
    # Il continue quand même : la bande s'ouvre, marquée, et c'est au journal
    _ouvrir(client, monde, continuer='1')
    nouvelle = Bande.query.filter(Bande.id != b.id).one()
    assert nouvelle.ouverte_sans_desinfection
    j = JournalAudit.query.filter_by(action=Action.SANS_DESINFECTION).one()
    assert nouvelle.numero in j.detail and 'B1' in j.detail
    # L'agent le voit sur la fiche de la ferme
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert f'Bande {nouvelle.numero} ouverte sans désinfection' in fiche


def test_pas_d_avertissement_si_desinfecte(client, monde):
    b = bande_ouverte(monde)
    vider(b, monde)
    connecter(client, 'eleveur1')
    fait(client, monde, 'Nettoyer et désinfecter')
    _ouvrir(client, monde)
    nouvelle = Bande.query.filter(Bande.id != b.id).one()
    assert not nouvelle.ouverte_sans_desinfection
    assert JournalAudit.query.filter_by(action=Action.SANS_DESINFECTION).count() == 0


# ── Annuler « Fait ✓ » dans les 10 secondes ────────────────────────────

def test_fait_annuler_dans_les_10_secondes(client, monde):
    bande_ouverte(monde)
    connecter(client, 'eleveur1')
    fait(client, monde, 'Laver les abreuvoirs')
    page = client.get('/entretien').get_data(as_text=True)
    assert 'Fait ✓ — Laver les abreuvoirs' in page and '/entretien/fait/annuler' in page
    client.post('/entretien/fait/annuler')
    assert EntretienFait.query.one().annule
    assert not carte(monde['f'], 'Laver les abreuvoirs')['faite']   # de nouveau à faire
    # Trop tard : refusé
    fait(client, monde, 'Laver les abreuvoirs')
    ligne = EntretienFait.query.filter_by(annule=False).one()
    ligne.cree_le = maintenant() - timedelta(seconds=40)
    db.session.commit()
    assert 'Fait ✓ —' not in client.get('/entretien').get_data(as_text=True)
    with client.session_transaction() as s:
        s['entretien_recent'] = [str(ligne.id)]
    client.post('/entretien/fait/annuler')
    assert not db.session.get(EntretienFait, ligne.id).annule


# ── Pannes : signaler, alerte agent, réparer, annuler la réparation ────

def _signaler(client, monde, **data):
    return client.post('/entretien/panne', data={'type': 'EAU', 'batiment': 'ferme', **data},
                       content_type='multipart/form-data')


def test_ecran_panne(client, monde):
    connecter(client, 'eleveur1')
    page = client.get('/entretien/panne').get_data(as_text=True)
    for nom in ('Chauffage', 'Eau', 'Électricité', 'Ventilation', 'Mangeoires', 'Bâtiment'):
        assert nom in page
    assert 'Toute la ferme' in page and 'B1' in page and 'B2' in page and 'Envoyer à mon agent' in page
    # Une ferme d'un seul bâtiment : pas de choix du bâtiment
    from app.models import UtilisateurFerme
    monde['el'].fermes = [UtilisateurFerme(ferme=monde['f2'])]
    db.session.commit()
    page = client.get('/entretien/panne').get_data(as_text=True)
    assert 'Toute la ferme' not in page and 'Dans quel bâtiment' not in page
    _signaler(client, monde, batiment='')
    assert Panne.query.one().batiment_id == monde['f2'].batiments[0].id


def test_panne_alerte_agent_reparee_et_annulation(client, monde):
    connecter(client, 'eleveur1')
    r = _signaler(client, monde, batiment=str(monde['f'].batiments[1].id), photo=(io.BytesIO(JPEG), 'eau.jpg'))
    assert r.status_code == 302
    p = Panne.query.one()
    assert p.statut == StatutPanne.SIGNALEE and p.photo and p.ou == 'B2' and not p.saisie_par_agent
    page = client.get('/entretien').get_data(as_text=True)
    assert 'carte-panne' in page and 'Eau en panne · B2' in page and 'Paul est prévenu' in page
    assert client.get(f'/entretien/panne/{p.id}/photo').status_code == 200
    accueil = client.get('/').get_data(as_text=True)
    assert re.search(r'data-tuile="entretien".*?class="pastille rouge"', accueil, re.S)
    # L'agent est alerté
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert 'Panne signalée : 💧 Eau · B2' in client.get('/').get_data(as_text=True)
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'id="entretien"' in fiche and 'Eau en panne · B2' in fiche
    # L'éleveur répare ; il peut annuler dans les 10 secondes
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    client.post(f'/entretien/panne/{p.id}/reparee')
    db.session.refresh(p)
    assert p.statut == StatutPanne.REPAREE and p.reparee_par == monde['el'].id
    page = client.get('/entretien').get_data(as_text=True)
    assert 'Réparé ✓ — Eau · B2' in page and 'carte-panne' not in page
    client.post(f'/entretien/panne/{p.id}/annuler')
    db.session.refresh(p)
    assert p.statut == StatutPanne.SIGNALEE and p.reparee_le is None
    j = JournalAudit.query.filter_by(action=Action.ANNULATION, table_nom='panne').one()
    assert 'de nouveau signalée' in j.detail
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert 'Panne signalée : 💧 Eau · B2' in client.get('/').get_data(as_text=True)   # l'alerte revient
    # Réparée pour de bon (trop tard pour annuler) : plus d'alerte
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    client.post(f'/entretien/panne/{p.id}/reparee')
    db.session.refresh(p)
    p.reparee_le = maintenant() - timedelta(seconds=40)
    db.session.commit()
    client.post(f'/entretien/panne/{p.id}/annuler')
    db.session.refresh(p)
    assert p.statut == StatutPanne.REPAREE
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert 'Panne signalée' not in client.get('/').get_data(as_text=True)


def test_panne_d_une_autre_ferme_refusee(client, monde):
    p = entretien.signaler(monde['f2'], 'EAU', None, monde['agent'])
    db.session.commit()
    connecter(client, 'eleveur1')
    assert client.post(f'/entretien/panne/{p.id}/reparee').status_code == 404


def test_type_de_panne_obligatoire(client, monde):
    connecter(client, 'eleveur1')
    page = _signaler(client, monde, type='').get_data(as_text=True)
    assert 'Touchez ce qui ne marche pas' in page and Panne.query.count() == 0


# ── L'agent pour l'éleveur ──────────────────────────────────────────────

def test_agent_coche_et_repare_pour_l_eleveur(client, monde):
    bande_ouverte(monde)
    p = entretien.signaler(monde['f'], 'CHAUFFAGE', monde['f'].batiments[0], monde['el'])
    db.session.commit()
    connecter(client, 'agent1')
    numero = monde['f'].numero
    page = client.get(f'/entretien?ferme={numero}').get_data(as_text=True)
    assert "saisie de l'agent pour l'éleveur" in page and 'Chauffage en panne · B1' in page
    fait(client, monde, 'Laver les abreuvoirs', ferme=numero)
    ligne = EntretienFait.query.one()
    assert ligne.saisi_par_agent and ligne.cree_par == monde['agent'].id
    assert JournalAudit.query.filter_by(action=Action.POUR_ELEVEUR, table_nom='entretien_fait').count() == 1
    client.post(f'/entretien/panne/{p.id}/reparee?ferme={numero}')
    db.session.refresh(p)
    assert p.statut == StatutPanne.REPAREE and p.reparee_par_agent
    # Un autre agent n'ouvre pas cette ferme
    client.post('/auth/deconnexion')
    connecter(client, 'agent2')
    assert client.get(f'/entretien?ferme={numero}').status_code == 404


# ── Hors ligne : Fait, Envoyer, Réparé ─────────────────────────────────

def test_hors_ligne_fait_panne_reparee(client, monde):
    bande_ouverte(monde)
    connecter(client, 'eleveur1')
    _, rep = rejouer(client, '/entretien/fait', {'tache': tache('Laver les abreuvoirs').id})
    assert rep['etat'] == 'ok'
    assert EntretienFait.query.one().appareil_id == 'tel-1'
    _, rep = rejouer(client, '/entretien/panne', {'type': 'ELECTRICITE', 'batiment': 'ferme'},
                     content_type='multipart/form-data')
    assert rep['etat'] == 'ok'
    p = Panne.query.one()
    assert p.batiment_id is None and p.ou == 'toute la ferme'
    _, rep = rejouer(client, f'/entretien/panne/{p.id}/reparee', {})
    assert rep['etat'] == 'ok'
    db.session.refresh(p)
    assert p.statut == StatutPanne.REPAREE
    # Saisies faites hors ligne : pas de bandeau « Annuler » (le téléphone a déjà affiché ✓)
    page = client.get('/entretien').get_data(as_text=True)
    assert 'Fait ✓ —' not in page and 'Réparé ✓ —' not in page


def test_formulaires_marques_hors_ligne(client, monde):
    bande_ouverte(monde)
    entretien.signaler(monde['f'], 'EAU', None, monde['el'])
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/entretien').get_data(as_text=True)
    assert 'data-hors-ligne="Entretien · Laver les abreuvoirs"' in page
    assert 'data-hors-ligne="Panne réparée · Eau"' in page
    assert 'data-hors-ligne="Panne · Ferme Un"' in client.get('/entretien/panne').get_data(as_text=True)


# ── Nombre de touches ──────────────────────────────────────────────────

def test_nombre_de_touches(client, monde):
    bande_ouverte(monde)
    connecter(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert 'href="/entretien"' in accueil                            # 1 : tuile Entretien
    page = client.get('/entretien').get_data(as_text=True)
    assert 'class="tache-bouton">Fait ✓' in page                     # Entretien → Fait : 2 touches
    assert 'href="/entretien/panne"' in page                         # 2 : « Quelque chose est en panne »
    _signaler(client, monde)                                         # 3 : Envoyer (type + bâtiment = choix)
    page = client.get('/entretien').get_data(as_text=True)
    assert "C'est réparé" in page                                    # Entretien → Réparé : 2 touches


# ── Accueil : tuile, pastille ──────────────────────────────────────────

def test_tuile_entretien_et_pastille(client, monde):
    connecter(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert 'data-tuile="entretien"' in accueil and 'tout est fait' in accueil
    bande_ouverte(monde)
    accueil = client.get('/').get_data(as_text=True)
    n = entretien.a_faire_aujourdhui(monde['f'])
    assert n == 3 and 'tâches à faire' in accueil                   # abreuvoirs, mangeoires, litière
    assert re.search(r'data-tuile="entretien".*?<span class="pastille[^"]*">3<', accueil, re.S)


# ── Protection des saisies en attente ──────────────────────────────────

def test_bandeau_des_saisies_en_attente_et_derniere_synchronisation(client, monde):
    js = client.get('/static/js/hors_ligne.js').get_data(as_text=True)
    assert 'bandeau-attente-longue' in js and '24 * 3600 * 1000' in js
    assert "Ne videz pas les données de l\\'application." in js
    connecter(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert "Dernière synchronisation du téléphone de l'éleveur :</strong>\n      jamais" in fiche
    def synchro():
        client.post('/auth/deconnexion')
        connecter(client, 'agent1')
        return client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True).split('Dernière synchronisation')[1][:300]

    # Une saisie de l'éleveur il y a 5 jours (le journal ne se modifie pas : on recule l'horloge)
    client.post('/auth/deconnexion')
    with freeze_time(datetime.now() - timedelta(days=5), tick=True):
        connecter(client, 'eleveur1')
        _signaler(client, monde)
    extrait = synchro()
    assert 'il y a 5 jours' in extrait and 'à vérifier' in extrait
    # Une simple connexion ne compte pas ; une saisie d'aujourd'hui, si
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    assert 'il y a 5 jours' in synchro()
    client.post('/auth/deconnexion')
    connecter(client, 'eleveur1')
    _signaler(client, monde, type='CHAUFFAGE')
    extrait = synchro()
    assert "aujourd'hui" in extrait and 'à vérifier' not in extrait


# ── Liste des tâches (ADMIN) ───────────────────────────────────────────

def test_liste_des_taches_admin(client_admin, client):
    page = client_admin.get('/administration/entretien').get_data(as_text=True)
    assert 'à valider par les vétérinaires' in page and 'Laver les abreuvoirs' in page
    assert TacheEntretien.query.count() == 7
    client_admin.post('/administration/entretien', data={'nom': 'Vider la fosse', 'icone': '🕳️',
                                                         'frequence': 'MOIS', 'portee': 'FERME',
                                                         'infrastructure': '', 'actif': 'on'})
    t = TacheEntretien.query.filter_by(nom='Vider la fosse').one()
    assert t.actif and t.ordre > max(x.ordre for x in TacheEntretien.query if x.id != t.id)
    page = client_admin.get(f'/administration/entretien?modifier={t.id}').get_data(as_text=True)
    assert 'Modifier « Vider la fosse »' in page
    client_admin.post('/administration/entretien', data={'id': t.id, 'nom': 'Vider la fosse', 'icone': '🕳️',
                                                         'frequence': 'MOIS', 'portee': 'FERME'})
    db.session.refresh(t)
    assert not t.actif                                               # désactivée, jamais supprimée
    assert 'Tâches d&#39;entretien' in client_admin.get('/').get_data(as_text=True)


def test_liste_des_taches_reservee_a_l_admin(client, monde):
    connecter(client, 'eleveur1')
    assert client.get('/administration/entretien').status_code in (302, 403)
