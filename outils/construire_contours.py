"""Construit app/data/provinces_gabon.json à partir des limites geoBoundaries.

Source : geoBoundaries, jeu « gbHumanitarian » GAB ADM1, issu de Second
Administrative Level Boundaries (SALB) des Nations unies, diffusé sur HDX.
Licence : Creative Commons Attribution 3.0 IGO (CC BY 3.0 IGO).
Téléchargement (une seule fois, à la main) :
https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbHumanitarian/GAB/ADM1/geoBoundaries-GAB-ADM1.geojson

Utilisation : python outils/construire_contours.py <fichier.geojson>
Les contours sont simplifiés (Douglas-Peucker, environ 500 m) et arrondis à
4 décimales : l'application n'appelle ensuite aucun service extérieur.
"""
import json
import sys
import unicodedata
from pathlib import Path

TOLERANCE = 0.005   # degré ≈ 550 m à l'équateur
SORTIE = Path(__file__).resolve().parent.parent / 'app' / 'data' / 'provinces_gabon.json'

CODES = {'estuaire': 'EST', 'haut-ogooue': 'HOG', 'moyen-ogooue': 'MOG', 'ngounie': 'NGO',
         'nyanga': 'NYA', 'ogooue-ivindo': 'OGI', 'ogooue-lolo': 'OGL',
         'ogooue-maritime': 'OGM', 'woleu-ntem': 'WNT'}


def _sans_accent(t):
    return ''.join(c for c in unicodedata.normalize('NFKD', t) if not unicodedata.combining(c)).lower()


def _distance_segment(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return ((x - x1) ** 2 + (y - y1) ** 2) ** .5
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return ((x - x1 - t * dx) ** 2 + (y - y1 - t * dy) ** 2) ** .5


def simplifier(points, tol):
    if len(points) < 4:
        return points
    garde = [False] * len(points)
    garde[0] = garde[-1] = True
    pile = [(0, len(points) - 1)]
    while pile:
        i, j = pile.pop()
        dmax, k = 0, None
        for m in range(i + 1, j):
            d = _distance_segment(points[m], points[i], points[j])
            if d > dmax:
                dmax, k = d, m
        if k is not None and dmax > tol:
            garde[k] = True
            pile += [(i, k), (k, j)]
    return [p for p, g in zip(points, garde) if g]


def main(chemin):
    donnees = json.loads(Path(chemin).read_text(encoding='utf-8'))
    provinces = {}
    for f in donnees['features']:
        code = CODES[_sans_accent(f['properties']['shapeName'])]
        geom = f['geometry']
        polygones = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        anneaux = []
        for poly in polygones:
            exterieur = simplifier(poly[0], TOLERANCE)    # les trous éventuels sont ignorés
            if len(exterieur) >= 4:
                anneaux.append([[round(x, 4), round(y, 4)] for x, y in exterieur])
        provinces[code] = anneaux
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps({
        'source': 'geoBoundaries (gbHumanitarian GAB ADM1), d\'après SALB — Nations unies, via HDX',
        'licence': 'CC BY 3.0 IGO',
        'simplification': f'Douglas-Peucker, tolérance {TOLERANCE}°',
        'provinces': provinces,
    }, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(SORTIE, SORTIE.stat().st_size, 'octets',
          {c: sum(len(a) for a in v) for c, v in provinces.items()})


if __name__ == '__main__':
    main(sys.argv[1])
