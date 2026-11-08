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
] + [
    # Lot 3 — bandes d'élevage
    ('bandes.duree_reference_jours', '45', TypeParametre.JOURS,
     'Durée de référence d\'une bande (jours) : fixe la date de fin prévue.'),
    ('bandes.poids_poussin_g', '40', TypeParametre.DECIMAL,
     'Poids moyen d\'un poussin à la mise en place (g), quand il n\'est pas pesé.'),
    ('bandes.saisie_passee_jours', '3', TypeParametre.JOURS,
     'L\'éleveur peut saisir un jour passé jusqu\'à ce nombre de jours (au-delà : agent ou ADMIN).'),
    ('bandes.frequence_pesee_jours', '7', TypeParametre.JOURS,
     'Une pesée est prévue tous les … jours.'),
    ('bandes.pesee_nombre_defaut', '10', TypeParametre.ENTIER,
     'Nombre de poulets à peser, proposé par défaut.'),
    ('bandes.ecart_courbe_pct', '10', TypeParametre.DECIMAL,
     'Écart toléré sous la courbe de croissance attendue (%), à valider par les vétérinaires.'),
    ('bandes.fin_proche_jours', '3', TypeParametre.JOURS,
     '« Fin de bande proche » affiché ce nombre de jours avant la fin prévue.'),
    ('bandes.seuil_orange_pct', '0.5', TypeParametre.DECIMAL,
     'Feu orange : morts du jour au-delà de ce % de l\'effectif présent, à valider par les vétérinaires.'),
    ('bandes.seuil_rouge_pct', '1', TypeParametre.DECIMAL,
     'Feu rouge : morts du jour au-delà de ce % de l\'effectif présent, à valider par les vétérinaires.'),
    ('bandes.courbe_poids', '0:42; 7:180; 14:450; 21:900; 28:1450; 35:2050; 42:2650; 49:3150',
     TypeParametre.TEXTE,
     'Courbe de croissance attendue « âge en jours : poids en g », à valider par les vétérinaires.'),
] + [
    # Lot 4 — santé animale
    ('sante.retard_vaccin_jours', '2', TypeParametre.JOURS,
     'Un vaccin non fait à la date prévue + ce nombre de jours est signalé « en retard ».'),
    ('sante.calendrier_valide', 'non', TypeParametre.BOOLEEN,
     'Calendrier vaccinal validé par les services vétérinaires (oui / non).'),
] + [
    # Lot 5 — tableaux de bord
    ('intrants.seuil_mortalite_arrivee_pct', '2', TypeParametre.DECIMAL,
     'Alerte DGE : poussins morts à l\'arrivée au-delà de ce % d\'une livraison, à valider par les vétérinaires.'),
] + [
    # Lot 6 — traçabilité
    ('tracabilite.adresse_publique', 'http://187.124.217.218:5021', TypeParametre.TEXTE,
     'Adresse du site imprimée dans les QR codes (à remplacer par le nom de domaine en HTTPS).'),
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
