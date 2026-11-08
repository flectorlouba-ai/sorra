import enum
import uuid

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db, login_manager
from app.models.base import HorodatageMixin


class Profil(enum.Enum):
    ADMIN     = 'ADMIN'
    DGE       = 'DGE'
    AGENT     = 'AGENT'
    ELEVEUR   = 'ELEVEUR'
    VETO      = 'VETO'
    BCEG      = 'BCEG'
    MAEDR     = 'MAEDR'
    OPERATEUR = 'OPERATEUR'
    AUDITEUR  = 'AUDITEUR'

    @property
    def libelle(self):
        return LIBELLES_PROFIL[self]


LIBELLES_PROFIL = {
    Profil.ADMIN:     'Administrateur',
    Profil.DGE:       'DGE — programme POUFA',
    Profil.AGENT:     'Agent technique',
    Profil.ELEVEUR:   'Éleveur',
    Profil.VETO:      'Services vétérinaires',
    Profil.BCEG:      'BCEG',
    Profil.MAEDR:     'MAEDR',
    Profil.OPERATEUR: 'Opérateur (abattoir, acheteur, distributeur)',
    Profil.AUDITEUR:  'Auditeur (ANINF)',
}

# Profils qui voient tout, sans périmètre
PROFILS_NATIONAUX = frozenset({Profil.ADMIN, Profil.DGE})


utilisateur_province = db.Table(
    'utilisateur_province',
    db.Column('utilisateur_id', db.Uuid,
              db.ForeignKey('utilisateur.id', ondelete='CASCADE'), primary_key=True),
    db.Column('province_id', db.Integer,
              db.ForeignKey('province.id'), primary_key=True),
)


class UtilisateurFerme(db.Model):
    """Rattachement d'un utilisateur à une ou plusieurs fermes.
    La clé étrangère vers `ferme` sera posée au lot 1, avec la table Ferme."""
    __tablename__ = 'utilisateur_ferme'

    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id', ondelete='CASCADE'),
                               primary_key=True)
    ferme_id       = db.Column(db.Uuid, primary_key=True)


class Utilisateur(UserMixin, HorodatageMixin, db.Model):
    __tablename__ = 'utilisateur'
    # Journal : la date de connexion et le compteur d'échecs ne sont pas des
    # modifications de la fiche (le blocage a ses propres lignes BLOCAGE /
    # DEBLOCAGE), le mot de passe n'est jamais recopié, les provinces le sont
    # par leur code.
    __journal_ignorer__  = {'derniere_connexion', 'echecs_connexion', 'bloque_jusqu_a'}
    __journal_masquer__  = {'mot_de_passe_hash'}
    __journal_relations__ = {'provinces': 'code'}

    id                 = db.Column(db.Uuid, primary_key=True, default=uuid.uuid4)
    identifiant        = db.Column(db.String(64), unique=True, nullable=False)
    nom                = db.Column(db.String(120), nullable=False)
    prenom             = db.Column(db.String(120), nullable=True)
    email              = db.Column(db.String(120), nullable=True)
    telephone          = db.Column(db.String(30), nullable=True)
    mot_de_passe_hash  = db.Column(db.String(256), nullable=False)
    profil             = db.Column(db.Enum(Profil, native_enum=False, length=20),
                                   nullable=False)
    actif              = db.Column(db.Boolean, nullable=False, default=True)
    doit_changer_mdp   = db.Column(db.Boolean, nullable=False, default=True)
    derniere_connexion = db.Column(db.DateTime(timezone=True), nullable=True)
    echecs_connexion   = db.Column(db.Integer, nullable=False, default=0, server_default='0')
    bloque_jusqu_a     = db.Column(db.DateTime(timezone=True), nullable=True)

    provinces = db.relationship('Province', secondary=utilisateur_province,
                                order_by='Province.ordre', lazy='selectin')
    fermes    = db.relationship(UtilisateurFerme, cascade='all, delete-orphan', lazy='selectin')

    def get_id(self):
        return str(self.id)

    @property
    def nom_complet(self):
        return f'{self.prenom} {self.nom}' if self.prenom else self.nom

    @property
    def est_national(self):
        return self.profil in PROFILS_NATIONAUX

    @property
    def est_bloque(self):
        from app.utils.dates import en_utc
        from app.models.base import maintenant
        return bool(self.bloque_jusqu_a) and en_utc(self.bloque_jusqu_a) > maintenant()

    @property
    def province_ids(self):
        return [p.id for p in self.provinces]

    @property
    def ferme_ids(self):
        return [f.ferme_id for f in self.fermes]

    def set_password(self, mdp):
        self.mot_de_passe_hash = generate_password_hash(mdp)

    def check_password(self, mdp):
        return check_password_hash(self.mot_de_passe_hash, mdp)

    def __repr__(self):
        return f'<Utilisateur {self.identifiant}>'


@login_manager.user_loader
def charger_utilisateur(user_id):
    try:
        uid = uuid.UUID(user_id)
    except (ValueError, TypeError):
        return None
    user = db.session.get(Utilisateur, uid)
    # Un compte désactivé perd sa session à la requête suivante
    return user if user and user.actif else None
