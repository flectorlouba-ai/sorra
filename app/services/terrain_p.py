"""Lot P — code PIN du terrain, file de synchronisation (envois hors ligne), guides PDF par profil."""
import io
import re
from datetime import date, timedelta

from app import db
from app.models import Profil, Utilisateur
from app.models.hors_ligne import EnvoiHorsLigne
from app.services.journal import enregistrer, Action

PROFILS_PIN = (Profil.ELEVEUR, Profil.AGENT, Profil.OPERATEUR)
PIN_ECHECS_MAX = 5


class ReglePin(Exception):
    pass


def regler_pin(user, pin, confirmation, mot_de_passe):
    if user.profil not in PROFILS_PIN:
        raise ReglePin('Le code est réservé aux comptes du terrain.')
    if not user.check_password(mot_de_passe or ''):
        raise ReglePin('Le mot de passe est incorrect.')
    if not re.fullmatch(r'\d{4,6}', pin or ''):
        raise ReglePin('Le code est fait de 4 à 6 chiffres.')
    if pin != confirmation:
        raise ReglePin('Les deux codes ne sont pas les mêmes.')
    if len(set(pin)) == 1 or pin in '0123456789' or pin in '9876543210':
        raise ReglePin('Ce code est trop simple (chiffres identiques ou qui se suivent).')
    user.set_pin(pin)
    enregistrer(Action.CHANGEMENT_MDP, utilisateur=user, detail='Code du terrain réglé')


def retirer_pin(user):
    user.pin_hash, user.pin_echecs = None, 0
    enregistrer(Action.CHANGEMENT_MDP, utilisateur=user, detail='Code du terrain retiré')


def verifier_pin(identifiant, pin):
    """L'utilisateur si le code est bon ; None sinon (échecs comptés, code coupé après PIN_ECHECS_MAX)."""
    user = Utilisateur.query.filter_by(identifiant=(identifiant or '').strip().lower()).first()
    if user is None or not user.actif or user.profil not in PROFILS_PIN or not user.pin_hash:
        return None
    if user.pin_echecs >= PIN_ECHECS_MAX:
        return None
    if user.check_pin(pin):
        user.pin_echecs = 0
        return user
    user.pin_echecs += 1
    if user.pin_echecs >= PIN_ECHECS_MAX:
        enregistrer(Action.BLOCAGE, utilisateur=user, detail='Code du terrain coupé après 5 échecs : mot de passe obligatoire')
    return None


# ── File de synchronisation ───────────────────────────────────────────────

def file_synchronisation(limite=300):
    envois = EnvoiHorsLigne.query.order_by(EnvoiHorsLigne.recu_le.desc()).limit(limite).all()
    lignes = []
    for e in envois:
        delai = None
        if e.saisi_le and e.recu_le:
            s, r = e.saisi_le, e.recu_le
            if (s.tzinfo is None) != (r.tzinfo is None):
                s, r = s.replace(tzinfo=None), r.replace(tzinfo=None)
            delai = max(0, (r - s).total_seconds() / 3600)
        lignes.append({'envoi': e, 'delai_h': delai})
    semaine = date.today() - timedelta(days=7)
    recents = [l for l in lignes if l['envoi'].recu_le and l['envoi'].recu_le.date() >= semaine]
    delais = [l['delai_h'] for l in recents if l['delai_h'] is not None]
    return {'lignes': lignes, 'n_semaine': len(recents), 'delai_moyen_h': (sum(delais) / len(delais)) if delais else None,
            'appareils': len({l['envoi'].appareil_id for l in recents if l['envoi'].appareil_id}),
            'en_retard': sum(1 for l in recents if (l['delai_h'] or 0) > 48)}


# ── Guides PDF par profil ─────────────────────────────────────────────────

def guide_pdf(profil):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Spacer, ListFlowable, ListItem, PageBreak
    from app.models.aide import Aide
    from app.services.bureau import FONCTIONS
    from app.services.rapports_pdf import _document, TITRE, SOUS, SECTION, TEXTE
    from app.utils import terrain
    p = Profil(profil) if not isinstance(profil, Profil) else profil
    t = {Profil.ELEVEUR: 'eleveur', Profil.AGENT: 'agent', Profil.OPERATEUR: 'operateur'}.get(p)
    aides = [a for a in Aide.query.filter_by(actif=True).order_by(Aide.ordre) if t and terrain.profil_de_l_aide(a.cle) == t]
    el = [Paragraph(f'Guide SORRA — {p.libelle}', TITRE),
          Paragraph('Ce guide reprend, écran par écran, ce que vous pouvez faire dans SORRA et comment. '
                    + ('Sur le téléphone : 3 touchers au plus, une case vide n\'est jamais un zéro, tout marche sans réseau et part dès qu\'il revient.' if t else
                       'Sur l\'ordinateur : à gauche vos fonctions, à droite les indicateurs, la carte et les tableaux ; chaque tableau s\'imprime et s\'exporte.'), TEXTE),
          Spacer(1, 0.4 * cm)]
    if FONCTIONS.get(p):
        el.append(Paragraph('Vos fonctions (version ordinateur)', SECTION))
        el.append(ListFlowable([ListItem(Paragraph(f'{ico} <b>{nom}</b>' + (f' — bouton « {bt[0]} »' if bt else ''), TEXTE)) for _, ico, nom, _, _, bt, _ in FONCTIONS[p]],
                               bulletType='bullet'))
        el.append(Spacer(1, 0.3 * cm))
    if aides:
        el.append(Paragraph('Comment faire ? (téléphone)', SECTION))
        for a in aides:
            el.append(Paragraph(f'<b>{a.titre}</b>', TEXTE))
            el.append(ListFlowable([ListItem(Paragraph(e.get('texte', ''), TEXTE)) for e in (a.etapes or [])], bulletType='1'))
            el.append(Spacer(1, 0.2 * cm))
    el.append(Spacer(1, 0.4 * cm))
    el.append(Paragraph('Sécurité', SECTION))
    el.append(Paragraph('Votre mot de passe est personnel. ' + ('Vous pouvez régler un code de 4 à 6 chiffres (Moi → Mon code) pour entrer plus vite : après 5 erreurs, le mot de passe redevient obligatoire. ' if t else '')
                        + 'Archiver, jamais supprimer : tout reste consultable et inscrit au journal.', TEXTE))
    el.append(Paragraph(f'Édité le {date.today():%d/%m/%Y} · SORRA ne remplace ni votre agent ni le vétérinaire.', SOUS))
    return _document(el)
