"""Lot 17 — écrans du vétérinaire : diagnostics (contenu réservé aux vétérinaires) et blocage des
sorties d'une bande (levé par un vétérinaire seulement, avec motif)."""
from app import db
from app.models.base import HorodatageMixin


class Diagnostic(HorodatageMixin, db.Model):
    __tablename__ = 'diagnostic'

    id          = db.Column(db.Integer, primary_key=True)
    alerte_id   = db.Column(db.Integer, db.ForeignKey('alerte_sanitaire.id'), nullable=False, index=True)
    maladie     = db.Column(db.String(150), nullable=False)
    prelevement = db.Column(db.Boolean, nullable=False, default=False)
    observations = db.Column(db.String(1000), nullable=True)
    veto_id     = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)

    alerte = db.relationship('AlerteSanitaire', backref=db.backref('diagnostics', order_by='Diagnostic.id.desc()'))
    veto = db.relationship('Utilisateur')


class BlocageSorties(HorodatageMixin, db.Model):
    """Une ligne par blocage ; actif tant que `leve_le` est vide."""
    __tablename__ = 'blocage_sorties'
    __perimetre_ferme__ = 'ferme_id'

    id          = db.Column(db.Integer, primary_key=True)
    bande_id    = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    ferme_id    = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    alerte_id   = db.Column(db.Integer, db.ForeignKey('alerte_sanitaire.id'), nullable=True)
    motif       = db.Column(db.String(300), nullable=False)
    pose_par    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    leve_le     = db.Column(db.DateTime(timezone=True), nullable=True)
    leve_par    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_levee = db.Column(db.String(300), nullable=True)

    bande = db.relationship('Bande')
    ferme = db.relationship('Ferme')
    alerte = db.relationship('AlerteSanitaire')
    poseur = db.relationship('Utilisateur', foreign_keys=[pose_par])
    leveur = db.relationship('Utilisateur', foreign_keys=[leve_par])

    @property
    def actif(self):
        return self.leve_le is None
