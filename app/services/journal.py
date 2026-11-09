"""Journal d'audit automatique.

Toute création, modification ou suppression passant par la session SQLAlchemy
est enregistrée au moment de l'écriture en base, dans la même transaction :
si l'opération est annulée, sa trace l'est aussi. On enregistre qui, quand,
depuis quelle adresse, quelle table, quel enregistrement, et les valeurs
avant / après (seulement les champs changés pour une modification).

Réglages possibles sur un modèle :
- `__journal_exclu__ = True` : table non journalisée (journal lui-même, compteurs) ;
- `__journal_ignorer__` : champs dont le seul changement ne crée pas de ligne ;
- `__journal_masquer__` : champs remplacés par « *** » (mots de passe) ;
- `__journal_relations__` : relations multiples à suivre, avec l'attribut à
  recopier (ex. `{'provinces': 'code'}`).

Les connexions, échecs, exports… s'enregistrent avec `enregistrer()`.
"""
import decimal
import enum
import uuid
from datetime import date, datetime

from flask import has_request_context, request
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.base import SaisieTerrainMixin, maintenant
from app.models.compteur import Compteur
from app.models.journal import JournalAudit


class Action:
    CREATION        = 'CREATION'
    MODIFICATION    = 'MODIFICATION'
    SUPPRESSION     = 'SUPPRESSION'
    ANNULATION      = 'ANNULATION'
    CONNEXION       = 'CONNEXION'
    ECHEC_CONNEXION = 'ECHEC_CONNEXION'
    DECONNEXION     = 'DECONNEXION'
    CHANGEMENT_MDP  = 'CHANGEMENT_MDP'
    EXPORT          = 'EXPORT'
    BLOCAGE         = 'BLOCAGE'
    DEBLOCAGE       = 'DEBLOCAGE'
    IMPORT          = 'IMPORT'
    FUSION          = 'FUSION'
    CONFIRMATION    = 'CONFIRMATION'
    CONFIRMATION_ANNULEE = 'CONF_ANNULEE'
    CORRECTION      = 'CORRECTION'
    POUR_ELEVEUR    = 'POUR_ELEVEUR'
    DELAI_ATTENTE   = 'DELAI_ATTENTE'
    LECTURE_QR      = 'LECTURE_QR'
    SANS_DESINFECTION = 'SANS_DESINFECTION'
    VERIFICATION    = 'VERIFICATION'
    REPONSE_VETO    = 'REPONSE_VETO'
    CONSENTEMENT    = 'CONSENTEMENT'
    PROPOSITION     = 'PROPOSITION'
    APPROBATION     = 'APPROBATION'
    REFUS           = 'REFUS'

    TOUTES = [CREATION, MODIFICATION, SUPPRESSION, ANNULATION, CONNEXION,
              ECHEC_CONNEXION, DECONNEXION, CHANGEMENT_MDP, EXPORT, BLOCAGE, DEBLOCAGE, IMPORT, FUSION,
              CONFIRMATION, CONFIRMATION_ANNULEE, CORRECTION, POUR_ELEVEUR, DELAI_ATTENTE, LECTURE_QR, SANS_DESINFECTION,
              VERIFICATION, REPONSE_VETO, CONSENTEMENT, PROPOSITION, APPROBATION, REFUS]

    LIBELLES = {
        CREATION: 'Création', MODIFICATION: 'Modification', SUPPRESSION: 'Suppression',
        ANNULATION: 'Annulation', CONNEXION: 'Connexion', ECHEC_CONNEXION: 'Échec de connexion',
        DECONNEXION: 'Déconnexion', CHANGEMENT_MDP: 'Changement de mot de passe',
        EXPORT: 'Export', BLOCAGE: 'Blocage du compte', DEBLOCAGE: 'Déblocage du compte',
        IMPORT: 'Import', FUSION: 'Fusion de localités',
        CONFIRMATION: 'Confirmation de réception', CONFIRMATION_ANNULEE: 'Confirmation annulée',
        CORRECTION: 'Correction', DELAI_ATTENTE: "Sortie pendant un délai d'attente", POUR_ELEVEUR: "Saisie de l'agent pour l'éleveur",
        LECTURE_QR: "Lecture d'un QR code",
        SANS_DESINFECTION: 'Bande ouverte sans désinfection',
        VERIFICATION: 'Saisie à vérifier tranchée', REPONSE_VETO: "Réponse du vétérinaire à l'éleveur",
        CONSENTEMENT: 'Consentement BCEG', PROPOSITION: 'Modification proposée (quatre yeux)',
        APPROBATION: 'Modification approuvée', REFUS: 'Modification refusée',
    }


