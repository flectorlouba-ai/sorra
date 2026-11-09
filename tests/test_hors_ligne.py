"""Lot 7 — hors connexion : envois après coup, doublons, conflits, reprise après coupure."""
import io
import uuid
from datetime import datetime, timedelta, timezone

from app import db
from app.models import Livraison, Parametre
from app.models.bande import SaisieJour, Pesee, Sortie
from app.models.hors_ligne import EnvoiHorsLigne, ConflitHorsLigne
from app.models.intrant import StatutLivraison as S
from app.models.sante import Declaration
from app.services import intrants
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte, recevoir, AUJ  # noqa: F401
from tests.test_sante import JPEG


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def rejouer(client, url, data, ident=None, il_y_a=timedelta(minutes=5), **kw):
    """Envoi après coup d'une saisie faite sans réseau, comme le fait le téléphone."""
    ident = ident or str(uuid.uuid4())
    heure = (datetime.now(timezone.utc) - il_y_a).isoformat()
    r = client.post(url, data=data, headers={'X-Hors-Ligne-Id': ident, 'X-Hors-Ligne-Horodatage': heure,
                                            'X-Hors-Ligne-Libelle': 'Essai', 'X-Appareil': 'tel-1'}, **kw)
    assert r.mimetype == 'application/json', r.get_data(as_text=True)[:300]
    return ident, r.get_json()


def test_envoi_apres_coup_et_doublon_refuse(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    ident, rep = rejouer(client, f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4,2'})
    assert rep['etat'] == 'ok' and 'Pesée enregistrée' in rep['message']
    p = Pesee.query.one()
    assert p.appareil_id == 'tel-1'
    envoi = db.session.get(EnvoiHorsLigne, uuid.UUID(ident))
    assert envoi.objet_table == 'pesee' and envoi.objet_id == str(p.id)
    # Même identifiant renvoyé (réponse perdue, double envoi) : jamais compté deux fois
    _, rep = rejouer(client, f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4,2'}, ident=ident)
    assert rep['etat'] == 'deja' and Pesee.query.count() == 1


def test_reprise_apres_coupure(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    file = [(str(uuid.uuid4()), f'/bandes/{b.numero}/saisie', {'morts': '2'}),
            (str(uuid.uuid4()), f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4'}),
            (str(uuid.uuid4()), f'/bandes/{b.numero}/sortie', {'motif': 'Autre', 'nombre': '5', 'poids_total': '10'})]
    # Le réseau coupe après les deux premiers envois : le téléphone n'a reçu aucune réponse
    for ident, url, data in file[:2]:
        rejouer(client, url, data, ident=ident)
    # Au retour du réseau, il renvoie toute la file
    etats = [rejouer(client, url, data, ident=ident)[1]['etat'] for ident, url, data in file]
    assert etats == ['deja', 'deja', 'ok']
    assert (SaisieJour.query.count(), Pesee.query.count(), Sortie.query.count()) == (1, 1, 1)
    assert SaisieJour.query.one().morts == 2 and EnvoiHorsLigne.query.count() == 3


def test_conflit_saisie_du_jour_la_plus_recente_gagne(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '4'})   # saisie de l'agent, en ligne
    changer(client, 'eleveur1')
    # Saisie du téléphone faite AVANT celle de l'agent : celle de l'agent est gardée
    ident, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '1', 'jour': AUJ.isoformat()},
                         il_y_a=timedelta(hours=2))
    assert rep['etat'] == 'conflit' and SaisieJour.query.one().morts == 4
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '1', 'jour': AUJ.isoformat()}, ident=ident)
    assert rep['etat'] == 'deja' and ConflitHorsLigne.query.count() == 1   # pas de second conflit
    # Saisie du téléphone plus récente : elle remplace (sans s'ajouter)
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '6', 'jour': AUJ.isoformat()},
                     il_y_a=timedelta(0))
    assert rep['etat'] == 'conflit' and SaisieJour.query.one().morts == 6
    conflits = ConflitHorsLigne.query.order_by(ConflitHorsLigne.id).all()
    assert len(conflits) == 2 and 'Gardée : la plus récente (4 morts' in conflits[0].detail
    assert 'Remplacée : 4 morts' in conflits[1].detail
    # L'agent est prévenu, et marque « vu »
    changer(client, 'agent1')
    assert '2 saisies faites sans réseau à vérifier' in client.get('/').get_data(as_text=True)
    page = client.get('/hors-ligne/a-verifier').get_data(as_text=True)
    assert 'Saisie du' in page and b.numero in page
    client.post(f'/hors-ligne/a-verifier/{conflits[0].id}/vu')
    assert '1 saisie faite sans réseau à vérifier' in client.get('/').get_data(as_text=True)
    changer(client, 'eleveur1')
    assert client.get('/hors-ligne/a-verifier').status_code == 403


