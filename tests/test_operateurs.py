"""Lot 1 — registre des opérateurs."""
import pytest

from app import db
from app.models import Operateur, Profil, JournalAudit
from tests.conftest import creer_utilisateur, connecter, province


def donnees(**champs):
    d = {'nom': 'Abattoir de Ntoum', 'type': 'Abattoir', 'province_id': str(province('EST').id),
         'contact': 'M. Ella', 'telephone': '066 00 00 00'}
    d.update(champs)
    return d


def test_dge_cree_et_modifie(client, app):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    r = client.post('/operateurs/nouveau', data=donnees(convention='on', convention_date='2026-10-01'))
    assert r.location.endswith('/operateurs/OPE-0001')
    client.post('/operateurs/nouveau', data=donnees(nom='Super U', type='Distributeur'))
    assert [o.numero for o in Operateur.query.order_by(Operateur.numero)] == ['OPE-0001', 'OPE-0002']
    op = Operateur.query.filter_by(numero='OPE-0001').one()
    assert op.convention and op.convention_date.isoformat() == '2026-10-01'
    client.post('/operateurs/OPE-0001/modifier', data=donnees())   # convention décochée
    db.session.refresh(op)
    assert op.actif is True and op.convention is False
    client.post('/operateurs/OPE-0001/modifier', data={'archiver': '1'})   # lot A1 : « Archiver »
    db.session.refresh(op)
    assert op.actif is False and op.archive_le is not None
    assert JournalAudit.query.filter_by(table_nom='operateur', action='CREATION').count() == 2
    assert not [r for r in client.application.url_map.iter_rules()
                if r.rule.startswith('/operateurs') and 'supprimer' in r.rule]


def test_champs_obligatoires(client, app):
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    page = client.post('/operateurs/nouveau', data=donnees(nom='', type='Inconnu')).get_data(as_text=True)
    assert 'nom est obligatoire' in page and 'Choisissez le type' in page


def test_agent_lecture_seule_de_ses_provinces(client, app):
    for nom, code in (('Abattoir EST', 'EST'), ('Abattoir HOG', 'HOG')):
        db.session.add(Operateur(numero=f'OPE-{code}', nom=nom, type='Abattoir', province=province(code)))
    db.session.commit()
    creer_utilisateur('agent', Profil.AGENT, ['EST'])
    connecter(client, 'agent')
    page = client.get('/operateurs/').get_data(as_text=True)
    assert 'Abattoir EST' in page and 'Abattoir HOG' not in page and 'Nouvel opérateur' not in page
    assert 'Modifier' not in client.get('/operateurs/OPE-EST').get_data(as_text=True)
    assert client.get('/operateurs/OPE-HOG').status_code == 403
    assert client.get('/operateurs/nouveau').status_code == 403
    assert client.post('/operateurs/OPE-EST/modifier', data=donnees()).status_code == 403


@pytest.mark.parametrize('profil', [Profil.VETO, Profil.ELEVEUR, Profil.BCEG, Profil.OPERATEUR])
def test_autres_profils_sans_acces(client, app, profil):
    creer_utilisateur('x', profil, ['EST'])
    connecter(client, 'x')
    assert client.get('/operateurs/').status_code == 403
