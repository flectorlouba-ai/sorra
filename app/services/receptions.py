"""Lot 19 — réception des lots par l'opérateur (abattoir, marché, acheteur, distributeur).

Fonctions 58 (écart à la réception), 63 (contrôles automatiques), 65 (refus), 66 (indicateurs : voir
app/indicateurs.py). Règles validées le 09/11/2026 :
- un scan est ROUGE (refus) si le QR est inconnu, le lot annulé, déjà reçu ou refusé par le vétérinaire,
  destiné à un autre opérateur, ou si les ventes de la bande sont bloquées par le vétérinaire ;
- il est ORANGE (réserve) si un contrôle bloquant manque : délai d'attente, vaccins, pesée. Ce qui est
  bloquant dépend du type d'opérateur et des paramètres `reception.controle_*` (quatre yeux) ;
- la sortie de la ferme (« annoncé ») n'est jamais modifiée : l'annoncé est recopié à côté du reçu ;
- tout écart de nombre, ou des morts au-delà du seuil, demande un motif (« Autre » : un texte) ; l'agent
  de la ferme et la DGE sont prévenus, le vétérinaire de la zone aussi au-delà du seuil de morts ;
- sous réserve : « ne pas abattre / ne pas vendre » jusqu'à la décision du vétérinaire (libérer ou refuser) ;
- chaque scan, accepté ou refusé, est inscrit au journal ; 3 refus du même QR en 24 h alertent la DGE.
"""
import hashlib
import re
from datetime import date, timedelta

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.liste_deroulante import ld_choices
from app.models.tracabilite import LotTrace, Reception, Scan, EtatReception as E, ResultatScan as R
from app.services import parametres
from app.services.journal import enregistrer, Action

TYPE_ABATTOIR = 'Abattoir'
MOTIF_AUTRE = 'Autre'
MODES = ('TOUS', 'ABATTOIR', 'INFO', 'NON')
# Contrôles réglables : (clé, libellé, mode par défaut). Les contrôles de refus (QR, destinataire, blocage)
# sont fixés dans le code.
REGLABLES = [
    ('vaccins', 'Vaccins obligatoires faits', 'ABATTOIR'),
    ('delai_attente', "Aucun traitement en délai d'attente", 'TOUS'),
    ('pesee', 'Pesée récente', 'ABATTOIR'),
]
SOURCES = ('CAMERA', 'NUMERO', 'HORS_LIGNE')
ADRESSE_QR = re.compile(r'/q/([A-Za-z0-9_-]{8,40})/?$')


class RegleReception(Exception):
    pass


# ── Lecture du lot ──────────────────────────────────────────────────────

def code_lu(texte):
    """Code du lot dans ce que la caméra a lu : l'adresse imprimée (…/q/<code>) ou le code seul."""
    texte = (texte or '').strip()
    m = ADRESSE_QR.search(texte.split('?')[0].split('#')[0])
    return m.group(1) if m else texte


def trouver(code=None, numero=None):
    """Lot (même annulé) correspondant au code du QR ou au numéro tapé ; None s'il est inconnu."""
    if code:
        return LotTrace.query.filter_by(code=code_lu(code)).first()
    if numero:
        return LotTrace.query.filter(db.func.upper(LotTrace.numero) == numero.strip().upper()).first()
    return None


def empreinte(code=None, numero=None, lot=None):
    """Empreinte du QR, pour compter les refus du même QR sans garder le code en clair."""
    texte = lot.code if lot is not None else (code_lu(code) if code else (numero or '').strip().upper())
    return hashlib.sha256(texte.encode('utf-8')).hexdigest()[:16]


# ── Contrôles (fonction 63) ─────────────────────────────────────────────

def mode(cle, defaut):
    v = str(parametres.obtenir(f'reception.controle_{cle}', defaut) or defaut).strip().upper()
    return v if v in MODES else defaut


def est_abattoir(operateur):
    return operateur is not None and operateur.type == TYPE_ABATTOIR


def bloquant(cle, defaut, operateur):
    m = mode(cle, defaut)
    return m == 'TOUS' or (m == 'ABATTOIR' and est_abattoir(operateur))


def reception_active(lot):
    return (Reception.query.filter(Reception.lot_id == lot.id, Reception.etat.in_(E.ACTIVES))
            .order_by(Reception.recu_le).first())


