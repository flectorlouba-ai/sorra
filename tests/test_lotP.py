"""Lot P — code PIN du terrain (réglage avec le mot de passe, règles de simplicité, connexion par code, 5 échecs → coupé,
retrait), file de synchronisation (ADMIN / DGE, consultation journalisée), guides PDF par profil (le sien ; tous pour
l'ADMIN), liens sur Moi et dans la zone titre."""
from app import db
from app.models import JournalAudit, Profil
from app.services import terrain_p
from tests.conftest import connecter, creer_utilisateur, MDP
from tests.test_bandes import monde  # noqa: F401


def test_code_du_terrain_reglage_connexion_et_coupure(client, monde):
    el = monde['el']
    connecter(client, 'eleveur1')
    page = client.get('/moi').get_data(as_text=True)
    assert 'data-moi="code"' in page and 'entrer plus vite' in page and 'data-moi="guide"' in page
    r = client.post('/auth/mon-code', data={'code': '1234', 'confirmation': '1234', 'mot_de_passe': MDP})
    assert 'trop simple' in r.get_data(as_text=True)
    r = client.post('/auth/mon-code', data={'code': '2719', 'confirmation': '2710', 'mot_de_passe': MDP})
    assert 'ne sont pas les mêmes' in r.get_data(as_text=True)
    r = client.post('/auth/mon-code', data={'code': '2719', 'confirmation': '2719', 'mot_de_passe': 'faux'})
    assert 'mot de passe est incorrect' in r.get_data(as_text=True)
    r = client.post('/auth/mon-code', data={'code': '2719', 'confirmation': '2719', 'mot_de_passe': MDP}, follow_redirects=True)
    assert el.pin_hash and el.check_pin('2719') and 'Code enregistré' in r.get_data(as_text=True)
    assert JournalAudit.query.filter(JournalAudit.detail == 'Code du terrain réglé').count() == 1
    client.post('/auth/deconnexion')
    # Connexion par code
    page = client.get('/auth/connexion').get_data(as_text=True)
    assert 'Entrer avec mon code' in page
    r = client.post('/auth/code', data={'identifiant': 'eleveur1', 'code': '0000'})
    assert r.status_code == 200 and 'Code refusé' in r.get_data(as_text=True) and el.pin_echecs == 1
    r = client.post('/auth/code', data={'identifiant': 'eleveur1', 'code': '2719'})
    assert r.status_code == 302 and el.pin_echecs == 0
    assert client.get('/').status_code == 200
    client.post('/auth/deconnexion')
    for _ in range(5):
        client.post('/auth/code', data={'identifiant': 'eleveur1', 'code': '9999'})
    assert el.pin_echecs == 5
    r = client.post('/auth/code', data={'identifiant': 'eleveur1', 'code': '2719'})
    assert r.status_code == 200                                               # coupé : même le bon code est refusé
    assert JournalAudit.query.filter(JournalAudit.action == 'BLOCAGE', JournalAudit.detail.contains('Code du terrain coupé')).count() == 1
    connecter(client, 'eleveur1')                                             # le mot de passe marche toujours
    assert 'coupé après 5 erreurs' in client.get('/auth/mon-code').get_data(as_text=True)
    client.post('/auth/mon-code', data={'retirer': '1'}, follow_redirects=True)
    assert el.pin_hash is None


def test_code_reserve_au_terrain(client, monde):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    assert client.get('/auth/mon-code').status_code == 404
    assert terrain_p.verifier_pin('dge', '1234') is None


def test_file_de_synchronisation_et_guides(client, monde):
    from app.models.hors_ligne import EnvoiHorsLigne
    from app.models.base import maintenant
    import uuid
    from datetime import timedelta
    db.session.add(EnvoiHorsLigne(id=uuid.uuid4(), utilisateur_id=monde['el'].id, appareil_id='tel-1', saisi_le=maintenant() - timedelta(hours=5),
                                  recu_le=maintenant(), adresse='/bandes/X/saisie', objet_table='saisie_jour', objet_id='abc'))
    db.session.commit()
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    page = client.get('/bureau/synchronisation').get_data(as_text=True)
    assert 'File de synchronisation' in page and 'Envois reçus (7 jours)' in page and '/bandes/X/saisie' in page and '5,0 h' in page
    assert JournalAudit.query.filter(JournalAudit.action == 'CONSULTATION', JournalAudit.detail.contains('synchronisation')).count() == 1
    r = client.get('/aide/guide/ELEVEUR.pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert client.get('/aide/guide/DGE.pdf').status_code == 200 and client.get('/aide/guide/XXX.pdf').status_code == 404
    assert JournalAudit.query.filter(JournalAudit.action == 'EXPORT', JournalAudit.detail.contains('Guide PDF')).count() == 2
    assert 'data-guide' in client.get('/').get_data(as_text=True)
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert client.get('/bureau/synchronisation').status_code == 403
    assert client.get('/aide/guide/AGENT.pdf').status_code == 200 and client.get('/aide/guide/DGE.pdf').status_code == 403
