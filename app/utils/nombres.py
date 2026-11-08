"""Affichage des quantités : « 1 200 », « 37,5 » (espace des milliers, virgule décimale)."""


def quantite(valeur, decimales=2):
    if valeur is None or valeur == '':
        return ''
    v = float(valeur)
    if v == int(v):
        return f'{int(v):,}'.replace(',', ' ')
    texte = f'{v:,.{decimales}f}'.rstrip('0').rstrip('.')
    return texte.replace(',', ' ').replace('.', ',')
