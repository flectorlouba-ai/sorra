"""Lot 6 — traçabilité : lots et QR codes."""
from app import db
from app.models import Profil, JournalAudit, Operateur, Parametre
from app.models.tracabilite import LotTrace
from app.services import bandes as regles, tracabilite
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def sortir(m, b, motif='Abattoir', nombre=100, user=None):
    op = Operateur.query.filter_by(type='Abattoir').one() if motif == 'Abattoir' else None
    s = regles.sortir(b, AUJ, motif, op, 'Marché de Ntoum' if motif != 'Abattoir' else '', nombre, nombre * 2,
                      user or m['el'])
    db.session.commit()
    return s


def test_un_lot_par_sortie_abattoir_ou_vente_jamais_reutilise(monde):
    b = bande_ouverte(monde)
    s1 = sortir(monde, b)
    s2 = sortir(monde, b, 'Vente')
    s3 = sortir(monde, b, 'Autre')
    assert s1.lot.numero == 'EST-001-B1-01-S1' and s2.lot.numero == 'EST-001-B1-01-S2' and s3.lot is None
    assert len(s1.lot.code) >= 20 and s1.lot.code != s2.lot.code
    tracabilite.annuler(s2.lot, 'erreur de saisie')
    db.session.commit()
    s4 = sortir(monde, b, 'Vente')
    assert s4.lot.numero == 'EST-001-B1-01-S3'   # le rang d'un lot annulé n'est jamais repris
    assert tracabilite.adresse(s1.lot) == f'http://187.124.217.218:5021/q/{s1.lot.code}'


def test_page_publique_sans_connexion_et_sans_donnee_personnelle(client, monde):
    monde['f'].exploitant_nom = 'Jean Obiang'
    monde['f'].exploitant_telephone = '+241 77 12 34 56'
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    page = client.get(f'/q/{lot.code}')
    texte = page.get_data(as_text=True)
    assert page.status_code == 200
    for attendu in ('Ferme Un', 'Ntoum', 'Estuaire', AUJ.strftime('%d/%m/%Y'), 'Produit au Gabon',
                    'Consommons gabonais', "n'est pas un certificat sanitaire", 'Élevé par', lot.numero):
        assert attendu in texte, attendu   # n° du lot affiché depuis le lot 8
    for interdit in ('Obiang', '77 12', 'Paul', 'Abattoir de Ntoum', 'Identifiant'):
        assert interdit not in texte, interdit
    journal = JournalAudit.query.filter_by(action='LECTURE_QR').one()
    assert journal.enregistrement_id == str(lot.id) and journal.adresse_ip and journal.utilisateur_id is None


def test_code_inconnu_ou_lot_annule(client, monde):
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    for code in ('nimportequoi123', 'x', '<script>', lot.code[:-1] + ('A' if lot.code[-1] != 'A' else 'B')):
        r = client.get(f'/q/{code}')
        assert r.status_code == 404 and 'Code inconnu' in r.get_data(as_text=True)
    tracabilite.annuler(lot, 'erreur')
    db.session.commit()
    r = client.get(f'/q/{lot.code}')
    assert r.status_code == 404 and 'Code inconnu' in r.get_data(as_text=True) and 'Ferme Un' not in r.get_data(as_text=True)
    assert JournalAudit.query.filter_by(action='LECTURE_QR').count() == 5


def test_code_masque_dans_le_journal(monde):
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    lignes = JournalAudit.query.filter_by(table_nom='lot_trace', action='CREATION').all()
    assert lignes and all(lot.code not in str(j.apres) + str(j.detail) for j in lignes)


