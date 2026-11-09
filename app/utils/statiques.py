"""Versions des fichiers statiques et de l'application (mise à jour automatique chez les éleveurs).

- Chaque fichier statique est appelé avec l'empreinte de son contenu (`eleveur.css?v=3f2a…`) :
  un fichier modifié a une nouvelle adresse, jamais prise dans un ancien cache.
- La version de l'application est l'empreinte de tous les fichiers statiques et gabarits :
  elle change à chaque mise à jour, sans y penser. Elle nomme les caches du service worker,
  qui supprime les anciens à son activation.
"""
import hashlib
import os

_empreintes = {}


def empreinte(dossier, nom):
    """Empreinte courte du contenu d'un fichier (recalculée si le fichier change)."""
    chemin = os.path.join(dossier, nom)
    try:
        cle = (chemin, os.path.getmtime(chemin), os.path.getsize(chemin))
    except OSError:
        return None
    if cle not in _empreintes:
        with open(chemin, 'rb') as f:
            _empreintes[cle] = hashlib.sha256(f.read()).hexdigest()[:10]
    return _empreintes[cle]


def version_application(*dossiers):
    """Empreinte de tous les fichiers des dossiers donnés (statiques, gabarits)."""
    h = hashlib.sha256()
    for dossier in dossiers:
        for racine, _, fichiers in sorted(os.walk(dossier)):
            for nom in sorted(fichiers):
                relatif = os.path.relpath(os.path.join(racine, nom), dossier).replace('\\', '/')
                h.update(relatif.encode('utf-8'))
                h.update((empreinte(racine, nom) or '').encode('ascii'))
    return h.hexdigest()[:12]


def installer(app):
    """`url_for('static', filename=…)` ajoute `?v=<empreinte>` partout, tout seul."""
    @app.url_defaults
    def _version_statique(endpoint, valeurs):
        if endpoint == 'static' and 'filename' in valeurs and 'v' not in valeurs:
            e = empreinte(app.static_folder, valeurs['filename'])
            if e:
                valeurs['v'] = e

