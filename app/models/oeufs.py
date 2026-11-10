"""Lot F — vente d'œufs d'une bande de ponte (recette de Mon argent)."""
from app import db
from app.models.base import ArchivableMixin, SaisieTerrainMixin


class VenteOeufs(ArchivableMixin, SaisieTerrainMixin, db.Model):
    __tablename__ = 'vente_oeufs'

    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    date            = db.Column(db.Date, nullable=False, index=True)
    oeufs           = db.Column(db.Integer, nullable=False)
    montant_fcfa    = db.Column(db.Integer, nullable=True)
    acheteur        = db.Column(db.String(150), nullable=True)
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    bande = db.relationship('Bande')

    @property
    def numero(self):
        return self.numero_metier

    @property
    def ferme(self):
        return self.bande.ferme