def test_meme_personne_les_saisies_du_jour_s_additionnent(client, monde):
    b = bande_ouverte(monde)
    aliment = monde['aliment'].id
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '3', 'sacs': '2', 'aliment_choisi': aliment})
    # Deux saisies faites ensuite sans réseau sur le même téléphone, dont une datée d'avant
    # la saisie en ligne : tout s'additionne, comme en ligne, sans conflit
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie',
                     {'morts': '2', 'sacs': '1', 'aliment_choisi': aliment, 'jour': AUJ.isoformat()},
                     il_y_a=timedelta(hours=1))
    assert rep['etat'] == 'ok' and 'ajouté à la saisie' in rep['message']
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '1', 'jour': AUJ.isoformat()},
                     il_y_a=timedelta(0))
    s = SaisieJour.query.one()
    assert rep['etat'] == 'ok' and s.morts == 6 and s.aliments[0].sacs == 3 and s.aliments[0].kg == 75
    assert ConflitHorsLigne.query.count() == 0


def test_meme_personne_deux_saisies_hors_ligne_s_additionnent(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '2', 'jour': AUJ.isoformat()}, il_y_a=timedelta(hours=3))
    rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '4', 'jour': AUJ.isoformat()}, il_y_a=timedelta(hours=1))
    assert SaisieJour.query.one().morts == 6 and ConflitHorsLigne.query.count() == 0


def test_deux_personnes_memes_valeurs_pas_de_conflit(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '3'})
    changer(client, 'eleveur1')
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '3', 'jour': AUJ.isoformat()})
    assert rep['etat'] == 'ok' and SaisieJour.query.one().morts == 3 and ConflitHorsLigne.query.count() == 0


def test_meme_personne_confirmation_de_livraison_sans_conflit(client, monde):
    liv = intrants.nouvelle_livraison(monde['f'], AUJ - timedelta(days=1), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': False,
                                     'part_subventionnee': None, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'eleveur1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')
    _, rep = rejouer(client, f'/livraisons/{liv.numero}/tout-recu', {}, il_y_a=timedelta(hours=1))
    assert rep['etat'] == 'ok' and ConflitHorsLigne.query.count() == 0
    assert db.session.get(Livraison, liv.id).statut == S.RECUE


def test_jour_passe_compte_depuis_le_jour_de_la_saisie(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    connecter(client, 'eleveur1')
    jour = (AUJ - timedelta(days=5)).isoformat()
    # En ligne, 5 jours en arrière est refusé à l'éleveur (limite 3 jours)…
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '1', 'jour': jour})
    assert SaisieJour.query.count() == 0
    # … mais une saisie faite ce jour-là sans réseau, envoyée aujourd'hui, est acceptée
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '1', 'jour': jour}, il_y_a=timedelta(days=5))
    assert rep['etat'] == 'ok', rep
    assert SaisieJour.query.one().date.isoformat() == jour


