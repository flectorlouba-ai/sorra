"""Logo SORRA : un poulet, dessiné une seule fois ici.

Le même dessin sert à l'écran (SVG, couleurs de la charte par les classes
« logo-<partie> » de perform.css) et dans les PDF (reportlab). Repère : 64 × 64,
origine en haut à gauche, comme le SVG.
"""
from markupsafe import Markup

# (partie, forme, données) — formes : 'ellipse' (cx, cy, rx, ry), 'cercle' (cx, cy, r),
# 'chemin' (liste de points ; 'C' = courbe de Bézier vers les 3 points suivants), 'trait' (x1, y1, x2, y2)
FORMES = [
    ('corps', 'chemin', [(54, 14), 'C', (62, 22), (60, 34), (52, 38), (60, 36), (58, 44), (52, 47),
                         'C', (46, 53), (30, 54), (22, 47), 'C', (16, 42), (16, 34), (18, 30),
                         'C', (19, 26), (14, 22), (14, 17), 'C', (14, 10), (24, 8), (27, 15),
                         'C', (29, 21), (28, 28), (34, 30), 'C', (42, 32), (48, 26), (50, 18)]),
    ('crete', 'chemin', [(15, 11), 'C', (14, 5), (19, 4), (20, 8), 'C', (21, 3), (26, 3), (25, 9),
                         'C', (29, 7), (31, 11), (27, 14), 'C', (23, 11), (18, 11), (15, 11)]),
    ('crete', 'ellipse', (13.2, 22.5, 2.4, 3.6)),
    ('bec', 'chemin', [(14.5, 15), (7.5, 18), (14.5, 20)]),
    ('oeil', 'cercle', (19.5, 14.5, 1.9)),
    ('aile', 'chemin', [(28, 37), 'C', (34, 33), (43, 34), (47, 39), 'C', (42, 45), (33, 46), (28, 37)]),
    ('pattes', 'trait', (31, 52, 30, 61)),
    ('pattes', 'trait', (40, 52, 41, 61)),
    ('pattes', 'trait', (26, 61, 34, 61)),
    ('pattes', 'trait', (37, 61, 45, 61)),
]


def _chemin_svg(points):
    d, i = f'M{points[0][0]},{points[0][1]}', 1
    while i < len(points):
        if points[i] == 'C':
            a, b, c = points[i + 1:i + 4]
            d += f' C{a[0]},{a[1]} {b[0]},{b[1]} {c[0]},{c[1]}'
            i += 4
        else:
            d += f' L{points[i][0]},{points[i][1]}'
            i += 1
    return d + ' Z'


def svg(classe='logo-poulet', titre='SORRA'):
    """Logo en SVG pour les gabarits (couleurs données par perform.css)."""
    parties = []
    for partie, forme, v in FORMES:
        c = f'class="logo-{partie}"'
        if forme == 'ellipse':
            parties.append(f'<ellipse {c} cx="{v[0]}" cy="{v[1]}" rx="{v[2]}" ry="{v[3]}"/>')
        elif forme == 'cercle':
            parties.append(f'<circle {c} cx="{v[0]}" cy="{v[1]}" r="{v[2]}"/>')
        elif forme == 'trait':
            parties.append(f'<line {c} x1="{v[0]}" y1="{v[1]}" x2="{v[2]}" y2="{v[3]}"/>')
        else:
            parties.append(f'<path {c} d="{_chemin_svg(v)}"/>')
    return Markup(f'<svg class="{classe}" viewBox="0 0 64 64" role="img" aria-label="{titre}">'
                  f'<title>{titre}</title>{"".join(parties)}</svg>')


def dessiner_pdf(canvas, x, y, taille, couleurs):
    """Logo dans un PDF reportlab : (x, y) = coin bas gauche ; `couleurs` : {partie: couleur}."""
    e = taille / 64.0

    def p(px, py):
        return x + px * e, y + (64 - py) * e

    canvas.saveState()
    canvas.setLineCap(1)
    for partie, forme, v in FORMES:
        couleur = couleurs[partie]
        canvas.setFillColor(couleur)
        canvas.setStrokeColor(couleur)
        if forme == 'ellipse':
            cx, cy = p(v[0], v[1])
            canvas.ellipse(cx - v[2] * e, cy - v[3] * e, cx + v[2] * e, cy + v[3] * e, stroke=0, fill=1)
        elif forme == 'cercle':
            cx, cy = p(v[0], v[1])
            canvas.circle(cx, cy, v[2] * e, stroke=0, fill=1)
        elif forme == 'trait':
            canvas.setLineWidth(2.6 * e)
            canvas.line(*p(v[0], v[1]), *p(v[2], v[3]))
        else:
            chemin = canvas.beginPath()
            chemin.moveTo(*p(*v[0]))
            i = 1
            while i < len(v):
                if v[i] == 'C':
                    chemin.curveTo(*p(*v[i + 1]), *p(*v[i + 2]), *p(*v[i + 3]))
                    i += 4
                else:
                    chemin.lineTo(*p(*v[i]))
                    i += 1
            chemin.close()
            canvas.drawPath(chemin, stroke=0, fill=1)
    canvas.restoreState()
