"""Lot V — icônes du bureau : un petit jeu d'icônes SVG au trait, dessinées ici, aucune ressource externe.

`icone(nom)` renvoie le SVG inline (24 × 24, trait courant, `currentColor`). Les émojis des fonctions
(services/bureau.FONCTIONS) et des titres sont traduits par EMOJIS ; un émoji inconnu est rendu tel quel.
"""
from markupsafe import Markup, escape

# nom → chemins SVG (viewBox 0 0 24 24, stroke 2, sans remplissage)
ICONES = {
    'tableau-de-bord': 'M3 3v18h18M7 14v4M11 10v8M15 6v12M19 12v6',
    'carte': 'M9 18l-6 3V6l6-3 6 3 6-3v15l-6 3-6-3zM9 3v15M15 6v15',
    'camion': 'M1 7h12v9H1zM13 11h5l3 3v2h-8zM5.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM17.5 19a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3z',
    'panier': 'M3 4h2l2.5 11h11L21 7H7M9 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM17 20a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
    'balance': 'M12 3v18M5 21h14M12 6l6 2M12 6L6 8M3 14l3-6 3 6a3 3 0 0 1-6 0zM15 14l3-6 3 6a3 3 0 0 1-6 0z',
    'trophee': 'M8 4h8v5a4 4 0 0 1-8 0zM8 6H5a3 3 0 0 0 3 4M16 6h3a3 3 0 0 1-3 4M12 13v4M8 21h8M9 17h6',
    'rapport': 'M6 2h8l5 5v15H6zM14 2v5h5M9 13h6M9 17h6M9 9h2',
    'cible': 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
    'sante': 'M5 3v6a7 7 0 0 0 14 0V3M9 3h2M3 3h2M15 3h4M12 16v2a3 3 0 0 0 6 0v-2M18 16a2 2 0 1 0 0-4 2 2 0 0 0 0 4',
    'courrier': 'M3 5h18v14H3zM3 6l9 7 9-7',
    'curseurs': 'M4 6h10M18 6h2M4 12h2M10 12h10M4 18h12M20 18h0M14 4v4M6 10v4M16 16v4',
    'calendrier': 'M4 5h16v16H4zM4 10h16M8 3v4M16 3v4',
    'utilisateurs': 'M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM2 21a7 7 0 0 1 14 0M16 3.5a4 4 0 0 1 0 7.5M22 21a7 7 0 0 0-5-6.7',
    'parametres': 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z',
    'journal': 'M4 3h13l3 3v15H4zM8 8h8M8 12h8M8 16h5',
    'cadenas': 'M5 11h14v10H5zM8 11V7a4 4 0 0 1 8 0v4M12 15v2',
    'cle': 'M14 3a6 6 0 1 0 3.5 10.9L21 17.4V21h-3.6l-.9-.9v-2h-2l-1.5-1.5A6 6 0 0 0 14 3zM15 8h.01',
    'bouclier': 'M12 2l8 3v7c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V5z',
    'loupe': 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5',
    'oeil': 'M2 12s4-7 10-7 10 7 10 7-4 7-10 7-10-7-10-7zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
    'argent': 'M3 7h18v10H3zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM6 10h.01M18 14h.01',
    'maison': 'M3 11l9-8 9 8M5 10v11h14V10M10 21v-6h4v6',
    'maisons': 'M2 11l5-4 5 4v9H2zM12 11l5-4 5 4v9h-10M6 20v-4h2v4M16 20v-4h2v4',
    'batiment': 'M4 21V7l6-3v17M10 21V11l10-4v14M4 21h18M7 9h.01M7 13h.01M7 17h.01M14 13h.01M14 17h.01M17 11h.01M17 15h.01',
    'usine': 'M3 21V9l5 3V9l5 3V9l5 3v9zM3 21h18M7 17h2M11 17h2M15 17h2M15 9V4h3v6',
    'banque': 'M3 10l9-6 9 6M4 10h16M6 10v8M10 10v8M14 10v8M18 10v8M3 21h18M3 18h18',
    'colis': 'M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10M7.5 5l9 4',
    'photo': 'M3 8h4l2-3h6l2 3h4v12H3zM12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
    'lien': 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
    'microscope': 'M6 18h8M3 21h18M12 18a6 6 0 0 0 6-6v-2M10 2h3l1 1-5 9-3-1zM9 14l2 1',
    'voiture': 'M3 13l2-5h14l2 5v5H3zM3 13h18M7 21v-3M17 21v-3M7 16h.01M17 16h.01',
    'stop': 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM5.6 5.6l12.8 12.8',
    'plus': 'M12 5v14M5 12h14',
    'telecharger': 'M12 3v12M6 11l6 6 6-6M4 21h16',
    'crayon': 'M4 20l4-1L19 8l-3-3L5 16zM14 7l3 3',
    'liste': 'M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01',
    'presse-papiers': 'M8 4h8v3H8zM8 5H5v16h14V5h-3M9 12h6M9 16h4',
    'poulet': 'M15 4a3 3 0 0 1 3 3v2l3 1-3 1v2a6 6 0 0 1-6 6H8a4 4 0 0 1-4-4v-1a5 5 0 0 1 5-5h3l1-3a2 2 0 0 1 2-2zM9 19v2M13 19v2M20 10h.01',
    'aide': 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01',
    'guide': 'M4 4h7a3 3 0 0 1 3 3v13a2 2 0 0 0-2-2H4zM20 4h-7a3 3 0 0 0-3 3v13a2 2 0 0 1 2-2h8z',
    'telephone': 'M7 2h10v20H7zM11 18h2',
    'cloche': 'M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 21h4',
    'sortie': 'M9 21H5V3h4M16 17l5-5-5-5M21 12H9',
    'alerte': 'M12 3l10 18H2zM12 10v4M12 18h.01',
    'imprimante': 'M6 9V3h12v6M6 18H3v-9h18v9h-3M6 14h12v7H6z',
    'excel': 'M5 3h10l4 4v14H5zM15 3v4h4M8 11l8 7M16 11l-8 7',
    'importer': 'M12 21V9M6 13l6-6 6 6M4 3h16',
    'fermer': 'M6 6l12 12M18 6L6 18',
    'chevron': 'M9 6l6 6-6 6',
    'horloge': 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2',
    'synchro': 'M21 12a9 9 0 0 1-15.5 6.2M3 12a9 9 0 0 1 15.5-6.2M3 3v6h6M21 21v-6h-6',
    'graphique': 'M3 17l6-6 4 4 8-8M15 7h6v6',
}

