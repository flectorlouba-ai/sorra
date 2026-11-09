"""Argent de l'éleveur (lot 11) : dépenses « J'ai payé ». Les ventes sont le montant des
sorties (`sortie.montant_fcfa`), les achats le prix payé des achats personnels
(`livraison.prix_paye_fcfa`). Noms pensés pour être repris par le futur module Économie
(charges, coût de production, marge)."""
from app import db
from app.models.base import SaisieTerrainMixin

CATEGORIE_DEFAUT_ICONE = '📦'


def icone_et_nom(valeur):
    """« 👷 Main-d'œuvre » → ('👷', "Main-d'œuvre") ; sans émoji en tête : ('📦', valeur)."""
    valeur = (valeur or '').strip()
    tete, _, reste = valeur.partition(' ')
    if reste and tete and not any(c.isalnum() for c in tete):
        return tete, reste.strip()
    return CATEGORIE_DEFAUT_ICONE, valeur


class Depense(SaisieTerrainMixin, db.Model):
    """« J'ai payé » : une dépense de la ferme, rattachée aux bandes à l'affichage
    (services/argent.py) et figée dans le bilan à la clôture."""
    __tablename__ = 'depense'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id        = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    batiment_id     = db.Column(db.Integer, db.ForeignKey('batiment.id'), nullable=True)
    categorie       = db.Column(db.String(60), nullable=False)
    montant_fcfa    = db.Column(db.Integer, nullable=False)
    date            = db.Column(db.Date, nullable=False, index=True)
    photo_recu      = db.Column(db.String(80), nullable=True)
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)
    annule          = db.Column(db.Boolean, nullable=False, default=False)

    ferme = db.relationship('Ferme')
    batiment = db.relationship('Batiment')

    @property
    def numero(self):
        return self.numero_metier

    @property
    def icone(self):
        return icone_et_nom(self.categorie)[0]

    @property
    def libelle(self):
        return icone_et_nom(self.categorie)[1]
