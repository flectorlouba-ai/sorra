"""Lot E — historique des positions d'une ferme (aucune n'est écrasée)."""
from app import db


class OriginePosition:
    GPS = 'GPS'               # relevé sur place
    MANUELLE = 'MANUELLE'     # corrigée à la main
    REPRISE = 'REPRISE'       # reprise des fiches (approximative)
    LIBELLES = {GPS: 'Relevé GPS', MANUELLE: 'Corrigée à la main', REPRISE: 'Reprise des fiches (approximative)'}


class PositionFerme(db.Model):
    __tablename__ = 'position_ferme'
    __perimetre_ferme__ = 'ferme_id'

    id                   = db.Column(db.Integer, primary_key=True)
    ferme_id             = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    latitude             = db.Column(db.Float, nullable=False)
    longitude            = db.Column(db.Float, nullable=False)
    precision_m          = db.Column(db.Integer, nullable=True)
    releve_le            = db.Column(db.DateTime(timezone=True), nullable=False)
    auteur_id            = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    appareil             = db.Column(db.String(64), nullable=True)
    hors_ligne           = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    origine              = db.Column(db.String(10), nullable=False)
    motif                = db.Column(db.String(300), nullable=True)
    province_trouvee     = db.Column(db.String(5), nullable=True)
    distance_province_km = db.Column(db.Integer, nullable=True)
    a_verifier           = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    en_vigueur           = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    ferme = db.relationship('Ferme')
    auteur = db.relationship('Utilisateur')

    @property
    def libelle_origine(self):
        return OriginePosition.LIBELLES.get(self.origine, self.origine)
