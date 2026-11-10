"""Contrôle de cohérence d'une position GPS et dessin d'une province.

Contours : app/data/provinces_gabon.json — geoBoundaries (gbHumanitarian, d'après
SALB, Nations unies, via HDX), licence CC BY 3.0 IGO, simplifiés à environ 500 m
(voir outils/construire_contours.py). Aucun service extérieur n'est appelé.

Un point est jugé « dans la province » s'il est à l'intérieur du contour, ou à
moins de TOLERANCE_KM de son bord : les contours simplifiés et la précision du
GPS rendraient sinon les fermes proches d'une limite faussement « hors province ».
"""
import json
import math
from functools import lru_cache
from pathlib import Path

TOLERANCE_KM = 5
KM_PAR_DEGRE = 111.32
_FICHIER = Path(__file__).resolve().parent.parent / 'data' / 'provinces_gabon.json'


@lru_cache(maxsize=1)
def contours():
    return json.loads(_FICHIER.read_text(encoding='utf-8'))['provinces']


def _dans_anneau(lon, lat, anneau):
    dedans = False
    j = len(anneau) - 1
    for i in range(len(anneau)):
        xi, yi = anneau[i]
        xj, yj = anneau[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            dedans = not dedans
        j = i
    return dedans


def _km_au_segment(lon, lat, a, b):
    # Projection locale en km (le Gabon est à cheval sur l'équateur : écart négligeable)
    c = math.cos(math.radians(lat))
    px, py = 0.0, 0.0
    ax, ay = (a[0] - lon) * c * KM_PAR_DEGRE, (a[1] - lat) * KM_PAR_DEGRE
    bx, by = (b[0] - lon) * c * KM_PAR_DEGRE, (b[1] - lat) * KM_PAR_DEGRE
    dx, dy = bx - ax, by - ay
    if dx == dy == 0:
        return math.hypot(ax - px, ay - py)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx - px, ay + t * dy - py)


def dans_province(lon, lat, code):
    return any(_dans_anneau(lon, lat, a) for a in contours().get(code, []))


def distance_km(lon, lat, code):
    """0 si le point est dans la province, sinon la distance à son bord en km."""
    if dans_province(lon, lat, code):
        return 0.0
    return min(_km_au_segment(lon, lat, a[i], a[i + 1])
               for a in contours().get(code, []) for i in range(len(a) - 1))


def province_du_point(lon, lat):
    return next((c for c in contours() if dans_province(lon, lat, c)), None)


def verifier(latitude, longitude, code_province):
    """Résultat du contrôle : {'ok': bool, 'distance_km': float, 'province_trouvee': code ou None}."""
    if latitude is None or longitude is None or code_province not in contours():
        return None
    d = distance_km(longitude, latitude, code_province)
    return {'ok': d <= TOLERANCE_KM, 'distance_km': round(d),
            'province_trouvee': None if d == 0 else province_du_point(longitude, latitude)}


def dessin(code_province, latitude=None, longitude=None, largeur=260, hauteur=180, marge=8, rayon_deg=None):
    """Chemins SVG du contour de la province, et position de l'épingle, à l'échelle. `rayon_deg` : vue zoomée autour
    du point (lot E-b, punaise : environ 1 km de chaque côté pour 0,01°)."""
    anneaux = contours().get(code_province)
    if not anneaux:
        return None
    xs = [p[0] for a in anneaux for p in a]
    ys = [p[1] for a in anneaux for p in a]
    if latitude is not None and longitude is not None and rayon_deg:
        xs, ys = [longitude - rayon_deg, longitude + rayon_deg], [latitude - rayon_deg, latitude + rayon_deg]
    elif latitude is not None and longitude is not None:
        xs.append(longitude)
        ys.append(latitude)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    echelle = min((largeur - 2 * marge) / ((x1 - x0) or 1), (hauteur - 2 * marge) / ((y1 - y0) or 1))
    dx = (largeur - (x1 - x0) * echelle) / 2
    dy = (hauteur - (y1 - y0) * echelle) / 2

    def proj(x, y):
        return round(dx + (x - x0) * echelle, 1), round(dy + (y1 - y) * echelle, 1)

    chemins = []
    for a in anneaux:
        pts = [proj(x, y) for x, y in a]
        chemins.append('M' + ' L'.join(f'{x},{y}' for x, y in pts) + ' Z')
    epingle = proj(longitude, latitude) if latitude is not None and longitude is not None else None
    # Lot E-b : de quoi convertir un point de la carte en latitude / longitude (punaise à glisser)
    return {'largeur': largeur, 'hauteur': hauteur, 'chemins': chemins, 'epingle': epingle,
            'projection': {'x0': x0, 'y1': y1, 'echelle': echelle, 'dx': dx, 'dy': dy}}
