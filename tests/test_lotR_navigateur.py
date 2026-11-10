"""Lot R — contrôles au navigateur (Playwright) sur les données fictives de la démonstration :
aucun débordement horizontal de 360 à 1 920 px sur les écrans de bureau de chaque profil, fenêtre entièrement
visible à 1024 × 560 et 390 × 700, menu des fonctionnalités en haut sous 900 px, téléphone inchangé (style terrain).
Le serveur est lancé à part (comme pour les captures) ; ignoré si Playwright n'est pas installé."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

playwright = pytest.importorskip('playwright.sync_api')

RACINE = Path(__file__).resolve().parent.parent
MDP = 'Demo-yl2-2026'
LARGEURS = (360, 768, 1024, 1440, 1920)
PROFILS = {'dge': '/', 'veto': '/', 'admin': '/', 'aninf': '/'}


def _port_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


@pytest.fixture(scope='module')
def serveur(tmp_path_factory):
    base = tmp_path_factory.mktemp('navig') / 'demo.db'
    env = {**os.environ, 'DATABASE_URL': f'sqlite:///{base.as_posix()}', 'YL2_DEMO': '1', 'YL2_2FA': '0',
           'YL2_ENV': 'production', 'SECRET_KEY': 'essai-navigateur', 'FLASK_APP': 'performyl2.py'}
    python = sys.executable
    subprocess.run([python, '-m', 'flask', 'db', 'upgrade'], cwd=RACINE, env=env, check=True, capture_output=True)
    subprocess.run([python, '-m', 'flask', 'demo-charger'], cwd=RACINE, env=env, check=True, capture_output=True)
    port = _port_libre()
    proc = subprocess.Popen([python, 'performyl2.py'], cwd=RACINE, env={**env, 'PORT': str(port)},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f'http://127.0.0.1:{port}'
    for _ in range(80):
        try:
            urllib.request.urlopen(url + '/auth/connexion')
            break
        except Exception:
            time.sleep(0.5)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def connexion(page, url, ident):
    page.context.clear_cookies()
    page.goto(url + '/auth/connexion')
    page.fill('#identifiant', ident)
    page.fill('#mot_de_passe', MDP)
    page.click('.btn-login')
    page.wait_for_load_state('networkidle')
    if '/presentation' in page.url:
        page.locator('.pres-ecran:not([hidden]) button[data-passer]').click()
        page.wait_for_load_state('networkidle')


def ouvrir(page, url):
    """Le serveur de développement coupe parfois une grande réponse (connexion réinitialisée) : un second essai."""
    for essai in range(2):
        try:
            page.goto(url, wait_until='commit')
            page.wait_for_load_state('load')
            page.wait_for_load_state('networkidle')
            return
        except Exception:
            if essai:
                raise


def deborde(page):
    return page.evaluate('document.documentElement.scrollWidth > document.documentElement.clientWidth + 1')


@pytest.mark.parametrize('ident', ['dge', 'veto', 'admin', 'aninf'])
def test_aucun_debordement_horizontal(serveur, ident):
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 1440, 'height': 900})
        page = ctx.new_page()
        connexion(page, serveur, ident)
        liens = page.eval_on_selector_all('.btns-fonctions .fb', 'els => els.map(e => e.getAttribute("href"))')
        assert liens, 'boutons des fonctionnalités absents'
        for chemin in ['/'] + liens[1:]:
            for largeur in LARGEURS:
                page.set_viewport_size({'width': largeur, 'height': 900})
                ouvrir(page, serveur + chemin)
                assert not deborde(page), f'{ident} {chemin} déborde à {largeur} px'
                if largeur < 900:
                    assert page.evaluate("getComputedStyle(document.querySelector('.btns-fonctions')).display") == 'flex'
        b.close()


def test_fenetre_entierement_visible(serveur):
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        for largeur, hauteur in ((1024, 560), (390, 700)):
            ctx = b.new_context(viewport={'width': largeur, 'height': hauteur})
            page = ctx.new_page()
            connexion(page, serveur, 'admin')
            page.goto(serveur + '/administration/utilisateurs/')
            page.click('button.btn-new')
            page.wait_for_timeout(400)
            boite = page.locator('.modal-overlay:not([hidden]) .modal-box').bounding_box()
            assert boite and boite['y'] >= 0 and boite['y'] + boite['height'] <= hauteur + 1, (largeur, hauteur, boite)
            pied = page.locator('.modal-overlay:not([hidden]) .modal-footer').bounding_box()
            assert pied and pied['y'] + pied['height'] <= hauteur + 1          # titre et boutons visibles
            ctx.close()
        b.close()


def test_telephone_des_profils_terrain_inchange(serveur):
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={'width': 360, 'height': 780}, is_mobile=True, has_touch=True)
        page = ctx.new_page()
        for ident in ('eleveur', 'agent.est', 'abattoir.owendo'):
            connexion(page, serveur, ident)
            page.goto(serveur + '/')
            page.wait_for_load_state('networkidle')
            assert page.evaluate("document.body.classList.contains('theme-terrain')"), ident
            assert not page.evaluate("document.body.classList.contains('bureau')"), ident
            assert not deborde(page)
        # Sur un écran large, l'éleveur passe en version ordinateur, et revient au terrain par le lien
        page.set_viewport_size({'width': 1440, 'height': 900})
        connexion(page, serveur, 'eleveur')
        page.goto(serveur + '/')
        page.wait_for_timeout(1500)
        page.wait_for_load_state('networkidle')
        assert page.evaluate("document.body.classList.contains('bureau')")
        page.click('[data-version-terrain]')
        page.wait_for_load_state('networkidle')
        assert page.evaluate("document.body.classList.contains('theme-terrain')")
        b.close()
