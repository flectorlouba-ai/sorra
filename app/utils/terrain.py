"""Espace TERRAIN (lot 19 ter) : qui a le style « illustré doux », et ce que montre son en-tête.

- éleveur : toujours ;
- agent : sauf s'il a choisi « Version bureau » (sur ordinateur ; retour par « Version terrain ») ;
- opérateur (abattoir, marché, acheteur, distributeur) : toujours.
Les autres profils (DGE, ADMIN, AUDITEUR, MAEDR, BCEG, VETO) restent en BUREAU (charte YL.1).
"""
from flask import has_request_context, request, session

from app.models.utilisateur import Profil

CLE_BUREAU = 'version_bureau'
PREFIXES = {'agent': 'ag_', 'operateur': 'op_'}
# Écrans de pilotage de l'agent (tableaux, fiches détaillées) : toujours au style BUREAU, même ouverts depuis
# l'espace terrain (« Ses chiffres », lien de la tournée gardée…). Rien n'est supprimé.
ECRANS_BUREAU_AGENT = {'agent.tournee', 'fermes.liste', 'fermes.fiche', 'bandes.fiche', 'bandes.liste', 'operateurs.liste',
                       'operateurs.fiche', 'livraisons.liste', 'livraisons.nouvelle', 'livraisons.fiche', 'sante.vaccins',
                       'pilotage.tableau', 'pilotage.carte', 'tracabilite.lots', 'tracabilite.lot', 'agent.commandes'}


def profil_terrain(user):
    """'eleveur', 'agent', 'operateur' ou None (style bureau)."""
    if not user or not user.is_authenticated:
        return None
    if user.profil not in (Profil.ELEVEUR, Profil.OPERATEUR, Profil.AGENT):
        return None
    if has_request_context():
        if session.get(CLE_BUREAU) or (request.endpoint or '').startswith('bureau.'):   # lot R : version ordinateur
            return None
        if user.profil == Profil.AGENT and request.endpoint in ECRANS_BUREAU_AGENT:
            return None
    return {Profil.ELEVEUR: 'eleveur', Profil.OPERATEUR: 'operateur', Profil.AGENT: 'agent'}[user.profil]


def cle_aide(profil, cle):
    """Clé de l'aide « Comment faire ? » pour ce profil : l'éleveur garde les siennes, l'agent et
    l'opérateur ont les leurs (ag_…, op_…), même sur un écran commun avec l'éleveur."""
    if not profil or not cle:
        return ''
    prefixe = PREFIXES.get(profil, '')
    if profil == 'eleveur':
        return '' if cle.startswith(tuple(PREFIXES.values())) else cle
    return cle if cle.startswith(prefixe) else prefixe + cle


def aide_pour(profil, cle):
    from app.models.aide import Aide
    c = cle_aide(profil, cle)
    return c if c and Aide.query.filter_by(cle=c, actif=True).first() is not None else ''


def profil_de_l_aide(cle):
    for profil, prefixe in PREFIXES.items():
        if cle.startswith(prefixe):
            return profil
    return 'eleveur'


def entete(user, profil):
    """Sous-titre de l'en-tête terrain : « Bonjour Paul · Estuaire · 14 fermes » (agent), le nom de
    l'établissement (opérateur). L'éleveur garde « Bonjour {Prénom} ! 👋 » (gabarit)."""
    if profil == 'agent':
        from app.models import Ferme
        n = Ferme.query.filter_by(agent_id=user.id).count()
        morceaux = [f'Bonjour {user.prenom or user.nom}'] + [p.nom for p in user.provinces[:2]]
        morceaux.append(f'{n} ferme{"s" if n > 1 else ""}')
        return ' · '.join(morceaux)
    if profil == 'operateur':
        return user.operateur.nom if user.operateur else 'Établissement à rattacher'
    return ''
