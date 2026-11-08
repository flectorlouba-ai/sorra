import pytest

from app import db
from app.models import JournalAudit, Utilisateur, Localite
from app.models.journal import JournalNonModifiable
from tests.conftest import province


def lignes(action, table=None):
    q = JournalAudit.query.filter_by(action=action)
    if table:
        q = q.filter_by(table_nom=table)
    return q.order_by(JournalAudit.id).all()


def test_creation_utilisateur_journalisee_sans_mot_de_passe(client_admin, admin):
    client_admin.post('/administration/utilisateurs/creer', data={
        'identifiant': 'agent1', 'nom': 'Mba', 'profil': 'AGENT',
        'provinces': [str(province('EST').id)], 'mot_de_passe': 'Provisoire-2026'})
    ligne = lignes('CREATION', 'utilisateur')[-1]
    assert ligne.identifiant == 'admin' and ligne.utilisateur_id == admin.id
    assert ligne.apres['identifiant'] == 'agent1'
    assert ligne.apres['mot_de_passe_hash'] == '***'
    assert ligne.apres['provinces'] == ['EST']
    assert ligne.avant is None
    assert ligne.adresse_ip


def test_modification_avant_apres(client_admin, admin):
    client_admin.post('/administration/utilisateurs/creer', data={
        'identifiant': 'agent1', 'nom': 'Mba', 'profil': 'AGENT',
        'provinces': [str(province('EST').id)], 'mot_de_passe': 'Provisoire-2026'})
    u = Utilisateur.query.filter_by(identifiant='agent1').one()
    client_admin.post(f'/administration/utilisateurs/{u.id}/modifier', data={
        'nom': 'Mba Obame', 'profil': 'AGENT', 'actif': 'on',
        'provinces': [str(province('EST').id), str(province('NGO').id)]})
    ligne = lignes('MODIFICATION', 'utilisateur')[-1]
    assert ligne.avant == {'nom': 'Mba', 'provinces': ['EST']}
    assert ligne.apres == {'nom': 'Mba Obame', 'provinces': ['EST', 'NGO']}


def test_connexion_ne_cree_pas_de_modification(client_admin):
    assert lignes('MODIFICATION', 'utilisateur') == []


def test_suppression_journalisee(app):
    loc = Localite(province=province('EST'), nom='Kango')
    db.session.add(loc)
    db.session.commit()
    db.session.delete(loc)
    db.session.commit()
    ligne = lignes('SUPPRESSION', 'localite')[-1]
    assert ligne.avant['nom'] == 'Kango' and ligne.apres is None


def test_operation_annulee_ne_laisse_pas_de_trace(app):
    db.session.add(Localite(province=province('EST'), nom='Cocobeach'))
    db.session.flush()
    db.session.rollback()
    assert lignes('CREATION', 'localite') == []


def test_journal_non_modifiable_par_l_application(app):
    db.session.add(Localite(province=province('EST'), nom='Kango'))
    db.session.commit()
    ligne = lignes('CREATION', 'localite')[-1]
    ligne.detail = 'falsifié'
    with pytest.raises(JournalNonModifiable):
        db.session.commit()
    db.session.rollback()
    db.session.delete(JournalAudit.query.first())
    with pytest.raises(JournalNonModifiable):
        db.session.commit()
    db.session.rollback()


def test_ecran_et_detail(client_admin):
    page = client_admin.get('/journal/').get_data(as_text=True)
    assert 'Connexion' in page and 'admin' in page
    ligne = lignes('CONNEXION')[-1]
    assert client_admin.get(f'/journal/{ligne.id}').status_code == 200


def test_filtres(client_admin):
    assert 'Aucune ligne' in client_admin.get('/journal/?action=EXPORT').get_data(as_text=True)
    assert 'Aucune ligne' in client_admin.get('/journal/?du=2000-01-01&au=2000-01-02').get_data(as_text=True)
    assert 'Aucune ligne' not in client_admin.get('/journal/?personne=admin').get_data(as_text=True)
    assert client_admin.get('/journal/?du=pas-une-date').status_code == 200


def test_export_csv_journalise(client_admin):
    r = client_admin.get('/journal/export.csv?action=CONNEXION')
    assert r.status_code == 200 and r.mimetype == 'text/csv'
    texte = r.get_data(as_text=True)
    assert texte.startswith('﻿Date;Personne') and 'Connexion' in texte
    export = lignes('EXPORT')[-1]
    assert export.identifiant == 'admin' and 'action=CONNEXION' in export.detail
