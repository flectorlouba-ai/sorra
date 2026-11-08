"""Règles des fermes : doublons, localités, droits, création, statut."""
import re
import unicodedata

from app import db
from app.models import Ferme, Localite, Profil, Batiment, FermeStatutHistorique
from app.models.base import maintenant
from app.services.numerotation import generer_numero, prochain_rang

STATUT_INITIAL = 'En préparation'
STATUT_SUSPENDUE = 'Suspendue'


# ── Comparaisons ────────────────────────────────────────────────────────

def normaliser_nom(texte):
    """« N'kok » → « nkok » : sans accents, majuscules, espaces ni ponctuation."""
    sans_accent = ''.join(c for c in unicodedata.normalize('NFKD', texte or '')
                          if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', sans_accent.lower())


def normaliser_telephone(texte):
    """Chiffres seuls, sans l'indicatif du Gabon ni le 0 initial."""
    chiffres = re.sub(r'\D', '', texte or '')
    for indicatif in ('00241', '241'):
        if chiffres.startswith(indicatif) and len(chiffres) > len(indicatif) + 6:
            chiffres = chiffres[len(indicatif):]
            break
    return chiffres.lstrip('0')


def _levenshtein(a, b):
    precedente = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        courante = [i]
        for j, cb in enumerate(b, 1):
            courante.append(min(precedente[j] + 1, courante[j - 1] + 1,
                                precedente[j - 1] + (ca != cb)))
        precedente = courante
    return precedente[-1]


def se_ressemblent(a, b):
    """Même nom à l'écriture près : N'kok / Nkok, Ntoum / Ntoun, Owendo / Owéndo."""
    na, nb = normaliser_nom(a), normaliser_nom(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    seuil = 1 if max(len(na), len(nb)) < 8 else 2
    return min(len(na), len(nb)) >= 4 and _levenshtein(na, nb) <= seuil


def localites_semblables(province_id, nom, sauf_id=None):
    return [l for l in Localite.query.filter_by(province_id=province_id).order_by(Localite.nom)
            if l.id != sauf_id and se_ressemblent(l.nom, nom)]


def localite_identique(province_id, nom):
    """Localité existante au même nom (à l'écriture près : majuscules, accents, apostrophes)."""
    cle = normaliser_nom(nom)
    return next((l for l in Localite.query.filter_by(province_id=province_id)
                 if normaliser_nom(l.nom) == cle), None)


# ── Doublons ────────────────────────────────────────────────────────────

def _designation(f):
    return f'{f.numero_metier} ({f.nom})'


def doublons(nom, telephone, localite_id, reference_ami=None, sauf_id=None):
    """Messages clairs pour chaque ferme existante en conflit (liste vide si aucun)."""
    messages = []
    autres = Ferme.query
    if sauf_id:
        autres = autres.filter(Ferme.id != sauf_id)
    if reference_ami:
        f = autres.filter(db.func.upper(Ferme.reference_ami) == reference_ami.strip().upper()).first()
        if f:
            messages.append(f'La référence AMI {reference_ami} est déjà celle de la ferme {_designation(f)}.')
    tel = normaliser_telephone(telephone)
    if tel:
        f = autres.filter(Ferme.telephone_normalise == tel).first()
        if f:
            messages.append(f'Ce téléphone est déjà celui de l\'exploitant de la ferme {_designation(f)}.')
    if localite_id and nom:
        cle = normaliser_nom(nom)
        f = next((f for f in autres.filter(Ferme.localite_id == localite_id)
                  if normaliser_nom(f.nom) == cle), None)
        if f:
            messages.append(f'Une ferme du même nom existe déjà dans cette localité : {_designation(f)}.')
    return messages


# ── Droits ──────────────────────────────────────────────────────────────

def peut_creer(user):
    return user.profil in (Profil.ADMIN, Profil.DGE, Profil.AGENT)


def peut_modifier(user, ferme):
    if user.profil in (Profil.ADMIN, Profil.DGE):
        return True
    return user.profil == Profil.AGENT and ferme.agent_id == user.id


def provinces_de_creation(user, toutes):
    """Provinces où l'utilisateur peut créer une ferme."""
    if user.profil == Profil.AGENT:
        return [p for p in toutes if p.id in user.province_ids]
    return toutes


# ── Écritures ───────────────────────────────────────────────────────────

def creer_ferme(province, auteur, **champs):
    ferme = Ferme(numero_metier=generer_numero('FERME', province.code, largeur=3),
                  province=province, statut=champs.pop('statut', None) or STATUT_INITIAL,
                  **champs)
    ferme.telephone_normalise = normaliser_telephone(ferme.exploitant_telephone)
    db.session.add(ferme)
    db.session.flush()
    ferme.historique.append(FermeStatutHistorique(statut=ferme.statut, date=maintenant(),
                                                  utilisateur_id=auteur.id if auteur else None))
    return ferme


def changer_statut(ferme, statut, auteur):
    if statut and statut != ferme.statut:
        ferme.statut = statut
        ferme.historique.append(FermeStatutHistorique(statut=statut, date=maintenant(),
                                                      utilisateur_id=auteur.id))


def ajouter_batiment(ferme, capacite, nom=None):
    rang = prochain_rang('BATIMENT', ferme.numero_metier)
    b = Batiment(ferme=ferme, rang=rang, code=f'B{rang}', nom=nom or None, capacite=capacite)
    db.session.add(b)
    return b


def creer_localite(province_id, nom, par_admin):
    loc = Localite(province_id=province_id, nom=nom.strip(), actif=True, a_verifier=not par_admin)
    db.session.add(loc)
    db.session.flush()
    return loc
