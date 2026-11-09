"""Numérotation, mixin hors ligne, paramètres."""
import uuid
from datetime import datetime, timezone

import pytest

from app import db
from app.models import SaisieTerrainMixin, StatutSynchro, Compteur
from app.services.numerotation import generer_numero
from app.services.parametres import normaliser, obtenir
from app.models.parametre import TypeParametre


class EssaiSaisie(SaisieTerrainMixin, db.Model):
    """Table d'essai : sert seulement à vérifier le mixin."""
    __tablename__ = 'essai_saisie'
    libelle = db.Column(db.String(50))


def test_numeros_qui_se_suivent(app):
    assert generer_numero('FERME', 'EST') == 'EST-000001'
    assert generer_numero('FERME', 'EST') == 'EST-000002'
    assert generer_numero('FERME', 'HOG') == 'HOG-000001'
    assert generer_numero('LOT', 'EST') == 'EST-000001'
    annee = datetime.now(timezone.utc).year
    assert generer_numero('DECL', 'DS', annuel=True) == f'DS-{annee}-000001'
    db.session.commit()
    assert Compteur.query.filter_by(type='FERME', prefixe='EST').one().dernier_numero == 2


def test_numero_jamais_reutilise(app):
    n1 = generer_numero('FERME', 'EST')
    db.session.commit()
    n2 = generer_numero('FERME', 'EST')
    db.session.commit()
    assert n1 != n2


def test_numerotation_non_journalisee(app):
    from app.models import JournalAudit
    generer_numero('FERME', 'EST')
    db.session.commit()
    assert JournalAudit.query.filter_by(table_nom='compteur').count() == 0


def test_mixin_hors_ligne(client_admin, admin):
    with client_admin.application.test_request_context():
        from flask_login import login_user
        login_user(admin)
        e = EssaiSaisie(libelle='essai')
        db.session.add(e)
        db.session.commit()
        assert isinstance(e.id, uuid.UUID)
        assert e.cree_par == admin.id and e.modifie_par == admin.id
        assert e.statut_synchro == StatutSynchro.SYNCHRONISE
        assert e.numero_provisoire is False and e.cree_le is not None


def test_mixin_id_fourni_par_l_appareil(app):
    uid = uuid.uuid4()
    e = EssaiSaisie(id=uid, libelle='terrain', appareil_id='tel-01',
                    statut_synchro=StatutSynchro.LOCAL, numero_metier='TMP-1', numero_provisoire=True)
    db.session.add(e)
    db.session.commit()
    assert db.session.get(EssaiSaisie, uid).appareil_id == 'tel-01'


@pytest.mark.parametrize('type_,texte,attendu', [
    (TypeParametre.ENTIER, ' 12 ', '12'), (TypeParametre.JOURS, '45', '45'),
    (TypeParametre.DECIMAL, '2,5', '2.5'), (TypeParametre.BOOLEEN, 'Oui', 'oui'),
    (TypeParametre.TEXTE, ' abc ', 'abc')])
def test_parametres_valeurs_valides(type_, texte, attendu):
    assert normaliser(type_, texte) == attendu


@pytest.mark.parametrize('type_,texte', [
    (TypeParametre.ENTIER, 'dix'), (TypeParametre.JOURS, '-1'),
    (TypeParametre.DECIMAL, 'x'), (TypeParametre.BOOLEEN, 'peut-être')])
def test_parametres_valeurs_refusees(type_, texte):
    with pytest.raises(ValueError):
        normaliser(type_, texte)


def test_obtenir_parametre(app):
    assert obtenir('securite.mdp_longueur_min') == 10
    assert obtenir('inconnu', 'défaut') == 'défaut'


def test_horloge_des_tests_figee():
    """Les tests tournent à une date fixe (tests/conftest.py) : rien ne dépend du jour réel."""
    from datetime import date
    from tests.conftest import JOUR_DES_TESTS
    from tests.test_bandes import AUJ
    assert date.today().isoformat() == JOUR_DES_TESTS[:10] == AUJ.isoformat()
