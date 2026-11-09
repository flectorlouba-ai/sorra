"""Consentement BCEG (lot 13). Le consentement est personnel : seul le RESPONSABLE d'une ferme financée
voit « 🏦 Ma banque » et répond. La dernière ligne de l'historique dit l'état ; un changement de
responsable fait tomber l'accord (ligne CADUC) et le nouveau responsable doit répondre.

Règle d'accès du profil BCEG (utils/permissions) : seulement les fermes financées dont la dernière
réponse est « accepte ». Sans réponse, après un refus, un retrait ou un changement de responsable :
aucun accès."""
from sqlalchemy import select, func

from app import db
from app.models import Ferme, Profil
from app.models.bceg import ConsentementBceg, DecisionBceg as D
from app.services.journal import enregistrer, Action


class RegleBceg(Exception):
    pass


def derniere(ferme):
    return (ConsentementBceg.query.filter_by(ferme_id=ferme.id)
            .order_by(ConsentementBceg.id.desc()).first())


def accord_en_cours(ferme):
    d = derniere(ferme)
    return bool(ferme.financee_bceg and d is not None and d.decision == D.ACCEPTE)


def fermes_du_responsable(user):
    """Fermes financées dont l'utilisateur est le responsable : lui seul voit « Ma banque »."""
    if user.profil != Profil.ELEVEUR:
        return []
    return Ferme.query.filter(Ferme.financee_bceg.is_(True), Ferme.responsable_id == user.id).all()


def a_repondre(user):
    """Fermes financées dont le responsable n'a pas encore répondu (pastille sur 👤 Moi)."""
    return [f for f in fermes_du_responsable(user)
            if derniere(f) is None or derniere(f).decision == D.CADUC]


def repondre(ferme, user, decision):
    if ferme not in fermes_du_responsable(user):
        raise RegleBceg('Seul le responsable de la ferme répond.')
    if decision not in (D.ACCEPTE, D.REFUSE, D.RETIRE):
        raise RegleBceg('Réponse inconnue.')
    d = derniere(ferme)
    if decision == D.RETIRE and (d is None or d.decision != D.ACCEPTE):
        raise RegleBceg("Il n'y a pas d'accord à retirer.")
    c = ConsentementBceg(ferme_id=ferme.id, utilisateur_id=user.id, decision=decision)
    db.session.add(c)
    db.session.flush()
    enregistrer(Action.CONSENTEMENT, table='ferme', enregistrement_id=ferme.id,
                detail=f'Ferme {ferme.numero} · BCEG : {c.libelle.lower()} par {user.nom_complet}.')
    return c


def regler(ferme, financee, responsable, user):
    """Agent de la ferme ou ADMIN : « financée par la BCEG » et responsable. Un changement de
    responsable fait tomber l'accord en cours ; le nouveau responsable devra répondre."""
    if responsable is not None and ferme.id not in responsable.ferme_ids:
        raise RegleBceg("Le responsable doit être un éleveur rattaché à la ferme.")
    if ferme.responsable_id != (responsable.id if responsable else None):
        d = derniere(ferme)
        if d is not None and d.decision != D.CADUC:
            db.session.add(ConsentementBceg(ferme_id=ferme.id, utilisateur_id=user.id, decision=D.CADUC))
        ferme.responsable_id = responsable.id if responsable else None
    ferme.financee_bceg = bool(financee)
    db.session.flush()


def condition_acces(colonne):
    """Fermes visibles du profil BCEG : financées ET dernière réponse « accepte »."""
    derniere_id = (select(func.max(ConsentementBceg.id)).where(ConsentementBceg.ferme_id == Ferme.id)
                   .correlate(Ferme).scalar_subquery())
    acceptees = (select(Ferme.id).join(ConsentementBceg, ConsentementBceg.id == derniere_id)
                 .where(Ferme.financee_bceg.is_(True), ConsentementBceg.decision == D.ACCEPTE))
    return colonne.in_(acceptees)
