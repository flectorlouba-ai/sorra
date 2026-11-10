"""Lot F — œufs d'une bande de ponte : œufs ramassés / cassés dans la saisie du jour (case vide ≠ zéro), stock en plateaux de 30,
taux de ponte, ventes d'œufs (recette de Mon argent, ligne du bilan, fiche du lot A1), chute de ponte (alerte + notification
à l'agent), tuile « 🥚 Mes œufs », réforme. Une bande de chair ne change pas."""
import html
from datetime import timedelta

from app import db
from app.models import JournalAudit, Profil
from app.models.notification import Notification, TypeNotification as T
from app.models.oeufs import VenteOeufs
from app.services import bandes, oeufs, argent, bilan, notifications
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401


def _ponte(monde, jours=20):
    from app.models.base import maintenant
    b = bande_ouverte(monde, jour=AUJ - timedelta(days=jours))
    bandes.typer(b, 'PONTE', None)
    monde['el'].presentation_vue_le = maintenant()          # l'accueil, pas la présentation
    db.session.commit()
    return b


def test_saisie_des_oeufs_case_vide_stock_et_taux(client, monde):
    b = _ponte(monde)
    connecter(client, 'eleveur1')
    r = client.post(f'/bandes/{b.numero}/saisie', data={'jour': AUJ.isoformat(), 'morts': '0', 'sacs': '0'}, follow_redirects=True)
    assert 'Notez les œufs ramassés' in r.get_data(as_text=True)                  # case vide ≠ zéro
    assert oeufs.stock(b) == 0
    r = client.post(f'/bandes/{b.numero}/saisie', data={'jour': AUJ.isoformat(), 'morts': '0', 'sacs': '0', 'oeufs': '800', 'casses': '20'})
    assert r.status_code == 302
    s = b.saisies[-1]
    assert s.oeufs_ramasses == 800 and s.oeufs_casses == 20
    assert oeufs.stock(b) == 780 and oeufs.plateaux(780) == (26, 0)
    assert oeufs.taux_du_jour(b) == round(100 * 800 / 997, 1)
    page = html.unescape(client.get('/', follow_redirects=True).get_data(as_text=True))
    assert 'data-tuile="oeufs"' in page and '26 plateaux en stock' in page
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'data-ponte' in page and 'taux de ponte' in page
    page = client.get('/oeufs').get_data(as_text=True)
    assert '🥚 Mes œufs' in page and '＋ J\'ai vendu des œufs' in page and 'Réformer la bande' in page and '/oeufs' in client.get('/hors-ligne/pages').json['pages']


def test_bande_de_chair_inchangee(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    page = client.get('/saisie-du-jour').get_data(as_text=True)
    assert 'Œufs ramassés' not in page and 'data-tuile="oeufs"' not in client.get('/', follow_redirects=True).get_data(as_text=True)
    r = client.post(f'/bandes/{b.numero}/saisie', data={'jour': AUJ.isoformat(), 'morts': '1', 'sacs': '2', 'aliment_choisi': str(monde['aliment'].id)})
    assert r.status_code == 302 and b.saisies[-1].oeufs_ramasses is None


def test_vente_d_oeufs_argent_bilan_fiche(client, monde):
    b = _ponte(monde)
    bandes.saisir(b, AUJ, 0, {}, monde['el'], oeufs=900, casses=0)
    db.session.commit()
    connecter(client, 'eleveur1')
    r = client.post(f'/oeufs/{b.numero}/vendre', data={'plateaux': '40', 'oeufs': '0', 'montant': '60000', 'acheteur': 'Marché'}, follow_redirects=True)
    assert "Il n'y a que 900 œufs en stock" in html.unescape(r.get_data(as_text=True))
    r = client.post(f'/oeufs/{b.numero}/vendre', data={'plateaux': '10', 'oeufs': '5', 'montant': '45 000', 'acheteur': 'Marché', 'jour': AUJ.isoformat()}, follow_redirects=True)
    v = VenteOeufs.query.one()
    assert v.oeufs == 305 and v.montant_fcfa == 45000 and v.acheteur == 'Marché' and v.numero.startswith('OEU-')
    assert oeufs.stock(b) == 595
    assert 'Enregistré ✓ — vente de 305 œufs' in r.get_data(as_text=True)
    assert JournalAudit.query.filter(JournalAudit.detail.contains("Vente d'œufs")).count() == 1
    mv = argent.mouvements([monde['f'].id])
    assert any(m['genre'] == 'vente_oeufs' and m['montant'] == 45000 and m['signe'] > 0 for m in mv)
    assert argent.totaux(mv)['gagne'] == 45000
    bl = bilan.bilan([monde['f']], annee=AUJ.year)
    assert sum(l['recettes_postes']["Ventes d'œufs"] for l in bl['mois']) == 45000
    page = html.unescape(client.get('/mon-argent?periode=tout').get_data(as_text=True))
    assert "Vente d'œufs" in page and 'fiche-vente_oeufs-' in client.get('/oeufs').get_data(as_text=True)
    # Fiche du lot A1 : modifier puis archiver
    r = client.post(f'/fiches/vente_oeufs/{v.id}', data={'oeufs': '300', 'montant_fcfa': '44000', 'acheteur': 'Marché', 'date': AUJ.isoformat(), 'retour': '/oeufs'})
    assert r.status_code == 302 and v.oeufs == 300 and v.montant_fcfa == 44000
    r = client.post(f'/fiches/vente_oeufs/{v.id}', data={'action': 'archiver', 'motif': 'erreur', 'retour': '/oeufs'})
    assert v.archive_le is not None and oeufs.stock(b) == 900 and argent.totaux(argent.mouvements([monde['f'].id]))['gagne'] == 0


def test_chute_de_ponte_alerte_et_notification(client, monde):
    b = _ponte(monde, jours=30)
    for i in range(14, 7, -1):                                   # l'agent peut saisir des jours anciens
        bandes.saisir(b, AUJ - timedelta(days=i), 0, {}, monde['agent'], oeufs=800, casses=0)
    for i in range(7, 0, -1):
        bandes.saisir(b, AUJ - timedelta(days=i), 0, {}, monde['agent'], oeufs=600, casses=0)
    db.session.commit()
    assert oeufs.chute(b, AUJ - timedelta(days=1)) == 25
    from app.routes.bureau import raisons_alerte
    from app.services import pilotage
    from app import indicateurs
    infos = pilotage.infos_ferme(monde['f'], indicateurs.production_fermes([monde['f']]))
    assert any('chute de ponte' in r for r in raisons_alerte(monde['f'], infos, monde['agent']))
    from datetime import datetime
    notifications.calculer(datetime.combine(AUJ - timedelta(days=1), datetime.min.time()).replace(hour=9))
    n = Notification.query.filter_by(utilisateur_id=monde['agent'].id, type=T.FEU_ROUGE).filter(Notification.titre.contains('Chute')).all()
    assert len(n) == 1 and 'baissé de 2' in n[0].texte   # 22–25 % selon le jour courant inclus and n[0].envoyee_le is not None
    connecter(client, 'eleveur1')
    assert 'data-chute-ponte' in client.get('/oeufs').get_data(as_text=True)


def test_reforme_clot_la_bande(client, monde):
    b = _ponte(monde)
    bandes.cloturer(b, monde['agent'], motif='Réforme')
    db.session.commit()
    assert not b.en_cours and oeufs.bandes_de_ponte([monde['f']]) == []
    connecter(client, 'eleveur1')
    assert client.get('/oeufs').status_code == 200 and 'data-tuile="oeufs"' not in client.get('/', follow_redirects=True).get_data(as_text=True)
