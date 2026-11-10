"""Lot G (repris au sous-lot K4) — Mon argent sur 12 mois, mini bilan PDF et fiscalité estimée.
Références : docs/maquettes/validees/maquette_mon_argent.html et SORRA_Mon_bilan_2026_exemple.pdf.
Les chiffres viennent des mouvements existants (ventes, dépenses « J'ai payé », achats « J'ai acheté »), jamais d'un
chiffre inventé ; une valeur absente s'affiche « — ». Seuils fiscaux : paramètres sensibles (quatre yeux)."""
import io
from datetime import date

from app.services import argent, parametres

MOIS_COURTS = ['Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin', 'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc']
MOIS_LETTRES = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D']
MOIS_LONGS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

# Postes du bilan (ordre de la maquette) et mots qui rattachent une dépense ou un achat à un poste
POSTES_DEPENSES = [('Poussins', ('poussin',)), ('Aliment', ('aliment',)),
                   ('Vaccins et médicaments', ('vaccin', 'médicament', 'medicament', 'soin', 'véto', 'veto', 'anticocc')),
                   ("Main-d'œuvre", ('main', 'salaire', 'ouvrier', 'personnel')), ('Énergie et eau', ('électric', 'electric', 'eau', 'carburant', 'gaz')),
                   ('Entretien et réparations', ('réparation', 'reparation', 'entretien', 'désinfect')), ('Transport', ('transport',)),
                   ('Autres', ())]
POSTES_RECETTES = ['Ventes de poulets', "Ventes d'œufs", 'Autres recettes (fientes, sacs…)']


def _poste(mv):
    if mv['genre'] == 'achat':
        texte = (mv['objet'].lignes[0].produit.type + ' ' + mv['objet'].lignes[0].produit.nom).lower()
    else:
        texte = ((getattr(mv['objet'], 'categorie', '') or '') + ' ' + mv['texte']).lower()
    for poste, mots in POSTES_DEPENSES:
        if any(m in texte for m in mots):
            return poste
    return 'Autres'


def mois_glissants(fin=None, n=12):
    fin = fin or date.today()
    liste = []
    for i in range(n - 1, -1, -1):
        y, m = fin.year, fin.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        liste.append((y, m))
    return liste


def bilan(fermes, annee=None, fin=None):
    """Chiffres de l'année civile (`annee`) ou des 12 derniers mois (`fin`) : par mois, par poste, totaux, marge."""
    ids = [f.id for f in fermes]
    mvts = argent.mouvements(ids) if ids else []
    if annee:
        mois = [(annee, m) for m in range(1, 13)]
    else:
        mois = mois_glissants(fin)
    cles = {k: i for i, k in enumerate(mois)}
    par_mois = [{'annee': y, 'mois': m, 'recettes': 0, 'depenses': 0, 'postes': {p: 0 for p, _ in POSTES_DEPENSES},
                 'recettes_postes': {p: 0 for p in POSTES_RECETTES}, 'futur': (y, m) > (date.today().year, date.today().month)}
                for y, m in mois]
    kg_vendus = 0
    for mv in mvts:
        k = (mv['date'].year, mv['date'].month)
        if k not in cles or not mv['montant']:
            continue
        ligne = par_mois[cles[k]]
        if mv['signe'] > 0:
            ligne['recettes'] += mv['montant']
            poste = 'Ventes de poulets' if mv['genre'] == 'vente' else 'Autres recettes (fientes, sacs…)'
            ligne['recettes_postes'][poste] += mv['montant']
            if mv['genre'] == 'vente':
                kg_vendus += mv['objet'].poids_total_kg or 0
        else:
            ligne['depenses'] += mv['montant']
            ligne['postes'][_poste(mv)] += mv['montant']
    for ligne in par_mois:
        ligne['benefice'] = ligne['recettes'] - ligne['depenses']
    recettes = sum(l['recettes'] for l in par_mois)
    depenses = sum(l['depenses'] for l in par_mois)
    benefice = recettes - depenses
    postes = {p: sum(l['postes'][p] for l in par_mois) for p, _ in POSTES_DEPENSES}
    meilleur = max((l for l in par_mois if l['recettes'] or l['depenses']), key=lambda l: l['benefice'], default=None)
    premier = sorted(((v, p) for p, v in postes.items() if v), reverse=True)[:2]
    return {'mois': par_mois, 'recettes': recettes, 'depenses': depenses, 'benefice': benefice,
            'marge': (100 * benefice / recettes) if recettes else None,
            'par_kg': (benefice / kg_vendus) if kg_vendus else None, 'kg_vendus': kg_vendus, 'postes': postes,
            'meilleur_mois': meilleur, 'premiers_postes': [(p, 100 * v / depenses) for v, p in premier] if depenses else [],
            'bandes_vendues': sum(1 for mv in mvts if mv['genre'] == 'vente' and (mv['date'].year, mv['date'].month) in cles)}


