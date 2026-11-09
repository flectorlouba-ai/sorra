"""Consentement BCEG (lot 13, fonction 5 du cahier des charges) : seul le responsable d'une ferme
financée répond ; chaque réponse est une ligne datée, jamais modifiée (historique). La dernière
ligne de la ferme dit l'état : ACCEPTE = accord en cours ; REFUSE, RETIRE, ou CADUC (changement
de responsable) = aucun accès de la BCEG."""
from app import db
from app.models.base import maintenant


class DecisionBceg:
    ACCEPTE = 'ACCEPTE'
    REFUSE = 'REFUSE'
    RETIRE = 'RETIRE'
    CADUC = 'CADUC'
    LIBELLES = {ACCEPTE: 'Accord donné', REFUSE: 'Refus', RETIRE: 'Accord retiré',
                CADUC: 'Accord tombé (changement de responsable)'}


class ConsentementBceg(db.Model):
    __tablename__ = 'consentement_bceg'
    __perimetre_ferme__ = 'ferme_id'

    id             = db.Column(db.Integer, primary_key=True)
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    decision       = db.Column(db.String(10), nullable=False)
    cree_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)

    ferme = db.relationship('Ferme')
    utilisateur = db.relationship('Utilisateur')

    @property
    def libelle(self):
        return DecisionBceg.LIBELLES.get(self.decision, self.decision)