_TABLES_EXCLUES = (JournalAudit, Compteur)
MASQUE = '***'


def _auteur():
    """(utilisateur_id, identifiant, adresse_ip) de la requête en cours, ou du système."""
    if not has_request_context():
        return None, 'système', None
    from flask_login import current_user
    ip = request.remote_addr
    try:
        if current_user and current_user.is_authenticated:
            return current_user.id, current_user.identifiant, ip
    except Exception:
        pass
    return None, None, ip


def _valeur(v):
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, enum.Enum):
        return v.value
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, (uuid.UUID, decimal.Decimal)):
        return str(v)
    return str(v)


def _identifiant(obj):
    cle = inspect(obj).identity
    if not cle:
        return None
    return str(cle[0]) if len(cle) == 1 else '/'.join(str(c) for c in cle)


def _relation_valeurs(objets, attr):
    return sorted(str(getattr(o, attr)) for o in objets)


def _instantane(obj):
    """Toutes les valeurs de l'objet (création, suppression)."""
    classe = type(obj)
    masquer = getattr(classe, '__journal_masquer__', set())
    etat = inspect(obj)
    donnees = {}
    for col in etat.mapper.column_attrs:
        v = getattr(obj, col.key)
        donnees[col.key] = MASQUE if (col.key in masquer and v is not None) else _valeur(v)
    for rel, attr in getattr(classe, '__journal_relations__', {}).items():
        donnees[rel] = _relation_valeurs(getattr(obj, rel) or [], attr)
    return donnees


def _differences(obj):
    """(avant, après) limités aux champs modifiés ; (None, None) si rien de notable."""
    classe = type(obj)
    ignorer = getattr(classe, '__journal_ignorer__', set())
    masquer = getattr(classe, '__journal_masquer__', set())
    etat = inspect(obj)
    avant, apres = {}, {}
    for col in etat.mapper.column_attrs:
        if col.key in ignorer or col.key in ('modifie_le',):
            continue
        hist = etat.attrs[col.key].history
        if not hist.has_changes() or not hist.deleted:
            continue
        ancien, nouveau = hist.deleted[0], getattr(obj, col.key)
        if ancien == nouveau:
            continue
        if col.key in masquer:
            avant[col.key], apres[col.key] = MASQUE, MASQUE + ' (modifié)'
        else:
            avant[col.key], apres[col.key] = _valeur(ancien), _valeur(nouveau)
    for rel, attr in getattr(classe, '__journal_relations__', {}).items():
        hist = etat.attrs[rel].history
        if not (hist.added or hist.deleted):
            continue
        actuels = list(getattr(obj, rel) or [])
        anciens = [o for o in actuels if o not in hist.added] + list(hist.deleted)
        a, n = _relation_valeurs(anciens, attr), _relation_valeurs(actuels, attr)
        if a != n:
            avant[rel], apres[rel] = a, n
    if not avant and not apres:
        return None, None
    return avant, apres


def _est_annulation(obj, apres):
    """Passage d'un champ `annule` / `est_annule` à vrai, ou d'un `statut` à ANNULE."""
    for champ in ('annule', 'est_annule'):
        if apres.get(champ) is True:
            return True
    return str(apres.get('statut', '')).upper() in ('ANNULE', 'ANNULEE')


def _journalisable(obj):
    return not isinstance(obj, _TABLES_EXCLUES) and not getattr(type(obj), '__journal_exclu__', False)


def _ligne(action, obj, avant, apres, auteur):
    uid, ident, ip = auteur
    return dict(horodatage=maintenant(), utilisateur_id=uid, identifiant=ident, adresse_ip=ip,
                action=action, table_nom=obj.__tablename__, enregistrement_id=_identifiant(obj),
                avant=avant, apres=apres, detail=None)