def refus_veterinaire(lot):
    return (Reception.query.filter(Reception.lot_id == lot.id, Reception.etat == E.REFUSEE,
                                   Reception.decision_par.isnot(None)).first())


def _heure(h):
    return h.astimezone().strftime('%d/%m/%Y à %H h %M') if h else '—'


def motif_refus(lot, operateur):
    """Pourquoi ce lot ne peut pas être reçu, en clair (None s'il peut l'être)."""
    from app.services import veto
    if lot is None:
        return 'QR inconnu : ce code ne correspond à aucun lot suivi par le programme.'
    if lot.annule:
        return f'Lot annulé par la ferme{" : " + lot.motif_annulation if lot.motif_annulation else ""}.'
    deja = reception_active(lot)
    if deja is not None:
        return f'Déjà reçu le {_heure(deja.recu_le)} par {deja.operateur.nom}.'
    refuse = refus_veterinaire(lot)
    if refuse is not None:
        return f'Lot refusé par le vétérinaire le {_heure(refuse.decision_le)}.'
    if lot.sortie.operateur_id != (operateur.id if operateur else None):
        dest = lot.sortie.operateur.nom if lot.sortie.operateur else (lot.sortie.destinataire_libre or 'un autre acheteur')
        return f'Ce lot est destiné à {dest}, pas à vous.'
    if veto.blocage_actif(lot.sortie.bande) is not None:
        return 'Ventes bloquées par le vétérinaire pour la bande de ce lot.'
    return None


def vaccins_manquants(bande, jour):
    """Vaccins du calendrier dont la date (au plus tard le jour de la sortie) est passée depuis au moins la
    tolérance, et qui ne sont pas faits. Ceux d'avant le début du suivi (rattrapage) ne comptent pas."""
    from app.services import sante
    tolerance = int(parametres.obtenir('reception.vaccin_tolerance_jours', 2))
    return [v for v in sante.vaccins_de_la_bande(bande, jour)
            if v['etat'] not in ('fait', 'avant_suivi') and (jour - v['prevu']).days >= tolerance]


def controles(lot, operateur, jour=None):
    """Liste ✓ / ✗ affichée à l'opérateur : [{'cle', 'libelle', 'ok', 'bloquant', 'detail'}]."""
    from app.services import sante, veto
    jour = jour or date.today()
    sortie = lot.sortie
    bande = sortie.bande
    deja = reception_active(lot) or refus_veterinaire(lot)
    liste = [
        {'cle': 'qr', 'libelle': 'QR connu et jamais reçu', 'ok': not lot.annule and deja is None,
         'bloquant': True, 'detail': None},
        {'cle': 'destinataire', 'libelle': 'Destiné à votre établissement',
         'ok': operateur is not None and sortie.operateur_id == operateur.id, 'bloquant': True, 'detail': None},
    ]
    for cle, libelle, defaut in REGLABLES:
        if cle == 'pesee':                 # ordre affiché : QR, destinataire, vaccins, délai, blocage, pesée
            liste.append({'cle': 'blocage', 'libelle': 'Bande non bloquée par le vétérinaire',
                          'ok': veto.blocage_actif(bande) is None, 'bloquant': True, 'detail': None})
        if mode(cle, defaut) == 'NON':
            continue
        if cle == 'delai_attente':
            fin = sante.fin_delai_attente(bande, jour)
            ok, detail = fin is None, (f"Délai d'attente du traitement jusqu'au {fin:%d/%m/%Y}" if fin else None)
        elif cle == 'vaccins':
            manquants = vaccins_manquants(bande, sortie.date)
            ok = not manquants
            detail = ('Pas fait : ' + ', '.join(f"{v['calendrier'].produit.nom} (prévu le {v['prevu']:%d/%m})"
                                                for v in manquants)) if manquants else None
        else:
            max_jours = int(parametres.obtenir('reception.pesee_max_jours', 7))
            derniere = max((p.date for p in bande.pesees if p.date <= sortie.date), default=None)
            ok = derniere is not None and (sortie.date - derniere).days < max_jours
            detail = (f'Dernière pesée le {derniere:%d/%m/%Y}' if derniere else 'Aucune pesée') if not ok else None
        liste.append({'cle': cle, 'libelle': libelle, 'ok': ok, 'bloquant': bloquant(cle, defaut, operateur),
                      'detail': detail})
    return liste


