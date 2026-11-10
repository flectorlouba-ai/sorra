"""Règles de l'entretien (lot 10) : tâches du jour, de la semaine, du mois et du vide sanitaire,
regroupées par tâche (« B1 et B2 »), cochées en un geste ; pannes Signalée → Réparée."""
from datetime import date, timedelta

from app import db
from app.models import Profil, JournalAudit, UtilisateurFerme
from app.models.base import maintenant
from app.models.bande import Bande, StatutBande
from app.models.entretien import (TacheEntretien, EntretienFait, Panne, Frequence, Portee, StatutPanne,
                                  TypePanne)
from app.services import bandes as regles_bandes
from app.services.journal import enregistrer, Action
from app.utils.dates import en_utc

DELAI_ANNULATION_SECONDES = 10
TOLERANCE_RESEAU_SECONDES = 20


class RegleEntretien(Exception):
    pass


# ── Périodes ────────────────────────────────────────────────────────────

def debut_periode(frequence, jour):
    """Premier jour de la période : le jour même, le lundi de la semaine, le 1er du mois."""
    if frequence == Frequence.SEMAINE:
        return jour - timedelta(days=jour.weekday())
    if frequence == Frequence.MOIS:
        return jour.replace(day=1)
    return jour


def periode_precedente(frequence, debut):
    if frequence == Frequence.SEMAINE:
        return debut - timedelta(days=7)
    if frequence == Frequence.MOIS:
        return (debut - timedelta(days=1)).replace(day=1)
    return debut - timedelta(days=1)


RETARD = {Frequence.SEMAINE: 'pas fait la semaine dernière', Frequence.MOIS: 'pas fait le mois dernier'}


# ── Tâches à afficher ───────────────────────────────────────────────────

def _faits(ferme, tache, periode=None, bande_ids=None):
    q = EntretienFait.query.filter_by(ferme_id=ferme.id, tache_id=tache.id, annule=False)
    if periode is not None:
        q = q.filter(EntretienFait.periode == periode)
    if bande_ids is not None:
        q = q.filter(EntretienFait.bande_id.in_(bande_ids))
    return q.all()


def desinfection_a_faire(batiment):
    """Dernière bande clôturée du bâtiment si sa désinfection n'est pas faite, sinon None."""
    tache = TacheEntretien.query.filter_by(frequence=Frequence.VIDE_SANITAIRE, actif=True).first()
    if tache is None or regles_bandes.bande_ouverte(batiment) is not None:
        return None
    derniere = regles_bandes.derniere_cloturee(batiment)
    if derniere is None:
        return None
    fait = EntretienFait.query.filter_by(tache_id=tache.id, bande_id=derniere.id, annule=False).first()
    return None if fait else derniere


def _cibles(ferme, tache, jour):
    """Bâtiments concernés (None = toute la ferme), avec la bande concernée pour le vide sanitaire."""
    infras = {i.infrastructure for i in ferme.infrastructures}
    if tache.infrastructure and tache.infrastructure not in infras:
        return []
    batiments = [b for b in sorted(ferme.batiments, key=lambda b: b.code) if b.actif]
    if tache.portee == Portee.FERME:
        return [(None, None)]
    if tache.portee == Portee.BANDE:
        return [(b, regles_bandes.bande_ouverte(b)) for b in batiments if regles_bandes.bande_ouverte(b)]
    if tache.portee == Portee.VIDE:
        # Bâtiments en vide sanitaire (bande clôturée, pas encore de nouvelle bande)
        return [(b, d) for b in batiments if regles_bandes.bande_ouverte(b) is None
                for d in [regles_bandes.derniere_cloturee(b)] if d]
    return []


def cartes(ferme, jour=None):
    """Une carte par tâche : bâtiments concernés regroupés, faite ou non, en retard ou non."""
    jour = jour or date.today()
    resultat = []
    for t in TacheEntretien.query.filter_by(actif=True).order_by(TacheEntretien.ordre, TacheEntretien.id):
        cibles = _cibles(ferme, t, jour)
        if not cibles:
            continue
        if t.frequence == Frequence.VIDE_SANITAIRE:
            # « Fait » pour ce vide sanitaire : la désinfection liée à la bande clôturée
            faits_ids = {f.batiment_id for f in _faits(ferme, t, bande_ids=[bande.id for _, bande in cibles])}
            periode = None
        else:
            periode = debut_periode(t.frequence, jour)
            faits_ids = {f.batiment_id for f in _faits(ferme, t, periode)}
        restants = [(b, bande) for b, bande in cibles if (b.id if b else None) not in faits_ids]
        retard = None
        if restants and t.frequence in RETARD:
            # La période précédente devait être faite (la cible existait déjà) et ne l'a pas été
            prec = periode_precedente(t.frequence, periode)
            existait = any(bande is None or bande.date_mise_en_place < periode for _, bande in cibles) \
                if t.portee == Portee.BANDE else ferme.cree_le.date() < periode
            if existait and not _faits(ferme, t, prec):
                retard = RETARD[t.frequence]
        codes = [b.code for b, _ in (restants or cibles) if b]
        if t.frequence == Frequence.VIDE_SANITAIRE:
            jours = min((jour - bande.date_cloture).days for _, bande in cibles if bande and bande.date_cloture)
            sous = f'{" et ".join(codes)} · vide sanitaire depuis {jours} jour{"s" if jours > 1 else ""}'
        else:
            sous = f'{" et ".join(codes) if codes else "toute la ferme"} · {t.libelle_frequence}'
        resultat.append({'tache': t, 'sous': sous, 'faite': not restants, 'retard': retard, 'periode': periode,
                         'restants': restants, 'cibles': cibles})
    # À faire d'abord (en retard en tête), puis les faites, en grisé
    return sorted(resultat, key=lambda c: (c['faite'], c['retard'] is None))


