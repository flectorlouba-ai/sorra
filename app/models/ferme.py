"""Fermes, bâtiments, historique du statut, infrastructures.

Une ferme ne se supprime pas (statut « Suspendue ») ; un bâtiment non plus
(actif / inactif). La ferme hérite de SaisieTerrainMixin : elle est créée sur
le terrain et son numéro (EST-001) est `numero_metier`.
"""
from app import db
from app.models.base import ArchivableMixin, SaisieTerrainMixin, maintenant


class SourcePosition:
    GPS = 'GPS'
    MANUELLE = 'MANUELLE'


class Ferme(ArchivableMixin, SaisieTerrainMixin, db.Model):
    __tablename__ = 'ferme'
    __perimetre__ = 'province_id'
    __perimetre_ferme__ = 'id'
    __journal_ignorer__ = {'telephone_normalise'}
    __journal_relations__ = {'infrastructures': 'infrastructure'}

    nom                  = db.Column(db.String(150), nullable=False)
    exploitant_nom       = db.Column(db.String(150), nullable=False)
    exploitant_telephone = db.Column(db.String(30), nullable=False)
    telephone_normalise  = db.Column(db.String(20), nullable=False, index=True)
    province_id          = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=False,
                                     index=True)
    localite_id          = db.Column(db.Integer, db.ForeignKey('localite.id'), nullable=False,
                                     index=True)
    reference_ami        = db.Column(db.String(60), nullable=True, unique=True)
    cohorte              = db.Column(db.Integer, nullable=True)
    statut               = db.Column(db.String(150), nullable=False)
    agent_id             = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True,
                                     index=True)
    observations         = db.Column(db.Text, nullable=True)

    latitude             = db.Column(db.Float, nullable=True)
    longitude            = db.Column(db.Float, nullable=True)
    gps_precision_m      = db.Column(db.Integer, nullable=True)
    gps_date             = db.Column(db.DateTime(timezone=True), nullable=True)
    gps_source           = db.Column(db.String(10), nullable=True)
    # Lot 13 : financement BCEG et responsable de la ferme (seul à répondre « Ma banque »)
    financee_bceg        = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    responsable_id       = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    # Lot A3 : membre du programme POUFA (sinon : ni livraisons ni commandes de l'État, pas de cible) ; capacité
    programme_poufa      = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    bandes_par_an        = db.Column(db.Integer, nullable=True, default=6, server_default='6')
    # Lot E : position gardée hors de la province (ou corrigée loin) : à vérifier par la DGE
    position_a_verifier  = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())

    province = db.relationship('Province')
    responsable = db.relationship('Utilisateur', foreign_keys=[responsable_id])
    localite = db.relationship('Localite')
    agent    = db.relationship('Utilisateur', foreign_keys=[agent_id])
    batiments = db.relationship('Batiment', back_populates='ferme', order_by='Batiment.rang',
                                lazy='selectin')
    historique = db.relationship('FermeStatutHistorique', back_populates='ferme',
                                 order_by='FermeStatutHistorique.date.desc()',
                                 cascade='all, delete-orphan')
    infrastructures = db.relationship('FermeInfrastructure', cascade='all, delete-orphan',
                                      order_by='FermeInfrastructure.infrastructure',
                                      lazy='selectin')

    @property
    def numero(self):
        return self.numero_metier

    @property
    def capacite_a_completer(self):
        """Lot A3 : aucun bâtiment en service, aucune place, ou bandes par an non renseignées."""
        return not self.capacite or not self.bandes_par_an

    @property
    def libelle_programme(self):
        return 'Programme POUFA' if self.programme_poufa else 'Hors programme'

    @property
    def capacite(self):
        """Places de la ferme : somme des bâtiments actifs (jamais saisie)."""
        return sum(b.capacite for b in self.batiments if b.actif)

    @property
    def a_une_position(self):
        return self.latitude is not None and self.longitude is not None

    def __repr__(self):
        return f'<Ferme {self.numero_metier}>'


class Batiment(ArchivableMixin, db.Model):
    __tablename__ = 'batiment'
    __table_args__ = (db.UniqueConstraint('ferme_id', 'code'),)

    id       = db.Column(db.Integer, primary_key=True)
    ferme_id = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    rang     = db.Column(db.Integer, nullable=False)
    code     = db.Column(db.String(10), nullable=False)
    nom      = db.Column(db.String(120), nullable=True)
    capacite = db.Column(db.Integer, nullable=False, default=0)
    actif    = db.Column(db.Boolean, nullable=False, default=True)

    ferme = db.relationship('Ferme', back_populates='batiments')


class FermeStatutHistorique(db.Model):
    __tablename__ = 'ferme_statut_historique'
    __journal_exclu__ = True   # le changement figure déjà dans la modification de la ferme

    id             = db.Column(db.Integer, primary_key=True)
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    statut         = db.Column(db.String(150), nullable=False)
    date           = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)

    ferme  = db.relationship('Ferme', back_populates='historique')
    auteur = db.relationship('Utilisateur')


class FermeInfrastructure(db.Model):
    __tablename__ = 'ferme_infrastructure'
    __journal_exclu__ = True   # suivi par la relation `infrastructures` de la ferme

    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id', ondelete='CASCADE'),
                               primary_key=True)
    infrastructure = db.Column(db.String(150), primary_key=True)