# ── Fiscalité estimée ───────────────────────────────────────────────────

def seuils():
    return {'isl': int(parametres.obtenir('fiscalite.seuil_isl_fcfa', 30_000_000)),
            'rsi': int(parametres.obtenir('fiscalite.seuil_rsi_fcfa', 60_000_000)),
            'rappel': parametres.obtenir('fiscalite.rappel_declaration', '30/04') or '30/04'}


def fiscalite(chiffre_affaires):
    """Régime estimé d'après le chiffre d'affaires de l'année civile : ISL sous le 1er seuil, régime simplifié (RSI) sous
    le 2d, réel au-delà. Indicatif : seuils réglables par l'administrateur (quatre yeux), à valider avec la DGI."""
    s = seuils()
    ca = chiffre_affaires or 0
    if ca < s['isl']:
        regime, code, seuil, suivant = 'Impôt synthétique libératoire', 'ISL', s['isl'], 'régime simplifié (RSI)'
        raison = f"car mon chiffre d'affaires est sous {_m(s['isl'])} FCFA"
    elif ca < s['rsi']:
        regime, code, seuil, suivant = 'Régime simplifié d’imposition', 'RSI', s['rsi'], 'régime réel'
        raison = f"car mon chiffre d'affaires est entre {_m(s['isl'])} et {_m(s['rsi'])} FCFA"
    else:
        regime, code, seuil, suivant = 'Régime réel', 'réel', None, None
        raison = f"car mon chiffre d'affaires dépasse {_m(s['rsi'])} FCFA"
    pct = round(100 * ca / seuil) if seuil else None
    return {'ca': ca, 'regime': regime, 'code': code, 'seuil': seuil, 'pct': pct, 'proche': bool(pct is not None and pct >= 80),
            'suivant': suivant, 'raison': raison, 'rappel': s['rappel'],
            'mention': 'Estimation indicative, seuils réglables, à valider avec la DGI. SORRA ne remplace pas un comptable.'}


def rappels(fermes, jour=None):
    """Lot G : les rappels fiscaux de l'éleveur — déclaration annuelle (30 jours avant la date réglée) et seuil de régime
    approché (≥ 80 %). [(code, titre, texte, échéance)]"""
    jour = jour or date.today()
    s = seuils()
    resultat = []
    try:
        jj, mm = (int(x) for x in s['rappel'].split('/')[:2])
        echeance = date(jour.year, mm, jj)
        if echeance < jour:
            echeance = date(jour.year + 1, mm, jj)
    except (ValueError, TypeError):
        echeance = None
    if echeance is not None:
        restant = (echeance - jour).days
        resultat.append(('declaration', 'Déclaration annuelle', f'à faire avant le {echeance:%d/%m/%Y}' + (f' · dans {restant} jour{"s" if restant > 1 else ""}' if restant <= 30 else ''), echeance, restant <= 30))
    f = fiscalite(bilan(fermes, annee=jour.year)['recettes'])
    if f['proche'] and f['suivant']:
        resultat.append(('seuil', 'Seuil de régime approché', f"{f['pct']} % du seuil de {_m(f['seuil'])} FCFA : au-delà, {f['suivant']}", None, True))
    return resultat


def _m(v):
    """30 000 000 → « 30 M »."""
    if v is None:
        return '—'
    if abs(v) >= 1_000_000:
        x = v / 1_000_000
        return (f'{x:.1f}'.rstrip('0').rstrip('.') if x < 100 else f'{x:.0f}').replace('.', ',') + ' M'
    return f'{v:,.0f}'.replace(',', ' ')


