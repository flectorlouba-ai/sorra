"""Mises à jour automatiques chez l'éleveur : caches versionnés, fichiers statiques versionnés,
service worker qui supprime les anciens caches, SVG jamais géants (correctif après le lot 9)."""
import re

from app.routes import hors_ligne as routes_hors_ligne
from app.utils import statiques
from tests.conftest import connecter
from tests.test_bandes import monde, bande_ouverte  # noqa: F401


def test_la_version_change_quand_un_fichier_change(tmp_path):
    (tmp_path / 'css').mkdir()
    feuille = tmp_path / 'css' / 'terrain.css'
    feuille.write_text('.a{color:red}', encoding='utf-8')
    v1, e1 = statiques.version_application(str(tmp_path)), statiques.empreinte(str(tmp_path), 'css/terrain.css')
    assert statiques.version_application(str(tmp_path)) == v1          # stable tant que rien ne change
    feuille.write_text('.a{color:blue} /* lot 9 */', encoding='utf-8')
    v2, e2 = statiques.version_application(str(tmp_path)), statiques.empreinte(str(tmp_path), 'css/terrain.css')
    assert v1 != v2 and e1 != e2


def test_le_nom_du_cache_change_avec_la_version(client, monkeypatch):
    def nom_des_caches():
        js = client.get('/sw.js').get_data(as_text=True)
        return re.search(r"var VERSION = '([0-9a-f]+)';", js).group(1), js
    v1, js = nom_des_caches()
    assert v1 == routes_hors_ligne.version()
    assert "PREFIXE + 'statiques-' + VERSION" in js and "PREFIXE + 'pages-' + VERSION" in js
    # Version suivante de l'application : nouveau nom de cache, l'ancien est supprimé à l'activation
    monkeypatch.setattr(statiques, 'version_application', lambda *d: 'abcdef123456')
    v2, js = nom_des_caches()
    assert v2 == 'abcdef123456' != v1
    for attendu in ('self.skipWaiting()', 'self.clients.claim()', 'caches.delete(n)',
                    "n.indexOf(PREFIXE) === 0 && n !== STATIQUES && n !== PAGES"):
        assert attendu in js, attendu


def test_service_worker_jamais_en_cache_et_strategies(client):
    r = client.get('/sw.js')
    assert r.mimetype == 'application/javascript' and r.headers['Service-Worker-Allowed'] == '/'
    assert 'no-store' in r.headers['Cache-Control']
    js = r.get_data(as_text=True)
    garder = re.search(r'var A_GARDER = (\[.*?\]);', js).group(1)
    for f in ('/static/css/terrain.css?v=', '/static/css/perform.css?v=', '/static/js/eleveur.js?v=',
              '/static/js/hors_ligne.js?v='):
        assert f in garder, f
    assert 'reseauDAbord(req, STATIQUES' in js            # CSS et JS : réseau d'abord
    assert 'CACHE_D_ABORD = /\\.(woff2?|ttf|png|jpe?g|webp|gif|svg|ico)$/i' in js   # seulement polices, images
    assert "{cache: 'reload'}" in js                       # jamais une copie du cache du navigateur
    hl = client.get('/static/js/hors_ligne.js').get_data(as_text=True)
    assert "updateViaCache: 'none'" in hl and "'controllerchange'" in hl and 'location.reload()' in hl


def test_fichiers_statiques_appeles_avec_leur_version(client, monde, app):
    bande_ouverte(monde)
    pages = [client.get('/auth/connexion').get_data(as_text=True)]
    connecter(client, 'eleveur1')
    pages += [client.get(u).get_data(as_text=True) for u in ('/', '/saisie-du-jour', '/mon-stock', '/j-ai-achete')]
    attendu = statiques.empreinte(app.static_folder, 'css/terrain.css')
    assert f'/static/css/terrain.css?v={attendu}' in pages[1]
    for page in pages:
        adresses = re.findall(r'(?:href|src)="(/static/[^"]+)"', page)
        assert adresses
        sans_version = [a for a in adresses if '?v=' not in a]
        assert sans_version == [], sans_version


def test_svg_du_poulet_toujours_avec_une_taille(client, monde):
    bande_ouverte(monde)
    pages = [client.get('/auth/connexion').get_data(as_text=True)]
    connecter(client, 'eleveur1')
    pages += [client.get(u).get_data(as_text=True) for u in ('/', '/saisie-du-jour', '/bandes/mes-bandes')]
    vus = 0
    for page in pages:
        for balise in re.findall(r'<svg class="(?:poulet|logo-poulet|poussin)[^>]*>', page):
            assert re.search(r' width="\d+"', balise) and re.search(r' height="\d+"', balise), balise
            vus += 1
    assert vus >= 6
