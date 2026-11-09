"""Lot 4 — santé animale."""
import io
from datetime import date, timedelta

import pytest

from app import db
from app.models import Produit, Profil, JournalAudit, UtilisateurFerme, Operateur, Parametre
from app.models.bande import SaisieJour
from app.models.sante import (Declaration, AlerteSanitaire, CalendrierVaccinal, Vaccination, Traitement,
                              StatutAlerte as SA)
from app.services import intrants, sante
from tests.conftest import creer_utilisateur, connecter, province
from tests.test_bandes import monde as monde_bandes, bande_ouverte, recevoir  # noqa: F401

AUJ = date.today()
JPEG = b'\xff\xd8\xff\xe0' + b'0' * 200
WEBM = b'\x1aE\xdf\xa3' + b'0' * 200


@pytest.fixture
def monde(monde_bandes):
    m = monde_bandes
    m['vaccin'] = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    m['medoc'] = Produit(nom='Anticoccidien', type='Médicament', unite='flacons', delai_attente_jours=7)
    db.session.add_all([m['vaccin'], m['medoc']])
    m['veto'] = creer_utilisateur('veto', Profil.VETO, ['EST'])
    m['veto_hog'] = creer_utilisateur('veto2', Profil.VETO, ['HOG'])
    db.session.commit()
    return m


def declarer(client, bande, **extra):
    data = {'bande': bande.numero, 'signes': ['Diarrhée', 'Abattement'], 'nombre': '12',
            'photos': [(io.BytesIO(JPEG), 'a.jpg')], 'audio': (io.BytesIO(WEBM), 'message.webm'), **extra}
    return client.post('/sante/declarer', data=data, content_type='multipart/form-data', follow_redirects=True)


# ── Déclaration ─────────────────────────────────────────────────────────

