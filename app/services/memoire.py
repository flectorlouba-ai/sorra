"""Calculs lourds des accueils nationaux gardés en mémoire quelques minutes (11/11/2026, accueil DGE).

Avec 150 élevages et 12 mois de saisies, les indicateurs et les 3 courbes sur 52 semaines, le tableau par province et
la liste des alertes coûtent plusieurs secondes. Ils sont calculés au plus une fois par période
(ACCUEIL_MEMOIRE_SECONDES, 300 s par défaut) et gardés dans un fichier du dossier `instance` : partagés par tous les
processus du serveur. La tâche planifiée `flask accueil-recalculer` (toutes les 4 minutes) les tient à jour, si bien
que personne n'attend le calcul. L'accueil affiche l'heure du calcul. 0 seconde = pas de mémoire (tests).

Seuls les profils dont l'accueil ne dépend pas de la personne (DGE, MAEDR, ADMIN, AUDITEUR : périmètre national) sont
gardés, une version par profil : aucune donnée d'un périmètre ne peut apparaître dans un autre.
"""
import os
import pickle
import time

from flask import current_app

PROFILS = ('DGE', 'MAEDR', 'ADMIN', 'AUDITEUR')


def duree():
    return int(current_app.config.get('ACCUEIL_MEMOIRE_SECONDES', 300))


def actif(user):
    return duree() > 0 and user.profil.value in PROFILS


def _fichier(cle):
    dossier = os.path.join(current_app.instance_path, 'memoire')
    os.makedirs(dossier, exist_ok=True)
    return os.path.join(dossier, f'{cle}.pickle')


def lire(cle):
    """(valeur, calculée_le) si elle a moins de `duree()` secondes, sinon None."""
    try:
        with open(_fichier(cle), 'rb') as f:
            quand, valeur = pickle.load(f)
    except (OSError, EOFError, pickle.PickleError, AttributeError, ImportError, ValueError):
        return None
    if time.time() - quand > duree():
        return None
    return valeur, quand


def ecrire(cle, valeur):
    chemin = _fichier(cle)
    provisoire = f'{chemin}.{os.getpid()}'
    with open(provisoire, 'wb') as f:
        pickle.dump((time.time(), valeur), f)
    os.replace(provisoire, chemin)                       # remplacement atomique : jamais un fichier à moitié écrit


def garder(user, nom, calcul, forcer=False):
    """Résultat de `calcul()` pour ce profil, gardé `duree()` secondes ; (valeur, calculée_le ou None)."""
    if not actif(user):
        return calcul(), None
    cle = f'{user.profil.value}_{nom}'
    if not forcer:
        trouve = lire(cle)
        if trouve is not None:
            return trouve
    valeur = calcul()
    try:
        ecrire(cle, valeur)
    except (OSError, pickle.PickleError, TypeError, AttributeError):
        return valeur, None
    return valeur, time.time()
