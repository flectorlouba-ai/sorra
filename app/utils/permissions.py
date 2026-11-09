"""Contrôle d'accès : profil et périmètre.

- `@profil_requis(Profil.ADMIN, Profil.AUDITEUR)` protège une route
  (connexion obligatoire, puis 403 si le profil ne figure pas dans la liste).
- `filtre_perimetre(requete)` restreint une requête au périmètre de
  l'utilisateur connecté. ADMIN et DGE voient tout. Les autres ne voient que
  les lignes de leurs provinces ; un utilisateur sans province ne voit rien.

Pour être filtrable, un modèle déclare la colonne qui porte la province :
`__perimetre__ = 'province_id'` (ou `'id'` pour la table Province).
Un modèle rattaché à une ferme déclare `__perimetre_ferme__` (`'id'` pour la
ferme, `'ferme_id'` ailleurs) : la règle des fermes s'applique alors (agent
référent, éleveur rattaché, vétérinaire de la province).
"""
import inspect
from functools import wraps

from flask import abort
from flask_login import current_user, login_required
from sqlalchemy import Select, false, select

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


def _condition_fermes(colonne, user):
    """Fermes visibles : l'agent celles dont il est le référent, l'éleveur les siennes,
    le vétérinaire celles de ses provinces ; les autres profils aucune (lot 1)."""
    from app.models.ferme import Ferme
    if user.profil == Profil.AGENT:
        return colonne.in_(select(Ferme.id).where(Ferme.agent_id == user.id))
    if user.profil == Profil.ELEVEUR:
        return colonne.in_(user.ferme_ids)
    if user.profil == Profil.VETO:
        return colonne.in_(select(Ferme.id).where(Ferme.province_id.in_(user.province_ids)))
    if user.profil == Profil.BCEG:
        # Lot 13 : seulement les fermes financées avec un accord en cours du responsable
        from app.services.bceg import condition_acces
        return condition_acces(colonne)
    return false()


def _condition_operateur(modele, user):
    """Lot 19 : un compte OPÉRATEUR ne voit que ce qui concerne SA fiche du registre (lots qui lui sont
    destinés, ses réceptions, ses scans), rien d'autre."""
    attr = getattr(modele, '__perimetre_operateur__', None)
    if attr is None or user.operateur_id is None:
        return false()
    colonne = getattr(modele, attr)
    return colonne(user.operateur_id) if inspect.ismethod(colonne) else colonne == user.operateur_id


def filtre_perimetre(requete, modele=None, utilisateur=None):
    user = utilisateur or current_user
    if not user or not user.is_authenticated:
        return _restreindre(requete, false())
    if user.est_national:
        return requete
    modele = modele or _modele(requete)
    if user.profil == Profil.OPERATEUR:
        return _restreindre(requete, _condition_operateur(modele, user))
    attr_ferme = getattr(modele, '__perimetre_ferme__', None)
    if attr_ferme:
        return _restreindre(requete, _condition_fermes(getattr(modele, attr_ferme), user))
    attr = getattr(modele, '__perimetre__', None)
    if attr is None:
        raise TypeError(f'{modele.__name__} ne déclare pas de colonne de périmètre.')
    return _restreindre(requete, getattr(modele, attr).in_(user.province_ids))
