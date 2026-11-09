"""Bandes d'élevage : une bande = un cycle (≈ 45 jours) dans un bâtiment.

Les saisies de terrain (bande, saisie du jour, pesée, sortie) héritent de
SaisieTerrainMixin : identifiant créé par l'application, prêt pour le hors ligne.
Rien ne se supprime ; une bande clôturée passe en lecture seule.
"""
from app import db
from app.models.base import SaisieTerrainMixin


class StatutBande:
    EN_COURS = 'EN_COURS'
    CLOTUREE = 'CLOTUREE'
    LIBELLES = {EN_COURS: 'En cours', CLOTUREE: 'Clôturée'}


class MotifSortie:
    """Fixés dans le code : l'abattoir exige un opérateur du registre."""
    ABATTOIR = 'Abattoir'
    VENTE = 'Vente'
    AUTRE = 'Autre'
    TOUS = [ABATTOIR, VENTE, AUTRE]


class Bande(SaisieTerrainMixin, db.Model):
    __tablename__ = 'bande'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id          = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    batiment_id       = db.Column(db.Integer, db.ForeignKey('batiment.id'), nullable=False, index=True)
    rang              = db.Column(db.Integer, nullable=False)
    date_mise_en_place = db.Column(db.Date, nullable=False)
    effectif_initial  = db.Column(db.Integer, nullable=False)
    poids_initial_g   = db.Column(db.Numeric(8, 2, asdecimal=False), nullable=False)
    rattrapage        = db.Column(db.Boolean, nullable=False, default=False)
    morts_avant_suivi = db.Column(db.Integer, nullable=False, default=0)   # rattrapage
    date_fin_prevue   = db.Column(db.Date, nullable=False)
    statut            = db.Column(db.String(10), nullable=False, default=StatutBande.EN_COURS, index=True)
    date_cloture      = db.Column(db.Date, nullable=True)
    cloturee_par      = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_cloture     = db.Column(db.Text, nullable=True)
    bilan             = db.Column(db.JSON, nullable=True)   # figé à la clôture
    # Lot 10 : bande ouverte alors que le bâtiment n'était pas marqué « nettoyé et désinfecté »
    ouverte_sans_desinfection = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    ferme = db.relationship('Ferme')
    batiment = db.relationship('Batiment')
    cloturant = db.relationship('Utilisateur', foreign_keys=[cloturee_par])
    poussins = db.relationship('BandePoussins', back_populates='bande', cascade='all, delete-orphan',
                               lazy='selectin')
    saisies = db.relationship('SaisieJour', back_populates='bande', order_by='SaisieJour.date',
                              lazy='selectin')
    pesees = db.relationship('Pesee', back_populates='bande', order_by='Pesee.date', lazy='selectin')
    sorties = db.relationship('Sortie', back_populates='bande', order_by='Sortie.date', lazy='selectin')

    @property
    def numero(self):
        return self.numero_metier

    @property
    def en_cours(self):
        return self.statut == StatutBande.EN_COURS

    @property
    def libelle_statut(self):
        return StatutBande.LIBELLES.get(self.statut, self.statut)


class BandePoussins(db.Model):
    """D'où viennent les poussins mis en place (ligne de livraison du lot 2)."""
    __tablename__ = 'bande_poussins'

    id                 = db.Column(db.Integer, primary_key=True)
    bande_id           = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    livraison_ligne_id = db.Column(db.Integer, db.ForeignKey('livraison_ligne.id'), nullable=False, index=True)
    quantite           = db.Column(db.Integer, nullable=False)

    bande = db.relationship('Bande', back_populates='poussins')
    ligne = db.relationship('LivraisonLigne')


class SaisieJour(SaisieTerrainMixin, db.Model):
    """Saisie du jour d'une bande : une par jour ; un second envoi s'y ajoute."""
    __tablename__ = 'saisie_jour'
    __table_args__ = (db.UniqueConstraint('bande_id', 'date'),)

    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    date            = db.Column(db.Date, nullable=False)
    morts           = db.Column(db.Integer, nullable=False, default=0)
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)

    bande = db.relationship('Bande', back_populates='saisies')
    aliments = db.relationship('SaisieAliment', back_populates='saisie', cascade='all, delete-orphan',
                               lazy='selectin')

    @property
    def sacs(self):
        return sum(a.sacs for a in self.aliments)

    @property
    def kg(self):
        return sum(a.kg for a in self.aliments)


class SaisieAliment(db.Model):
    __tablename__ = 'saisie_aliment'
    __table_args__ = (db.UniqueConstraint('saisie_id', 'produit_id'),)

    id         = db.Column(db.Integer, primary_key=True)
    saisie_id  = db.Column(db.Uuid, db.ForeignKey('saisie_jour.id'), nullable=False, index=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    sacs       = db.Column(db.Numeric(10, 2, asdecimal=False), nullable=False, default=0)
    kg         = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False, default=0)

    saisie = db.relationship('SaisieJour', back_populates='aliments')
    produit = db.relationship('Produit', lazy='joined')


class Pesee(SaisieTerrainMixin, db.Model):
    __tablename__ = 'pesee'

    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    date            = db.Column(db.Date, nullable=False)
    nombre_pesees   = db.Column(db.Integer, nullable=False)
    poids_total_kg  = db.Column(db.Numeric(10, 3, asdecimal=False), nullable=False)
    poids_moyen_g   = db.Column(db.Numeric(10, 1, asdecimal=False), nullable=False)
    poids_attendu_g = db.Column(db.Numeric(10, 1, asdecimal=False), nullable=True)
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)

    bande = db.relationship('Bande', back_populates='pesees')


class Sortie(SaisieTerrainMixin, db.Model):
    """Sortie de poulets. Les ventes (Économie) et les lots QR (Traçabilité) se
    rattacheront à son identifiant, sans colonne supplémentaire ici."""
    __tablename__ = 'sortie'

    bande_id         = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    date             = db.Column(db.Date, nullable=False)
    motif            = db.Column(db.String(20), nullable=False)
    operateur_id     = db.Column(db.Integer, db.ForeignKey('operateur.id'), nullable=True)
    destinataire_libre = db.Column(db.String(150), nullable=True)
    nombre           = db.Column(db.Integer, nullable=False)
    poids_total_kg   = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)
    saisi_par_agent  = db.Column(db.Boolean, nullable=False, default=False)

    bande = db.relationship('Bande', back_populates='sorties')
    operateur = db.relationship('Operateur')

    @property
    def destinataire(self):
        if self.operateur:
            return self.operateur.nom
        return self.destinataire_libre or '—'
