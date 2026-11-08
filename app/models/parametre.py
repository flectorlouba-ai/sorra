import enum

from app import db
from app.models.base import maintenant


class TypeParametre(enum.Enum):
    TEXTE   = 'TEXTE'
    ENTIER  = 'ENTIER'
    DECIMAL = 'DECIMAL'
    BOOLEEN = 'BOOLEEN'
    JOURS   = 'JOURS'

    @property
    def libelle(self):
        return {'TEXTE': 'Texte', 'ENTIER': 'Nombre entier', 'DECIMAL': 'Nombre décimal',
                'BOOLEEN': 'Oui / non', 'JOURS': 'Durée en jours'}[self.value]


# Paramètres livrés au lot 0 : (clé, valeur, type, description)
PARAMETRES_DEFAUT = [
    ('securite.mdp_longueur_min', '10', TypeParametre.ENTIER,
     'Nombre minimal de caractères d\'un mot de passe.'),
    ('securite.duree_session_minutes', '60', TypeParametre.ENTIER,
     'Durée d\'inactivité, en minutes, au bout de laquelle la session se ferme.'),
    ('securite.echecs_avant_blocage', '5', TypeParametre.ENTIER,
     'Nombre d\'échecs de connexion consécutifs avant le blocage du compte.'),
    ('securite.blocage_minutes', '15', TypeParametre.ENTIER,
     'Durée du blocage, en minutes, après trop d\'échecs de connexion.'),
    ('intrants.delai_confirmation_jours', '3', TypeParametre.JOURS,
     'Nombre de jours après lesquels une livraison non confirmée est signalée dans les alertes.'),
    ('intrants.alerte_ecart_jours', '30', TypeParametre.JOURS,
     'Pendant combien de jours une livraison reçue avec écart reste signalée dans les alertes.'),
]


class Parametre(db.Model):
    __tablename__ = 'parametre'

    id          = db.Column(db.Integer, primary_key=True)
    cle         = db.Column(db.String(100), unique=True, nullable=False)
    valeur      = db.Column(db.Text, nullable=False, default='')
    type        = db.Column(db.Enum(TypeParametre, native_enum=False, length=10),
                            nullable=False, default=TypeParametre.TEXTE)
    description = db.Column(db.Text, nullable=True)
    modifie_le  = db.Column(db.DateTime(timezone=True), nullable=True, onupdate=maintenant)
    modifie_par = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)

    auteur = db.relationship('Utilisateur')