def test_refus_signale_au_telephone_et_a_l_agent(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    _, rep = rejouer(client, f'/bandes/{b.numero}/sortie', {'motif': 'Autre', 'nombre': '5000', 'poids_total': '10'})
    assert rep['etat'] == 'refuse' and 'entre 1 et 997' in rep['message'] and Sortie.query.count() == 0
    c = ConflitHorsLigne.query.one()
    assert c.quoi == 'Envoi refusé : Essai' and c.ferme_id == monde['f'].id
    _, rep = rejouer(client, f'/bandes/{b.numero}/saisie', {'morts': '-3'})
    assert rep['etat'] == 'refuse' and EnvoiHorsLigne.query.count() == 0


def test_connexion_perdue_la_saisie_reste_sur_le_telephone(client, monde):
    b = bande_ouverte(monde)
    _, rep = rejouer(client, f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4'})
    assert rep['etat'] == 'connexion' and Pesee.query.count() == 0
    assert client.get('/hors-ligne/jeton').status_code == 401
    connecter(client, 'eleveur1')
    assert client.get('/hors-ligne/jeton').get_json()['etat'] == 'ok'
    # Session expirée pendant l'envoi (inactivité) : réponse « connexion », rien n'est perdu
    Parametre.query.filter_by(cle='securite.duree_session_minutes').one().valeur = '0'
    db.session.commit()
    with client.session_transaction() as s:
        s['derniere_activite'] = 1
    _, rep = rejouer(client, f'/bandes/{b.numero}/pesee', {'nombre': '10', 'poids_total': '4'})
    assert rep['etat'] == 'connexion' and Pesee.query.count() == 0


def test_conflit_confirmation_de_livraison(client, monde):
    liv = intrants.nouvelle_livraison(monde['f'], AUJ - timedelta(days=1), None)
    db.session.add(liv)
    intrants.remplacer_lignes(liv, [{'produit': monde['aliment'], 'quantite_livree': 40, 'subventionne': False,
                                     'part_subventionnee': None, 'valeur_unitaire': None}])
    db.session.commit()
    connecter(client, 'agent1')
    client.post(f'/livraisons/{liv.numero}/tout-recu')   # l'agent confirme en ligne
    changer(client, 'eleveur1')
    ligne = liv.lignes[0]
    # L'éleveur avait confirmé « reçu moins » sans réseau, plus tôt : la confirmation de l'agent reste
    _, rep = rejouer(client, f'/livraisons/{liv.numero}/recu-moins',
                     {f'recue-{ligne.id}': '30', f'motif-{ligne.id}': 'Sacs abîmés'}, il_y_a=timedelta(hours=3))
    assert rep['etat'] == 'conflit'
    assert db.session.get(Livraison, liv.id).statut == S.RECUE
    # Plus récente : elle remplace
    _, rep = rejouer(client, f'/livraisons/{liv.numero}/recu-moins',
                     {f'recue-{ligne.id}': '30', f'motif-{ligne.id}': 'Sacs abîmés'}, il_y_a=timedelta(0))
    db.session.expire_all()
    assert rep['etat'] == 'conflit' and db.session.get(Livraison, liv.id).statut == S.RECUE_ECART
    assert ConflitHorsLigne.query.count() == 2


def test_declaration_avec_photo_envoyee_apres_coup(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    data = {'bande': b.numero, 'signes': ['Diarrhée'], 'nombre': '3', 'photos': [(io.BytesIO(JPEG), 'photo.jpg')]}
    ident, rep = rejouer(client, '/sante/declarer', data, content_type='multipart/form-data')
    assert rep['etat'] == 'ok' and len(Declaration.query.one().photos) == 1
    data['photos'] = [(io.BytesIO(JPEG), 'photo.jpg')]
    _, rep = rejouer(client, '/sante/declarer', data, ident=ident, content_type='multipart/form-data')
    assert rep['etat'] == 'deja' and Declaration.query.count() == 1


def test_sans_en_tete_rien_ne_change(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/pesee', data={'nombre': '10', 'poids_total': '4'})
    assert r.status_code == 302 and EnvoiHorsLigne.query.count() == 0


def test_application_installable(client, monde):
    r = client.get('/sw.js')
    assert r.status_code == 200 and r.headers['Service-Worker-Allowed'] == '/' and b'performyl2-pages' in r.data
    assert client.get('/static/manifest.webmanifest').status_code == 200
    assert client.get('/hors-ligne/ping').status_code == 204
    connecter(client, 'eleveur1')
    page = client.get('/').get_data(as_text=True)
    assert 'manifest.webmanifest' in page and 'js/hors_ligne.js' in page and 'data-utilisateur=' in page
    assert 'data-hors-ligne="Saisie du jour' not in page   # pas de bande ici : pas de formulaire
    b = bande_ouverte(monde)
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'data-hors-ligne="Saisie du jour · bâtiment B1"' in page
    assert 'data-hors-ligne="Pesée' in client.get(f'/bandes/{b.numero}/pesee').get_data(as_text=True)
