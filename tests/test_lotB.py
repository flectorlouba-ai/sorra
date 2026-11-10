"""Lot B — moteur d'imports Excel / CSV : modèle téléchargeable, lecture .xlsx et .csv, correspondance proposée puis mémorisée,
aperçu, vérification ligne à ligne (règles existantes), import en un lot, rapport Excel, annulation (archivage), journal,
droits (ADMIN et DGE seulement)."""
import io
from datetime import timedelta

from openpyxl import Workbook, load_workbook

from app import db
from app.models import JournalAudit, Profil
from app.models.bande import Bande
from app.models.imports import CorrespondanceImport, LotImport
from app.services import imports
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, AUJ  # noqa: F401


def _xlsx(entetes, lignes):
    wb = Workbook()
    ws = wb.active
    ws.append(entetes)
    for l in lignes:
        ws.append(l)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_modeles_et_lecture(client, monde):
    creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    r = client.get('/imports/')
    assert r.status_code == 200 and 'Imports Excel / CSV' in r.get_data(as_text=True) and 'Lots d' in r.get_data(as_text=True)
    r = client.get('/imports/modele/bandes.xlsx')
    assert r.status_code == 200
    ws = load_workbook(io.BytesIO(r.data)).active
    assert [c.value for c in ws[1]][:3] == ['N° de ferme *', 'Bâtiment (code) *', 'Mise en place (AAAA-MM-JJ) *']
    entetes, lignes = imports.lire('N° de ferme;Bâtiment;Mise en place\nEST-001;B1;2026-05-01\n'.encode('utf-8'), 'x.csv')
    assert entetes == ['N° de ferme', 'Bâtiment', 'Mise en place'] and lignes == [(2, ['EST-001', 'B1', '2026-05-01'])]
    corresp = imports.correspondance('bandes', entetes)
    assert corresp == {'N° de ferme': 'ferme', 'Bâtiment': 'batiment', 'Mise en place': 'date_mise_en_place'}


def test_import_de_bandes_puis_annulation(client, monde):
    admin = creer_utilisateur('admin', Profil.ADMIN)
    connecter(client, 'admin')
    f = monde['f']
    debut = (AUJ - timedelta(days=30)).isoformat()
    contenu = _xlsx(['Ferme', 'Batiment', 'Date', 'Poussins', 'Morts déjà comptés', 'Poids'],
                    [[f.numero, 'B1', debut, 500, 10, 40], [f.numero, 'B2', debut, 300, None, None],
                     ['XXX-999', 'B1', debut, 100, None, None], [f.numero, 'B9', debut, 100, None, None]])
    # Aperçu : correspondance proposée (par le nom), « Poussins » → effectif à confirmer à la main
    r = client.post('/imports/apercu', data={'modele': 'bandes', 'fichier': (io.BytesIO(contenu), 'bandes.xlsx')}, content_type='multipart/form-data')
    page = r.get_data(as_text=True)
    assert r.status_code == 200 and 'Aperçu · bandes.xlsx · 4 ligne(s)' in page and 'data-correspondance="Ferme"' in page
    # Vérification avec la correspondance confirmée
    corresp = {'col_0': 'ferme', 'col_1': 'batiment', 'col_2': 'date_mise_en_place', 'col_3': 'effectif', 'col_4': 'morts_cumules', 'col_5': 'poids_g'}
    r = client.post('/imports/verifier', data=corresp)
    page = r.get_data(as_text=True)
    assert '2 ligne(s) prête(s) sur 4' in page and 'ferme inconnue' in page and 'inconnu pour' in page
    assert CorrespondanceImport.query.filter_by(modele='bandes', entete='Poussins').one().colonne == 'effectif'   # mémorisée
    assert imports.correspondance('bandes', ['Poussins'])['Poussins'] == 'effectif'
    # Import
    r = client.post('/imports/importer', follow_redirects=True)
    lot = LotImport.query.one()
    assert lot.nb_importees == 2 and lot.nb_lignes == 4 and len(lot.lignes) == 2
    bandes = Bande.query.filter_by(ferme_id=f.id).all()
    assert len(bandes) == 2 and all(b.rattrapage for b in bandes) and {b.effectif_initial for b in bandes} == {500, 300}
    page = r.get_data(as_text=True)
    assert f'Import n° {lot.id}' in page and '2 ligne(s) importée(s) sur 4' in page
    assert JournalAudit.query.filter(JournalAudit.action == 'IMPORT').count() == 1
    r = client.get(f'/imports/lots/{lot.id}/rapport.xlsx')
    ws = load_workbook(io.BytesIO(r.data)).active
    assert ws['B2'].value == 'Résultat' and sum(1 for row in ws.iter_rows(min_row=3, values_only=True) if row[1] == 'refusée') == 2
    # Annulation : les bandes créées sont archivées, jamais supprimées
    r = client.post(f'/imports/lots/{lot.id}/annuler', data={'motif': ''}, follow_redirects=True)
    assert 'Indiquez le motif' in r.get_data(as_text=True)
    r = client.post(f'/imports/lots/{lot.id}/annuler', data={'motif': 'fichier erroné'}, follow_redirects=True)
    assert lot.annule_le is not None and '2 enregistrement(s) archivé(s)' in r.get_data(as_text=True)
    from app.models.base import AVEC_ARCHIVES
    toutes = Bande.query.execution_options(**{AVEC_ARCHIVES: True}).filter_by(ferme_id=f.id).all()
    assert len(toutes) == 2 and all(b.archive_le is not None for b in toutes) and Bande.query.filter_by(ferme_id=f.id).count() == 0
    assert JournalAudit.query.filter(JournalAudit.detail.contains("Lot d'import")).count() == 1
    r = client.post(f'/imports/lots/{lot.id}/annuler', data={'motif': 'encore'}, follow_redirects=True)
    assert 'déjà annulé' in r.get_data(as_text=True)


