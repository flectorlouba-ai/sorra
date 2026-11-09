"""Traçabilité : lots de poulets sortis vers un abattoir ou vendus, et leur QR code.

Chaque sortie « Abattoir » ou « Vente » crée un lot numéroté comme la bande, suivi
du rang de la sortie (EST-001-B1-07-S2), jamais réutilisé. Le QR code ne contient
qu'une adresse avec un code tiré au hasard (impossible à deviner) ; la page publique
ne montre ni téléphone ni nom de personne. Les lectures sont inscrites au journal.
"""
from app import db
from app.models.base import HorodatageMixin, SaisieTerrainMixin


class LotTrace(HorodatageMixin, db.Model):
    __tablename__ = 'lot_trace'
    __perimetre_ferme__ = 'ferme_id'
    __journal_masquer__ = {'code'}   # le code du QR n'apparaît pas en clair dans le journal

    id               = db.Column(db.Integer, primary_key=True)
    numero           = db.Column(db.String(50), unique=True, nullable=False)
    code             = db.Column(db.String(40), unique=True, nullable=False)
    sortie_id        = db.Column(db.Uuid, db.ForeignKey('sortie.id'), unique=True, nullable=False)
    ferme_id         = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=False, index=True)
    cree_par         = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    annule           = db.Column(db.Boolean, nullable=False, default=False)
    motif_annulation = db.Column(db.Text, nullable=True)

    sortie = db.relationship('Sortie', backref=db.backref('lot', uselist=False))
    ferme = db.relationship('Ferme')
    createur = db.relationship('Utilisateur')

    @classmethod
    def condition_operateur(cls, operateur_id):
        """Lots destinés à cet opérateur (lot 19) : ceux dont la sortie le désigne."""
        from app.models.bande import Sortie
        return cls.sortie_id.in_(db.select(Sortie.id).where(Sortie.operateur_id == operateur_id))

    __perimetre_operateur__ = 'condition_operateur'

    def __repr__(self):
        return f'<LotTrace {self.numero}>'


# ── Lot 19 : réception par l'opérateur (abattoir, marché) et scans ──────

class EtatReception:
    VALIDEE = 'VALIDEE'
    SOUS_RESERVE = 'SOUS_RESERVE'
    REFUSEE = 'REFUSEE'
    ACTIVES = (VALIDEE, SOUS_RESERVE)       # le lot est reçu : un nouveau scan dit « déjà reçu »
    LIBELLES = {VALIDEE: 'Validée', SOUS_RESERVE: 'En attente du vétérinaire', REFUSEE: 'Refusée'}


class Reception(SaisieTerrainMixin, db.Model):
    """Ce que l'opérateur a reçu au quai. La sortie de la ferme (« annoncé ») n'est jamais modifiée :
    l'annoncé est recopié ici, à côté de ce qui a été compté."""
    __tablename__ = 'reception'
    __perimetre_ferme__ = 'ferme_id'
    __perimetre_operateur__ = 'operateur_id'

    lot_id         = db.Column(db.Integer, db.ForeignKey('lot_trace.id'), nullable=True, index=True)
    ferme_id       = db.Column(db.Uuid, db.ForeignKey('ferme.id'), nullable=True, index=True)
    operateur_id   = db.Column(db.Integer, db.ForeignKey('operateur.id'), nullable=False, index=True)
    recu_le        = db.Column(db.DateTime(timezone=True), nullable=False)
    lot_saisi      = db.Column(db.String(60), nullable=True)    # numéro tapé, si le QR n'a pas été lu
    annonce        = db.Column(db.Integer, nullable=True)
    annonce_kg     = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    vivants        = db.Column(db.Integer, nullable=True)
    morts          = db.Column(db.Integer, nullable=True)
    poids_kg       = db.Column(db.Numeric(12, 2, asdecimal=False), nullable=True)
    etat           = db.Column(db.String(14), nullable=False, index=True)
    motif_refus    = db.Column(db.Text, nullable=True)
    controles      = db.Column(db.JSON, nullable=True)          # contrôles au moment de la réception
    motif_ecart    = db.Column(db.String(150), nullable=True)
    explication    = db.Column(db.Text, nullable=True)
    hors_ligne     = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    vu_le          = db.Column(db.DateTime(timezone=True), nullable=True)   # l'opérateur a vu le résultat
    decision_par   = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    decision_le    = db.Column(db.DateTime(timezone=True), nullable=True)
    decision_motif = db.Column(db.Text, nullable=True)

    lot = db.relationship('LotTrace', backref=db.backref('receptions', order_by='Reception.recu_le'))
    ferme = db.relationship('Ferme')
    operateur = db.relationship('Operateur')
    veterinaire = db.relationship('Utilisateur', foreign_keys=[decision_par])

    @property
    def libelle_etat(self):
        return EtatReception.LIBELLES.get(self.etat, self.etat)

    @property
    def ecart(self):
        """Poulets manquants (+) ou en trop (−) : annoncé − (vivants + morts)."""
        if self.annonce is None or self.vivants is None or self.morts is None:
            return None
        return self.annonce - self.vivants - self.morts

    @property
    def morts_pct(self):
        if not self.annonce or self.morts is None:
            return None
        return self.morts / self.annonce * 100

    def __repr__(self):
        return f'<Reception {self.lot_saisi or self.lot_id} {self.etat}>'


class ResultatScan:
    VERT = 'VERT'
    ORANGE = 'ORANGE'
    ROUGE = 'ROUGE'
    LIBELLES = {VERT: 'Accepté', ORANGE: 'Réserve', ROUGE: 'Refusé'}


class Scan(db.Model):
    """Chaque lecture d'un lot par un opérateur, acceptée ou refusée. Le code du QR n'est jamais gardé
    en clair : seule son empreinte sert à compter les refus du même QR."""
    __tablename__ = 'scan'
    __journal_exclu__ = True        # chaque scan a sa propre ligne « Scan d'un lot » au journal
    __perimetre_operateur__ = 'operateur_id'

    id             = db.Column(db.Integer, primary_key=True)
    horodatage     = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    utilisateur_id = db.Column(db.Uuid, db.ForeignKey('utilisateur.id'), nullable=True)
    operateur_id   = db.Column(db.Integer, db.ForeignKey('operateur.id'), nullable=True, index=True)
    lot_id         = db.Column(db.Integer, db.ForeignKey('lot_trace.id'), nullable=True, index=True)
    empreinte      = db.Column(db.String(16), nullable=False, index=True)
    saisie         = db.Column(db.String(60), nullable=True)    # numéro tapé (jamais le code du QR)
    source         = db.Column(db.String(12), nullable=False)   # CAMERA, NUMERO, HORS_LIGNE
    resultat       = db.Column(db.String(6), nullable=False, index=True)
    motif          = db.Column(db.Text, nullable=True)

    utilisateur = db.relationship('Utilisateur')
    operateur = db.relationship('Operateur')
    lot = db.relationship('LotTrace')

    @property
    def libelle_resultat(self):
        return ResultatScan.LIBELLES.get(self.resultat, self.resultat)
