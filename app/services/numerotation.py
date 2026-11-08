"""Numérotation automatique, reprise de YL.1 et rendue générique.

`generer_numero('FERME', 'EST')`            → EST-000001, EST-000002…
`generer_numero('DECL', 'DS', annuel=True)` → DS-2026-000001 (repart à 1 chaque année)

Sûreté en cas d'accès simultanés : la ligne du compteur est lue avec
SELECT … FOR UPDATE, donc verrouillée sous PostgreSQL jusqu'à la fin de la
transaction ; un second appel attend que le premier ait validé. (SQLite, en
local, ne permet qu'une écriture à la fois sur toute la base.)
Un numéro n'est jamais réutilisé : le compteur ne fait que monter, et il n'y a
aucune fonction pour le faire redescendre. Si la transaction est annulée, le
numéro n'a été donné à personne et sera attribué à la suivante.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.compteur import Compteur


def _verrouiller(type_, prefixe, annee):
    requete = (select(Compteur)
               .filter_by(type=type_, prefixe=prefixe, annee=annee)
               .with_for_update())
    return db.session.execute(requete).scalar_one_or_none()


def generer_numero(type_, prefixe, annuel=False, largeur=6):
    annee = datetime.now(timezone.utc).year if annuel else 0
    compteur = _verrouiller(type_, prefixe, annee)
    if compteur is None:
        # Premier numéro de la série : deux appels simultanés peuvent tenter
        # de créer la ligne ; la contrainte d'unicité départage, le perdant relit.
        try:
            with db.session.begin_nested():
                db.session.add(Compteur(type=type_, prefixe=prefixe, annee=annee,
                                        dernier_numero=0))
        except IntegrityError:
            pass
        compteur = _verrouiller(type_, prefixe, annee)
    compteur.dernier_numero += 1
    db.session.flush()
    n = compteur.dernier_numero
    if annuel:
        return f'{prefixe}-{annee}-{n:0{largeur}d}'
    return f'{prefixe}-{n:0{largeur}d}'
