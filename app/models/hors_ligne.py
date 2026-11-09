"""Saisies faites sans réseau puis envoyées au retour du réseau.

Chaque saisie gardée sur le téléphone porte un identifiant unique (UUID) tiré
sur l'appareil. Le serveur note chaque identifiant reçu : un même envoi rejoué
(coupure pendant l'envoi, double clic) n'est jamais compté deux fois.
Règle des conflits : la saisie la plus récente gagne, et l'agent est prévenu.
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


class ConflitHorsLigne(db.Model):
    """Saisie envoyée après coup qui a rencontré une autre version, ou a été refusée :
    l'agent de la ferme la voit dans ses alertes jusqu'à ce qu'il la marque « vue »."""
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

    ferme = db.relationship('Ferme')
    auteur = db.relationship('Utilisateur', foreign_keys=[utilisateur_id])
