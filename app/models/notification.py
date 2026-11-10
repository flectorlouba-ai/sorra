"""Lot T — notifications Web Push : abonnements, préférences, journal des envois (jamais de donnée personnelle)."""
from app import db
from app.models.base import maintenant


class TypeNotification:
    # éleveur
    SAISIE_OUBLIEE = 'SAISIE_OUBLIEE'
    PESEE_RETARD = 'PESEE_RETARD'
    VACCIN_DEMAIN = 'VACCIN_DEMAIN'
    REPONSE_VETO = 'REPONSE_VETO'
    LIVRAISON_A_CONFIRMER = 'LIVRAISON_A_CONFIRMER'
    VENTES_BLOQUEES = 'VENTES_BLOQUEES'
    RAPPEL_FISCAL = 'RAPPEL_FISCAL'        # lot G : déclaration annuelle, seuil de régime approché
    # agent
    FEU_ROUGE = 'FEU_ROUGE'
    FERME_SANS_SAISIE = 'FERME_SANS_SAISIE'
    DEUX_VERSIONS = 'DEUX_VERSIONS'
    ACTION_RETARD = 'ACTION_RETARD'
    VISITE_DEMAIN = 'VISITE_DEMAIN'
    # opérateur
    LOT_EN_ROUTE = 'LOT_EN_ROUTE'
    LOT_DECIDE = 'LOT_DECIDE'
    # vétérinaire, DGE
    SIGNALEMENT = 'SIGNALEMENT'
    ALERTE_SANITAIRE = 'ALERTE_SANITAIRE'
    ECART_48H = 'ECART_48H'
    PARAMETRE_A_APPROUVER = 'PARAMETRE_A_APPROUVER'

    # Ce qui ne se coupe pas : les alertes sanitaires (éleveur, agent, vétérinaire, DGE)
    TOUJOURS = (FEU_ROUGE, ALERTE_SANITAIRE, VENTES_BLOQUEES)

    LIBELLES = {
        SAISIE_OUBLIEE: ('📝', 'Rappel de la saisie du jour', "si rien n'est noté à l'heure choisie"),
        PESEE_RETARD: ('⚖️', 'Pesée en retard', None), VACCIN_DEMAIN: ('💉', 'Vaccin à faire demain', None),
        REPONSE_VETO: ('💬', 'Réponses du vétérinaire', None), LIVRAISON_A_CONFIRMER: ('🚚', 'Livraisons à confirmer', None),
        VENTES_BLOQUEES: ('⛔', 'Ventes bloquées', 'toujours actif'),
        RAPPEL_FISCAL: ('🏛️', 'Rappels fiscaux', 'déclaration annuelle, seuil de régime'),
        FEU_ROUGE: ('🔴', 'Alertes sanitaires', 'toujours actives'), FERME_SANS_SAISIE: ('📵', 'Ferme sans saisie', 'depuis 2 jours'),
        DEUX_VERSIONS: ('⚖️', 'Deux versions à trancher', None), ACTION_RETARD: ('🎯', 'Action en retard', None),
        VISITE_DEMAIN: ('📋', 'Visite prévue demain', None),
        LOT_EN_ROUTE: ('🚚', 'Lot en route vers vous', None), LOT_DECIDE: ('🩺', 'Lot libéré ou refusé par le vétérinaire', None),
        SIGNALEMENT: ('📨', 'Nouveau signalement', None), ALERTE_SANITAIRE: ('🔴', 'Alertes sanitaires', 'toujours actives'),
        ECART_48H: ('⏳', 'Écart à trancher depuis 48 h', None), PARAMETRE_A_APPROUVER: ('👀', 'Paramètre à approuver', None),
    }
    PAR_PROFIL = {
        'ELEVEUR': (SAISIE_OUBLIEE, PESEE_RETARD, VACCIN_DEMAIN, REPONSE_VETO, LIVRAISON_A_CONFIRMER, VENTES_BLOQUEES, RAPPEL_FISCAL),
        'AGENT': (FEU_ROUGE, FERME_SANS_SAISIE, DEUX_VERSIONS, ACTION_RETARD, VISITE_DEMAIN),
        'OPERATEUR': (LOT_EN_ROUTE, LOT_DECIDE),
        'VETO': (SIGNALEMENT, ALERTE_SANITAIRE, ECART_48H, PARAMETRE_A_APPROUVER),
        'DGE': (SIGNALEMENT, ALERTE_SANITAIRE, ECART_48H, PARAMETRE_A_APPROUVER),
    }


class AbonnementPush(db.Model):
    __tablename__ = 'abonnement_push'

    id               = db.Column(db.Integer, primary_key=True)
    utilisateur_id   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False, index=True)
    appareil         = db.Column(db.String(64), nullable=True)
    endpoint         = db.Column(db.Text, nullable=False)
    p256dh           = db.Column(db.String(200), nullable=False)
    auth             = db.Column(db.String(100), nullable=False)
    cree_le          = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    dernier_envoi_le = db.Column(db.DateTime(timezone=True), nullable=True)
    actif            = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())

    utilisateur = db.relationship('Utilisateur')
    __journal_masquer__ = {'endpoint', 'p256dh', 'auth'}


class PreferenceNotification(db.Model):
    __tablename__ = 'preference_notification'
    __table_args__ = (db.UniqueConstraint('utilisateur_id', 'type'),)

    id             = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    type           = db.Column(db.String(30), nullable=False)
    actif          = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    heure          = db.Column(db.Integer, nullable=True)          # rappel de la saisie : 17, 18 ou 19


class Notification(db.Model):
    """Le journal des envois : titre et texte courts, sans nom ni téléphone ; `cle` évite tout doublon."""
    __tablename__ = 'notification'
    __table_args__ = (db.UniqueConstraint('utilisateur_id', 'cle'),)

    id             = db.Column(db.Integer, primary_key=True)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False, index=True)
    type           = db.Column(db.String(30), nullable=False)
    cle            = db.Column(db.String(120), nullable=False)
    titre          = db.Column(db.String(80), nullable=False)
    texte          = db.Column(db.String(200), nullable=False)
    lien           = db.Column(db.String(200), nullable=True)
    cree_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    envoyee_le     = db.Column(db.DateTime(timezone=True), nullable=True)
    resultat       = db.Column(db.String(40), nullable=True)      # envoyee, sans_abonnement, sans_cles, erreur:…

    utilisateur = db.relationship('Utilisateur')