def test_import_saisies_et_depenses_csv(client, monde):
    from tests.test_bandes import bande_ouverte
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=10))
    creer_utilisateur('dge', Profil.DGE)
    connecter(client, 'dge')
    csv = f"N° de bande;Jour;Morts;Sacs d'aliment;Aliment\n{b.numero};{(AUJ - timedelta(days=2)).isoformat()};3;2;{monde['aliment'].nom}\n{b.numero};{(AUJ + timedelta(days=1)).isoformat()};1;;\n"
    client.post('/imports/apercu', data={'modele': 'saisies', 'fichier': (io.BytesIO(csv.encode('utf-8')), 'saisies.csv')}, content_type='multipart/form-data')
    r = client.post('/imports/verifier', data={'col_0': 'bande', 'col_1': 'date', 'col_2': 'morts', 'col_3': 'sacs', 'col_4': 'aliment'})
    assert '1 ligne(s) prête(s) sur 2' in r.get_data(as_text=True) and 'jour hors de la bande' in r.get_data(as_text=True)
    client.post('/imports/importer')
    s = next(x for x in b.saisies if x.date == AUJ - timedelta(days=2))
    assert s.morts == 3 and s.sacs == 2
    csv = f"Ferme,Jour,Pour quoi ?,Montant\n{monde['f'].numero},{AUJ.isoformat()},⚡ Électricité,15000\n"
    client.post('/imports/apercu', data={'modele': 'depenses', 'fichier': (io.BytesIO(csv.encode('utf-8')), 'dep.csv')}, content_type='multipart/form-data')
    client.post('/imports/verifier', data={'col_0': 'ferme', 'col_1': 'date', 'col_2': 'categorie', 'col_3': 'montant'})
    client.post('/imports/importer')
    from app.models.argent import Depense
    assert Depense.query.filter_by(ferme_id=monde['f'].id, montant_fcfa=15000).count() == 1
    assert LotImport.query.count() == 2


def test_imports_reserves_a_l_admin_et_la_dge(client, monde):
    for ident in ('agent1', 'eleveur1'):
        connecter(client, ident)
        assert client.get('/imports/').status_code == 403
        client.post('/auth/deconnexion')
    creer_utilisateur('veto', Profil.VETO, ['EST'])
    connecter(client, 'veto')
    assert client.get('/imports/').status_code == 403