# émojis utilisés par le bureau → nom d'icône
EMOJIS = {
    '📊': 'tableau-de-bord', '🗺️': 'carte', '🚚': 'camion', '🛒': 'panier', '⚖️': 'balance', '🏆': 'trophee',
    '📑': 'rapport', '🎯': 'cible', '🩺': 'sante', '📨': 'courrier', '🎚️': 'curseurs', '📅': 'calendrier',
    '👥': 'utilisateurs', '⚙️': 'parametres', '📜': 'journal', '🔐': 'cadenas', '🔑': 'cle', '🛡️': 'bouclier',
    '🔍': 'loupe', '🔎': 'loupe', '👀': 'oeil', '💰': 'argent', '🏠': 'maison', '🏘️': 'maisons', '🏛️': 'batiment',
    '🏭': 'usine', '🏦': 'banque', '📦': 'colis', '📷': 'photo', '🔗': 'lien', '🔬': 'microscope', '🚗': 'voiture',
    '⛔': 'stop', '➕': 'plus', '＋': 'plus', '⬇️': 'telecharger', '📝': 'crayon', '📋': 'presse-papiers', '🐔': 'poulet',
    '❓': 'aide', '📘': 'guide', '📱': 'telephone', '🔔': 'cloche', '⏻': 'sortie', '⚠️': 'alerte', '🖨️': 'imprimante',
    '✕': 'fermer', '🔒': 'cadenas', '⏱️': 'horloge', '🔄': 'synchro', '📈': 'graphique',
}


def icone(nom, classe='', titre=None):
    """SVG inline de l'icône `nom` (ou de l'émoji correspondant). Émoji inconnu → rendu tel quel."""
    cle = EMOJIS.get(nom.strip(), nom.strip()) if nom else ''
    d = ICONES.get(cle)
    if not d:
        return Markup(escape(nom))
    t = f'<title>{escape(titre)}</title>' if titre else ''
    return Markup(f'<svg class="ico{(" " + classe) if classe else ""}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="{"false" if titre else "true"}" '
                  f'focusable="false" data-icone="{cle}">{t}<path d="{d}"/></svg>')


def sans_emoji(texte):
    """Le texte sans son émoji de tête (« 🎯 Mes actions » → « Mes actions »)."""
    if not texte:
        return texte
    mots = texte.split(' ', 1)
    if len(mots) == 2 and mots[0] in EMOJIS:
        return mots[1]
    return texte


def emoji_de_tete(texte):
    """L'émoji de tête du texte s'il est connu, sinon None."""
    if not texte:
        return None
    tete = texte.split(' ', 1)[0]
    return tete if tete in EMOJIS else None
