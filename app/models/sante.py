"""Santé animale : déclarations sanitaires, alertes, calendrier vaccinal,
vaccinations et traitements.

Une déclaration n'est transmise qu'aux services vétérinaires de la province (et
reste visible de l'éleveur qui l'a faite). Une alerte n'est visible de la DGE
qu'une fois CONFIRMÉE par un vétérinaire ; jamais du public.
"""
from app import db
from app.models.base import SaisieTerrainMixin, HorodatageMixin, maintenant


class StatutAlerte:
    NOUVELLE = 'NOUVELLE'
    EN_ANALYSE = 'EN_ANALYSE'
    CONFIRMEE = 'CONFIRMEE'
    INFIRMEE = 'INFIRMEE'
    CLOSE = 'CLOSE'
    LIBELLES = {NOUVELLE: 'Nouvelle', EN_ANALYSE: 'En analyse', CONFIRMEE: 'Confirmée',
                INFIRMEE: 'Infirmée', CLOSE: 'Close'}
    # Nouvelle → En analyse → Confirmée ou Infirmée → Close
    SUIVANTS = {NOUVELLE: [EN_ANALYSE], EN_ANALYSE: [CONFIRMEE, INFIRMEE],
                CONFIRMEE: [CLOSE], INFIRMEE: [CLOSE], CLOSE: []}
    OUVERTES = (NOUVELLE, EN_ANALYSE)


class OrigineAlerte:
    DECLARATION = 'DECLARATION'
    FEU_ROUGE = 'FEU_ROUGE'
    RECEPTION = 'RECEPTION'    # lot 19 : morts à la réception (abattoir, marché) au-delà du seuil
    LIBELLES = {DECLARATION: 'Déclaration de l\'éleveur', FEU_ROUGE: 'Mortalité anormale (feu rouge)',
                RECEPTION: 'Morts à la réception du lot'}


class Declaration(SaisieTerrainMixin, db.Model):
    __tablename__ = 'declaration'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id        = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=True, index=True)
    signes          = db.Column(db.JSON, nullable=False, default=list)
    nombre_animaux  = db.Column(db.Integer, nullable=False, default=1)
    audio           = db.Column(db.String(80), nullable=True)      # nom du fichier enregistré
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)

    ferme = db.relationship('Ferme')
    bande = db.relationship('Bande')
    photos = db.relationship('DeclarationPhoto', back_populates='declaration', cascade='all, delete-orphan',
                             order_by='DeclarationPhoto.id', lazy='selectin')
    auteur = db.relationship('Utilisateur', foreign_keys='Declaration.cree_par')


class DeclarationPhoto(db.Model):
    __tablename__ = 'declaration_photo'

    id             = db.Column(db.Integer, primary_key=True)
    declaration_id = db.Column(db.Uuid, db.ForeignKey('declaration.id'), nullable=False, index=True)
    fichier        = db.Column(db.String(80), nullable=False)
    type_mime      = db.Column(db.String(30), nullable=False)

    declaration = db.relationship('Declaration', back_populates='photos')


class AlerteSanitaire(HorodatageMixin, db.Model):
    __tablename__ = 'alerte_sanitaire'
    __perimetre_ferme__ = 'ferme_id'

    id             = db.Column(db.Integer, primary_key=True)
    numero         = db.Column(db.String(20), unique=True, nullable=False)
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    bande_id       = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=True, index=True)
    declaration_id = db.Column(db.Uuid, db.ForeignKey('declaration.id'), nullable=True)
    origine        = db.Column(db.String(12), nullable=False)
    statut         = db.Column(db.String(12), nullable=False, default=StatutAlerte.NOUVELLE, index=True)
    confirmee      = db.Column(db.Boolean, nullable=False, default=False)   # visible de la DGE

    ferme = db.relationship('Ferme')
    bande = db.relationship('Bande')
    declaration = db.relationship('Declaration')
    historique = db.relationship('AlerteHistorique', back_populates='alerte', order_by='AlerteHistorique.date',
                                 cascade='all, delete-orphan', lazy='selectin')
    reponses = db.relationship('ReponseVeterinaire', back_populates='alerte', order_by='ReponseVeterinaire.id',
                               lazy='selectin')

    @property
    def libelle_statut(self):
        return StatutAlerte.LIBELLES.get(self.statut, self.statut)

    @property
    def libelle_origine(self):
        return OrigineAlerte.LIBELLES.get(self.origine, self.origine)


class AlerteHistorique(db.Model):
    __tablename__ = 'alerte_historique'
    __journal_exclu__ = True   # le changement de statut figure déjà dans la modification de l'alerte

    id             = db.Column(db.Integer, primary_key=True)
    alerte_id      = db.Column(db.Integer, db.ForeignKey('alerte_sanitaire.id'), nullable=False, index=True)
    statut         = db.Column(db.String(12), nullable=False)
    date           = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    commentaire    = db.Column(db.Text, nullable=True)

    alerte = db.relationship('AlerteSanitaire', back_populates='historique')
    auteur = db.relationship('Utilisateur')


class CalendrierVaccinal(db.Model):
    """Calendrier de référence : âge (jours) → vaccin du catalogue et mode."""
    __tablename__ = 'calendrier_vaccinal'

    id         = db.Column(db.Integer, primary_key=True)
    age_jours  = db.Column(db.Integer, nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    mode       = db.Column(db.String(60), nullable=False)
    actif      = db.Column(db.Boolean, nullable=False, default=True)

    produit = db.relationship('Produit', lazy='joined')


class Vaccination(SaisieTerrainMixin, db.Model):
    __tablename__ = 'vaccination'

    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    calendrier_id   = db.Column(db.Integer, db.ForeignKey('calendrier_vaccinal.id'), nullable=True)
    date            = db.Column(db.Date, nullable=False)
    produit_id      = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    mode            = db.Column(db.String(60), nullable=False)
    nombre_animaux  = db.Column(db.Integer, nullable=False)
    quantite        = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)   # déduite du stock
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)
    annule          = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())   # lot 11 : « Annuler (10) »

    bande = db.relationship('Bande')
    produit = db.relationship('Produit', lazy='joined')
    calendrier = db.relationship('CalendrierVaccinal')


class Traitement(SaisieTerrainMixin, db.Model):
    __tablename__ = 'traitement'

    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=False, index=True)
    date_debut      = db.Column(db.Date, nullable=False)
    date_fin        = db.Column(db.Date, nullable=False)
    produit_id      = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=False)
    motif           = db.Column(db.String(200), nullable=False)
    nombre_animaux  = db.Column(db.Integer, nullable=False)
    quantite        = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=False)   # déduite du stock
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)

    bande = db.relationship('Bande')
    produit = db.relationship('Produit', lazy='joined')


class ReponseVeterinaire(HorodatageMixin, db.Model):
    """Réponse du vétérinaire à l'éleveur sur une alerte (lot 12) : datée, signée, au journal.
    Ne s'efface pas ; `lue_le` fait disparaître la pastille de l'éleveur."""
    __tablename__ = 'reponse_veterinaire'

    id        = db.Column(db.Integer, primary_key=True)
    alerte_id = db.Column(db.Integer, db.ForeignKey('alerte_sanitaire.id'), nullable=False, index=True)
    texte     = db.Column(db.String(300), nullable=True)
    conseils  = db.Column(db.JSON, nullable=False, default=list)
    veto_id   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    lue_le    = db.Column(db.DateTime(timezone=True), nullable=True)

    alerte = db.relationship('AlerteSanitaire', back_populates='reponses')
    veto = db.relationship('Utilisateur')

