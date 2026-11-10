"""Lot 17 — écrans du vétérinaire : signalements par gravité, diagnostic invisible de l'agent, blocage
des sorties (refus en ligne, sortie reçue sans réseau après le blocage → à vérifier, pas de lot ni de QR,
message à l'éleveur, levée par un vétérinaire avec motif), paramètres sanitaires (quatre yeux),
recherche de lots amont et aval (export, journal)."""
import re
from datetime import timedelta

from app import db
from app.models import Profil, JournalAudit, Parametre
from app.models.bande import Sortie
from app.models.base import maintenant
from app.models.sante import OrigineAlerte
from app.models.tracabilite import LotTrace
from app.models.veto import BlocageSorties, Diagnostic
from app.services import sante, veto as regles
from tests.conftest import creer_utilisateur, connecter
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from tests.test_hors_ligne import rejouer


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def _veto(telephone='+241 66 00 11 22'):
    v = creer_utilisateur('veto1', Profil.VETO, ['EST'])
    v.telephone = telephone
    db.session.commit()
    return v


def _sortie(monde, nombre='50'):
    abattoir = next(o for o in __import__('app.models', fromlist=['Operateur']).Operateur.query if o.type == 'Abattoir')
    return {'motif': 'Abattoir', 'operateur': str(abattoir.id), 'nombre': nombre, 'poids_total': '100',
            'jour': AUJ.isoformat()}


# ── A. Gravité ──────────────────────────────────────────────────────────

def test_signalements_tries_par_gravite(client, monde):
    b = bande_ouverte(monde)
    _veto()
    peu = sante.declarer(monde['f'], b, ['Toux'], 2, [], None, monde['el']).id
    beaucoup = sante.declarer(monde['f'], b, ['Diarrhée'], 30, [], None, monde['el']).id
    rouge = sante._nouvelle_alerte(monde['f'], b, OrigineAlerte.FEU_ROUGE)
    db.session.commit()
    alertes = {a.declaration_id: a for a in rouge.query.all()}
    a_peu, a_beaucoup = alertes[peu], alertes[beaucoup]
    assert (regles.gravite(a_peu), regles.gravite(a_beaucoup), regles.gravite(rouge)) == (1, 2, 3)
    a_peu.cree_le = maintenant() - timedelta(hours=30)              # sans réponse depuis plus de 24 h : +1
    db.session.commit()
    assert regles.gravite(a_peu) == 2
    connecter(client, 'veto1')
    page = client.get('/sante/alertes').get_data(as_text=True)
    assert [int(g) for g in re.findall(r'data-gravite="(\d)"', page)] == [3, 2, 2]
    assert page.index(rouge.numero) < page.index(a_peu.numero) < page.index(a_beaucoup.numero)   # le plus ancien d'abord
    assert 'data-fonction="bloquees"' in client.get('/').get_data(as_text=True)         # lot R : bouton Ventes bloquées


# ── B. Diagnostic ───────────────────────────────────────────────────────

def test_diagnostic_invisible_de_l_agent(client, monde):
    b = bande_ouverte(monde)
    _veto()
    sante.declarer(monde['f'], b, ['Toux'], 12, [], None, monde['el'])
    db.session.commit()
    a = sante.alertes_visibles(creer_utilisateur('admin', Profil.ADMIN)).one()
    db.session.commit()
    connecter(client, 'veto1')
    assert 'Choisissez la maladie' in client.post(f'/sante/alertes/{a.numero}/diagnostic', data={'maladie': 'Autre'},
                                                  follow_redirects=True).get_data(as_text=True)
    client.post(f'/sante/alertes/{a.numero}/diagnostic', data={'maladie': 'Newcastle', 'prelevement': 'on',
                                                              'observations': 'Râles, torticolis'})
    d = Diagnostic.query.one()
    assert d.maladie == 'Newcastle' and d.prelevement
    page = client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    assert 'Râles, torticolis' in page and 'data-diagnostic' in page
    # L'agent : « diagnostic posé le … », jamais le contenu
    changer(client, 'agent1')
    fiche = client.get(f'/fermes/{monde["f"].numero}').get_data(as_text=True)
    assert 'diagnostic posé le' in fiche and 'Newcastle' not in fiche and 'torticolis' not in fiche
    assert client.get(f'/sante/alertes/{a.numero}').status_code == 403
    assert client.post(f'/sante/alertes/{a.numero}/diagnostic', data={'maladie': 'X'}).status_code == 403
    # La DGE (alerte confirmée) ne lit pas le diagnostic ; l'ADMIN le lit
    a.statut = 'CONFIRMEE'
    creer_utilisateur('dge', Profil.DGE)
    db.session.commit()
    changer(client, 'dge')
    assert 'torticolis' not in client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    changer(client, 'admin')
    assert 'torticolis' in client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)


