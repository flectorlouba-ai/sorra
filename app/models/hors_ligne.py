"""Saisies faites sans réseau puis envoyées au retour du réseau.

Chaque saisie gardée sur le téléphone porte un identifiant unique (UUID) tiré
sur l'appareil. Le serveur note chaque identifiant reçu : un même envoi rejoué
(coupure pendant l'envoi, double clic) n'est jamais compté deux fois.
Règle des conflits (lot 12) : deux personnes, deux versions gardées ; celle de l'éleveur compte
jusqu'à la décision de l'agent (ou de la DGE), avec motif. Rien n'est perdu ni écrasé.
"""
from app import db
from app.models.base import maintenant


class EnvoiHorsLigne(db.Model):
    __tablename__ = 'envoi_hors_ligne'
    __journal_exclu__ = True   # la saisie elle-même est déjà au journal

    id             = db.Column(db.Uuid, primary_key=True)   # tiré sur le téléphone
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    appareil_id    = db.Column(db.String(64), nullable=True)
    saisi_le       = db.Column(db.DateTime(timezone=True), nullable=True)   # heure du téléphone
    recu_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    adresse        = db.Column(db.String(255), nullable=False)
    objet_table    = db.Column(db.String(60), nullable=True)
    objet_id       = db.Column(db.String(64), nullable=True)


class GenreVerification:
    MESSAGE = 'MESSAGE'            # refus d'une saisie envoyée après coup : « Vu »
    SAISIE_JOUR = 'SAISIE_JOUR'    # morts / aliment du jour : deux versions
    LIVRAISON = 'LIVRAISON'        # confirmation de livraison : deux versions
    SORTIE = 'SORTIE'              # doublon possible de sortie
    A_TRANCHER = (SAISIE_JOUR, LIVRAISON, SORTIE)


class StatutVerification:
    A_VERIFIER = 'A_VERIFIER'
    TRANCHE = 'TRANCHE'


class ConflitHorsLigne(db.Model):
    """« Saisies à vérifier » : refus d'une saisie envoyée après coup (à marquer « vue »), ou deux
    versions de la même saisie par deux personnes (à trancher, motif obligatoire, lot 12)."""
    __tablename__ = 'conflit_hors_ligne'
    __perimetre_ferme__ = 'ferme_id'

    id             = db.Column(db.Integer, primary_key=True)
    cree_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=True, index=True)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    quoi           = db.Column(db.String(150), nullable=False)
    detail         = db.Column(db.Text, nullable=False)
    vu_le          = db.Column(db.DateTime(timezone=True), nullable=True)
    vu_par         = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    # Lot 12 : deux versions et la décision
    genre          = db.Column(db.String(12), nullable=False, default=GenreVerification.MESSAGE,
                               server_default=GenreVerification.MESSAGE, index=True)
    statut         = db.Column(db.String(12), nullable=True, index=True)
    objet_table    = db.Column(db.String(40), nullable=True)
    objet_id       = db.Column(db.String(64), nullable=True)
    bande_id       = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=True, index=True)
    versions       = db.Column(db.JSON, nullable=True)
    retenue        = db.Column(db.String(20), nullable=True)
    motif          = db.Column(db.Text, nullable=True)
    decide_par     = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    decide_le      = db.Column(db.DateTime(timezone=True), nullable=True)

    ferme = db.relationship('Ferme')
    bande = db.relationship('Bande')
    auteur = db.relationship('Utilisateur', foreign_keys=[utilisateur_id])
    decideur = db.relationship('Utilisateur', foreign_keys=[decide_par])

    @property
    def a_trancher(self):
        return self.genre in GenreVerification.A_TRANCHER and self.statut == StatutVerification.A_VERIFIER