def a_faire_aujourdhui(ferme, jour=None):
    return sum(1 for c in cartes(ferme, jour) if not c['faite'])


def marquer_fait(ferme, tache, user, jour=None):
    """« Fait ✓ » : toutes les cibles encore à faire de la carte. Renvoie les lignes créées."""
    from app.services import hors_ligne
    jour = jour or hors_ligne.jour_de_saisie()
    carte = next((c for c in cartes(ferme, jour) if c['tache'].id == tache.id), None)
    if carte is None:
        raise RegleEntretien('Cette tâche ne concerne pas la ferme.')
    agent = user.profil == Profil.AGENT
    lignes = []
    for b, bande in carte['restants']:
        f = EntretienFait(ferme_id=ferme.id, batiment_id=b.id if b else None, tache_id=tache.id,
                          periode=carte['periode'], bande_id=bande.id if tache.frequence == Frequence.VIDE_SANITAIRE and bande else None,
                          fait_le=jour, saisi_par_agent=agent)
        db.session.add(f)
        lignes.append(f)
    if agent and lignes:
        enregistrer(Action.POUR_ELEVEUR, table='entretien_fait', enregistrement_id=lignes[0].id,
                    detail=f'Entretien « {tache.nom} » ({carte["sous"]}) coché par l\'agent {user.nom_complet} pour l\'éleveur.')
    db.session.flush()
    return lignes


def annulable(lignes, user):
    if not lignes or any(l.annule or l.cree_par != user.id for l in lignes):
        return False
    ecoule = (maintenant() - en_utc(lignes[0].cree_le)).total_seconds()
    return ecoule <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def annuler_fait(lignes):
    for l in lignes:
        l.annule = True


# ── Pannes ──────────────────────────────────────────────────────────────

def pannes_en_cours(ferme):
    return (Panne.query.filter_by(ferme_id=ferme.id, statut=StatutPanne.SIGNALEE, archive_le=None)
            .order_by(Panne.signalee_le.desc()).all())


def signaler(ferme, type_panne, batiment, user, photo=None):
    if type_panne not in TypePanne.ICONES:
        raise RegleEntretien("Touchez ce qui ne marche pas.")
    if batiment is not None and batiment.ferme_id != ferme.id:
        raise RegleEntretien('Bâtiment inconnu.')
    p = Panne(ferme_id=ferme.id, batiment_id=batiment.id if batiment else None, type=type_panne, photo=photo,
              saisie_par_agent=user.profil == Profil.AGENT)
    db.session.add(p)
    db.session.flush()
    return p


def reparer(panne, user):
    if panne.statut == StatutPanne.REPAREE:
        return
    panne.statut = StatutPanne.REPAREE
    panne.reparee_le = maintenant()
    panne.reparee_par = user.id
    panne.reparee_par_agent = user.profil == Profil.AGENT


def reparation_annulable(panne, user):
    if panne.statut != StatutPanne.REPAREE or panne.reparee_par != user.id or not panne.reparee_le:
        return False
    ecoule = (maintenant() - en_utc(panne.reparee_le)).total_seconds()
    return ecoule <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def annuler_reparation(panne, user):
    """« Réparé ✓ — Annuler » : la panne redevient « Signalée », l'alerte de l'agent revient."""
    panne.statut = StatutPanne.SIGNALEE
    panne.reparee_le = panne.reparee_par = None
    panne.reparee_par_agent = False
    enregistrer(Action.ANNULATION, table='panne', enregistrement_id=panne.id,
                detail=f'Réparation de la panne « {panne.libelle} » ({panne.ou}) annulée aussitôt par '
                       f'{user.nom_complet} : la panne est de nouveau signalée.')


# ── Pour l'agent : résumé de la fiche ferme ─────────────────────────────

ACTIONS_SANS_SAISIE = ('CONNEXION', 'DECONNEXION', 'ECHEC_CONNEXION', 'CHANGEMENT_MDP', 'BLOCAGE',
                       'DEBLOCAGE', 'EXPORT', 'LECTURE_QR')


def derniere_synchronisation(ferme):
    """Date de la dernière saisie reçue d'un éleveur de la ferme (journal), sans les connexions."""
    eleveurs = [uf.utilisateur_id for uf in UtilisateurFerme.query.filter_by(ferme_id=ferme.id)]
    if not eleveurs:
        return None
    j = (JournalAudit.query.filter(JournalAudit.utilisateur_id.in_(eleveurs),
                                   JournalAudit.action.notin_(ACTIONS_SANS_SAISIE))
         .order_by(JournalAudit.horodatage.desc()).first())
    return j.horodatage if j else None


def resume_ferme(ferme, jour=None):
    jour = jour or date.today()
    vide = TacheEntretien.query.filter_by(frequence=Frequence.VIDE_SANITAIRE).first()
    desinfections = []
    for b in sorted(ferme.batiments, key=lambda b: b.code):
        if not b.actif:
            continue
        dernier = (EntretienFait.query.filter_by(batiment_id=b.id, tache_id=vide.id, annule=False)
                   .order_by(EntretienFait.fait_le.desc()).first()) if vide else None
        desinfections.append({'batiment': b, 'derniere': dernier.fait_le if dernier else None,
                              'a_faire': desinfection_a_faire(b) is not None})
    synchro = derniere_synchronisation(ferme)
    return {'pannes': pannes_en_cours(ferme),
            'retards': [c for c in cartes(ferme, jour) if c['retard']],
            'desinfections': desinfections,
            'sans_desinfection': Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS,
                                                       ouverte_sans_desinfection=True).all(),
            'synchro': synchro,
            'synchro_jours': (maintenant() - en_utc(synchro)).days if synchro else None}
