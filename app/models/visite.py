"""Visites techniques de l'agent (lot 12) : planifiées, puis compte rendu (constats,
recommandations, position GPS, photo), lu par l'éleveur dans « 👤 Moi → 📋 Mes visites »."""
from app import db
from app.models.base import ArchivableMixin, SaisieTerrainMixin


class StatutVisite:
    PREVUE = 'PREVUE'
    FAITE = 'FAITE'
    ANNULEE = 'ANNULEE'


class Visite(ArchivableMixin, SaisieTerrainMixin, db.Model):
    __tablename__ = 'visite'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id             = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    agent_id             = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    date_prevue          = db.Column(db.Date, nullable=True, index=True)
    objet                = db.Column(db.String(60), nullable=False)
    statut               = db.Column(db.String(10), nullable=False, default=StatutVisite.PREVUE, index=True)
    faite_le             = db.Column(db.Date, nullable=True)
    constats             = db.Column(db.String(500), nullable=True)
    recommandations      = db.Column(db.JSON, nullable=False, default=list)
    recommandation_libre = db.Column(db.String(300), nullable=True)
    latitude             = db.Column(db.Float, nullable=True)
    longitude            = db.Column(db.Float, nullable=True)
    photo                = db.Column(db.String(80), nullable=True)
    # Lot E : précision du téléphone, distance à la ferme (recalculée par le serveur), explication si éloignée
    precision_m          = db.Column(db.Integer, nullable=True)
    distance_m           = db.Column(db.Integer, nullable=True)
    motif_distance       = db.Column(db.String(300), nullable=True)
    motif_annulation     = db.Column(db.String(300), nullable=True)
    vue_par_eleveur_le   = db.Column(db.DateTime(timezone=True), nullable=True)
    # Lot 16 : biosécurité (grille {point: oui/non/so}, score %, mesures correctives [{point, mesure}])
    biosecurite          = db.Column(db.JSON, nullable=True)
    score_biosecurite    = db.Column(db.Integer, nullable=True)
    mesures_correctives  = db.Column(db.JSON, nullable=True)

    ferme = db.relationship('Ferme')
    agent = db.relationship('Utilisateur', foreign_keys=[agent_id])

    @property
    def toutes_recommandations(self):
        return list(self.recommandations or []) + ([self.recommandation_libre] if self.recommandation_libre else [])
