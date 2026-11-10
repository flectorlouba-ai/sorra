"""Lot D — plans d'actions."""
from datetime import date

from app import db
from app.models.base import ArchivableMixin, HorodatageMixin, maintenant


class OrigineAction:
    ALERTE = 'ALERTE'
    VISITE = 'VISITE'
    RAPPORT = 'RAPPORT'
    ARBITRAGE = 'ARBITRAGE'
    MANUEL = 'MANUEL'
    TOUS = (ALERTE, VISITE, RAPPORT, ARBITRAGE, MANUEL)
    LIBELLES = {ALERTE: 'Alerte sanitaire', VISITE: 'Visite', RAPPORT: 'Rapport', ARBITRAGE: 'Arbitrage', MANUEL: 'Manuelle'}


class Priorite:
    HAUTE, MOYENNE, BASSE = 'HAUTE', 'MOYENNE', 'BASSE'
    TOUTES = (HAUTE, MOYENNE, BASSE)
    LIBELLES = {HAUTE: 'Haute', MOYENNE: 'Moyenne', BASSE: 'Basse'}


class Action(ArchivableMixin, HorodatageMixin, db.Model):
    """Une action d'un plan d'actions (lot D). L'état est calculé : à faire, en cours, faite, en retard."""
    __tablename__ = 'action'
    __perimetre_ferme__ = 'ferme_id'

    id             = db.Column(db.Integer, primary_key=True)
    numero         = db.Column(db.String(20), nullable=False, unique=True)
    intitule       = db.Column(db.String(200), nullable=False)
    origine        = db.Column(db.String(10), nullable=False, default=OrigineAction.MANUEL)
    origine_table  = db.Column(db.String(40), nullable=True)
    origine_id     = db.Column(db.String(64), nullable=True)
    perimetre      = db.Column(db.String(10), nullable=False, default='FERME')        # FERME, PROVINCE, NATIONAL
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=True, index=True)
    province_id    = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=True)
    responsable_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False, index=True)
    creee_par      = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    echeance       = db.Column(db.Date, nullable=False, index=True)
    priorite       = db.Column(db.String(8), nullable=False, default=Priorite.MOYENNE)
    avancement     = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    faite_le       = db.Column(db.DateTime(timezone=True), nullable=True)
    commentaire    = db.Column(db.String(1000), nullable=True)
    photo          = db.Column(db.String(80), nullable=True)

    ferme = db.relationship('Ferme')
    province = db.relationship('Province')
    responsable = db.relationship('Utilisateur', foreign_keys=[responsable_id])
    createur = db.relationship('Utilisateur', foreign_keys=[creee_par])

    @property
    def etat(self):
        if self.faite_le is not None:
            return 'FAITE'
        if self.echeance < date.today():
            return 'RETARD'
        return 'EN_COURS' if self.avancement > 0 else 'A_FAIRE'

    LIBELLES_ETAT = {'A_FAIRE': 'À faire', 'EN_COURS': 'En cours', 'FAITE': 'Faite', 'RETARD': 'En retard'}

    @property
    def libelle_etat(self):
        return self.LIBELLES_ETAT[self.etat]

    @property
    def retard_jours(self):
        return (date.today() - self.echeance).days if self.etat == 'RETARD' else 0

    @property
    def libelle_perimetre(self):
        if self.perimetre == 'FERME' and self.ferme:
            return f'{self.ferme.numero} · {self.ferme.nom}'
        if self.perimetre == 'PROVINCE' and self.province:
            return self.province.nom
        return 'National'

    @property
    def libelle_origine(self):
        return OrigineAction.LIBELLES.get(self.origine, self.origine)
