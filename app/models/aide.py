"""Aides « Comment faire ? » (lot 13) : une aide par écran principal de l'éleveur, 3 étapes au plus,
modifiables par l'ADMIN (Configuration → Aides), chaque modification inscrite au journal."""
from app import db
from app.models.base import HorodatageMixin

# Captures simplifiées : le vrai bouton reproduit en petit (libellé, style)
CAPTURES = {
    '': ('', ''),
    'aucun_mort': ('✓ Aucun mort', 'case'),
    'plus': ('+', 'rond'),
    'comme_hier': ('Comme hier (2 sacs)', 'case'),
    'pas_aliment': ("Pas d'aliment donné", 'case'),
    'envoyer': ('Envoyer ✓', 'vert'),
    'enregistrer': ('Enregistrer', 'bleu'),
    'enregistrer_pesee': ('Enregistrer la pesée', 'bleu'),
    'enregistrer_sortie': ('Enregistrer la sortie', 'bleu'),
    'types_sortie': ('🏭 Abattoir · 💵 Vente · Autre', 'case'),
    'cest_fait': ("✓ C'est fait", 'vert'),
    'annuler': ('Annuler (10)', 'sombre'),
    'signes': ('🤧 Toux · 💩 Diarrhée', 'case'),
    'photo': ('📷 Photo', 'case'),
    'envoyer_veto': ('Envoyer au vétérinaire', 'rouge'),
    'produit': ('🌾 Aliment démarrage', 'case'),
    'categorie': ('⚡ Électricité', 'case'),
    'fait': ('Fait ✓', 'vert'),
    'panne': ('⚠️ Quelque chose est en panne', 'rose'),
    'gagne': ('Gagné 600 000', 'case'),
    'depense': ('Dépensé 165 000', 'case'),
    'reste': ('Reste 435 000', 'case'),
    'balance': ('⚖️ 10 poulets', 'case'),
}
GROUPES = ['Chaque jour', 'Ma bande', 'Santé', 'Mon argent']


class Aide(HorodatageMixin, db.Model):
    __tablename__ = 'aide'

    id     = db.Column(db.Integer, primary_key=True)
    cle    = db.Column(db.String(20), unique=True, nullable=False)
    groupe = db.Column(db.String(30), nullable=False)
    titre  = db.Column(db.String(120), nullable=False)
    etapes = db.Column(db.JSON, nullable=False, default=list)    # [{texte, capture}], 3 au plus
    actif  = db.Column(db.Boolean, nullable=False, default=True)
    ordre  = db.Column(db.Integer, nullable=False, default=0)
