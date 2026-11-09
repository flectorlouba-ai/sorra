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
    ('securite.duree_session_minutes', '30', TypeParametre.ENTIER,
     'Pilotage : durée d\'inactivité, en minutes, au bout de laquelle la session se ferme '
     '(jamais pour l\'éleveur ni l\'agent).'),
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
    # Lot 18 — classement des fermes (quatre yeux), e-mail des rapports mensuels (coupé)
    ('classement.poids_mortalite', '35', TypeParametre.ENTIER, 'Classement des fermes : poids de la mortalité. Quatre yeux.'),
    ('classement.poids_ic', '25', TypeParametre.ENTIER, "Classement des fermes : poids de l'indice de consommation. Quatre yeux."),
    ('classement.poids_gmq', '20', TypeParametre.ENTIER, 'Classement des fermes : poids de la croissance (GMQ). Quatre yeux.'),
    ('classement.poids_regularite', '20', TypeParametre.ENTIER, 'Classement des fermes : poids de la régularité des saisies. Quatre yeux.'),
    ('classement.seuil_complet_pct', '80', TypeParametre.ENTIER, 'Classement : % de jours saisis en dessous duquel une bande est incomplète (ignorée). Quatre yeux.'),
    ('classement.mortalite_note_zero_pct', '10', TypeParametre.DECIMAL, 'Classement : mortalité (%) qui donne la note 0 (0 % donne 100). Quatre yeux.'),
    ('classement.ic_note_100', '1.4', TypeParametre.DECIMAL, 'Classement : indice de consommation qui donne la note 100. Quatre yeux.'),
    ('classement.ic_note_zero', '2.6', TypeParametre.DECIMAL, 'Classement : indice de consommation qui donne la note 0. Quatre yeux.'),
    ('classement.gmq_note_zero', '30', TypeParametre.DECIMAL, 'Classement : GMQ (g/j) qui donne la note 0. Quatre yeux.'),
    ('classement.gmq_note_100', '70', TypeParametre.DECIMAL, 'Classement : GMQ (g/j) qui donne la note 100. Quatre yeux.'),
    ('rapports.email_destinataires', '', TypeParametre.TEXTE,
     'Adresses qui recevront le rapport mensuel national (séparées par des virgules). Envoi coupé tant que '
     'rapports.email_actif vaut 0.'),
    ('rapports.email_actif', '0', TypeParametre.BOOLEEN,
     "Envoi du rapport mensuel par e-mail (0 = coupé). Il faut aussi un serveur de messagerie configuré."),
] + [
    # Lot 16 — écart de stock (quatre yeux)
    ('intrants.seuil_ecart_stock_pct', '10', TypeParametre.ENTIER,
     "Écart de stock (livré − utilisé − compté) au-delà duquel la ferme passe en orange chez l'agent, en % du livré. "
     'Quatre yeux.'),
] + [
    # Lot 6 — traçabilité
    ('tracabilite.adresse_publique', 'http://187.124.217.218:5021', TypeParametre.TEXTE,
     'Adresse du site imprimée dans les QR codes (à remplacer par le nom de domaine en HTTPS).'),
] + [
    # Lot 8 — espace éleveur : étoiles du bilan et conseil du feu rouge
    ('bandes.etoiles_mortalite_3_pct', '3', TypeParametre.DECIMAL,
     "Bilan : 3 étoiles si la mortalité est au plus de ce % (et l'indice de consommation au plus du seuil). À valider par les vétérinaires."),
    ('bandes.etoiles_ic_3', '1.7', TypeParametre.DECIMAL,
     'Bilan : indice de consommation maximal pour 3 étoiles. À valider par les vétérinaires.'),
    ('bandes.etoiles_mortalite_2_pct', '5', TypeParametre.DECIMAL,
     'Bilan : 2 étoiles si la mortalité est au plus de ce % (sinon 1 étoile, jamais 0). À valider par les vétérinaires.'),
    ('sante.conseil_feu_rouge', "Isolez les poulets malades et ne vendez pas avant l'avis du vétérinaire.", TypeParametre.TEXTE,
     "Conseil affiché à l'éleveur quand le feu de sa bande est rouge. À faire valider par les services vétérinaires."),
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

# Lot 15 — socle de sécurité
PARAMETRES_DEFAUT += [
    ('securite.profils_2fa', 'ADMIN,DGE,MAEDR,BCEG,AUDITEUR', TypeParametre.TEXTE,
     'Profils pour lesquels la double authentification est obligatoire (jamais l\'éleveur). Quatre yeux.'),
    ('verifications.delai_rouge_heures', '48', TypeParametre.ENTIER,
     'Heures après lesquelles un doublon de sortie non tranché passe en rouge et remonte à la DGE. Quatre yeux.'),
]

# Lot 19 — réception par l'opérateur (abattoir, marché) : contrôles et alertes, quatre yeux.
# Un contrôle vaut TOUS (bloquant pour tous les opérateurs), ABATTOIR (bloquant pour l'abattoir, affiché
# pour les autres), INFO (affiché seulement) ou NON (pas affiché).
PARAMETRES_RECEPTION = [
    ('reception.controle_delai_attente', 'TOUS', TypeParametre.TEXTE,
     "Réception : aucun traitement en délai d'attente. TOUS, ABATTOIR, INFO ou NON. Quatre yeux."),
    ('reception.controle_vaccins', 'ABATTOIR', TypeParametre.TEXTE,
     'Réception : vaccins obligatoires faits. TOUS, ABATTOIR, INFO ou NON. Quatre yeux.'),
    ('reception.controle_pesee', 'ABATTOIR', TypeParametre.TEXTE,
     'Réception : pesée récente. TOUS, ABATTOIR, INFO ou NON. Quatre yeux.'),
    ('reception.pesee_max_jours', '7', TypeParametre.JOURS,
     'Réception : la dernière pesée doit dater de moins de ce nombre de jours avant la sortie. Quatre yeux.'),
    ('reception.vaccin_tolerance_jours', '2', TypeParametre.JOURS,
     'Réception : un vaccin en retard de moins de ce nombre de jours ne met pas le lot en réserve. Quatre yeux.'),
    ('reception.seuil_morts_pct', '2', TypeParametre.DECIMAL,
     "Réception : morts à l'arrivée (% de l'annoncé) au-delà desquels le vétérinaire de la zone est alerté. "
     'Quatre yeux.'),
    ('reception.refus_alerte_nombre', '3', TypeParametre.ENTIER,
     'Réception : nombre de refus du même QR (tous opérateurs) qui alerte la DGE. Quatre yeux.'),
    ('reception.refus_alerte_heures', '24', TypeParametre.ENTIER,
     'Réception : période (heures) sur laquelle les refus du même QR sont comptés. Quatre yeux.'),
]
PARAMETRES_DEFAUT += PARAMETRES_RECEPTION

# Lot 19 ter — téléphone de contact de la DGE (Moi de l'agent)
PARAMETRES_DEFAUT += [
    ('contact.telephone_dge', '', TypeParametre.TEXTE,
     "Téléphone de contact de la DGE affiché aux agents (« 📞 Appeler la DGE »). Vide : celui du premier compte DGE "
     "actif qui a un téléphone ; aucun : rien ne s'affiche."),
]

