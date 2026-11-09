"""Lot 18 — rapports mensuels nationaux produits automatiquement et gardés (jamais modifiés)."""
from app import db
from app.models.base import maintenant


class RapportMensuel(db.Model):
    __tablename__ = 'rapport_mensuel'

    id               = db.Column(db.Integer, primary_key=True)
    mois             = db.Column(db.String(7), nullable=False, unique=True)      # « 2026-10 »
    fichier          = db.Column(db.String(80), nullable=False)
    genere_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    genere_par       = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    email_prepare_le = db.Column(db.DateTime(timezone=True), nullable=True)
    email_envoye_le  = db.Column(db.DateTime(timezone=True), nullable=True)
