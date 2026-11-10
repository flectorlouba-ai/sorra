"""Lot M — BCEG (fermes financées avec accord : accueil, tableau, bilan ; rien sans accord) et MAEDR (agrégats nationaux sans
ferme nommée, rapports soumis par la DGE, visa / refus journalisé)."""
import html
from datetime import timedelta

from app import db
from app.models import JournalAudit, Profil
from app.models.rapport import Rapport, TypeRapport
from app.services import bceg, maedr, rapports
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401


def test_bceg_ne_voit_que_les_fermes_avec_accord(client, monde):
    banque = creer_utilisateur('banque', Profil.BCEG)
    f = monde['f']
    bande_ouverte(monde)
    connecter(client, 'banque')
    page = html.unescape(client.get('/').get_data(as_text=True))
    assert 'Fermes financées' in page and 'Avec accord de l’éleveur' in page and "n'a donné son accord" in page
    assert client.get('/bceg/fermes').status_code == 200
    assert client.get(f'/mon-argent/bilan.pdf?ferme={f.numero}').status_code == 403
    # Financée + accord de l'éleveur → visible, bilan accessible
    bceg.regler(f, True, monde['el'], monde['agent'])
    bceg.repondre(f, monde['el'], 'ACCEPTE')
    db.session.commit()
    page = client.get('/bceg/fermes').get_data(as_text=True)
    assert f.numero in page and '✓ en cours' in page and 'Recettes 12 mois' in page
    assert client.get(f'/mon-argent/bilan.pdf?ferme={f.numero}').status_code == 200
    # Accord retiré → plus rien
    bceg.repondre(f, monde['el'], 'RETIRE')
    db.session.commit()
    assert f.numero not in client.get('/bceg/fermes').get_data(as_text=True)
    assert client.get(f'/mon-argent/bilan.pdf?ferme={f.numero}').status_code == 403


def test_maedr_agregats_et_visa(client, monde):
    dge = creer_utilisateur('dge', Profil.DGE)
    ministere = creer_utilisateur('ministere', Profil.MAEDR)
    bande_ouverte(monde)
    connecter(client, 'ministere')
    page = client.get('/').get_data(as_text=True)
    assert 'Production nationale 12 mois' in page and 'Rapports à viser' in page and 'Estuaire' in page
    assert monde['f'].nom not in page and monde['f'].numero not in page                      # jamais une ferme nommée
    assert 'Aucun rapport soumis' in client.get('/maedr/visas').get_data(as_text=True)
    # La DGE génère un rapport national et le soumet
    from app.services.dge import mois_termines
    r, _ = rapports.generer(TypeRapport.NATIONAL, mois_termines(1)[0], dge)
    db.session.commit()
    client.post('/auth/deconnexion')
    connecter(client, 'dge')
    page = client.get('/rapports/standards').get_data(as_text=True)
    assert 'Soumettre au visa MAEDR' in page and 'Interne' in page
    resp = client.post(f'/bureau/fiche/DGE-7/{r.id}', data={'action': 'modifier', 'retour': '/rapports/standards'}, follow_redirects=True)
    assert r.diffusion == 'SOUMIS' and 'soumis au visa' in resp.get_data(as_text=True)
    assert maedr.n_a_viser() == 1
    # Le MAEDR refuse sans motif → refusé ; puis valide
    client.post('/auth/deconnexion')
    connecter(client, 'ministere')
    page = client.get('/maedr/visas').get_data(as_text=True)
    assert r.periode in page and 'Soumis au MAEDR' in page and 'data-bouton="modifier">Viser' in page
    resp = client.post(f'/bureau/fiche/MAEDR-2/{r.id}', data={'action': 'modifier', 'Diffusion': 'refuser', 'Motif': '', 'retour': '/maedr/visas'}, follow_redirects=True)
    assert r.diffusion == 'SOUMIS' and 'motif du refus' in resp.get_data(as_text=True)
    resp = client.post(f'/bureau/fiche/MAEDR-2/{r.id}', data={'action': 'modifier', 'Diffusion': 'valider', 'retour': '/maedr/visas'}, follow_redirects=True)
    assert r.diffusion == 'VALIDE' and r.vise_par == ministere.id
    assert JournalAudit.query.filter(JournalAudit.action == 'APPROBATION', JournalAudit.detail.contains('Visa MAEDR')).count() == 1
    assert client.get(f'/rapports/standards/{r.id}.pdf').status_code == 200
    # La DGE voit la diffusion et la date du visa
    client.post('/auth/deconnexion')
    connecter(client, 'dge')
    page = client.get('/rapports/standards').get_data(as_text=True)
    assert 'Diffusable (visa MAEDR)' in page
    # Un rapport de ferme ne se soumet pas
    b = monde['f']
    rf = Rapport.query.filter_by(type=TypeRapport.FERME).first()
    if rf is not None:
        resp = client.post(f'/bureau/fiche/DGE-7/{rf.id}', data={'action': 'modifier'}, follow_redirects=True)
        assert rf.diffusion is None


def test_maedr_et_bceg_sans_donnees_des_autres(client, monde):
    creer_utilisateur('ministere', Profil.MAEDR)
    connecter(client, 'ministere')
    assert client.get('/fermes/').status_code == 403
    assert client.get('/imports/').status_code == 403
    assert client.get('/mon-argent/bilan.pdf?ferme=EST-001').status_code == 403
