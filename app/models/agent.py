"""Lot 16 — écrans de l'agent : commandes d'intrants (Envoyée → Validée/Refusée → Livrée) et
inventaires de stock (écart livré − utilisé − compté)."""
from app import db
from app.models.base import HorodatageMixin


class StatutCommande:
    ENVOYEE = 'ENVOYEE'
    VALIDEE = 'VALIDEE'
    REFUSEE = 'REFUSEE'
    LIVREE = 'LIVREE'
    LIBELLES = {ENVOYEE: 'Envoyée', VALIDEE: 'Validée', REFUSEE: 'Refusée', LIVREE: 'Livrée'}


class CommandeIntrant(HorodatageMixin, db.Model):
    __tablename__ = 'commande_intrant'
    __perimetre_ferme__ = 'ferme_id'

    id            = db.Column(db.Integer, primary_key=True)
    ferme_id      = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    produit_id    = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    quantite      = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    motif         = db.Column(db.String(300), nullable=True)
    statut        = db.Column(db.String(10), nullable=False, default=StatutCommande.ENVOYEE, index=True)
    demandee_par  = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    decidee_par   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    decidee_le    = db.Column(db.DateTime(timezone=True), nullable=True)
    motif_refus   = db.Column(db.String(300), nullable=True)
    refus_lu_le   = db.Column(db.DateTime(timezone=True), nullable=True)
    livraison_id  = db.Column(db.Uuid, db.ForeignKey('livraison.id'), nullable=True)

    ferme = db.relationship('Ferme')
    produit = db.relationship('Produit', lazy='joined')
    demandeur = db.relationship('Utilisateur', foreign_keys=[demandee_par])
    decideur = db.relationship('Utilisateur', foreign_keys=[decidee_par])
    livraison = db.relationship('Livraison')

    @property
    def libelle_statut(self):
        return StatutCommande.LIBELLES.get(self.statut, self.statut)


class InventaireStock(HorodatageMixin, db.Model):
    """Stock compté par l'agent ; livré et utilisé sont figés au moment du comptage."""
    __tablename__ = 'inventaire_stock'
    __perimetre_ferme__ = 'ferme_id'

    id         = db.Column(db.Integer, primary_key=True)
    ferme_id   = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    jour       = db.Column(db.Date, nullable=False)
    livre      = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    utilise    = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    compte     = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    agent_id   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)

    ferme = db.relationship('Ferme')
    produit = db.relationship('Produit', lazy='joined')

    @property
    def ecart(self):
        return round((self.livre or 0) - (self.utilise or 0) - (self.compte or 0), 2)

    @property
    def ecart_pct(self):
        return round(abs(self.ecart) * 100 / self.livre, 1) if self.livre else 0