def examiner(lot, operateur, jour=None):
    """Résultat d'un scan : couleur (VERT, ORANGE, ROUGE), motif du refus, contrôles, bloquants manquants."""
    refus = motif_refus(lot, operateur)
    if refus:
        return {'couleur': R.ROUGE, 'refus': refus, 'controles': controles(lot, operateur, jour) if lot else [],
                'manquants': []}
    liste = controles(lot, operateur, jour)
    manquants = [c for c in liste if c['bloquant'] and not c['ok']]
    return {'couleur': R.ORANGE if manquants else R.VERT, 'refus': None, 'controles': liste, 'manquants': manquants}


# ── Journal des scans ───────────────────────────────────────────────────

def noter_scan(lot, operateur, user, source, resultat, motif=None, code=None, numero=None):
    """Chaque scan, accepté ou refusé : une ligne de scan et une ligne au journal (qui, quand, QR, résultat,
    motif). Trop de refus du même QR alertent la DGE. L'appelant valide la transaction."""
    s = Scan(horodatage=maintenant(), utilisateur_id=user.id, operateur_id=operateur.id if operateur else None,
             lot_id=lot.id if lot else None, empreinte=empreinte(code, numero, lot),
             saisie=(numero or '').strip()[:60] or None, source=source if source in SOURCES else 'CAMERA',
             resultat=resultat, motif=motif)
    db.session.add(s)
    quoi = f'lot {lot.numero}' if lot else f'« {(numero or "")[:40]} »' if numero else 'QR inconnu'
    enregistrer(Action.SCAN, table='lot_trace', enregistrement_id=lot.id if lot else None,
                detail=f'{operateur.nom if operateur else "—"} : {quoi} — {R.LIBELLES[resultat]}'
                       f'{" — " + motif if motif else ""}')
    if resultat == R.ROUGE:
        _alerte_refus_repetes(s, lot)
    db.session.flush()
    return s


def _alerte_refus_repetes(scan, lot):
    from app.models.hors_ligne import ConflitHorsLigne
    nombre = int(parametres.obtenir('reception.refus_alerte_nombre', 3))
    heures = int(parametres.obtenir('reception.refus_alerte_heures', 24))
    db.session.flush()
    refus = (Scan.query.filter(Scan.empreinte == scan.empreinte, Scan.resultat == R.ROUGE,
                               Scan.horodatage >= maintenant() - timedelta(hours=heures)).count())
    if refus != nombre:          # une seule alerte, au moment où le seuil est atteint
        return
    quoi = f'lot {lot.numero}' if lot else 'un QR inconnu'
    db.session.add(ConflitHorsLigne(
        ferme_id=lot.ferme_id if lot else None, quoi=f'{nombre} refus de scan : {quoi}'[:150],
        detail=f'Le même QR ({quoi}) a été refusé {nombre} fois en {heures} h à la réception '
               f'(dernier motif : {scan.motif}). À vérifier : tentative de revente, QR copié ou erreur de destinataire.'))


# ── Réception ───────────────────────────────────────────────────────────

def motifs_ecart():
    return [v for v, _ in ld_choices('motifs_ecart_quai')]


