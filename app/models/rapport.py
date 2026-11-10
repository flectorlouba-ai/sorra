"""Lot D — rapports standards gardés (PDF)."""
from datetime import date

from app import db
from app.models.base import ArchivableMixin, HorodatageMixin, maintenant


class TypeRapport:
    NATIONAL = 'NATIONAL'
    PROVINCE = 'PROVINCE'
    FERME = 'FERME'
    AGENT = 'AGENT'
    BANDE = 'BANDE'
    LIBELLES = {NATIONAL: 'National', PROVINCE: 'Provincial', FERME: 'Ferme', AGENT: 'Agent', BANDE: 'Bilan de bande'}


class Rapport(db.Model):
    """Un PDF produit et gardé : type, période (« 2026-10 » ou la date), cible, fichier."""
    __tablename__ = 'rapport'
    __perimetre_ferme__ = 'ferme_id'

    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(10), nullable=False, index=True)
    periode     = db.Column(db.String(10), nullable=False)
    province_id = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=True)
    ferme_id    = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=True, index=True)
    agent_id    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    bande_id    = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=True)
    fichier     = db.Column(db.String(120), nullable=False)
    pages       = db.Column(db.Integer, nullable=True)
    genere_le   = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    genere_par  = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    automatique = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    # Lot M : diffusion — soumis au visa du MAEDR, validé ou refusé
    diffusion   = db.Column(db.String(12), nullable=True)
    soumis_le   = db.Column(db.DateTime(timezone=True), nullable=True)
    soumis_par  = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    vise_le     = db.Column(db.DateTime(timezone=True), nullable=True)
    vise_par    = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    motif_visa  = db.Column(db.String(300), nullable=True)

    province = db.relationship('Province')
    ferme = db.relationship('Ferme')
    agent = db.relationship('Utilisateur', foreign_keys=[agent_id])
    bande = db.relationship('Bande')
    auteur = db.relationship('Utilisateur', foreign_keys=[genere_par])
    viseur = db.relationship('Utilisateur', foreign_keys=[vise_par])

    LIBELLES_DIFFUSION = {None: 'Interne', 'SOUMIS': 'Soumis au MAEDR', 'VALIDE': 'Diffusable (visa MAEDR)', 'REFUSE': 'Refusé par le MAEDR'}

    @property
    def libelle_diffusion(self):
        return self.LIBELLES_DIFFUSION.get(self.diffusion, self.diffusion)

    @property
    def libelle_type(self):
        return TypeRapport.LIBELLES.get(self.type, self.type)

    @property
    def cible(self):
        if self.type == TypeRapport.FERME and self.ferme:
            return f'{self.ferme.numero} · {self.ferme.nom}'
        if self.type == TypeRapport.AGENT and self.agent:
            return self.agent.nom_complet
        if self.type == TypeRapport.PROVINCE and self.province:
            return self.province.nom
        if self.type == TypeRapport.BANDE and self.bande:
            return self.bande.numero
        return 'National'


