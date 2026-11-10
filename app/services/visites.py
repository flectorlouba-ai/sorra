"""Visites techniques de l'agent (lot 12) : planifier, compte rendu (constats, recommandations,
position GPS, photo), annuler avec motif ; l'éleveur lit les recommandations dans « Mes visites »."""
from datetime import date

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.visite import Visite, StatutVisite as SV

JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']


class RegleVisite(Exception):
    pass


def objets():
    from app.models.liste_deroulante import ld_choices
    return [v for v, _ in ld_choices('objets_visite')]


def recommandations_types():
    from app.models.liste_deroulante import ld_choices
    return [v for v, _ in ld_choices('recommandations_visite')]


def planifier(ferme, jour, objet, user):
    if jour is None:
        raise RegleVisite('Choisissez la date de la visite.')
    if jour < date.today():
        raise RegleVisite('La date de la visite est passée.')
    if not objet:
        raise RegleVisite("Choisissez l'objet de la visite.")
    v = Visite(ferme_id=ferme.id, agent_id=user.id, date_prevue=jour, objet=objet[:60], statut=SV.PREVUE)
    db.session.add(v)
    db.session.flush()
    return v


def compte_rendu(ferme, visite, user, objet, constats, recommandations, libre, latitude, longitude, photo, jour,
                 precision=None, motif_distance=None):
    """Visite prévue → faite ; sans visite prévue, une visite non planifiée est créée."""
    recommandations = [r for r in (recommandations or []) if r]
    constats = (constats or '').strip()[:500] or None
    libre = (libre or '').strip()[:300] or None
    if not constats and not recommandations and not libre:
        raise RegleVisite('Écrivez un constat ou cochez une recommandation.')
    if visite is None:
        if not objet:
            raise RegleVisite("Choisissez l'objet de la visite.")
        visite = Visite(ferme_id=ferme.id, agent_id=user.id, objet=objet[:60])
        db.session.add(visite)
    elif visite.statut != SV.PREVUE:
        from app.services import hors_ligne
        if not hors_ligne.actif():
            raise RegleVisite('Cette visite a déjà son compte rendu.')
        # Saisi sans réseau, reçu après un autre compte rendu (ou une annulation) : rien n'est perdu (lot 12),
        # les deux sont gardés ; l'agent de la ferme est prévenu
        prevue = visite
        visite = Visite(ferme_id=ferme.id, agent_id=user.id, objet=(objet or prevue.objet)[:60])
        db.session.add(visite)
        hors_ligne.signaler(ferme, 'Deux comptes rendus pour la même visite',
                            f'Visite prévue le {prevue.date_prevue:%d/%m} : un compte rendu saisi sans réseau est '
                            f'arrivé après un autre. Les deux sont gardés.', user)
    visite.statut, visite.faite_le = SV.FAITE, jour or date.today()
    visite.constats, visite.recommandations, visite.recommandation_libre = constats, recommandations, libre
    visite.latitude, visite.longitude, visite.photo = latitude, longitude, photo
    visite.vue_par_eleveur_le = None
    # Lot E : la distance à la ferme est recalculée par le serveur ; loin : l'explication est gardée (le compte
    # rendu part quand même)
    from app.services import positions
    visite.ferme = ferme
    visite.precision_m = int(precision) if precision else None
    visite.distance_m = positions.distance_visite(visite)
    visite.motif_distance = (motif_distance or '').strip()[:300] or None
    db.session.flush()
    return visite


def annuler(visite, motif, user):
    if visite.statut != SV.PREVUE:
        raise RegleVisite('Seule une visite prévue peut être annulée.')
    if not (motif or '').strip():
        raise RegleVisite("Indiquez le motif de l'annulation.")
    visite.statut, visite.motif_annulation = SV.ANNULEE, motif.strip()[:300]   # journal : ANNULATION automatique


def prochaine(ferme_ids):
    """Prochaine visite prévue (aujourd'hui ou plus tard) ; une visite passée non faite n'est plus montrée."""
    if not ferme_ids:
        return None
    return (Visite.query.filter(Visite.ferme_id.in_(ferme_ids), Visite.statut == SV.PREVUE,
                                Visite.date_prevue >= date.today())
            .order_by(Visite.date_prevue).first())


def quand(jour):
    """« aujourd'hui », « demain », « jeudi 12 » (cette semaine et la suivante), sinon « le 03/12 »."""
    ecart = (jour - date.today()).days
    if ecart == 0:
        return "aujourd'hui"
    if ecart == 1:
        return 'demain'
    if 0 < ecart < 14:
        return f'{JOURS[jour.weekday()]} {jour.day}'
    return f'le {jour.strftime("%d/%m")}'


def faites(ferme_ids):
    return (Visite.query.filter(Visite.ferme_id.in_(ferme_ids), Visite.statut == SV.FAITE)
            .order_by(Visite.faite_le.desc(), Visite.cree_le.desc()).all()) if ferme_ids else []


def nouvelles(ferme_ids):
    return sum(1 for v in faites(ferme_ids) if v.vue_par_eleveur_le is None)


def marquer_vues(ferme_ids):
    for v in faites(ferme_ids):
        if v.vue_par_eleveur_le is None:
            v.vue_par_eleveur_le = maintenant()


def du_jour_pour_agent(user):
    """Visites prévues aujourd'hui ou en retard (passées, pas faites), pour l'encadré Alertes de l'agent."""
    from app.utils.permissions import filtre_perimetre
    return (filtre_perimetre(Visite.query, utilisateur=user)
            .filter(Visite.statut == SV.PREVUE, Visite.date_prevue <= date.today(), Visite.agent_id == user.id)
            .order_by(Visite.date_prevue).all()) if user.profil == Profil.AGENT else []
