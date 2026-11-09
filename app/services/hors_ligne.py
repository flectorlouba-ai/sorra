"""Envois faits après coup par le téléphone (saisies gardées sans réseau).

Le téléphone rejoue le formulaire d'origine sur la même adresse, avec trois en-têtes :
`X-Hors-Ligne-Id` (UUID tiré sur l'appareil), `X-Hors-Ligne-Horodatage` (heure de la
saisie sur le téléphone) et `X-Appareil`. Les écrans existants font tout le travail
(contrôles, journal, alertes) ; ce module ajoute seulement :
- le refus des doublons (un identifiant déjà reçu n'est jamais rejoué) ;
- une réponse courte en JSON au lieu de la page HTML ;
- la note de l'identifiant reçu dans la même transaction que la saisie ;
- les conflits : la saisie la plus récente gagne, l'agent est prévenu.
Voir docs/hors_ligne.md.
"""
import uuid
from datetime import date, datetime, timezone
from urllib.parse import unquote

from flask import g, request, session, jsonify, flash, has_request_context, template_rendered
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.base import SaisieTerrainMixin, maintenant
from app.models.hors_ligne import EnvoiHorsLigne, ConflitHorsLigne
from app.models.journal import JournalAudit

ENTETE = 'X-Hors-Ligne-Id'


def actif():
    """Vrai pendant le rejeu d'une saisie faite sans réseau."""
    return has_request_context() and g.get('hors_ligne') is not None


def saisi_le():
    """Heure de la saisie sur le téléphone (ou None)."""
    return g.hors_ligne['saisi_le'] if actif() else None


def jour_de_saisie():
    """Jour où la saisie a été faite (aujourd'hui hors rejeu) : sert de référence pour
    « aujourd'hui » et pour la limite des jours passés."""
    h = saisi_le()
    return h.astimezone().date() if h else date.today()


def plus_recente(serveur_le):
    """Vrai si la saisie du téléphone est plus récente que la version du serveur."""
    h = saisi_le()
    if h is None or serveur_le is None:
        return True
    if serveur_le.tzinfo is None:
        serveur_le = serveur_le.replace(tzinfo=timezone.utc)
    return h >= serveur_le


def signaler(ferme, quoi, detail, utilisateur=None):
    """Conflit ou refus visible de l'agent de la ferme. L'appelant valide la transaction."""
    from app import db
    u = utilisateur or (current_user if current_user.is_authenticated else None)
    db.session.add(ConflitHorsLigne(ferme_id=ferme.id if ferme else None, utilisateur_id=u.id if u else None,
                                    quoi=quoi[:150], detail=detail))


def conflit():
    """À appeler par un écran qui a tranché un conflit (la réponse dira « conflit »)."""
    if actif():
        g.hors_ligne['etat'] = 'conflit'


def libelle():
    return (g.hors_ligne['libelle'] if actif() else '') or request.path


# ── Accroches de requête ────────────────────────────────────────────────

def _lire_entetes():
    try:
        ident = uuid.UUID(request.headers.get(ENTETE, ''))
    except ValueError:
        return None
    h = request.headers.get('X-Hors-Ligne-Horodatage', '')
    try:
        saisi = datetime.fromisoformat(h.replace('Z', '+00:00')) if h else None
        if saisi and saisi.tzinfo is None:
            saisi = saisi.replace(tzinfo=timezone.utc)
        if saisi and saisi > maintenant():
            saisi = maintenant()   # horloge du téléphone en avance : on ne la croit pas
    except ValueError:
        saisi = None
    return {'id': ident, 'saisi_le': saisi, 'etat': 'ok', 'note': False, 'erreur': None,
            'libelle': unquote(request.headers.get('X-Hors-Ligne-Libelle', ''))[:150],
            'appareil': request.headers.get('X-Appareil', '')[:64] or None}


def _avant_requete():
    g.pop('hors_ligne', None)     # jamais l'état d'une requête précédente (contexte partagé dans les tests)
    if request.method != 'POST' or ENTETE not in request.headers:
        return None
    infos = _lire_entetes()
    if infos is None:
        return jsonify(etat='refuse', message='Envoi illisible.'), 400
    if not current_user.is_authenticated:
        return jsonify(etat='connexion')
    from app import db
    if db.session.get(EnvoiHorsLigne, infos['id']) is not None:
        return jsonify(etat='deja', message='Déjà reçu.')
    # Messages restés d'une page précédente : mis de côté, rendus après l'envoi
    infos['anciens'] = session.pop('_flashes', [])
    g.hors_ligne = infos
    return None


