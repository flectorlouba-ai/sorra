"""Intrants : catalogue des produits, livraisons aux fermes et leur confirmation.

Les types et les unités sont fixés ici (et non dans les listes configurables) :
l'application s'appuie sur « Poussins » (morts à l'arrivée, attente de bande)
et « Aliment » (sacs ↔ kg). Les renommer casserait ces calculs.
"""
from app import db
from app.models.base import SaisieTerrainMixin, HorodatageMixin

TYPE_POUSSINS = 'Poussins'
TYPE_ALIMENT = 'Aliment'
TYPES_INTRANT = [TYPE_POUSSINS, TYPE_ALIMENT, 'Vaccin', 'Médicament', 'Autre']
UNITE_SACS = 'sacs'
UNITES = ['têtes', UNITE_SACS, 'kg', 'doses', 'flacons', 'litres', 'unités']


class StatutLivraison:
    A_CONFIRMER = 'A_CONFIRMER'
    RECUE = 'RECUE'
    RECUE_ECART = 'RECUE_ECART'
    ANNULEE = 'ANNULEE'

    LIBELLES = {A_CONFIRMER: 'À confirmer', RECUE: 'Reçue', RECUE_ECART: 'Reçue avec écart',
                ANNULEE: 'Annulée'}
    CONFIRMEES = (RECUE, RECUE_ECART)


class Produit(HorodatageMixin, db.Model):
    __tablename__ = 'produit'

    id           = db.Column(db.Integer, primary_key=True)
    nom          = db.Column(db.String(150), nullable=False, unique=True)
    type         = db.Column(db.String(20), nullable=False)
    unite        = db.Column(db.String(20), nullable=False)
    poids_sac_kg = db.Column(db.Numeric(8, 2, asdecimal=False), nullable=True)
    # Médicaments : jours d'attente entre la fin d'un traitement et l'abattage
    delai_attente_jours = db.Column(db.Integer, nullable=True)
    actif        = db.Column(db.Boolean, nullable=False, default=True)

    @property
    def en_sacs(self):
        return self.unite == UNITE_SACS and bool(self.poids_sac_kg)

    def __repr__(self):
        return f'<Produit {self.nom}>'


class Livraison(SaisieTerrainMixin, db.Model):
    """Une livraison = une ferme, une date, un fournisseur, une ou plusieurs lignes.
    Le numéro (LIV-2026-000001) est `numero_metier`. Pas de suppression."""
    __tablename__ = 'livraison'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id          = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    date_livraison    = db.Column(db.Date, nullable=False)
    fournisseur       = db.Column(db.String(150), nullable=True)
    statut            = db.Column(db.String(12), nullable=False, default=StatutLivraison.A_CONFIRMER,
                                  index=True)
    confirmee_le      = db.Column(db.DateTime(timezone=True), nullable=True)
    confirmee_par     = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    confirmee_par_agent = db.Column(db.Boolean, nullable=False, default=False)
    annulee_le        = db.Column(db.DateTime(timezone=True), nullable=True)
    annulee_par       = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_annulation  = db.Column(db.Text, nullable=True)

    ferme = db.relationship('Ferme')
    lignes = db.relationship('LivraisonLigne', back_populates='livraison',
                             cascade='all, delete-orphan', order_by='LivraisonLigne.id',
                             lazy='selectin')
    confirmateur = db.relationship('Utilisateur', foreign_keys=[confirmee_par])
    annulateur = db.relationship('Utilisateur', foreign_keys=[annulee_par])

    @property
    def numero(self):
        return self.numero_metier

    @property
    def libelle_statut(self):
        return StatutLivraison.LIBELLES.get(self.statut, self.statut)

    @property
    def a_confirmer(self):
        return self.statut == StatutLivraison.A_CONFIRMER

    @property
    def confirmee(self):
        return self.statut in StatutLivraison.CONFIRMEES

    @property
    def contient_poussins(self):
        return any(l.produit.type == TYPE_POUSSINS for l in self.lignes)


class LivraisonLigne(db.Model):
    __tablename__ = 'livraison_ligne'
    __table_args__ = (db.UniqueConstraint('livraison_id', 'produit_id'),)

    id                  = db.Column(db.Integer, primary_key=True)
    livraison_id        = db.Column(db.Uuid, db.ForeignKey('livraison.id'), nullable=False, index=True)
    produit_id          = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    quantite_livree     = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    subventionne        = db.Column(db.Boolean, nullable=False, default=False)
    part_subventionnee  = db.Column(db.Integer, nullable=True)        # en %
    valeur_unitaire     = db.Column(db.Integer, nullable=True)        # en FCFA
    quantite_recue      = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    motif_ecart         = db.Column(db.String(150), nullable=True)
    morts_arrivee       = db.Column(db.Integer, nullable=True)        # poussins seulement

    livraison = db.relationship('Livraison', back_populates='lignes')
    produit = db.relationship('Produit', lazy='joined')

    @property
    def ecart(self):
        if self.quantite_recue is None:
            return None
        return self.quantite_recue - self.quantite_livree