def test_declaration_de_l_eleveur_et_visibilite(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.get(f'/sante/declarer?bande={b.numero}').get_data(as_text=True)
    assert 'Diarrhée' in page and 'Envoyer au vétérinaire' in page and 'bi-droplet-half' in page
    r = declarer(client, b)
    assert 'Envoyé au vétérinaire ✓' in r.get_data(as_text=True)
    d = Declaration.query.one()
    assert d.signes == ['Diarrhée', 'Abattement'] and d.nombre_animaux == 12 and len(d.photos) == 1 and d.audio
    a = AlerteSanitaire.query.one()
    assert a.statut == SA.NOUVELLE and a.declaration_id == d.id and a.numero.startswith('ALS-')
    assert 'Diarrhée' in client.get('/sante/mes-declarations').get_data(as_text=True)
    photo = f'/sante/declarations/{d.id}/photo/{d.photos[0].fichier}'
    assert client.get(photo).status_code == 200
    client.post('/auth/deconnexion')
    # Vétérinaire de la province : voit et ouvre ; celui d'une autre province : non
    connecter(client, 'veto')
    assert 'Diarrhée' in client.get('/sante/declarations').get_data(as_text=True)
    assert client.get(photo).data == JPEG
    assert client.get(f'/sante/declarations/{d.id}/audio/{d.audio}').status_code == 200
    assert a.numero in client.get('/').get_data(as_text=True)          # encadré Alertes
    client.post('/auth/deconnexion')
    connecter(client, 'veto2')
    assert 'Diarrhée' not in client.get('/sante/declarations').get_data(as_text=True)
    assert client.get(photo).status_code == 403
    client.post('/auth/deconnexion')
    # Agent : transmis aux SEULS vétérinaires (question ouverte dans le rapport)
    connecter(client, 'agent1')
    assert client.get('/sante/declarations').status_code == 403
    assert client.get(photo).status_code == 403


def test_declaration_controles(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = declarer(client, b, signes=[]).get_data(as_text=True)
    assert 'au moins un signe' in page
    page = declarer(client, b, photos=[(io.BytesIO(b'pas une image'), 'x.jpg')]).get_data(as_text=True)
    assert 'pas reconnu' in page and Declaration.query.count() == 0


def test_declaration_par_l_agent(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'agent1')
    declarer(client, b)
    d = Declaration.query.one()
    assert d.saisi_par_agent
    assert 'Déclaration sanitaire' in JournalAudit.query.filter_by(action='POUR_ELEVEUR').order_by(
        JournalAudit.id.desc()).first().detail


# ── Alertes ─────────────────────────────────────────────────────────────

def test_qualification_par_le_veto_et_visibilite_dge(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    declarer(client, b)
    a = AlerteSanitaire.query.one()
    client.post('/auth/deconnexion')
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    assert client.get(f'/sante/alertes/{a.numero}').status_code == 403      # pas encore confirmée
    assert a.numero not in client.get('/sante/alertes?statut=toutes').get_data(as_text=True)
    client.post('/auth/deconnexion')
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    page = client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    assert 'Commentaire' not in page                                          # l'ADMIN ne qualifie pas
    client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.EN_ANALYSE, 'commentaire': 'x'})
    assert db.session.get(AlerteSanitaire, a.id).statut == SA.NOUVELLE
    client.post('/auth/deconnexion')
    connecter(client, 'veto')
    r = client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.CONFIRMEE, 'commentaire': 'trop tôt'},
                    follow_redirects=True)
    assert "n&#39;est pas possible" in r.get_data(as_text=True)
    r = client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.EN_ANALYSE, 'commentaire': ''},
                    follow_redirects=True)
    assert 'commentaire est obligatoire' in r.get_data(as_text=True)
    client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.EN_ANALYSE, 'commentaire': 'Visite demain'})
    client.post(f'/sante/alertes/{a.numero}', data={'statut': SA.CONFIRMEE, 'commentaire': 'Coccidiose'})
    a = db.session.get(AlerteSanitaire, a.id)
    assert a.statut == SA.CONFIRMEE and a.confirmee and [h.statut for h in a.historique] == [
        SA.NOUVELLE, SA.EN_ANALYSE, SA.CONFIRMEE]
    client.post('/auth/deconnexion')
    connecter(client, 'dge')
    assert a.numero in client.get('/sante/alertes').get_data(as_text=True)
    assert a.numero in client.get('/').get_data(as_text=True)               # encadré de la DGE
    assert client.get(f'/sante/alertes/{a.numero}').status_code == 200


def test_feu_rouge_cree_une_seule_alerte(client, monde):
    b = bande_ouverte(monde, effectif=1000, jour=AUJ - timedelta(days=3))
    for i in (1, 2):
        db.session.add(SaisieJour(bande=b, date=b.date_mise_en_place + timedelta(days=i), morts=1))
    db.session.commit()
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '15'})
    a = AlerteSanitaire.query.one()
    assert a.origine == 'FEU_ROUGE' and a.bande_id == b.id and '15 morts' in a.historique[0].commentaire
    client.post(f'/bandes/{b.numero}/saisie', data={'morts': '5', 'ajouter': '1'})
    assert AlerteSanitaire.query.count() == 1


# ── Vaccins ─────────────────────────────────────────────────────────────

def test_calendrier_a_faire_vaccination_et_stock(client, monde):
    db.session.add_all([CalendrierVaccinal(age_jours=7, produit=monde['vaccin'], mode='Eau de boisson'),
                        CalendrierVaccinal(age_jours=8, produit=monde['vaccin'], mode='Eau de boisson')])
    recevoir(monde['f'], [(monde['vaccin'], 2000, 0)])
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=7))
    taches = [t['texte'] for t in sante.a_faire(b)]
    assert 'Vaccin du jour : Vaccin Gumboro (eau de boisson)' in taches
    assert 'Demain : vaccin Vaccin Gumboro (eau de boisson)' in taches
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Vaccin du jour' in page and '/sante/vacciner/' in page
    entree = CalendrierVaccinal.query.filter_by(age_jours=7).one()
    client.post(f'/sante/vacciner/{b.numero}', data={'calendrier': entree.id, 'produit_id': monde['vaccin'].id,
                                                     'mode': 'Eau de boisson', 'nombre': '997'})
    v = Vaccination.query.one()
    assert v.quantite == 997 and v.calendrier_id == entree.id
    stock = {s['produit'].nom: s['stock'] for s in intrants.stock_ferme(monde['f'])}
    assert stock['Vaccin Gumboro'] == 2000 - 997
    etats = {x['calendrier'].age_jours: x['etat'] for x in sante.vaccins_de_la_bande(b)}
    assert etats == {7: 'fait', 8: 'demain'}


