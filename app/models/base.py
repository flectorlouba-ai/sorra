"""Éléments communs aux tables.

`SaisieTerrainMixin` prépare le hors ligne : toute future table de saisie
terrain (fiche d'élevage, déclaration sanitaire, visite…) en hérite.
- l'identifiant est un UUID produit par l'application, donc aussi par un
  téléphone sans réseau, sans risque de collision à la synchronisation ;
- `numero_metier` est le numéro lisible (ex. EST-000012). Saisi hors ligne, il
  est provisoire (`numero_provisoire`) jusqu'à l'attribution par le serveur ;
- `statut_synchro` dit si la ligne n'existe que sur l'appareil, est à jour,
  ou entre en conflit avec une autre saisie.
"""
import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import declared_attr

from app import db


def maintenant():
    return datetime.now(timezone.utc)


class StatutSynchro(enum.Enum):
    LOCAL       = 'LOCAL'
    SYNCHRONISE = 'SYNCHRONISE'
    CONFLIT     = 'CONFLIT'


class HorodatageMixin:
    cree_le    = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    modifie_le = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant,
                           onupdate=maintenant)


class ArchivableMixin:
    """Lot A : ARCHIVER remplace SUPPRIMER. Un élément archivé est masqué des listes et exclu des calculs,
    mais conservé ; il peut être restauré. Archivage et restauration sont au journal (avant / après)."""
    archive_le = db.Column(db.DateTime(timezone=True), nullable=True)

    @declared_attr
    def archive_par(cls):
        # use_alter : l'utilisateur pointe déjà vers l'opérateur (cycle utilisateur ↔ opérateur)
        return db.Column(db.Uuid, db.ForeignKey('utilisateur.id', use_alter=True), nullable=True)

    @property
    def archive(self):
        return self.archive_le is not None


class SaisieTerrainMixin(HorodatageMixin):
    id                = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    numero_metier     = db.Column(db.String(40), nullable=True, unique=True)
    numero_provisoire = db.Column(db.Boolean, nullable=False, default=False)
    appareil_id       = db.Column(db.String(64), nullable=True)
    statut_synchro    = db.Column(db.Enum(StatutSynchro, native_enum=False, length=12),
                                  nullable=False, default=StatutSynchro.SYNCHRONISE)

    @declared_attr
    def cree_par(cls):
        return db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)

    @declared_attr
    def modifie_par(cls):
        return db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)


# Lot A : les saisies archivées sont masquées de TOUTES les requêtes (listes et calculs) sans retoucher chaque
# requête. Seules les saisies que rien d'autre ne référence sont filtrées ainsi (ferme, bande et achat ne s'archivent
# que vides) ; la sortie (référencée par son lot) a des filtres explicites ; produit, opérateur et bâtiment gardent
# aussi leur colonne `actif`, tenue à jour à l'archivage. Un écran « Voir les archivées » passe l'option
# d'exécution AVEC_ARCHIVES.
AVEC_ARCHIVES = 'avec_archives'
_MASQUEES = []


def masquer_archivees(*modeles):
    _MASQUEES.extend(modeles)


_INSTALLE = []


def installer_masquage(session_cls):
    from sqlalchemy import event
    from sqlalchemy.orm import with_loader_criteria
    if session_cls in _INSTALLE:
        return
    _INSTALLE.append(session_cls)
    event.listen(session_cls, 'before_flush', _synchroniser_actif)

    @event.listens_for(session_cls, 'do_orm_execute')
    def _sans_archives(etat):
        if not etat.is_select or etat.execution_options.get(AVEC_ARCHIVES):
            return
        for m in _MASQUEES:
            etat.statement = etat.statement.options(
                with_loader_criteria(m, lambda cls: cls.archive_le.is_(None), include_aliases=True))


def _synchroniser_actif(session, flush_context, instances):
    """Produit, opérateur, bâtiment : `actif` et l'archivage disent la même chose (« Archiver » remplace
    « Désactiver », lot A point 6)."""
    from sqlalchemy import inspect
    for o in list(session.dirty) + list(session.new):
        if not isinstance(o, ArchivableMixin) or not hasattr(o, 'actif') or o.actif is None:
            continue
        if o in session.new:
            if not o.actif and o.archive_le is None:
                o.archive_le = maintenant()
            continue
        if not inspect(o).attrs.actif.history.has_changes():
            continue
        if o.actif:
            o.archive_le = o.archive_par = None
        elif o.archive_le is None:
            o.archive_le, o.archive_par = maintenant(), _utilisateur_id()


def _utilisateur_id():
    try:
        from flask import has_request_context
        from flask_login import current_user
        if has_request_context() and current_user.is_authenticated:
            return current_user.id
    except Exception:
        pass
    return None
