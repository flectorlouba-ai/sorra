"""Contrôle d'accès : profil et périmètre.

- `@profil_requis(Profil.ADMIN, Profil.AUDITEUR)` protège une route
  (connexion obligatoire, puis 403 si le profil ne figure pas dans la liste).
- `filtre_perimetre(requete)` restreint une requête au périmètre de
  l'utilisateur connecté. ADMIN et DGE voient tout. Les autres ne voient que
  les lignes de leurs provinces ; un utilisateur sans province ne voit rien.

Pour être filtrable, un modèle déclare la colonne qui porte la province :
`__perimetre__ = 'province_id'` (ou `'id'` pour la table Province).
Au lot 1, les modèles rattachés à une ferme déclareront aussi
`__perimetre_ferme__ = 'ferme_id'` : un utilisateur rattaché à des fermes
(éleveur, agent) sera alors limité à ces fermes.
"""
from functools import wraps

from flask import abort
from flask_login import current_user, login_required
from sqlalchemy import Select, false

from app.models.utilisateur import Profil


def a_profil(*profils):
    if not current_user or not current_user.is_authenticated:
        return False
    noms = {p.value if isinstance(p, Profil) else p for p in profils}
    return current_user.profil.value in noms


def profil_requis(*profils):
    def decorateur(vue):
        @wraps(vue)
        @login_required
        def enveloppe(*args, **kwargs):
            if not a_profil(*profils):
                abort(403)
            return vue(*args, **kwargs)
        return enveloppe
    return decorateur


def _modele(requete):
    return requete.column_descriptions[0]['entity']


def _restreindre(requete, condition):
    return requete.where(condition) if isinstance(requete, Select) else requete.filter(condition)


def filtre_perimetre(requete, modele=None, utilisateur=None):
    user = utilisateur or current_user
    if not user or not user.is_authenticated:
        return _restreindre(requete, false())
    if user.est_national:
        return requete
    modele = modele or _modele(requete)
    attr = getattr(modele, '__perimetre__', None)
    if attr is None:
        raise TypeError(f'{modele.__name__} ne déclare pas de colonne de périmètre.')
    requete = _restreindre(requete, getattr(modele, attr).in_(user.province_ids))
    attr_ferme = getattr(modele, '__perimetre_ferme__', None)
    if attr_ferme and user.ferme_ids:
        requete = _restreindre(requete, getattr(modele, attr_ferme).in_(user.ferme_ids))
    return requete
