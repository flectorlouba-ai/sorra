"""Lecture et contrôle des paramètres (table Parametre)."""
from decimal import Decimal, InvalidOperation

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


def obtenir(cle, defaut=None):
    p = Parametre.query.filter_by(cle=cle).first()
    if p is None:
        return defaut
    try:
        return convertir(p.type, p.valeur)
    except ValueError:
        return defaut
