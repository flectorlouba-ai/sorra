"""Socle de sécurité (lot 15) : chaîne d'empreintes du journal, propositions à approuver
(« quatre yeux »), sessions enregistrées."""
from app import db
from app.models.base import maintenant


class JournalChaine(db.Model):
    """Empreinte SHA-256 de chaque entrée du journal, qui inclut celle de la précédente. Table à part :
    le journal lui-même n'est jamais modifié (déclencheur). En écriture seule, elle aussi."""
    __tablename__ = 'journal_chaine'
    __journal_exclu__ = True

    journal_id  = db.Column(db.BigInteger().with_variant(db.Integer, 'sqlite'),
                            db.ForeignKey('journal_audit.id'), primary_key=True, autoincrement=False)
    precedente  = db.Column(db.String(64), nullable=False)
    empreinte   = db.Column(db.String(64), nullable=False)


class StatutProposition:
    EN_ATTENTE = 'EN_ATTENTE'
    APPROUVEE = 'APPROUVEE'
    REFUSEE = 'REFUSEE'
    LIBELLES = {EN_ATTENTE: 'En attente', APPROUVEE: 'Approuvée', REFUSEE: 'Refusée'}


class Proposition(db.Model):
    """Modification d'un paramètre sensible, proposée par une personne, approuvée ou refusée par une
    autre. L'ancienne valeur s'applique jusqu'à l'approbation."""
    __tablename__ = 'proposition'

    id             = db.Column(db.Integer, primary_key=True)
    genre          = db.Column(db.String(12), nullable=False)          # PARAMETRE, FORMULE, CALENDRIER, PROFIL
    cle            = db.Column(db.String(120), nullable=False)
    libelle        = db.Column(db.String(200), nullable=False)
    domaine        = db.Column(db.String(12), nullable=False, default='GENERAL')   # SANITAIRE : le VETO décide aussi
    avant          = db.Column(db.Text, nullable=True)
    apres          = db.Column(db.Text, nullable=False)
    donnees        = db.Column(db.JSON, nullable=True)                  # ce qu'il faut appliquer
    motif          = db.Column(db.Text, nullable=False)
    statut         = db.Column(db.String(12), nullable=False, default=StatutProposition.EN_ATTENTE, index=True)
    propose_par    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False)
    propose_le     = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    decide_par     = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    decide_le      = db.Column(db.DateTime(timezone=True), nullable=True)
    motif_decision = db.Column(db.Text, nullable=True)

    auteur = db.relationship('Utilisateur', foreign_keys=[propose_par])
    decideur = db.relationship('Utilisateur', foreign_keys=[decide_par])

    @property
    def libelle_statut(self):
        return StatutProposition.LIBELLES.get(self.statut, self.statut)


class SessionUtilisateur(db.Model):
    __tablename__ = 'session_utilisateur'
    __journal_exclu__ = True        # ouverture et fermeture sont déjà des lignes du journal

    id                = db.Column(db.String(36), primary_key=True)
    utilisateur_id    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=False, index=True)
    appareil          = db.Column(db.String(120), nullable=True)
    adresse_ip        = db.Column(db.String(45), nullable=True)
    ouverte_le        = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    derniere_activite = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    fermee_le         = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    fermee_par        = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_fermeture   = db.Column(db.String(200), nullable=True)

    utilisateur = db.relationship('Utilisateur', foreign_keys=[utilisateur_id])