def _avant_ecriture(session, flush_context, instances):
    """Renseigne cree_par / modifie_par des tables de saisie terrain."""
    uid = _auteur()[0]
    if uid is None:
        return
    for obj in session.new:
        if isinstance(obj, SaisieTerrainMixin):
            obj.cree_par = obj.cree_par or uid
            obj.modifie_par = obj.modifie_par or uid
    for obj in session.dirty:
        if isinstance(obj, SaisieTerrainMixin) and session.is_modified(obj):
            obj.modifie_par = uid


def _apres_ecriture(session, flush_context):
    # Les collections new / dirty / deleted et l'historique des champs sont
    # encore disponibles ici ; les identifiants des nouvelles lignes aussi.
    auteur = _auteur()
    lignes = []
    for obj in session.new:
        if _journalisable(obj):
            lignes.append(_ligne(Action.CREATION, obj, None, _instantane(obj), auteur))
    for obj in session.dirty:
        if _journalisable(obj) and obj not in session.deleted:
            avant, apres = _differences(obj)
            if apres is not None:
                action = Action.ANNULATION if _est_annulation(obj, apres) else Action.MODIFICATION
                lignes.append(_ligne(action, obj, avant, apres, auteur))
    for obj in session.deleted:
        if _journalisable(obj):
            lignes.append(_ligne(Action.SUPPRESSION, obj, _instantane(obj), None, auteur))
    if lignes:
        # Insertion directe : pas de nouveau passage dans ce même événement.
        session.connection().execute(JournalAudit.__table__.insert(), lignes)


def chainer(session, flush_context=None):
    """Lot 15 : chaque nouvelle entrée du journal reçoit son empreinte SHA-256 (qui inclut celle de la
    précédente), dans la table à part `journal_chaine`. Le journal n'est jamais modifié."""
    from sqlalchemy import select
    from app.models.securite import JournalChaine
    from app.utils.empreinte import empreinte, GENESE
    conn = session.connection()
    dernier = conn.execute(select(JournalChaine.journal_id, JournalChaine.empreinte)
                           .order_by(JournalChaine.journal_id.desc()).limit(1)).first()
    depuis, precedente = (dernier.journal_id, dernier.empreinte) if dernier else (0, GENESE)
    nouvelles = conn.execute(select(JournalAudit.__table__).where(JournalAudit.id > depuis)
                             .order_by(JournalAudit.id)).mappings().all()
    if not nouvelles:
        return
    lignes = []
    for r in nouvelles:
        e = empreinte(precedente, r)
        lignes.append({'journal_id': r['id'], 'precedente': precedente, 'empreinte': e})
        precedente = e
    conn.execute(JournalChaine.__table__.insert(), lignes)


def verifier_chaine():
    """(intact, nombre d'entrées, première entrée rompue ou None)."""
    from sqlalchemy import select
    from app import db
    from app.models.securite import JournalChaine
    from app.utils.empreinte import empreinte, GENESE
    chaine = {c.journal_id: c for c in JournalChaine.query}
    precedente, n = GENESE, 0
    for r in db.session.execute(select(JournalAudit.__table__).order_by(JournalAudit.id)).mappings():
        n += 1
        c = chaine.get(r['id'])
        if c is None or c.precedente != precedente or empreinte(precedente, r) != c.empreinte:
            return False, n, db.session.get(JournalAudit, r['id'])
        precedente = c.empreinte
    return True, n, None


_installe = False


def installer():
    global _installe
    if _installe:
        return
    event.listen(Session, 'before_flush', _avant_ecriture)
    event.listen(Session, 'after_flush', _apres_ecriture)
    event.listen(Session, 'after_flush_postexec', chainer)
    _installe = True


def enregistrer(action, table=None, enregistrement_id=None, detail=None,
                utilisateur=None, identifiant=None):
    """Ajoute une ligne « événement » (connexion, export…) à la session courante.
    L'appelant valide la transaction."""
    from app import db
    uid, ident, ip = _auteur()
    if utilisateur is not None:
        uid, ident = utilisateur.id, utilisateur.identifiant
    if identifiant is not None:
        ident = identifiant
    db.session.add(JournalAudit(
        horodatage=maintenant(), utilisateur_id=uid, identifiant=ident, adresse_ip=ip,
        action=action, table_nom=table,
        enregistrement_id=str(enregistrement_id) if enregistrement_id is not None else None,
        detail=detail,
    ))
