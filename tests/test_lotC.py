"""Lot C — indicateurs : mortalité et viabilité à 5 niveaux (formules dans app/indicateurs.py), participation à
l'objectif national, « Mes indicateurs » par profil avec 3 courbes sur 52 semaines (trous, jamais zéro), périmètres."""
from datetime import timedelta

import pytest

from app import db, indicateurs as ind
from app.models import Profil, Province
from app.services import bandes as regles, mes_indicateurs
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401


def saisir(b, jour, morts, user):
    regles.saisir(b, jour, morts, {}, user)
    db.session.commit()


# ── Formules ────────────────────────────────────────────────────────────

def test_mortalite_et_viabilite_agregees(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))       # 997 poussins mis en place
    saisir(b, AUJ - timedelta(days=2), 7, monde['el'])
    r = ind.mortalite_viabilite([b])
    assert r['morts'] == 7 and r['mis_en_place'] == 997
    assert r['mortalite'] == pytest.approx(7 * 100 / 997) and r['viabilite'] == pytest.approx(100 - 7 * 100 / 997)
    assert ind.mortalite_viabilite([])['mortalite'] is None                  # rien à calculer : pas zéro


def test_semaines_et_trous(app):
    sem = ind.semaines()
    assert len(sem) == 52 and sem[-1][0] <= AUJ <= sem[-1][1] and sem[0][0].weekday() == 0
    assert ind.serie_somme_hebdo([]) == [None] * 52                          # semaine sans donnée = trou
    serie = ind.serie_compte_hebdo([AUJ - timedelta(weeks=3)])
    assert serie[:48] == [None] * 48 and serie[48] == 1 and serie[49:] == [0, 0, 0]


def test_serie_mortalite_hebdo_trou_sans_saisie(client, monde):
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=20))
    saisir(b, AUJ - timedelta(days=1), 10, monde['el'])
    serie = ind.serie_mortalite_hebdo([b])
    assert serie[-1] is not None or serie[-2] is not None
    assert serie[0] is None                                                  # bien avant la bande : trou
    connues = [v for v in serie if v is not None]
    assert connues and connues[-1] == pytest.approx(10 * 100 / 997)


# ── 5 niveaux ───────────────────────────────────────────────────────────

def test_niveaux_national_province_cohorte_ferme_bande(client_admin, monde):
    b = bande_ouverte(monde)
    saisir(b, AUJ, 5, monde['el'])
    monde['f'].cohorte = 1
    db.session.commit()
    page = client_admin.get('/indicateurs/niveaux').get_data(as_text=True)
    assert 'data-niveau="national"' in page and 'Estuaire' in page and '>Province<' in page
    est = Province.query.filter_by(code='EST').one()
    page = client_admin.get(f'/indicateurs/niveaux?niveau=province&province={est.id}').get_data(as_text=True)
    assert 'Cohorte 1' in page and '>Cohorte<' in page
    page = client_admin.get(f'/indicateurs/niveaux?niveau=cohorte&province={est.id}&cohorte=1').get_data(as_text=True)
    assert monde['f'].numero in page and '>Ferme<' in page
    page = client_admin.get(f'/indicateurs/niveaux?niveau=ferme&ferme={monde["f"].numero}').get_data(as_text=True)
    assert b.numero in page and '>Bande<' in page and '0,5 %' in page      # 5 / 997


def test_niveaux_dans_le_perimetre(client, monde):
    autre = creer_utilisateur('agent_hog', Profil.AGENT, ['HOG'])
    connecter(client, 'agent_hog')
    page = client.get('/indicateurs/niveaux').get_data(as_text=True)
    assert monde['f'].numero not in page and 'Estuaire' not in page
    assert client.get(f'/indicateurs/niveaux?niveau=ferme&ferme={monde["f"].numero}').status_code == 404
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert 'Estuaire' in client.get('/indicateurs/niveaux').get_data(as_text=True)


# ── Mes indicateurs par profil ──────────────────────────────────────────

@pytest.mark.parametrize('ident, profil', [('eleveur1', None), ('agent1', None), ('veto', Profil.VETO),
                                           ('dge', Profil.DGE), ('admin2', Profil.ADMIN)])
def test_mes_indicateurs_par_profil(client, monde, ident, profil):
    if profil:
        creer_utilisateur(ident, profil, ['EST'])
    b = bande_ouverte(monde)
    saisir(b, AUJ, 3, monde['el'])
    connecter(client, ident)
    page = client.get('/mes-indicateurs').get_data(as_text=True)
    assert page.count('data-courbe=') == 3 and 'data-mes-indicateurs' in page
    assert 'jamais comptée comme zéro' in page


def test_nombre_d_indicateurs_cles(client, monde):
    for profil, ident in ((Profil.VETO, 'veto'), (Profil.DGE, 'dge'), (Profil.ADMIN, 'admin2')):
        creer_utilisateur(ident, profil, ['EST'])
    bande_ouverte(monde)
    from app.models import Utilisateur
    for ident in ('eleveur1', 'agent1', 'veto', 'dge', 'admin2'):
        d = mes_indicateurs.pour(Utilisateur.query.filter_by(identifiant=ident).one())
        assert 4 <= len(d['cartes']) + len(d['courbes']) and len(d['courbes']) == 3, ident
        assert 5 <= len(d['cartes']) + 3 <= 11, ident


def test_veterinaire_sans_donnee_financiere(client, monde):
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    bande_ouverte(monde)
    connecter(client, 'veto')
    page = client.get('/mes-indicateurs').get_data(as_text=True)
    assert 'FCFA' not in page and 'Gagné' not in page
    page = client.get('/indicateurs/niveaux').get_data(as_text=True)
    assert 'FCFA' not in page


def test_lien_mes_indicateurs_dans_moi_sans_changer_les_tuiles(client, monde):
    connecter(client, 'eleveur1')
    assert '/mes-indicateurs' in client.get('/moi').get_data(as_text=True)
    client.post('/auth/deconnexion')
    connecter(client, 'agent1')
    assert '/mes-indicateurs' in client.get('/terrain/moi').get_data(as_text=True)
