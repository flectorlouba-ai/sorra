from app import db


class Compteur(db.Model):
    """Dernier numéro attribué pour un couple (type, préfixe), par année ou non.
    `annee` vaut 0 pour une numérotation continue : une valeur NULL ne serait
    pas protégée par la contrainte d'unicité sous PostgreSQL."""
    __tablename__ = 'compteur'
    __table_args__ = (db.UniqueConstraint('type', 'prefixe', 'annee'),)

    id             = db.Column(db.Integer, primary_key=True)
    type           = db.Column(db.String(40), nullable=False)
    prefixe        = db.Column(db.String(20), nullable=False)
    annee          = db.Column(db.Integer, nullable=False, default=0)
    dernier_numero = db.Column(db.Integer, nullable=False, default=0)
