"""Journal d'audit, en écriture seule.

Trois protections contre la modification ou la suppression :
1. aucune route ne le permet ;
2. l'application refuse toute mise à jour ou suppression par le modèle (ci-dessous) ;
3. la base refuse UPDATE et DELETE par un déclencheur posé par la migration.
"""
from sqlalchemy import event

from app import db
from app.models.base import maintenant


class JournalNonModifiable(Exception):
    pass


class JournalAudit(db.Model):
    __tablename__ = 'journal_audit'

    id               = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                                 primary_key=True)
    horodatage       = db.Column(db.DateTime(timezone=True), nullable=False,
                                 default=maintenant, index=True)
    utilisateur_id   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True,
                                 index=True)
    identifiant      = db.Column(db.String(64), nullable=True)
    adresse_ip       = db.Column(db.String(45), nullable=True)
    action           = db.Column(db.String(20), nullable=False, index=True)
    table_nom        = db.Column(db.String(60), nullable=True, index=True)
    enregistrement_id = db.Column(db.String(64), nullable=True)
    avant            = db.Column(db.JSON, nullable=True)
    apres            = db.Column(db.JSON, nullable=True)
    detail           = db.Column(db.Text, nullable=True)

    utilisateur = db.relationship('Utilisateur')


@event.listens_for(JournalAudit, 'before_update')
def _refuser_modification(mapper, connection, cible):
    raise JournalNonModifiable('Le journal d\'audit ne peut pas être modifié.')


@event.listens_for(JournalAudit, 'before_delete')
def _refuser_suppression(mapper, connection, cible):
    raise JournalNonModifiable('Le journal d\'audit ne peut pas être supprimé.')