def court(v):
    return _m(v)


# ── Mini bilan PDF (2 pages A4 paysage) ─────────────────────────────────

def bilan_pdf(ferme, fermes, annee, user=None, demo=False):
    from reportlab.graphics import renderPDF
    from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, PolyLine
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import cm
    from reportlab.pdfgen import canvas
    from app.utils.logo import dessiner_pdf
    from app.services.rapports_pdf import COULEURS_LOGO
    from app.utils.nombres import quantite

    b = bilan(fermes, annee=annee)
    fisc = fiscalite(b['recettes'])
    NOIR, BLEU, VERT, ORANGE, FOND, GRIS = (colors.HexColor('#0c2461'), colors.HexColor('#1241a8'), colors.HexColor('#2fa36b'),
                                            colors.HexColor('#f08a24'), colors.HexColor('#fbf8f2'), colors.HexColor('#555555'))
    tampon = io.BytesIO()
    L, H = landscape(A4)
    c = canvas.Canvas(tampon, pagesize=landscape(A4))
    c.setTitle(f'SORRA — Mon bilan {annee}')
    auj = date.today()
    dernier = max((l for l in b['mois'] if l['recettes'] or l['depenses']), key=lambda l: l['mois'], default=None)
    periode = f'janvier à {MOIS_LONGS[(dernier["mois"] if dernier else auj.month) - 1]} {annee}'

    def entete(titre, sous, droite):
        c.setFillColor(BLEU)
        c.roundRect(1 * cm, H - 2.6 * cm, L - 2 * cm, 1.8 * cm, 8, fill=1, stroke=0)
        c.setFillColor(NOIR)
        c.roundRect(1.4 * cm, H - 2.35 * cm, 1.3 * cm, 1.3 * cm, 6, fill=1, stroke=0)
        dessiner_pdf(c, 1.6 * cm, H - 2.25 * cm, 0.9 * cm, COULEURS_LOGO)
        c.setFillColor(colors.white)
        c.setFont('Helvetica-Bold', 16)
        c.drawString(3.1 * cm, H - 1.6 * cm, titre)
        c.setFont('Helvetica', 9)
        c.drawString(3.1 * cm, H - 2.2 * cm, sous)
        y = H - 1.45 * cm
        for i, ligne in enumerate(droite):
            c.setFont('Helvetica-Bold' if i == 0 else 'Helvetica', 9)
            c.drawRightString(L - 1.4 * cm, y, ligne)
            y -= 0.45 * cm

    def pied(page):
        c.setFillColor(GRIS)
        c.setFont('Helvetica', 7)
        texte = (f'Généré par SORRA le {auj:%d/%m/%Y} à partir des saisies de la ferme (ventes, dépenses, achats).'
                 + (' Données de démonstration, fictives.' if demo else '') + f' · Page {page} / 2')
        c.drawString(1 * cm, 0.7 * cm, texte)

    # ── Page 1 ──
    entete(f'Mon bilan {annee}', f'Mini bilan comptable de la ferme · {periode}',
           [f'Ferme {ferme.numero} · {ferme.exploitant_nom}', f'{ferme.localite.nom}, {ferme.province.nom} · {ferme.libelle_programme}',
            f'{quantite(ferme.capacite)} places · {b["bandes_vendues"]} vente(s) de poulets'])
    cartes = [('💰 Recettes', f'{quantite(b["recettes"])} FCFA', VERT), ('🧾 Dépenses', f'{quantite(b["depenses"])} FCFA', ORANGE),
              ('✅ Bénéfice', f'{quantite(b["benefice"])} FCFA', NOIR),
              ('📈 Marge', (f'{b["marge"]:.1f} %'.replace('.', ',') if b['marge'] is not None else '—'), BLEU)]
    largeur = (L - 2 * cm - 3 * 0.4 * cm) / 4
    for i, (titre, valeur, couleur) in enumerate(cartes):
        x = 1 * cm + i * (largeur + 0.4 * cm)
        c.setFillColor(colors.white); c.setStrokeColor(colors.HexColor('#dddddd'))
        c.roundRect(x, H - 4.9 * cm, largeur, 1.9 * cm, 6, fill=1, stroke=1)
        c.setFillColor(GRIS); c.setFont('Helvetica', 8); c.drawString(x + 0.3 * cm, H - 3.5 * cm, titre.split(' ', 1)[1])
        c.setFillColor(couleur); c.setFont('Helvetica-Bold', 15); c.drawString(x + 0.3 * cm, H - 4.3 * cm, valeur)
        if i == 3 and b['par_kg'] is not None:
            c.setFillColor(GRIS); c.setFont('Helvetica', 7.5); c.drawString(x + 0.3 * cm, H - 4.7 * cm, f'≈ {quantite(round(b["par_kg"]))} FCFA par kg vendu')
    # graphique
    gx, gy, gl, gh = 1 * cm, 5.3 * cm, L - 2 * cm, H - 5.3 * cm - 5.5 * cm
    c.setFillColor(FOND); c.roundRect(gx, gy, gl, gh, 8, fill=1, stroke=0)
    c.setFillColor(NOIR); c.setFont('Helvetica-Bold', 10)
    c.drawString(gx + 0.4 * cm, gy + gh - 0.6 * cm, 'Mes recettes, mes dépenses et mon bénéfice, mois par mois')
    c.setFont('Helvetica', 8)
    c.setFillColor(VERT); c.rect(gx + 0.4 * cm, gy + gh - 1.2 * cm, 0.3 * cm, 0.25 * cm, fill=1, stroke=0); c.setFillColor(NOIR); c.drawString(gx + 0.8 * cm, gy + gh - 1.15 * cm, 'Recettes')
    c.setFillColor(ORANGE); c.rect(gx + 2.6 * cm, gy + gh - 1.2 * cm, 0.3 * cm, 0.25 * cm, fill=1, stroke=0); c.setFillColor(NOIR); c.drawString(gx + 3 * cm, gy + gh - 1.15 * cm, 'Dépenses')
    c.setStrokeColor(NOIR); c.setLineWidth(1.5); c.line(gx + 5 * cm, gy + gh - 1.08 * cm, gx + 5.5 * cm, gy + gh - 1.08 * cm); c.drawString(gx + 5.7 * cm, gy + gh - 1.15 * cm, 'Bénéfice du mois')
    zone_x, zone_y, zone_l, zone_h = gx + 1.6 * cm, gy + 1.1 * cm, gl - 2.2 * cm, gh - 2.8 * cm
    maxi = max([l['recettes'] for l in b['mois']] + [l['depenses'] for l in b['mois']] + [abs(l['benefice']) for l in b['mois']] + [1])
    mini = min([l['benefice'] for l in b['mois']] + [0])
    echelle = zone_h / (maxi - mini) if maxi - mini else 1
    zero = zone_y + (-mini) * echelle
    c.setStrokeColor(colors.HexColor('#cccccc')); c.setLineWidth(0.4)
    for frac in (0, 0.25, 0.5, 0.75, 1):
        v = mini + frac * (maxi - mini)
        y = zone_y + (v - mini) * echelle
        c.line(zone_x, y, zone_x + zone_l, y)
        c.setFillColor(GRIS); c.setFont('Helvetica', 7); c.drawRightString(zone_x - 0.15 * cm, y - 0.1 * cm, ('+' if v > 0 else '') + _m(v) if v else '0')
    pas = zone_l / 12
    points = []
    for i, l in enumerate(b['mois']):
        x0 = zone_x + i * pas
        c.setFillColor(VERT); c.rect(x0 + pas * 0.12, zero, pas * 0.3, l['recettes'] * echelle, fill=1, stroke=0)
        c.setFillColor(ORANGE); c.rect(x0 + pas * 0.5, zero, pas * 0.3, l['depenses'] * echelle, fill=1, stroke=0)
        points.append((x0 + pas / 2, zone_y + (l['benefice'] - mini) * echelle))
        c.setFillColor(NOIR); c.setFont('Helvetica-Bold', 8); c.drawCentredString(x0 + pas / 2, zone_y - 0.5 * cm, MOIS_COURTS[l['mois'] - 1])
    c.setStrokeColor(NOIR); c.setLineWidth(1.5)
    actifs = [(p, l) for p, l in zip(points, b['mois']) if not l['futur']]
    for (p1, _), (p2, _) in zip(actifs, actifs[1:]):
        c.line(p1[0], p1[1], p2[0], p2[1])
    for p, _ in actifs:
        c.setFillColor(NOIR); c.circle(p[0], p[1], 2.5, fill=1, stroke=0)
    # encadrés du bas
    bx, by, bl, bh = 1 * cm, 1.3 * cm, (L - 2.4 * cm) * 0.58, 3.6 * cm
    c.setFillColor(FOND); c.roundRect(bx, by, bl, bh, 8, fill=1, stroke=0)
    c.setFillColor(NOIR); c.setFont('Helvetica-Bold', 10); c.drawString(bx + 0.4 * cm, by + bh - 0.6 * cm, "Ce qu'il faut retenir")
    c.setFont('Helvetica', 8.5)
    phrases = ["• Les mois d'achat des poussins sont en négatif, les mois de vente en positif : c'est normal."]
    if b['meilleur_mois'] and b['meilleur_mois']['benefice'] > 0:
        phrases.append(f"• Bénéfice cumulé de l'année : {_m(b['benefice'])} FCFA ; meilleur mois : {MOIS_LONGS[b['meilleur_mois']['mois'] - 1]} ({_m(b['meilleur_mois']['benefice'])} FCFA).")
    elif b['recettes'] or b['depenses']:
        phrases.append(f"• Résultat cumulé de l'année : {_m(b['benefice'])} FCFA (les ventes de la bande en cours ne sont pas encore enregistrées).")
    if b['premiers_postes']:
        p = b['premiers_postes']
        phrases.append(f"• Le premier poste de dépense est {p[0][0].lower()} ({p[0][1]:.0f} % des dépenses)" + (f", puis {p[1][0].lower()} ({p[1][1]:.0f} %)." if len(p) > 1 else '.'))
    if not (b['recettes'] or b['depenses']):
        phrases.append("• Aucun mouvement enregistré cette année : le bilan se remplira avec « J'ai payé », « J'ai acheté » et les ventes.")
    for i, ph in enumerate(phrases[:3]):
        c.drawString(bx + 0.4 * cm, by + bh - 1.2 * cm - i * 0.55 * cm, ph[:150])
    fx = bx + bl + 0.4 * cm
    fl = L - 1 * cm - fx
    c.setFillColor(FOND); c.roundRect(fx, by, fl, bh, 8, fill=1, stroke=0)
    c.setFillColor(NOIR); c.setFont('Helvetica-Bold', 10); c.drawString(fx + 0.4 * cm, by + bh - 0.6 * cm, '🏛 Ma fiscalité (indicatif)'.replace('🏛 ', ''))
    c.setFont('Helvetica', 8.5)
    c.drawString(fx + 0.4 * cm, by + bh - 1.15 * cm, f"Chiffre d'affaires de l'année : {_m(fisc['ca'])} FCFA")
    if fisc['seuil']:
        c.setFillColor(colors.HexColor('#dddddd')); c.roundRect(fx + 0.4 * cm, by + bh - 1.6 * cm, fl - 0.8 * cm, 0.25 * cm, 3, fill=1, stroke=0)
        c.setFillColor(ORANGE if fisc['proche'] else VERT); c.roundRect(fx + 0.4 * cm, by + bh - 1.6 * cm, (fl - 0.8 * cm) * min(1, fisc['pct'] / 100), 0.25 * cm, 3, fill=1, stroke=0)
    c.setFillColor(NOIR)
    c.drawString(fx + 0.4 * cm, by + bh - 2.1 * cm, f"Régime estimé : {fisc['regime']}" + (f" — {fisc['pct']} % du seuil." if fisc['pct'] is not None else '.'))
    if fisc['proche'] and fisc['suivant']:
        c.drawString(fx + 0.4 * cm, by + bh - 2.6 * cm, f"⚠ Proche du seuil : au-delà de {_m(fisc['seuil'])}, {fisc['suivant']}.".replace('⚠ ', ''))
    c.setFillColor(GRIS); c.setFont('Helvetica', 7.5)
    c.drawString(fx + 0.4 * cm, by + bh - 3.1 * cm, "Seuils réglables par l'administrateur, à valider avec la DGI. SORRA ne remplace pas un comptable.")
    pied(1)
    c.showPage()

    # ── Page 2 : détail par mois ──
    entete(f'Mon bilan {annee} — détail par mois', f'Ferme {ferme.numero} · montants en FCFA', [])
    colonnes = ['Poste'] + MOIS_COURTS + ['Total']
    l0 = 4.6 * cm
    lm = (L - 2 * cm - l0 - 2.2 * cm) / 12
    xs = [1 * cm, 1 * cm + l0] + [1 * cm + l0 + lm * (i + 1) for i in range(12)] + [L - 1 * cm]
    y = H - 3.4 * cm
    c.setFillColor(NOIR); c.rect(1 * cm, y - 0.15 * cm, L - 2 * cm, 0.55 * cm, fill=1, stroke=0)
    c.setFillColor(colors.white); c.setFont('Helvetica-Bold', 7.5)
    c.drawString(xs[0] + 0.1 * cm, y, 'Poste')
    for i, m in enumerate(MOIS_COURTS):
        c.drawRightString(xs[i + 2] - 0.1 * cm, y, m)
    c.drawRightString(xs[14] - 0.1 * cm, y, 'Total')
    y -= 0.6 * cm

    def rangee(nom, valeurs, total, gras=False, couleur=NOIR, fond=None, signe=False):
        nonlocal y
        if fond:
            c.setFillColor(fond); c.rect(1 * cm, y - 0.15 * cm, L - 2 * cm, 0.5 * cm, fill=1, stroke=0)
        c.setFillColor(couleur); c.setFont('Helvetica-Bold' if gras else 'Helvetica', 7.5)
        c.drawString(xs[0] + 0.1 * cm, y, nom)
        for i, v in enumerate(valeurs):
            t = '—' if not v else ((('−' if v < 0 else '') + quantite(abs(v))) if signe else quantite(v))
            c.setFillColor(couleur if v else colors.HexColor('#aaaaaa'))
            c.drawRightString(xs[i + 2] - 0.1 * cm, y, t)
        c.setFillColor(couleur)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawRightString(xs[14] - 0.1 * cm, y, '—' if not total else ((('−' if total < 0 else '') + quantite(abs(total))) if signe else quantite(total)))
        c.setStrokeColor(colors.HexColor('#eeeeee')); c.setLineWidth(0.3); c.line(1 * cm, y - 0.2 * cm, L - 1 * cm, y - 0.2 * cm)
        y -= 0.5 * cm

    def section(titre):
        nonlocal y
        c.setFillColor(colors.HexColor('#f0f5ff')); c.rect(1 * cm, y - 0.15 * cm, L - 2 * cm, 0.5 * cm, fill=1, stroke=0)
        c.setFillColor(BLEU); c.setFont('Helvetica-Bold', 8); c.drawString(xs[0] + 0.1 * cm, y, titre)
        y -= 0.55 * cm

    section('Recettes')
    for poste in POSTES_RECETTES:
        vals = [l['recettes_postes'][poste] for l in b['mois']]
        rangee(poste, vals, sum(vals))
    rangee('Total recettes', [l['recettes'] for l in b['mois']], b['recettes'], gras=True, couleur=VERT)
    section('Dépenses')
    for poste, _ in POSTES_DEPENSES:
        vals = [l['postes'][poste] for l in b['mois']]
        rangee(poste, vals, sum(vals))
    rangee('Total dépenses', [l['depenses'] for l in b['mois']], b['depenses'], gras=True, couleur=ORANGE)
    rangee('Bénéfice du mois', [l['benefice'] for l in b['mois']], b['benefice'], gras=True, fond=colors.HexColor('#fff8dc'), signe=True)
    c.setFillColor(GRIS); c.setFont('Helvetica', 7)
    c.drawString(1 * cm, y - 0.3 * cm, "Les recettes viennent des ventes et sorties enregistrées ; les dépenses de « J'ai payé » et « J'ai acheté », y compris les intrants du programme à leur valeur. "
                 + (f'{MOIS_LONGS[auj.month - 1].capitalize()} : mois en cours.' if annee == auj.year else ''))
    pied(2)
    c.showPage()
    c.save()
    return tampon.getvalue()
