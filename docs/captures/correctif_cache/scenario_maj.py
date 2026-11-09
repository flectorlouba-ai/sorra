"""Scénario réel : un navigateur garde l'ancienne version (lot 8) en cache, puis l'application est
mise à jour. On regarde la PREMIÈRE ouverture après la mise à jour, sans aucune action.

A : lot 8 → lot 9 d'avant le correctif (37b7baf)  — doit reproduire la page sans style.
B : lot 8 → version corrigée (dépôt actuel)         — doit s'afficher correctement toute seule.
"""
import os, shutil, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

S, DEPOT, PY = sys.argv[1], sys.argv[2], sys.argv[3]
B = 'http://127.0.0.1:5030'


def serveur(dossier, base):
    env = dict(os.environ, PORT='5030', DATABASE_URL=f'sqlite:///{base}', YL2_ENV='production', SECRET_KEY='demo')
    p = subprocess.Popen([PY, 'performyl2.py'], cwd=dossier, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            urllib.request.urlopen(B + '/auth/connexion'); return p
        except Exception:
            time.sleep(0.25)
    raise RuntimeError('serveur')


def arreter(p):
    p.terminate(); p.wait(10); time.sleep(0.5)


def etat(page):
    return page.evaluate("""() => {
      const t = document.querySelector('.tuiles'), p = document.querySelector('.ligne-etat svg');
      return {tuiles_en_grille: t ? getComputedStyle(t).display === 'grid' : null,
              largeur_poulet: p ? Math.round(p.getBoundingClientRect().width) : null,
              largeur_page: document.documentElement.scrollWidth};
    }""")


def scenario(nom, ancienne, nouvelle, base):
    with sync_playwright() as pw:
        navigateur = pw.chromium.launch()
        ctx = navigateur.new_context(viewport={'width': 360, 'height': 780}, is_mobile=True)
        page = ctx.new_page()
        # 1. Ancienne version : l'éleveur utilise l'application, le service worker garde ses fichiers
        p = serveur(ancienne, base)
        page.goto(B + '/auth/connexion'); page.fill('#identifiant', 'eleveur'); page.fill('#mot_de_passe', 'Demo-yl2-2026')
        page.click('.btn-login'); page.wait_for_load_state('networkidle')
        page.evaluate('navigator.serviceWorker.ready.then(() => true)')
        for _ in range(3):
            page.reload(); page.wait_for_load_state('networkidle'); page.wait_for_timeout(800)
        avant = page.evaluate('caches.keys()')
        controle = page.evaluate('!!navigator.serviceWorker.controller')
        arreter(p)
        # 2. Mise à jour du serveur ; l'éleveur rouvre simplement l'accueil
        p = serveur(nouvelle, base)
        chargements = []
        page.on('load', lambda: chargements.append(page.url))
        page.goto(B + '/'); page.wait_for_timeout(300)
        premier = etat(page)
        page.screenshot(path=os.path.join(S, f'scenario_{nom}_premier_affichage.png'))
        page.wait_for_timeout(5000)   # le nouveau service worker s'installe, prend la main, recharge
        final = etat(page)
        page.screenshot(path=os.path.join(S, f'scenario_{nom}_apres_5s.png'))
        apres = page.evaluate('caches.keys()')
        navigateur.close(); arreter(p)
    print(f'--- {nom} ---')
    print('  ancienne version : page contrôlée par le service worker :', controle, '| caches :', avant)
    print('  premier affichage après mise à jour :', premier)
    print('  5 s plus tard (sans rien toucher)   :', final, '| chargements de la page :', len(chargements))
    print('  caches après                        :', apres)


base = os.path.join(S, 'demo_scenario.db')
shutil.copy(os.path.join(os.path.dirname(DEPOT), 'demo_performyl2.db'), base)
scenario('A_lot8_vers_lot9_avant_correctif', os.path.join(S, 'wt_lot8'), os.path.join(S, 'wt_lot9'), base)
scenario('B_lot8_vers_version_corrigee', os.path.join(S, 'wt_lot8'), DEPOT, base)