def test_pages_internes_selon_le_perimetre(client, monde):
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    connecter(client, 'agent1')
    assert lot.numero in client.get('/tracabilite/lots').get_data(as_text=True)
    page = client.get(f'/tracabilite/lots/{lot.numero}').get_data(as_text=True)
    assert 'Imprimer les étiquettes' in page and '<svg' in page and 'Annuler ce lot' not in page
    r = client.get(f'/tracabilite/lots/{lot.numero}/etiquettes.pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF'
    assert JournalAudit.query.filter_by(action='EXPORT', table_nom='lot_trace').count() == 1
    assert lot.numero in client.get(f'/bandes/{b.numero}').get_data(as_text=True)   # depuis la sortie
    creer_utilisateur('agent3', Profil.AGENT, ['EST'])
    creer_utilisateur('veto1', Profil.VETO, ['EST'])
    creer_utilisateur('veto2', Profil.VETO, ['HOG'])
    db.session.commit()
    changer(client, 'agent3')   # pas sa ferme
    assert client.get(f'/tracabilite/lots/{lot.numero}').status_code == 404
    changer(client, 'veto1')
    assert client.get(f'/tracabilite/lots/{lot.numero}').status_code == 200
    assert 'data-fonction="tracabilite"' in client.get('/').get_data(as_text=True)     # lot R : bouton Traçabilité
    changer(client, 'veto2')
    assert lot.numero not in client.get('/tracabilite/lots').get_data(as_text=True)
    changer(client, 'eleveur1')
    assert client.get('/tracabilite/lots').status_code == 403


def test_annulation_par_l_admin_avec_motif(client, client_admin, monde):
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    page = client.get(f'/tracabilite/lots/{lot.numero}').get_data(as_text=True)
    assert 'Annuler ce lot' in page
    client.post(f'/tracabilite/lots/{lot.numero}/annuler', data={'motif': ''})
    assert not db.session.get(LotTrace, lot.id).annule
    client.post(f'/tracabilite/lots/{lot.numero}/annuler', data={'motif': 'Poulets restés à la ferme'})
    db.session.refresh(lot)
    assert lot.annule and JournalAudit.query.filter_by(action='ANNULATION', table_nom='lot_trace').count() == 1
    assert 'Imprimer les étiquettes' not in client.get(f'/tracabilite/lots/{lot.numero}').get_data(as_text=True)
    assert client.get(f'/tracabilite/lots/{lot.numero}/etiquettes.pdf').status_code == 302
    changer(client, 'agent1')
    assert client.post(f'/tracabilite/lots/{lot.numero}/annuler', data={'motif': 'x'}).status_code == 403


def test_adresse_publique_reglable(monde):
    Parametre.query.filter_by(cle='tracabilite.adresse_publique').one().valeur = 'https://yl2.example.ga/'
    db.session.commit()
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    assert tracabilite.adresse(lot) == f'https://yl2.example.ga/q/{lot.code}'
    assert tracabilite.svg(tracabilite.adresse(lot)).startswith('<svg')


def test_avertissement_adresse_provisoire(client, client_admin, monde):
    b = bande_ouverte(monde)
    lot = sortir(monde, b).lot
    page = client.get(f'/tracabilite/lots/{lot.numero}').get_data(as_text=True)
    assert 'Adresse provisoire : ne pas imprimer pour de vrai.' in page and '187.124.217.218' in page
    # La fiche de la bande mène à cet écran, pas directement au PDF
    fiche = client.get(f'/bandes/{b.numero}').get_data(as_text=True)
    assert f'/tracabilite/lots/{lot.numero}"' in fiche and 'etiquettes.pdf' not in fiche
    p = Parametre.query.filter_by(cle='tracabilite.adresse_publique').one()
    for adresse, provisoire in (('http://localhost:5021', True), ('https://187.124.217.218', False),
                                ('https://performyl2.ga', False), ('http://performyl2.ga', False)):
        p.valeur = adresse
        db.session.commit()
        assert tracabilite.adresse_provisoire() is provisoire, adresse
    assert 'Adresse provisoire' not in client.get(f'/tracabilite/lots/{lot.numero}').get_data(as_text=True)
