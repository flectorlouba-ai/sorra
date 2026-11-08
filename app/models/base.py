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