# ── C. Blocage des sorties ──────────────────────────────────────────────

def test_blocage_refus_message_a_verifier_et_levee(client, monde):
    b = bande_ouverte(monde)
    _veto()
    connecter(client, 'veto1')
    assert 'motif du blocage' in client.post('/surveillance/bloquer', data={'bande': b.numero},
                                             follow_redirects=True).get_data(as_text=True)
    client.post('/surveillance/bloquer', data={'bande': b.numero, 'motif': 'Suspicion de Newcastle'})
    bl = BlocageSorties.query.one()
    assert bl.actif and bl.motif == 'Suspicion de Newcastle'
    assert JournalAudit.query.filter_by(table_nom='blocage_sorties', action='CREATION').count() == 1
    # L'éleveur : message rouge sur l'accueil et à la place du formulaire, avec 📞 le vétérinaire
    changer(client, 'eleveur1')
    accueil = client.get('/').get_data(as_text=True)
    assert 'Le vétérinaire a bloqué les ventes de cette bande' in accueil and 'tel:+24166001122' in accueil
    page = client.get(f'/bandes/{b.numero}/sortie').get_data(as_text=True)
    assert 'data-blocage-sorties' in page and 'name="nombre"' not in page          # pas de formulaire, même gardé
    # En ligne : refusée par le serveur, pas de lot
    page = client.post(f'/bandes/{b.numero}/sortie', data=_sortie(monde)).get_data(as_text=True)
    assert 'bloqué les ventes' in page and Sortie.query.count() == 0 and LotTrace.query.count() == 0
    # Faite sans réseau avant de savoir, reçue après : gardée, à vérifier, sans lot ni QR
    _, rep = rejouer(client, f'/bandes/{b.numero}/sortie', _sortie(monde, '40'))
    s = Sortie.query.one()
    assert (s.blocage_id, s.a_verifier, s.mise_de_cote, s.lot) == (bl.id, True, True, None)
    assert LotTrace.query.count() == 0
    # Le vétérinaire la voit dans Surveillance (compteur sur la tuile) et la vérifie
    changer(client, 'veto1')
    assert re.search(r'data-fonction="bloquees"[^>]*><span class="pa">1</span>', client.get('/').get_data(as_text=True))
    page = client.get('/surveillance').get_data(as_text=True)
    assert f'data-sortie-a-verifier="{s.id}"' in page and f'data-blocage="{b.numero}"' in page
    client.post(f'/surveillance/sorties/{s.id}', data={'choix': 'sortis'})
    assert (s.a_verifier, s.mise_de_cote, s.lot) == (False, False, None)           # comptée, toujours sans QR
    # Levée : seul un vétérinaire, avec motif (ni l'agent, ni la DGE, ni l'ADMIN)
    for ident, profil in (('agent1', None), ('dge', Profil.DGE), ('admin', Profil.ADMIN)):
        if profil:
            creer_utilisateur(ident, profil)
            db.session.commit()
        changer(client, ident)
        assert client.post(f'/surveillance/{bl.id}/lever', data={'motif': 'x'}).status_code == 403
    changer(client, 'veto1')
    assert 'motif de la levée' in client.post(f'/surveillance/{bl.id}/lever', data={},
                                              follow_redirects=True).get_data(as_text=True)
    client.post(f'/surveillance/{bl.id}/lever', data={'motif': 'Analyses négatives'})
    assert not bl.actif and bl.motif_levee == 'Analyses négatives'
    changer(client, 'eleveur1')
    assert 'bloqué les ventes' not in client.get('/').get_data(as_text=True)
    client.post(f'/bandes/{b.numero}/sortie', data=_sortie(monde, '10'))
    nouvelle = Sortie.query.filter_by(nombre=10).one()
    assert nouvelle.lot is not None                                                  # de nouveau un lot et un QR


