"""Espace éleveur « illustré doux » (lot 8) : étoiles, série de jours, record,
progression de la bande, messages vivants. Calculs seulement : rien n'est stocké en
plus, sauf les étoiles gardées dans le bilan figé à la clôture."""
from datetime import date, timedelta

from app.services import parametres

# ── Bilan en étoiles (idée 6) ───────────────────────────────────────────

PHRASES_ETOILES = {3: 'Votre meilleure bande !', 2: 'Bonne bande !', 1: 'La prochaine sera meilleure'}


def etoiles(mortalite, indice_consommation):
    """1 à 3 étoiles, jamais 0. Indice de consommation inconnu : 2 étoiles au plus.
    Seuils dans les Paramètres, à valider par les vétérinaires."""
    if mortalite is None:
        return 1
    m3 = float(parametres.obtenir('bandes.etoiles_mortalite_3_pct', 3))
    ic3 = float(parametres.obtenir('bandes.etoiles_ic_3', 1.7))
    m2 = float(parametres.obtenir('bandes.etoiles_mortalite_2_pct', 5))
    if mortalite <= m3 and indice_consommation is not None and indice_consommation <= ic3:
        return 3
    if mortalite <= m2:
        return 2
    return 1


def etoiles_du_bilan(bilan):
    """Étoiles gardées dans le bilan (bilans d'avant le lot 8 : calculées à l'affichage)."""
    if not bilan:
        return None
    n = bilan.get('etoiles')
    return n if n else etoiles(bilan.get('mortalite'), bilan.get('indice_consommation'))


# ── Série de jours (idée 4) ─────────────────────────────────────────────

def _jours(bande):
    return {s.date for s in bande.saisies}


def _series(dates):
    """Longueurs des suites de jours consécutifs, avec leur dernier jour : [(fin, longueur)]."""
    resultat, fin, n = [], None, 0
    for d in sorted(dates):
        if fin is not None and d == fin + timedelta(days=1):
            n += 1
        else:
            if fin is not None:
                resultat.append((fin, n))
            n = 1
        fin = d
    if fin is not None:
        resultat.append((fin, n))
    return resultat


def depart_serie(bande, jour=None):
    """Jour d'où la série se compte : aujourd'hui si la saisie est faite, sinon hier
    (la série ne tombe pas à 0 le matin, avant la saisie du jour)."""
    jour = jour or date.today()
    return jour if jour in _jours(bande) else jour - timedelta(days=1)


def serie(bande, jour=None):
    """Jours consécutifs avec une saisie, dans cette bande (une saisie faite sans réseau
    compte à sa date)."""
    dates, d, n = _jours(bande), depart_serie(bande, jour), 0
    while d in dates:
        n += 1
        d -= timedelta(days=1)
    return n


def plus_longue_serie(bande):
    return max((n for _, n in _series(_jours(bande))), default=0)


def etat_serie(bande, bandes_de_l_eleveur, jour=None):
    """{'n', 'nouveau_record', 'repart'} pour la pastille et l'écran « Bien reçu ! ».
    Record personnel : la plus longue série de l'éleveur, toutes bandes confondues ;
    « nouveau » quand la série en cours le dépasse (à partir de 3 jours)."""
    n = serie(bande, jour)
    fin_en_cours = depart_serie(bande, jour)
    avant = 0
    for b in bandes_de_l_eleveur:
        for fin, longueur in _series(_jours(b)):
            if b.id == bande.id and fin == fin_en_cours:
                continue   # la série en cours ne se bat pas elle-même
            avant = max(avant, longueur)
    anciennes = any(d < fin_en_cours - timedelta(days=n) for d in _jours(bande)) if n else bool(_jours(bande))
    return {'n': n, 'nouveau_record': n >= 3 and n > avant, 'record': max(avant, n),
            'repart': anciennes and n <= 1}


# ── La bande qui grandit (idée 2) ───────────────────────────────────────

def progression(bande, age):
    duree = max(1, (bande.date_fin_prevue - bande.date_mise_en_place).days) if bande.date_fin_prevue else \
        int(parametres.obtenir('bandes.duree_reference_jours', 45))
    pct = max(0, min(100, round(age / duree * 100)))
    reste = duree - age
    if age <= 7:
        message = "C'est parti !"
    elif abs(age - duree / 2) <= 2:
        message = 'À mi-chemin !'
    elif reste > 0:
        message = f'Plus que {reste} jour{"s" if reste > 1 else ""}'
    else:
        message = 'Durée prévue atteinte'
    return {'duree': duree, 'pct': pct, 'message': message}


# ── Messages vivants (idée 7) ───────────────────────────────────────────

def gain_pesee(bande):
    """Écart avec la pesée précédente : (gain en g, jours entre les deux) si positif, sinon None."""
    if len(bande.pesees) < 2:
        return None
    avant, apres = bande.pesees[-2], bande.pesees[-1]
    gain = round(apres.poids_moyen_g - avant.poids_moyen_g)
    jours = (apres.date - avant.date).days
    return (gain, jours) if gain > 0 and jours > 0 else None