def _entier(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        n = int(str(v).strip())
    except ValueError:
        raise RegleReception('Tapez des nombres entiers.')
    if n < 0:
        raise RegleReception('Un nombre ne peut pas être négatif.')
    return n


def _poids(v):
    if v is None or str(v).strip() == '':
        return None
    try:
        p = float(str(v).strip().replace(',', '.').replace(' ', ''))
    except ValueError:
        raise RegleReception('Le poids total doit être un nombre (kg).')
    if p <= 0:
        raise RegleReception('Le poids total doit être positif.')
    return p


def seuil_morts():
    return float(parametres.obtenir('reception.seuil_morts_pct', 2))


def ecart_a_expliquer(annonce, vivants, morts):
    """Vrai si l'écart doit être expliqué : nombre différent de l'annoncé, ou morts au-delà du seuil."""
    if annonce is None:
        return False
    seuil = seuil_morts()
    return (annonce - vivants - morts) != 0 or (annonce and morts / annonce * 100 > seuil)


def recevoir(operateur, user, vivants, morts, poids, choix='valider', motif_ecart=None, explication=None,
             code=None, numero=None, hors_ligne=False):
    """Enregistre la réception d'un lot. En ligne, un lot refusé (rouge) ne peut pas être reçu : erreur.
    Reçue sans réseau, la réception est contrôlée à l'arrivée : refusée ou sous réserve d'elle-même, et
    l'opérateur le voit dans « À traiter ». L'appelant valide la transaction."""
    if user.profil != Profil.OPERATEUR or operateur is None:
        raise RegleReception('Seul un compte opérateur rattaché à un établissement reçoit des lots.')
    lot = trouver(code, numero)
    examen = examiner(lot, operateur)
    if hors_ligne:
        noter_scan(lot, operateur, user, 'HORS_LIGNE', examen['couleur'], examen['refus'], code, numero)
    if choix == 'refuser':
        if examen['couleur'] == R.ROUGE:
            raise RegleReception(examen['refus'])
        r = _nouvelle(lot, operateur, examen, E.REFUSEE, numero, hors_ligne)
        manque = '; '.join(c['libelle'] + (f" ({c['detail']})" if c['detail'] else '') for c in examen['manquants'])
        r.motif_refus = f'Refusé au quai : {manque}' if manque else "Refusé au quai par l'opérateur."
        _prevenir_agent(r, f'Lot {lot.numero} refusé à la réception', r.motif_refus)
        db.session.flush()
        return r
    vivants, morts, poids = _entier(vivants), _entier(morts), _poids(poids)
    if examen['couleur'] == R.ROUGE:
        if not hors_ligne:
            raise RegleReception(examen['refus'])
        r = _nouvelle(lot, operateur, examen, E.REFUSEE, numero, hors_ligne)
        r.vivants, r.morts, r.poids_kg, r.motif_refus = vivants, morts, poids, examen['refus']
        db.session.flush()
        return r
    if vivants is None or morts is None:
        raise RegleReception("Tapez le nombre de poulets vivants et de morts (« 0 » s'il n'y a pas de mort).")
    if poids is None:
        raise RegleReception('Tapez le poids total (kg).')
    if vivants + morts == 0:
        raise RegleReception('Aucun poulet compté : refusez le lot plutôt.')
    annonce = lot.sortie.nombre
    a_expliquer = ecart_a_expliquer(annonce, vivants, morts)
    motif_ecart = (motif_ecart or '').strip() or None
    explication = (explication or '').strip() or None
    if a_expliquer and not hors_ligne:
        if motif_ecart not in motifs_ecart():
            raise RegleReception("Il y a un écart avec l'annoncé : touchez la raison.")
        if motif_ecart == MOTIF_AUTRE and not explication:
            raise RegleReception('« Autre » : expliquez en quelques mots.')
    etat = E.SOUS_RESERVE if examen['manquants'] else E.VALIDEE
    r = _nouvelle(lot, operateur, examen, etat, numero, hors_ligne)
    r.vivants, r.morts, r.poids_kg = vivants, morts, poids
    r.motif_ecart = motif_ecart if a_expliquer else None
    r.explication = explication if a_expliquer else None
    db.session.flush()
    if a_expliquer:
        _alertes_ecart(r)
    return r


def _nouvelle(lot, operateur, examen, etat, numero, hors_ligne):
    r = Reception(lot_id=lot.id if lot else None, ferme_id=lot.ferme_id if lot else None, operateur_id=operateur.id,
                  recu_le=maintenant(), lot_saisi=lot.numero if lot else ((numero or '').strip()[:60] or 'QR inconnu'),
                  annonce=lot.sortie.nombre if lot else None, annonce_kg=lot.sortie.poids_total_kg if lot else None,
                  etat=etat, controles=examen['controles'], hors_ligne=hors_ligne)
    if hors_ligne:
        from app.services import hors_ligne as hl
        r.recu_le = hl.saisi_le() or r.recu_le
    db.session.add(r)
    return r


def a_expliquer(r):
    return r.etat != E.REFUSEE and r.vivants is not None and ecart_a_expliquer(r.annonce, r.vivants, r.morts)


def explication_manquante(r):
    """Réception gardée sans réseau avec un écart non expliqué : à compléter par l'opérateur."""
    return a_expliquer(r) and (not r.motif_ecart or (r.motif_ecart == MOTIF_AUTRE and not r.explication))


def expliquer(r, motif_ecart, explication, user):
    if user.profil != Profil.OPERATEUR or r.operateur_id != user.operateur_id:
        raise RegleReception('Seul l\'établissement qui a reçu le lot explique son écart.')
    if not a_expliquer(r):
        raise RegleReception('Cette réception n\'a pas d\'écart à expliquer.')
    motif_ecart, explication = (motif_ecart or '').strip(), (explication or '').strip()
    if motif_ecart not in motifs_ecart():
        raise RegleReception('Touchez la raison de l\'écart.')
    if motif_ecart == MOTIF_AUTRE and not explication:
        raise RegleReception('« Autre » : expliquez en quelques mots.')
    r.motif_ecart, r.explication = motif_ecart, explication or None
    # Les alertes sont parties à la réception ; le message de l'agent et de la DGE reçoit la raison
    from app.models.hors_ligne import ConflitHorsLigne
    for c in ConflitHorsLigne.query.filter_by(objet_table='reception', objet_id=str(r.id)):
        c.detail = texte_ecart(r)


def texte_ecart(r):
    morts = f'{r.morts} mort{"s" if r.morts > 1 else ""} à l\'arrivée ({r.morts_pct:.1f} %)'.replace('.', ',')
    ecart = r.ecart
    nombre = (f'{ecart} poulet{"s" if abs(ecart) > 1 else ""} en {"moins" if ecart > 0 else "trop"}'
              if ecart else 'nombre conforme')
    raison = (r.motif_ecart or 'raison pas encore donnée') + (f' — {r.explication}' if r.explication else '')
    return (f'Annoncé {r.annonce}, reçus vivants {r.vivants}, {morts} ; {nombre}. '
            f'Raison : {raison}. Reçu par {r.operateur.nom} le {_heure(r.recu_le)}.')


def _prevenir_agent(r, quoi, detail):
    """Message visible de l'agent de la ferme (Saisies à vérifier) et de la DGE (Arbitrages)."""
    from app.models.hors_ligne import ConflitHorsLigne
    db.session.add(ConflitHorsLigne(ferme_id=r.ferme_id, bande_id=r.lot.sortie.bande_id if r.lot else None,
                                    quoi=quoi[:150], detail=detail, objet_table='reception', objet_id=str(r.id)))


def _alertes_ecart(r):
    """Écart à la réception : l'agent et la DGE sont prévenus ; au-delà du seuil de morts, le vétérinaire de la
    zone aussi (signalement), quel que soit le motif."""
    from app.models.sante import OrigineAlerte
    from app.services import sante
    _prevenir_agent(r, f'Écart à la réception du lot {r.lot.numero}', texte_ecart(r))
    seuil = float(parametres.obtenir('reception.seuil_morts_pct', 2))
    if r.morts_pct is not None and r.morts_pct > seuil:
        sante._nouvelle_alerte(r.ferme, r.lot.sortie.bande, OrigineAlerte.RECEPTION,
                               commentaire=f'Lot {r.lot.numero} : {texte_ecart(r)}')


# ── Décision du vétérinaire (réception sous réserve) ────────────────────

def peut_decider(user, r):
    from app.utils.permissions import filtre_perimetre
    return (user.profil == Profil.VETO and r.etat == E.SOUS_RESERVE
            and filtre_perimetre(Reception.query, utilisateur=user).filter(Reception.id == r.id).first() is not None)


def decider(r, liberer, motif, user):
    """Seul le vétérinaire de la zone libère ou refuse un lot reçu sous réserve ; motif obligatoire."""
    if user.profil != Profil.VETO:
        raise RegleReception('Seul le vétérinaire décide d\'un lot reçu sous réserve.')
    if r.etat != E.SOUS_RESERVE:
        raise RegleReception('Ce lot n\'attend pas de décision.')
    if not peut_decider(user, r):
        raise RegleReception('Ce lot ne vient pas de votre zone.')
    if not (motif or '').strip():
        raise RegleReception('Indiquez le motif de la décision.')
    r.etat = E.VALIDEE if liberer else E.REFUSEE
    r.decision_par, r.decision_le, r.decision_motif = user.id, maintenant(), motif.strip()[:500]
    r.vu_le = None                         # l'opérateur voit la décision dans « À traiter »
    if not liberer:
        r.motif_refus = f'Refusé par le vétérinaire : {r.decision_motif}'
    enregistrer(Action.DECISION_RECEPTION, table='reception', enregistrement_id=r.id,
                detail=f'Lot {r.lot.numero} reçu par {r.operateur.nom} : '
                       f'{"libéré" if liberer else "refusé"} par {user.nom_complet} — {r.decision_motif}')


def sous_reserve_visibles(user):
    from app.utils.permissions import filtre_perimetre
    return (filtre_perimetre(Reception.query, utilisateur=user).filter(Reception.etat == E.SOUS_RESERVE)
            .order_by(Reception.recu_le))


# ── Écrans de l'opérateur ───────────────────────────────────────────────

def attendus(operateur, jours=None):
    """Lots destinés à cet opérateur, pas encore reçus (ni refusés par le vétérinaire), non annulés.
    `jours` : seulement ceux sortis depuis ce nombre de jours (« cette semaine »)."""
    from app.models.bande import Sortie
    q = (LotTrace.query.join(Sortie, LotTrace.sortie_id == Sortie.id)
         .filter(Sortie.operateur_id == operateur.id, LotTrace.annule.is_(False)))
    if jours is not None:
        q = q.filter(Sortie.date >= date.today() - timedelta(days=jours))
    pris = db.select(Reception.lot_id).where(Reception.lot_id.isnot(None), db.or_(
        Reception.etat.in_(E.ACTIVES), Reception.decision_par.isnot(None)))
    return q.filter(LotTrace.id.notin_(pris)).order_by(Sortie.date.desc(), LotTrace.numero).all()


def a_traiter(operateur):
    """Réceptions sous réserve, et résultats pas encore vus : décision du vétérinaire, réception refusée ou
    écart à expliquer après un envoi sans réseau."""
    rs = (Reception.query.filter(Reception.operateur_id == operateur.id)
          .filter(db.or_(Reception.etat == E.SOUS_RESERVE, Reception.vu_le.is_(None)))
          .order_by(Reception.recu_le.desc()).all())
    return [r for r in rs if r.etat == E.SOUS_RESERVE or explication_manquante(r)
            or (r.vu_le is None and (r.hors_ligne or r.decision_par is not None))]


def marquer_vu(r):
    if r.etat != E.SOUS_RESERVE and not explication_manquante(r):
        r.vu_le = maintenant()


# ── Ce que voient l'éleveur et le public ────────────────────────────────

def derniere_reception(lot):
    if lot is None:
        return None
    rs = [r for r in lot.receptions if r.etat in E.ACTIVES or r.decision_par is not None]
    return rs[-1] if rs else None


def nom_du_type(operateur):
    """« l'abattoir », « le marché », « l'acheteur », « le distributeur »."""
    t = (operateur.type or '').strip().lower()
    return {'abattoir': "l'abattoir", 'marché': 'le marché', 'acheteur': "l'acheteur",
            'distributeur': 'le distributeur'}.get(t, "l'acheteur")


def etat_pour_eleveur(sortie):
    """Phrase simple pour l'éleveur, ou None (pas de lot, ou lot pas destiné à un opérateur du registre)."""
    lot = getattr(sortie, 'lot', None)
    if lot is None or sortie.operateur is None:
        return None
    r = derniere_reception(lot)
    qui = nom_du_type(sortie.operateur)
    if r is None:
        return {'etape': 'parti', 'texte': '✓ Partis'}
    if r.etat == E.SOUS_RESERVE:
        return {'etape': 'attente', 'texte': '◷ En attente du vétérinaire'}
    if r.etat == E.REFUSEE:
        return {'etape': 'refuse', 'texte': "✗ Le vétérinaire n'a pas accepté ces poulets — appelez votre agent"}
    morts = f' et {r.morts} mort{"s" if r.morts > 1 else ""} au transport' if r.morts else ''
    return {'etape': 'recu', 'texte': f'✓ Reçus par {qui}',
            'compte': f'{qui[0].upper() + qui[1:]} a compté {r.vivants} vivants{morts}'}


def etape_publique(lot):
    """Étape « Reçus à l'abattoir » de la page publique : seulement quand le lot est reçu ET validé."""
    r = derniere_reception(lot)
    if r is None or r.etat != E.VALIDEE:
        return None
    qui = nom_du_type(r.operateur)
    lieu = {"l'abattoir": "à l'abattoir", 'le marché': 'au marché'}.get(qui, f'par {qui}')
    return {'titre': f'Reçus {lieu}', 'date': r.recu_le, 'nom': r.operateur.nom}
