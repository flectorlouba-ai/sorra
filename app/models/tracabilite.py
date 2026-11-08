"""Traçabilité : lots de poulets sortis vers un abattoir ou vendus, et leur QR code.

Chaque sortie « Abattoir » ou « Vente » crée un lot numéroté comme la bande, suivi
du rang de la sortie (EST-001-B1-07-S2), jamais réutilisé. Le QR code ne contient
qu'une adresse avec un code tiré au hasard (impossible à deviner) ; la page publique
ne montre ni téléphone ni nom de personne. Les lectures sont inscrites au journal.
"""
from app import db
from app.models.base import HorodatageMixin


class LotTrace(HorodatageMixin, db.Model):
    __tablename__ = 'lot_trace'
    __perimetre_ferme__ = 'ferme_id'
    __journal_masquer__ = {'code'}   # le code du QR n'apparaît pas en clair dans le journal

    id               = db.Column(db.Integer, primary_key=True)
    numero           = db.Column(db.String(50), unique=True, nullable=False)
    code             = db.Column(db.String(40), unique=True, nullable=False)
    sortie_id        = db.Column(db.Uuid, db.ForeignKey('sortie.id'), unique=True, nullable=False)
    ferme_id         = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    cree_par         = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    annule           = db.Column(db.Boolean, nullable=False, default=False)
    motif_annulation = db.Column(db.Text, nullable=True)

    sortie = db.relationship('Sortie', backref=db.backref('lot', uselist=False))
    ferme = db.relationship('Ferme')
    createur = db.relationship('Utilisateur')

    def __repr__(self):
        return f'<LotTrace {self.numero}>'
