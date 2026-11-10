"""Socle de sécurité (lot 15) : double authentification TOTP (RFC 6238, sans bibliothèque externe),
codes de secours à usage unique, sessions enregistrées."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
import uuid
from urllib.parse import quote

from flask import current_app, request
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.models.securite import SessionUtilisateur
from app.services import parametres

PAS = 30
CHIFFRES = 6
NB_CODES_SECOURS = 8
PILOTAGE_SANS_EXPIRATION = (Profil.ELEVEUR, Profil.AGENT)   # jamais de déconnexion automatique


# ── Double authentification ─────────────────────────────────────────────

def active_sur_ce_serveur():
    """Interrupteur YL2_2FA : actif en production ; coupé seulement en local et en démo."""
    return bool(current_app.config.get('DEUX_FACTEURS'))


def profils_obligatoires():
    texte = parametres.obtenir('securite.profils_2fa', 'ADMIN,DGE,MAEDR,BCEG,AUDITEUR') or ''
    return {p.strip().upper() for p in texte.split(',') if p.strip()} - {'ELEVEUR'}


def obligatoire(user):
    return user.profil != Profil.ELEVEUR and user.profil.value in profils_obligatoires()


def possible(user):
    return user.profil != Profil.ELEVEUR


def a_demander(user):
    """Faut-il un second facteur à la connexion ? (activée, ou obligatoire pour ce profil)."""
    return active_sur_ce_serveur() and possible(user) and (user.totp_active or obligatoire(user))


def nouveau_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _code(secret, compteur):
    cle = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    h = hmac.new(cle, struct.pack('>Q', compteur), hashlib.sha1).digest()
    o = h[-1] & 0x0F
    n = (struct.unpack('>I', h[o:o + 4])[0] & 0x7FFFFFFF) % (10 ** CHIFFRES)
    return f'{n:0{CHIFFRES}d}'


def code_actuel(secret, instant=None):
    return _code(secret, int((instant or time.time()) // PAS))


def verifier_code(secret, saisi, instant=None):
    """Code à 6 chiffres, toléré sur la période précédente et la suivante (décalage d'horloge)."""
    saisi = ''.join(c for c in (saisi or '') if c.isdigit())
    if not secret or len(saisi) != CHIFFRES:
        return False
    t = int((instant or time.time()) // PAS)
    return any(hmac.compare_digest(_code(secret, t + d), saisi) for d in (-1, 0, 1))


def adresse_otpauth(user, secret):
    return (f'otpauth://totp/SORRA:{quote(user.identifiant)}?secret={secret}&issuer=SORRA'
            f'&digits={CHIFFRES}&period={PAS}')


def qr_svg(texte):
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics import renderSVG
    w = QrCodeWidget(texte, barLevel='M', barBorder=2)
    x1, y1, x2, y2 = w.getBounds()
    d = Drawing(200, 200, transform=[200 / (x2 - x1), 0, 0, 200 / (y2 - y1), 0, 0])
    d.add(w)
    # En image (data URI) : le SVG de reportlab porte un prologue XML qui ne doit pas entrer dans la page
    import base64
    return 'data:image/svg+xml;base64,' + base64.b64encode(renderSVG.drawToString(d).encode('utf-8')).decode('ascii')


def nouveaux_codes_secours(user):
    """8 codes « 1234-5678 », montrés UNE fois ; seules leurs empreintes sont gardées."""
    codes = [f'{secrets.randbelow(10**4):04d}-{secrets.randbelow(10**4):04d}' for _ in range(NB_CODES_SECOURS)]
    user.codes_secours = [generate_password_hash(c) for c in codes]
    return codes


def utiliser_code_secours(user, saisi):
    saisi = (saisi or '').strip()
    restants = list(user.codes_secours or [])
    for i, h in enumerate(restants):
        if check_password_hash(h, saisi):
            del restants[i]
            user.codes_secours = restants          # usage unique
            return True
    return False


def reinitialiser(user):
    user.totp_secret, user.totp_active, user.codes_secours = None, False, None


# ── Sessions ────────────────────────────────────────────────────────────

def _appareil():
    ua = request.headers.get('User-Agent', '')[:300]
    systeme = next((s for s in ('Android', 'iPhone', 'Windows', 'Mac OS', 'Linux') if s in ua), 'Appareil')
    nav = next((n for n in ('Edg', 'Chrome', 'Firefox', 'Safari') if n in ua), 'navigateur')
    return f'{systeme} · {"Edge" if nav == "Edg" else nav}'


def ouvrir(user):
    s = SessionUtilisateur(id=str(uuid.uuid4()), utilisateur_id=user.id, appareil=_appareil(),
                           adresse_ip=request.remote_addr)
    db.session.add(s)
    return s


def fermer(sid, par=None, motif=None):
    s = db.session.get(SessionUtilisateur, sid) if sid else None
    if s is not None and s.fermee_le is None:
        s.fermee_le, s.fermee_par, s.motif_fermeture = maintenant(), par.id if par else None, motif
    return s


def ouvertes(utilisateur_id=None):
    q = SessionUtilisateur.query.filter(SessionUtilisateur.fermee_le.is_(None))
    if utilisateur_id is not None:
        q = q.filter(SessionUtilisateur.utilisateur_id == utilisateur_id)
    return q.order_by(SessionUtilisateur.derniere_activite.desc())


def expire_par_inactivite(user):
    return user.profil not in PILOTAGE_SANS_EXPIRATION


# ── Lot S : limite de débit sur la connexion ───────────────────────────
import os as _os
import time as _time
from collections import deque as _deque

_TENTATIVES = {}            # adresse → horodatages des tentatives (par processus ; suffisant pour freiner une attaque)
LIMITE_TENTATIVES, LIMITE_FENETRE_S = 30, 600


def connexion_trop_frequente(adresse):
    """Vrai si plus de LIMITE_TENTATIVES tentatives de connexion depuis cette adresse en LIMITE_FENETRE_S secondes."""
    now = _time.time()
    d = _TENTATIVES.setdefault(adresse or '?', _deque())
    while d and now - d[0] > LIMITE_FENETRE_S:
        d.popleft()
    d.append(now)
    return len(d) > LIMITE_TENTATIVES


def oublier_tentatives():
    _TENTATIVES.clear()


# ── Lot S : mots de passe courants ───────────────────────────────────────
_COURANTS = None


def mot_de_passe_courant(mdp):
    """Vrai si le mot de passe figure dans la liste des mots de passe les plus courants (app/utils/mots_de_passe_courants.txt)
    ou s'il est trop simple (un seul caractère répété, suite de chiffres)."""
    global _COURANTS
    if _COURANTS is None:
        chemin = _os.path.join(_os.path.dirname(__file__), '..', 'utils', 'mots_de_passe_courants.txt')
        try:
            _COURANTS = {l.strip().lower() for l in open(chemin, encoding='utf-8') if l.strip()}
        except OSError:
            _COURANTS = set()
    m = (mdp or '').strip().lower()
    if m in _COURANTS or m.replace(' ', '') in _COURANTS:
        return True
    if len(set(m)) <= 2 or m.isdigit() and m in '01234567890123456789' * 2:
        return True
    return False


# ── Lot S : appareil inconnu ─────────────────────────────────────────────

def appareil_inconnu(user):
    """Vrai si ce compte n'a jamais ouvert de session depuis un appareil de ce type (système · navigateur)."""
    a = _appareil()
    return not SessionUtilisateur.query.filter(SessionUtilisateur.utilisateur_id == user.id, SessionUtilisateur.appareil == a).first()
