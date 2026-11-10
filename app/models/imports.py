"""Lot B — lots d'import (Excel / CSV), lignes créées par un lot (pour l'annulation) et correspondances mémorisées."""
from app import db
from app.models.base import maintenant


class LotImport(db.Model):
    __tablename__ = 'lot_import'

    id               = db.Column(db.Integer, primary_key=True)
    modele           = db.Column(db.String(30), nullable=False, index=True)
    fichier          = db.Column(db.String(150), nullable=True)
    cree_par         = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    cree_le          = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    nb_lignes        = db.Column(db.Integer, nullable=False, default=0)
    nb_importees     = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    rapport          = db.Column(db.Text, nullable=True)                    # JSON : ligne, ok, erreurs, numéro
    annule_le        = db.Column(db.DateTime(timezone=True), nullable=True)
    annule_par       = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_annulation = db.Column(db.String(300), nullable=True)

    auteur = db.relationship('Utilisateur', foreign_keys=[cree_par])
    lignes = db.relationship('LigneImport', back_populates='lot', cascade='all, delete-orphan', lazy='selectin')


class LigneImport(db.Model):
    __tablename__ = 'ligne_import'

    id                = db.Column(db.Integer, primary_key=True)
    lot_id            = db.Column(db.Integer, db.ForeignKey('lot_import.id'), nullable=False, index=True)
    table_nom         = db.Column(db.String(60), nullable=False)
    enregistrement_id = db.Column(db.String(64), nullable=False)
    ligne             = db.Column(db.Integer, nullable=True)

    lot = db.relationship('LotImport', back_populates='lignes')


class CorrespondanceImport(db.Model):
    """Entête d'un fichier → colonne du modèle, retenue d'un import à l'autre."""
    __tablename__ = 'correspondance_import'
    __table_args__ = (db.UniqueConstraint('modele', 'entete'),)

    id       = db.Column(db.Integer, primary_key=True)
    modele   = db.Column(db.String(30), nullable=False)
    entete   = db.Column(db.String(120), nullable=False)
    colonne  = db.Column(db.String(60), nullable=False)
    cree_par = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
