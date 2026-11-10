"""Lot D — plans d'actions : création (manuelle ou depuis une alerte, une visite, un arbitrage, un rapport),
affectation, avancement, clôture avec commentaire et photo, retards, journal."""
from datetime import date

from app import db
from app.models import Ferme, Profil, Province, Utilisateur
from app.models.action import Action, OrigineAction, Priorite
from app.models.base import maintenant
from app.services.journal import enregistrer, Action as J
from app.services.numerotation import generer_numero
from app.utils.permissions import filtre_perimetre


class RegleAction(Exception):
    pass


GESTIONNAIRES = (Profil.DGE, Profil.ADMIN, Profil.AGENT)


def _jour(texte):
    try:
        return date.fromisoformat((texte or '').strip())
    except ValueError:
        raise RegleAction("Indiquez l'échéance (une date).")


def responsables_possibles(user):
    """À qui confier une action : la DGE à un agent ou à elle-même ; l'agent à lui-même."""
    if user.profil in (Profil.DGE, Profil.ADMIN):
        agents = Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True).order_by(Utilisateur.nom).all()
        return [user] + [a for a in agents if a.id != user.id]
    return [user]


def creer(user, intitule, echeance, responsable=None, priorite=Priorite.MOYENNE, ferme=None, province=None,
          origine=OrigineAction.MANUEL, origine_table=None, origine_id=None, commentaire=None):
    intitule = (intitule or '').strip()
    if not intitule:
        raise RegleAction("Écrivez l'intitulé de l'action.")
    if user.profil not in GESTIONNAIRES:
        raise RegleAction('Seuls la DGE, un agent ou un administrateur créent une action.')
    responsable = responsable or user
    if responsable.id not in {r.id for r in responsables_possibles(user)}:
        raise RegleAction('Vous ne pouvez pas confier une action à cette personne.')
    if ferme is not None and filtre_perimetre(Ferme.query, utilisateur=user).filter(Ferme.id == ferme.id).first() is None:
        raise RegleAction('Cette ferme est hors de votre périmètre.')
    if priorite not in Priorite.TOUTES:
        priorite = Priorite.MOYENNE
    echeance = echeance if isinstance(echeance, date) else _jour(echeance)
    perimetre = 'FERME' if ferme is not None else 'PROVINCE' if province is not None else 'NATIONAL'
    a = Action(numero=generer_numero('ACTION', 'ACT', annuel=True), intitule=intitule[:200], origine=origine,
               origine_table=origine_table, origine_id=str(origine_id) if origine_id else None, perimetre=perimetre,
               ferme_id=ferme.id if ferme else None, province_id=province.id if province else (ferme.province_id if ferme else None),
               responsable_id=responsable.id, creee_par=user.id, echeance=echeance, priorite=priorite,
               commentaire=(commentaire or '').strip()[:1000] or None)
    db.session.add(a)
    db.session.flush()
    enregistrer(J.CREATION, table='action', enregistrement_id=a.id,
                detail=f'Action {a.numero} « {a.intitule} » créée par {user.nom_complet}, confiée à '
                       f'{responsable.nom_complet}, pour le {echeance:%d/%m/%Y} ({a.libelle_origine.lower()})')
    return a


def peut_modifier(user, a):
    return user.profil in (Profil.DGE, Profil.ADMIN) or user.id in (a.responsable_id, a.creee_par)


def modifier(user, a, **champs):
    if not peut_modifier(user, a):
        raise RegleAction('Vous ne pouvez pas modifier cette action.')
    avant = f'{a.intitule} · {a.echeance:%d/%m} · {a.priorite} · {a.avancement} %'
    if 'intitule' in champs and (champs['intitule'] or '').strip():
        a.intitule = champs['intitule'].strip()[:200]
    if champs.get('echeance'):
        a.echeance = _jour(champs['echeance'])
    if champs.get('priorite') in Priorite.TOUTES:
        a.priorite = champs['priorite']
    if champs.get('responsable') is not None and user.profil in (Profil.DGE, Profil.ADMIN):
        a.responsable_id = champs['responsable'].id
    if champs.get('avancement') is not None:
        try:
            a.avancement = min(100, max(0, int(champs['avancement'])))
        except (TypeError, ValueError):
            raise RegleAction("L'avancement est un pourcentage (0 à 100).")
    if 'commentaire' in champs:
        a.commentaire = (champs['commentaire'] or '').strip()[:1000] or None
    if champs.get('photo'):
        a.photo = champs['photo']
    enregistrer(J.MODIFICATION, table='action', enregistrement_id=a.id,
                detail=f'Action {a.numero} modifiée par {user.nom_complet} : {avant} → '
                       f'{a.intitule} · {a.echeance:%d/%m} · {a.priorite} · {a.avancement} %')
    return a


def cloturer(user, a, commentaire=None, photo=None):
    if not peut_modifier(user, a):
        raise RegleAction('Vous ne pouvez pas clôturer cette action.')
    if a.faite_le is not None:
        return a
    a.faite_le, a.avancement = maintenant(), 100
    if commentaire:
        a.commentaire = commentaire.strip()[:1000]
    if photo:
        a.photo = photo
    enregistrer(J.MODIFICATION, table='action', enregistrement_id=a.id,
                detail=f'Action {a.numero} faite ({user.nom_complet})' + (f' — {a.commentaire}' if a.commentaire else ''))
    return a


def rouvrir(user, a):
    if not peut_modifier(user, a):
        raise RegleAction('Vous ne pouvez pas rouvrir cette action.')
    a.faite_le, a.avancement = None, min(a.avancement, 90)
    enregistrer(J.MODIFICATION, table='action', enregistrement_id=a.id, detail=f'Action {a.numero} rouverte ({user.nom_complet})')
    return a


def visibles(user):
    """Les actions du périmètre : la DGE et l'ADMIN voient tout, l'agent celles de ses fermes ou dont il est responsable."""
    q = Action.query
    if user.profil in (Profil.DGE, Profil.ADMIN):
        return q
    ids = [f.id for f in filtre_perimetre(Ferme.query, utilisateur=user)]
    return q.filter(db.or_(Action.responsable_id == user.id, Action.creee_par == user.id,
                           Action.ferme_id.in_(ids) if ids else db.false()))


def en_retard(user):
    return [a for a in visibles(user).filter(Action.faite_le.is_(None), Action.echeance < date.today())]


def mes_actions(user):
    """Les actions dont la personne est responsable, les plus urgentes d'abord (retard, puis échéance)."""
    actions = Action.query.filter_by(responsable_id=user.id).all()
    ordre = {'RETARD': 0, 'A_FAIRE': 1, 'EN_COURS': 1, 'FAITE': 2}
    return sorted(actions, key=lambda a: (ordre[a.etat], a.echeance))


def n_en_retard(user):
    return len(en_retard(user))


def phrase_echeance(a):
    """« ⏰ en retard de 2 jours », « pour demain », « pour le 14/11 »."""
    if a.etat == 'FAITE':
        return f'✓ faite le {a.faite_le:%d/%m}'
    d = (a.echeance - date.today()).days
    if d < 0:
        return f'⏰ en retard de {-d} jour{"s" if -d > 1 else ""}'
    if d == 0:
        return "pour aujourd'hui"
    if d == 1:
        return 'pour demain'
    return f'pour le {a.echeance:%d/%m}'
