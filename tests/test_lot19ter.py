"""Lot 19 ter — espace TERRAIN : l'agent et l'opérateur au style de l'éleveur. Présentation seulement : les règles,
services, contrôles, hors ligne et journal des lots 12 à 19 ne changent pas (leurs tests restent verts)."""
import html
import re

import pytest

from app import db
from app.models import Profil, JournalAudit, Parametre, Operateur, Utilisateur
from app.models.hors_ligne import ConflitHorsLigne
from tests.conftest import creer_utilisateur, connecter, province
from tests.test_bandes import monde, bande_ouverte, AUJ  # noqa: F401
from app.services import bandes as regles


def texte(r):
    return html.unescape(r.get_data(as_text=True))


def visible(page):
    """Texte que l'utilisateur lit : sans balises, scripts ni styles."""
    page = re.sub(r'<(script|style)\b.*?</\1>', ' ', page, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', page))


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


def corps(page):
    return re.search(r'<body[^>]*>', page).group(0)


@pytest.fixture
def terrain(monde):
    abattoir = Operateur.query.filter_by(type='Abattoir').one()
    op = creer_utilisateur('abattoir1', Profil.OPERATEUR, ['EST'])
    op.operateur_id = abattoir.id
    creer_utilisateur('dge', Profil.DGE)
    creer_utilisateur('veto1', Profil.VETO, ['EST'])
    b = bande_ouverte(monde)
    regles.peser(b, AUJ, 10, 20, monde['el'])
    db.session.commit()
    return {**monde, 'abattoir': abattoir, 'b': b}


# ── A. Deux styles ──────────────────────────────────────────────────────

def test_style_terrain_pour_les_trois_profils_bureau_pour_les_autres(client, terrain):
    for ident, classe in (('eleveur1', 'terrain-eleveur'), ('agent1', 'terrain-agent'), ('abattoir1', 'terrain-operateur')):
        changer(client, ident)
        page = texte(client.get('/'))
        assert 'css/terrain.css' in page and 'theme-terrain' in corps(page) and classe in corps(page), ident
        assert ('theme-eleveur' in corps(page)) == (ident == 'eleveur1'), ident     # fêtes de l'éleveur seulement
        assert ('js/eleveur.js' in page) == (ident == 'eleveur1'), ident
    for ident in ('dge', 'veto1'):
        changer(client, ident)
        page = texte(client.get('/'))
        assert 'css/terrain.css' not in page and 'theme-terrain' not in corps(page), ident


def test_entete_verte_pour_l_operateur_sans_copie(client, terrain):
    css = client.get('/static/css/terrain.css').get_data(as_text=True)
    assert '.terrain-operateur{--t-entete-debut:var(--e-prairie);--t-entete-fin:var(--e-prairie-sombre);}' in css
    assert '--e-prairie:#2fa36b' in css and '--e-prairie-sombre:#1f7a4f' in css
    assert 'linear-gradient(135deg,var(--t-entete-debut),var(--t-entete-fin))' in css
    connecter(client, 'abattoir1')
    page = texte(client.get('/'))
    assert 'terrain-operateur' in corps(page) and 'Abattoir de Ntoum' in page          # nom de l'établissement


def test_aucune_fete_pour_l_agent_et_l_operateur(client, terrain):
    css = client.get('/static/css/terrain.css').get_data(as_text=True)
    assert '.theme-eleveur .compteur-valeur.rebond' in css                             # le rebond : éleveur seul
    assert '.terrain-agent .bien-recu,.terrain-operateur .bien-recu' in css
    for ident in ('agent1', 'abattoir1'):
        changer(client, ident)
        for url in ('/', f'/bandes/{terrain["b"].numero}/saisir' if ident == 'agent1' else '/operateur/scanner'):
            page = texte(client.get(url))
            assert 'bien-recu' not in page and 'etincelles' not in page and 'js/eleveur.js' not in page, (ident, url)


# ── B, C. Agent ─────────────────────────────────────────────────────────

def test_accueil_de_l_agent_huit_tuiles_et_ligne_d_etat(client, terrain):
    db.session.add(ConflitHorsLigne(ferme_id=terrain['f'].id, quoi='Écart à la réception du lot X', detail='essai'))
    db.session.commit()
    connecter(client, 'agent1')
    page = texte(client.get('/'))
    assert re.findall(r'data-tuile="([a-z_]+)"', page) == ['tournee', 'fermes', 'saisir', 'visite', 'a_verifier',
                                                           'stock', 'nouvel_eleveur', 'moi']
    assert re.search(r'Bonjour Paul · Estuaire · \d+ fermes?', page)
    assert '1 saisie à vérifier' in page and '📶 Tout est envoyé ✓' in page and 'data-etat-envoi' in page
    assert 'data-entete="cloche"' in page and 'data-entete="moi"' in page
    for lien in re.findall(r'class="tuile[^"]*" href="([^"#]+)"', page):        # aucune tuile morte
        assert client.get(lien, follow_redirects=True).status_code == 200, lien


def test_tournee_fermes_et_fiche(client, terrain):
    f = terrain['f']
    f.latitude, f.longitude = 0.39, 9.45
    from app.models import SaisieJour
    db.session.add(SaisieJour(bande=terrain['b'], date=AUJ, morts=200))   # feu rouge : la ferme entre dans la tournée
    db.session.commit()
    connecter(client, 'agent1')
    page = texte(client.get('/terrain/tournee'))
    assert f'1. {f.numero}' in page and '🔴 Beaucoup de morts' in page and 'geo:0.39,9.45' in page
    assert 'Gardée sur le téléphone à' in page                                      # affiché sans réseau seulement
    page = texte(client.get('/terrain/fermes'))
    assert f.numero in page and terrain['f2'].numero not in page            # seulement ses fermes, l'urgente d'abord
    page = texte(client.get(f'/terrain/fermes/{f.numero}'))
    for attendu in ('Saisir pour', 'Faire la visite', 'Stock', 'Ses chiffres', 'Position : relevée ✓', 'BCEG',
                    'Dernière visite'):
        assert attendu in page, attendu


def test_saisir_pour_un_eleveur_utilise_les_ecrans_de_l_eleveur(client, terrain):
    b = terrain['b']
    connecter(client, 'agent1')
    page = texte(client.get(f'/terrain/saisir?ferme={terrain["f"].numero}'))
    for lien in (f'/bandes/{b.numero}/saisir', f'/bandes/{b.numero}/pesee', f'/sante/vacciner/{b.numero}',
                 f'/bandes/{b.numero}/sortie'):
        assert f'href="{lien}"' in page, lien
    assert 'saisi par Paul pour' in page
    saisie = texte(client.get(f'/bandes/{b.numero}/saisir'))
    eleveur_form = open('app/templates/bandes/_form_saisie.html', encoding='utf-8').read()
    assert 'Aucun mort' in eleveur_form and 'Aucun mort' in saisie and 'placeholder="—"' in saisie   # même formulaire
    client.post(f'/bandes/{b.numero}/saisie', data={'jour': AUJ.isoformat(), 'morts': '2',
                                                   'aliment_choisi': str(terrain['aliment'].id), 'sacs': '1'})
    ligne = JournalAudit.query.filter_by(action='POUR_ELEVEUR').order_by(JournalAudit.id.desc()).first()
    assert ligne is not None and 'agent' in ligne.detail.lower()


def test_a_verifier_au_style_terrain_meme_regle(client, terrain):
    from app.services import verifications
    from app.models import SaisieJour
    b = terrain['b']
    s = SaisieJour(bande=b, date=AUJ, morts=12)
    db.session.add(s)
    db.session.commit()
    verifications.deux_versions_saisie(b, s, 17, {}, terrain['agent'])
    db.session.commit()
    c = ConflitHorsLigne.query.filter_by(genre='SAISIE_JOUR').one()
    connecter(client, 'agent1')
    page = texte(client.get('/hors-ligne/a-verifier'))
    assert 'Quelle version garder ?' in page and 'Pourquoi ?' in page and 'Recompté ensemble' in page
    assert 'compte en attendant' in page and 'Valider' in page
    client.post(f'/hors-ligne/a-verifier/{c.id}/trancher', data={'choix': '1', 'motif': 'Autre',
                                                                'motif_autre': 'Compté avec Pierre au bâtiment'})
    db.session.refresh(c)
    assert c.statut == 'TRANCHE' and c.motif == 'Compté avec Pierre au bâtiment'     # même règle, même journal
    assert JournalAudit.query.filter_by(action='VERIFICATION').count() == 1


def test_stock_en_mots_sans_pourcentage(client, terrain):
    connecter(client, 'agent1')
    from app.services import agent
    agent.compter(terrain['f'], terrain['aliment'], 30, terrain['agent'])
    db.session.commit()
    page = texte(client.get(f'/terrain/stock?ferme={terrain["f"].numero}'))
    assert 'Reçu ' in page and 'Utilisé' in page and 'Reste 30' in page
    assert re.search(r'🟠 [\d,.]+ sacs manquent|✓ ça correspond', page) and ' %' not in visible(page).split('Commande')[0]
    assert 'Livraison reçue' in page and 'Compter le stock' in page and 'Commande pour la bande suivante' in page


def test_nouvel_eleveur_ferme_enregistree_ou_nouvelle_avec_reseau(client, terrain):
    connecter(client, 'agent1')
    page = texte(client.get('/terrain/nouvel-eleveur'))
    assert 'Ferme déjà enregistrée' in page and 'Nouvelle ferme' in page and 'Marche aussi sans réseau' in page   # lot E-b
    page = texte(client.get(f'/fermes/{terrain["f"].numero}/eleveurs/nouveau'))
    assert '1. La personne' in page and '2. La ferme' in page and '3. Le compte' in page and 'data-hors-ligne=' in page
    assert 'Avec du réseau seulement' in texte(client.get('/fermes/nouvelle'))


def test_moi_version_bureau_et_telephone_dge(client, terrain):
    connecter(client, 'agent1')
    page = texte(client.get('/terrain/moi'))
    assert 'Version ordinateur' in page and 'lien-bureau' in page and 'Appeler la DGE' not in page   # aucun téléphone
    dge = Utilisateur.query.filter_by(identifiant='dge').one()
    dge.telephone = '+241 66 11 22 33'
    db.session.commit()
    assert 'tel:+24166112233' in texte(client.get('/terrain/moi'))                  # premier compte DGE
    Parametre.query.filter_by(cle='contact.telephone_dge').one().valeur = '+241 11 22 33 44'
    db.session.commit()
    assert 'tel:+24111223344' in texte(client.get('/terrain/moi'))                  # le paramètre d'abord
    # Version bureau : les écrans de pilotage existants ; retour au terrain
    client.get('/terrain/bureau')
    page = texte(client.get('/'))
    assert 'data-fonction="fermes"' in page and 'theme-terrain' not in corps(page)
    assert client.get('/tournee').status_code == 200 and client.get(f'/fermes/{terrain["f"].numero}').status_code == 200
    client.get('/terrain/version-terrain')
    assert 'terrain-agent' in corps(texte(client.get('/')))


def test_presentation_et_aides_propres_a_chaque_profil(client, terrain):
    for ident, prefixe in (('agent1', 'ag_'), ('abattoir1', 'op_')):
        u = Utilisateur.query.filter_by(identifiant=ident).one()
        u.presentation_vue_le = None
        db.session.commit()
        changer(client, ident)
        r = client.get('/')
        assert r.status_code == 302 and '/terrain/presentation' in r.location               # une fois par compte
        client.post('/terrain/presentation/vue')
        assert client.get('/').status_code == 200
        liste = texte(client.get('/aide'))
        cles = set(re.findall(r'href="/aide/([a-z_]+)', liste))
        assert cles and all(c.startswith(prefixe) for c in cles), cles               # pas les aides de l'éleveur
        assert client.get('/aide/saisie').status_code == 404
    changer(client, 'agent1')
    assert 'data-aide="ag_tournee"' in texte(client.get('/terrain/tournee'))
    changer(client, 'eleveur1')
    cles = set(re.findall(r'href="/aide/([a-z_]+)', texte(client.get('/aide'))))
    assert len(cles) == 9 and not any(c.startswith(('ag_', 'op_')) for c in cles)   # éleveur : ses 9 aides


# ── D, E. Opérateur ─────────────────────────────────────────────────────

MOTS_INTERDITS = ('réserve', 'reserve', 'bloquant', 'événement', 'evenement')


def test_aucun_mot_technique_chez_l_operateur(client, terrain):
    from datetime import timedelta
    ok = regles.sortir(terrain['b'], AUJ, 'Abattoir', terrain['abattoir'], '', 100, 200, terrain['el']).lot
    a_part = regles.sortir(terrain['b'], AUJ, 'Abattoir', terrain['abattoir'], '', 50, 100, terrain['el']).lot
    db.session.commit()
    connecter(client, 'abattoir1')
    pages = [texte(client.get(u)) for u in ('/', '/operateur/scanner', '/operateur/attendus', '/operateur/receptions',
                                           f'/operateur/lot?code={ok.code}', '/operateur/lot?code=Inconnu123456789')]
    for p in terrain['b'].pesees:
        p.date = AUJ - timedelta(days=9)
    db.session.commit()
    page = texte(client.get(f'/operateur/lot?code={a_part.code}'))
    assert 'Gardez ces poulets à part' in page and 'Je les reçois et je les garde à part' in page and 'Je refuse ce lot' in page
    pages.append(page)
    r = client.post('/operateur/recevoir', data={'numero': a_part.numero, 'vivants': '50', 'morts': '0', 'poids': '100',
                                                 'choix': 'reserve'}, follow_redirects=True)
    pages.append(texte(r))                                                            # message après envoi
    from app.models.tracabilite import Reception
    rec = Reception.query.filter_by(lot_id=a_part.id).one()
    pages += [texte(client.get(f'/operateur/receptions/{rec.id}')), texte(client.get('/operateur/receptions')),
              texte(client.get('/terrain/moi'))]
    for p in pages:
        lu = visible(p).lower()
        for mot in MOTS_INTERDITS:
            assert mot not in lu, (mot, lu[:200])
    assert '◷ Attend le vétérinaire' in pages[-2]


def test_ecrans_de_l_operateur_en_phrases(client, terrain):
    lot = regles.sortir(terrain['b'], AUJ, 'Abattoir', terrain['abattoir'], '', 100, 200, terrain['el']).lot
    db.session.commit()
    connecter(client, 'abattoir1')
    page = texte(client.get('/'))
    assert re.findall(r'data-tuile="([a-z_]+)"', page) == ['recevoir', 'arrivent', 'receptions', 'moi']
    assert '1 lot arrive cette semaine' in page
    page = texte(client.get('/operateur/scanner'))
    assert 'Mettez le QR dans le cadre jaune' in page and 'Le QR ne marche pas ? Tapez le numéro :' in page
    page = texte(client.get(f'/operateur/lot?code={lot.code}'))
    for phrase in ('✓ Vous pouvez recevoir ce lot', '✅', 'Bien envoyé à votre abattoir', 'Pas de médicament récent',
                   'Pesés aujourd', '🐔 Vivants reçus', '💀 Morts à l\'arrivée', '⚖️ Poids total (kg)', '✓ Valider la réception',
                   "L'agent de la ferme et le vétérinaire sont prévenus. Les chiffres de la ferme ne sont pas changés."):
        assert phrase in page, phrase
    page = texte(client.get('/operateur/attendus'))
    assert '🐔 100 poulets' in page and 'partis ce matin' in page


# ── F. Sans réseau : liste unique complète pour l'agent et l'opérateur ──

@pytest.mark.parametrize('ident', ['agent1', 'abattoir1'])
def test_toutes_les_pages_terrain_sont_gardees_sans_reseau(client, terrain, app, ident):
    from app.routes import hors_ligne as hl
    connecter(client, ident)
    gardees = set(client.get('/hors-ligne/pages').get_json()['pages'])
    oubliees = []
    for regle in app.url_map.iter_rules():
        if ('GET' not in regle.methods or regle.arguments or regle.rule.startswith(('/static', '/q/'))
                or regle.endpoint in ('terrain.bureau', 'terrain.version_terrain', 'auth.deconnexion')
                or regle.endpoint in hl.EN_LIGNE_SEULEMENT or regle.endpoint in hl.VERSION_BUREAU_AGENT):
            continue
        r = client.get(regle.rule)
        if r.status_code == 200 and r.mimetype == 'text/html' and regle.rule not in gardees:
            oubliees.append(regle.rule)
    assert oubliees == []
    for p in gardees:                                                     # chaque page gardée s'ouvre
        assert client.get(p).status_code == 200, p
    if ident == 'agent1':
        n = terrain['f'].numero
        for p in (f'/terrain/fermes/{n}', f'/terrain/saisir?ferme={n}', f'/terrain/stock?ferme={n}', '/aide/ag_tournee'):
            assert p in gardees, p
    else:
        assert '/aide/op_recevoir' in gardees
