"""Registre des opérateurs (abattoirs, acheteurs, distributeurs). Pas de suppression :
un opérateur se désactive. Pas de compte de connexion pour eux dans ce lot."""
from app import db
from app.models.base import ArchivableMixin, HorodatageMixin


class Operateur(ArchivableMixin, HorodatageMixin, db.Model):
    __tablename__ = 'operateur'
    __perimetre__ = 'province_id'

    id               = db.Column(db.Integer, primary_key=True)
    numero           = db.Column(db.String(20), unique=True, nullable=False)
    nom              = db.Column(db.String(150), nullable=False)
    type             = db.Column(db.String(150), nullable=False)
    province_id      = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=False,
                                 index=True)
    localite_id      = db.Column(db.Integer, db.ForeignKey('localite.id'), nullable=True)
    contact          = db.Column(db.String(150), nullable=True)
    telephone        = db.Column(db.String(30), nullable=True)
    convention       = db.Column(db.Boolean, nullable=False, default=False)
    convention_date  = db.Column(db.Date, nullable=True)
    actif            = db.Column(db.Boolean, nullable=False, default=True)

    province = db.relationship('Province')
    localite = db.relationship('Localite')

    def __repr__(self):
        return f'<Operateur {self.numero}>'