def test_vaccin_en_retard_signale_a_l_agent_et_au_veto(client, monde):
    db.session.add(CalendrierVaccinal(age_jours=7, produit=monde['vaccin'], mode='Spray'))
    db.session.commit()
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    for ident in ('agent1', 'veto'):
        connecter(client, ident)
        assert f'{b.numero} · vaccin en retard' in client.get('/').get_data(as_text=True), ident
        client.post('/auth/deconnexion')
    connecter(client, 'agent2')
    assert 'vaccin en retard' not in client.get('/').get_data(as_text=True)


def test_calendrier_modifiable_par_le_veto_seulement(client, monde):
    connecter(client, 'veto')
    page = client.get('/sante/vaccins').get_data(as_text=True)
    assert 'à valider par les vétérinaires' in page and 'Valider le calendrier' in page
    client.post('/sante/calendrier', data={'age_jours': '14', 'produit_id': monde['vaccin'].id, 'mode': 'Spray'})
    assert CalendrierVaccinal.query.one().age_jours == 14
    client.post('/sante/calendrier/valider')
    assert Parametre.query.filter_by(cle='sante.calendrier_valide').one().valeur == 'oui'
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert client.get('/sante/vaccins').status_code == 200
    assert client.post('/sante/calendrier', data={'age_jours': '1'}).status_code == 403


# ── Traitements, délai d'attente ────────────────────────────────────────

def test_traitement_stock_et_delai_d_attente(client, monde):
    recevoir(monde['f'], [(monde['medoc'], 10, 0)])
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    r = client.post(f'/sante/traiter/{b.numero}', data={'produit_id': monde['medoc'].id, 'motif': 'diarrhée',
                                                         'date_debut': AUJ.isoformat(), 'date_fin': AUJ.isoformat(),
                                                         'nombre': '997', 'quantite': '2'}, follow_redirects=True)
    assert "Délai d&#39;attente" in r.get_data(as_text=True)
    assert Traitement.query.one().quantite == 2
    stock = {s['produit'].nom: s['stock'] for s in intrants.stock_ferme(monde['f'])}
    assert stock['Anticoccidien'] == 8
    assert sante.fin_delai_attente(b) == AUJ + timedelta(days=7)
    page = client.get(f'/bandes/{b.numero}/sortie').get_data(as_text=True)
    assert "Délai d'attente en cours" in page
    op = Operateur.query.filter_by(type='Abattoir').one()
    r = client.post(f'/bandes/{b.numero}/sortie', data={'motif': 'Abattoir', 'operateur': op.id, 'nombre': '100',
                                                        'poids_total': '200'}, follow_redirects=True)
    assert 'ATTENTION' in r.get_data(as_text=True)
    assert JournalAudit.query.filter_by(action='DELAI_ATTENTE').count() == 1   # non bloquant, mais journalisé
    assert b.sorties and b.sorties[0].nombre == 100


def test_catalogue_delai_d_attente(client_admin):
    client_admin.post('/administration/catalogue/creer', data={'nom': 'Antibio', 'type': 'Médicament',
                                                               'unite': 'flacons', 'delai_attente_jours': '5'})
    assert Produit.query.filter_by(nom='Antibio').one().delai_attente_jours == 5


@pytest.mark.parametrize('profil', [Profil.BCEG, Profil.MAEDR, Profil.OPERATEUR, Profil.AUDITEUR])
def test_pas_d_acces(client, monde, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    for url in ('/sante/alertes', '/sante/declarations', '/sante/vaccins'):
        assert client.get(url).status_code == 403
