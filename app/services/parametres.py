"""Lecture et contrôle des paramètres (table Parametre)."""
from decimal import Decimal, InvalidOperation

from flask import has_request_context, request

from app.models.parametre import Parametre, TypeParametre

_VRAI = {'oui', 'true', '1', 'vrai'}
_FAUX = {'non', 'false', '0', 'faux'}


def convertir(type_, texte):
    """Valeur Python du texte selon le type. Lève ValueError si le texte ne convient pas."""
    texte = (texte or '').strip()
    if type_ == TypeParametre.TEXTE:
        return texte
    if type_ in (TypeParametre.ENTIER, TypeParametre.JOURS):
        try:
            n = int(texte)
        except ValueError:
            raise ValueError('Un nombre entier est attendu.')
        if type_ == TypeParametre.JOURS and n < 0:
            raise ValueError('Une durée ne peut pas être négative.')
        return n
    if type_ == TypeParametre.DECIMAL:
        try:
            return Decimal(texte.replace(',', '.'))
        except InvalidOperation:
            raise ValueError('Un nombre est attendu (ex. 2,5).')
    if type_ == TypeParametre.BOOLEEN:
        if texte.lower() in _VRAI:
            return True
        if texte.lower() in _FAUX:
            return False
        raise ValueError('Oui ou non est attendu.')
    raise ValueError('Type inconnu.')


def normaliser(type_, texte):
    """Texte à enregistrer : validé, et écrit de façon uniforme."""
    v = convertir(type_, texte)
    if type_ == TypeParametre.BOOLEEN:
        return 'oui' if v else 'non'
    if type_ == TypeParametre.DECIMAL:
        return format(v, 'f')
    return str(v)


def _tous():
    """Tous les paramètres, lus une fois par requête web (les indicateurs en lisent beaucoup)."""
    if has_request_context():
        cache = getattr(request, '_yl2_parametres', None)
        if cache is None:
            cache = {p.cle: (p.type, p.valeur) for p in Parametre.query}
            request._yl2_parametres = cache
        return cache
    return {p.cle: (p.type, p.valeur) for p in Parametre.query}


def oublier_cache():
    if has_request_context() and hasattr(request, '_yl2_parametres'):
        del request._yl2_parametres


def obtenir(cle, defaut=None):
    p = _tous().get(cle)
    if p is None:
        return defaut
    try:
        return convertir(*p)
    except ValueError:
        return defaut
