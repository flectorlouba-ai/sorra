"""Entretien simple des installations (lot 10) : tâches préparées par l'équipe, cochées par
l'éleveur, et pannes signalées à l'agent. Repris de la maintenance préventive de PERFORM YL.1
(un modèle de tâche avec une fréquence, une réalisation datée), en beaucoup plus simple :
des périodes de calendrier fixes, pas d'échéances glissantes ni d'équipements détaillés."""
from app import db
from app.models.base import ArchivableMixin, SaisieTerrainMixin, HorodatageMixin, maintenant


class Frequence:
    JOUR = 'JOUR'
    SEMAINE = 'SEMAINE'                  # du lundi au dimanche
    MOIS = 'MOIS'                        # mois du calendrier
    VIDE_SANITAIRE = 'VIDE_SANITAIRE'    # une fois par vide sanitaire (bande clôturée)
    LIBELLES = {JOUR: 'chaque jour', SEMAINE: 'chaque semaine', MOIS: 'chaque mois',
                VIDE_SANITAIRE: 'à chaque vide sanitaire'}
    TOUTES = [JOUR, SEMAINE, MOIS, VIDE_SANITAIRE]


class Portee:
    BANDE = 'BANDE'    # chaque bâtiment avec une bande en cours
    FERME = 'FERME'    # une fois pour toute la ferme
    VIDE = 'VIDE'      # le bâtiment dont la bande vient d'être clôturée
    LIBELLES = {BANDE: 'bâtiments avec une bande en cours', FERME: 'toute la ferme',
                VIDE: 'bâtiment en vide sanitaire'}
    TOUTES = [BANDE, FERME, VIDE]


class TypePanne:
    """Liste système : les 6 grosses images de « Qu'est-ce qui ne marche pas ? »."""
    TOUS = [('CHAUFFAGE', '🔥', 'Chauffage'), ('EAU', '💧', 'Eau'), ('ELECTRICITE', '⚡', 'Électricité'),
            ('VENTILATION', '🌀', 'Ventilation'), ('MANGEOIRES', '🍽️', 'Mangeoires'), ('BATIMENT', '🏠', 'Bâtiment')]
    ICONES = {c: i for c, i, _ in TOUS}
    LIBELLES = {c: n for c, _, n in TOUS}


class StatutPanne:
    SIGNALEE = 'SIGNALEE'
    REPAREE = 'REPAREE'
    LIBELLES = {SIGNALEE: 'Signalée', REPAREE: 'Réparée'}


class TacheEntretien(HorodatageMixin, db.Model):
    """Modèle de tâche, préparé par l'équipe (ADMIN, écran Configuration)."""
    __tablename__ = 'tache_entretien'

    id             = db.Column(db.Integer, primary_key=True)
    nom            = db.Column(db.String(120), nullable=False)
    icone          = db.Column(db.String(16), nullable=False, default='🔧')
    frequence      = db.Column(db.String(16), nullable=False)
    portee         = db.Column(db.String(10), nullable=False)
    infrastructure = db.Column(db.String(150), nullable=True)   # la ferme doit l'avoir (liste existante)
    actif          = db.Column(db.Boolean, nullable=False, default=True)
    ordre          = db.Column(db.Integer, nullable=False, default=0)

    @property
    def libelle_frequence(self):
        return Frequence.LIBELLES.get(self.frequence, self.frequence)


class EntretienFait(ArchivableMixin, SaisieTerrainMixin, db.Model):
    """« Fait ✓ » : une tâche faite pour un bâtiment (ou toute la ferme) et une période."""
    __tablename__ = 'entretien_fait'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id        = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    batiment_id     = db.Column(db.Integer, db.ForeignKey('batiment.id'), nullable=True)   # vide : toute la ferme
    tache_id        = db.Column(db.Integer, db.ForeignKey('tache_entretien.id'), nullable=False)
    periode         = db.Column(db.Date, nullable=True)        # jour, lundi de la semaine, 1er du mois
    bande_id        = db.Column(db.Uuid, db.ForeignKey('bande.id'), nullable=True)   # désinfection : la bande clôturée
    fait_le         = db.Column(db.Date, nullable=False)
    saisi_par_agent = db.Column(db.Boolean, nullable=False, default=False)
    annule          = db.Column(db.Boolean, nullable=False, default=False)

    tache = db.relationship('TacheEntretien')
    batiment = db.relationship('Batiment')
    ferme = db.relationship('Ferme')


class Panne(ArchivableMixin, SaisieTerrainMixin, db.Model):
    """Panne signalée par l'éleveur (ou l'agent) : Signalée → Réparée."""
    __tablename__ = 'panne'
    __perimetre_ferme__ = 'ferme_id'

    ferme_id          = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    batiment_id       = db.Column(db.Integer, db.ForeignKey('batiment.id'), nullable=True)   # vide : toute la ferme
    type              = db.Column(db.String(16), nullable=False)
    photo             = db.Column(db.String(80), nullable=True)
    statut            = db.Column(db.String(10), nullable=False, default=StatutPanne.SIGNALEE, index=True)
    signalee_le       = db.Column(db.DateTime(timezone=True), nullable=False, default=maintenant)
    saisie_par_agent  = db.Column(db.Boolean, nullable=False, default=False)
    reparee_le        = db.Column(db.DateTime(timezone=True), nullable=True)
    reparee_par       = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    reparee_par_agent = db.Column(db.Boolean, nullable=False, default=False)

    ferme = db.relationship('Ferme')
    batiment = db.relationship('Batiment')
    reparateur = db.relationship('Utilisateur', foreign_keys=[reparee_par])

    @property
    def icone(self):
        return TypePanne.ICONES.get(self.type, '🔧')

    @property
    def libelle(self):
        return TypePanne.LIBELLES.get(self.type, self.type)

    @property
    def ou(self):
        return self.batiment.code if self.batiment else 'toute la ferme'