def test_blocage_depuis_le_signalement(client, monde):
    b = bande_ouverte(monde)
    _veto()
    sante.declarer(monde['f'], b, ['Toux'], 12, [], None, monde['el'])
    db.session.commit()
    connecter(client, 'veto1')
    from app.models.sante import AlerteSanitaire
    a = AlerteSanitaire.query.one()
    assert 'Bloquer les sorties de cette bande' in client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    client.post('/surveillance/bloquer', data={'bande': b.numero, 'alerte': a.numero, 'motif': 'Attente analyses'})
    assert BlocageSorties.query.one().alerte_id == a.id
    page = client.get(f'/sante/alertes/{a.numero}').get_data(as_text=True)
    assert 'sorties bloquées' in page and 'Bloquer les sorties de cette bande' not in page
    assert 'déjà bloquées' in client.post('/surveillance/bloquer', data={'bande': b.numero, 'motif': 'x'},
                                          follow_redirects=True).get_data(as_text=True)


# ── D. Paramètres sanitaires ────────────────────────────────────────────

def test_parametres_sanitaires_quatre_yeux(client, monde):
    _veto()
    creer_utilisateur('veto2', Profil.VETO, ['EST'])
    db.session.commit()
    connecter(client, 'veto1')
    page = client.get('/parametres-sanitaires').get_data(as_text=True)
    assert 'data-parametre="bandes.seuil_rouge_pct"' in page and 'securite.' not in page
    p = Parametre.query.filter_by(cle='bandes.seuil_rouge_pct').one()
    avant = p.valeur
    client.post(f'/parametres-sanitaires/{p.id}', data={'valeur': '3', 'motif': 'Saison des pluies'})
    assert p.valeur == avant
    autre = Parametre.query.filter_by(cle='securite.duree_session_minutes').one()
    assert client.post(f'/parametres-sanitaires/{autre.id}', data={'valeur': '5', 'motif': 'x'}).status_code == 403
    changer(client, 'veto2')
    from app.models.securite import Proposition
    prop = Proposition.query.filter_by(cle='bandes.seuil_rouge_pct').one()
    client.post(f'/approbations/{prop.id}', data={'decision': 'approuver'})
    db.session.refresh(p)
    assert p.valeur == '3'


# ── E. Recherche de lots ────────────────────────────────────────────────

def test_recherche_amont_aval_export_et_journal(client, monde):
    b = bande_ouverte(monde)
    from app.models.intrant import Livraison
    liv = Livraison.query.filter(Livraison.lignes.any()).order_by(Livraison.cree_le).first()
    liv.fournisseur = 'Couvoir du Komo'
    db.session.commit()
    connecter(client, 'eleveur1')
    client.post(f'/bandes/{b.numero}/sortie', data=_sortie(monde, '100'))
    lot = LotTrace.query.one()
    _veto()
    changer(client, 'veto1')
    assert 'au moins 3 caractères' in client.get('/recherche-lots?q=ab').get_data(as_text=True)
    for q in (lot.numero, b.numero, 'Komo', liv.numero):
        page = client.get(f'/recherche-lots?q={q}').get_data(as_text=True)
        assert f'data-fiche-bande="{b.numero}"' in page, q
        assert 'Couvoir du Komo' in page and lot.numero in page and 'Abattoir de Ntoum' in page, q
    assert JournalAudit.query.filter_by(action='RECHERCHE').count() == 4
    r = client.get('/recherche-lots.csv?q=Komo')
    texte = r.data.decode('utf-8-sig')
    assert r.status_code == 200 and 'amont' in texte and 'aval' in texte and lot.numero in texte
    assert JournalAudit.query.filter_by(action='EXPORT', table_nom='lot').count() == 1
    # Hors de la province : rien
    creer_utilisateur('veto_hog', Profil.VETO, ['HOG'])
    db.session.commit()
    changer(client, 'veto_hog')
    page = client.get(f'/recherche-lots?q={b.numero}').get_data(as_text=True)
    assert 'data-fiche-bande' not in page and 'hors de votre province' in page
    changer(client, 'agent1')
    assert client.get('/recherche-lots?q=Komo').status_code == 403