def _apres_requete(reponse):
    if request.method != 'POST' or ENTETE not in request.headers or reponse.mimetype == 'application/json':
        return reponse
    from app import db
    messages = session.pop('_flashes', [])   # pas get_flashed_messages : il garde la 1re lecture
    erreurs = [m for c, m in messages if c == 'danger']
    if 300 <= reponse.status_code < 400:
        if '/auth/' in (reponse.location or ''):
            return jsonify(etat='connexion')
        etat = 'refuse' if erreurs else (g.hors_ligne['etat'] if actif() else 'ok')
        message = erreurs[0] if erreurs else ' '.join(m for _, m in messages)
    else:
        etat = 'refuse'
        message = (g.hors_ligne['erreur'] if actif() else None) or (erreurs[0] if erreurs else None) \
            or 'Saisie refusée.'
    if etat == 'refuse' and actif() and current_user.is_authenticated:
        try:
            db.session.rollback()
            g.hors_ligne['note'] = True   # un envoi refusé n'est pas noté comme reçu
            signaler(_ferme_de_l_adresse(), f'Envoi refusé : {libelle()}',
                     f'Saisie faite sans réseau le {_heure(saisi_le())}, refusée à l\'envoi : {message}')
            db.session.commit()
        except Exception:   # le refus reste signalé au téléphone
            db.session.rollback()
    if actif():
        for categorie, texte in g.hors_ligne['anciens']:
            flash(texte, categorie)
    return jsonify(etat=etat, message=message)


def _heure(h):
    return h.astimezone().strftime('%d/%m à %H:%M') if h else '—'


def _ferme_de_l_adresse():
    """Ferme concernée, d'après l'adresse rejouée (bande, livraison ou ferme)."""
    from app.models import Ferme, Livraison
    from app.models.bande import Bande
    morceaux = request.path.strip('/').split('/')
    if len(morceaux) >= 2 and morceaux[0] == 'bandes':
        b = Bande.query.filter_by(numero_metier=morceaux[1]).first()
        return b.ferme if b else None
    if len(morceaux) >= 2 and morceaux[0] == 'livraisons':
        liv = Livraison.query.filter_by(numero_metier=morceaux[1]).first()
        return liv.ferme if liv else None
    if request.values.get('bande'):
        b = Bande.query.filter_by(numero_metier=request.values.get('bande')).first()
        return b.ferme if b else None
    return Ferme.query.filter_by(numero_metier=request.values.get('ferme', '')).first()


def _gabarit_rendu(sender, template, context, **extra):
    if actif() and g.hors_ligne['erreur'] is None:
        erreur = context.get('erreur') or (context.get('erreurs') or [None])[0]
        if erreur:
            g.hors_ligne['erreur'] = str(erreur)


# ── Note de l'identifiant dans la transaction de la saisie ──────────────

def _avant_ecriture(session, flush_context, instances):
    if not actif():
        return
    infos = g.hors_ligne
    # Un conflit tranché sans rien changer compte aussi : l'identifiant est noté, jamais rejoué
    nouveaux = [o for o in session.new if not isinstance(o, (JournalAudit, EnvoiHorsLigne))]
    for obj in nouveaux:
        if isinstance(obj, SaisieTerrainMixin):
            obj.id = obj.id or uuid.uuid4()   # connu avant l'insertion, pour le noter ci-dessous
            obj.appareil_id = obj.appareil_id or infos['appareil']
    if infos['note'] or not (nouveaux or any(session.is_modified(o) for o in session.dirty)):
        return
    objet = next((o for o in nouveaux if isinstance(o, SaisieTerrainMixin)), None)
    session.add(EnvoiHorsLigne(id=infos['id'], utilisateur_id=current_user.id, appareil_id=infos['appareil'],
                               saisi_le=infos['saisi_le'], adresse=request.path[:255],
                               objet_table=objet.__tablename__ if objet else None,
                               objet_id=str(objet.id) if objet is not None and objet.id else None))
    infos['note'] = True


def _apres_annulation(session, previous_transaction=None):
    if actif():
        g.hors_ligne['note'] = False


_ecoute = False


def installer(app):
    global _ecoute
    from app import db
    app.before_request(_avant_requete)
    app.after_request(_apres_requete)
    template_rendered.connect(_gabarit_rendu, app)
    if not _ecoute:
        event.listen(Session, 'before_flush', _avant_ecriture)
        event.listen(Session, 'after_soft_rollback', _apres_annulation)
        _ecoute = True

    @app.errorhandler(IntegrityError)
    def _doublon(e):
        # Deux envois simultanés du même identifiant : le second est un doublon
        db.session.rollback()
        if actif() and db.session.get(EnvoiHorsLigne, g.hors_ligne['id']) is not None:
            return jsonify(etat='deja', message='Déjà reçu.')
        raise e
