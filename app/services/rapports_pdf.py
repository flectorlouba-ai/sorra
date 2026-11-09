"""Rapports PDF générés à la demande (reportlab, bibliothèque libre, sans service extérieur) :
hebdomadaire (province ou national), mensuel national, fin de bande.
Couleurs reprises de la charte (bleu nuit, bleu, gris)."""
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from app.utils.logo import dessiner_pdf
from app.utils.nombres import quantite

# Couleurs de la charte (perform.css : --noir, --noir3, --off, --grise)
NOIR = colors.HexColor('#0c2461')
BLEU = colors.HexColor('#1241a8')
FOND = colors.HexColor('#f0f5ff')
TRAIT = colors.HexColor('#eeeeee')
# Logo : mêmes couleurs que perform.css (--blanc, --rouge-vif, --ambre-vif, --noir, --b200)
COULEURS_LOGO = {'corps': colors.white, 'crete': colors.HexColor('#dc2626'), 'bec': colors.HexColor('#f59e0b'),
                 'oeil': NOIR, 'aile': colors.HexColor('#bfdbfe'), 'pattes': colors.HexColor('#f59e0b')}

TITRE = ParagraphStyle('titre', fontName='Helvetica-Bold', fontSize=16, textColor=NOIR, spaceAfter=4)
SOUS = ParagraphStyle('sous', fontName='Helvetica', fontSize=9, textColor=colors.HexColor('#555555'), spaceAfter=10)
SECTION = ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=11, textColor=BLEU, spaceBefore=10, spaceAfter=4)
TEXTE = ParagraphStyle('texte', fontName='Helvetica', fontSize=9, textColor=NOIR)


def _q(v, n=1, suffixe=''):
    return '—' if v is None else f'{quantite(round(v, n))}{suffixe}'


def _table(lignes, largeurs=None):
    t = Table(lignes, colWidths=largeurs, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NOIR), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, FOND]),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, TRAIT), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def _pied(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NOIR)
    canvas.rect(0, A4[1] - 0.6 * cm, A4[0], 0.6 * cm, fill=1, stroke=0)
    dessiner_pdf(canvas, 1.5 * cm, A4[1] - 0.57 * cm, 0.54 * cm, COULEURS_LOGO)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.drawString(2.2 * cm, A4[1] - 0.42 * cm, 'SORRA — Suivi et traçabilité de la filière avicole')
    canvas.setFillColor(colors.HexColor('#888888'))
    canvas.setFont('Helvetica', 7.5)
    canvas.drawString(1.5 * cm, 1 * cm, f'Généré le {date.today().strftime("%d/%m/%Y")} · page {doc.page}')
    canvas.restoreState()


def _document(elements):
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.6 * cm, title='SORRA')
    doc.build(elements, onFirstPage=_pied, onLaterPages=_pied)
    return tampon.getvalue()


def _chiffres(t):
    return _table([
        ['Fermes actives', 'Bandes en cours', 'Poulets présents', 'Mortalité moyenne'],
        [f'{t["fermes_actives"]} / {t["fermes"]}', str(t['bandes_en_cours']), quantite(t['effectifs_presents']),
         _q(t['mortalite'], 2, ' %')],
        ['Sortis (têtes)', 'Sortis (tonnes)', 'Aliment (tonnes)', 'Régularité des saisies'],
        [quantite(t['sortis_tetes']), _q(t['sortis_kg'] / 1000, 2), _q(t['aliment_kg'] / 1000, 2),
         _q(t['regularite'], 0, ' %')],
    ], [4.4 * cm] * 4)


def rapport_periode(titre, sous_titre, donnees, alertes_sanitaires):
    t = donnees['total']
    elements = [Paragraph(titre, TITRE), Paragraph(sous_titre, SOUS), _chiffres(t)]
    if len(donnees['par_province']) > 1:
        elements += [Paragraph('Par province', SECTION), _table(
            [['Province', 'Fermes actives', 'Bandes', 'Présents', 'Mortalité', 'Sortis (t)', 'Feux rouges']] +
            [[p['province'].nom, str(p['fermes_actives']), str(p['bandes_en_cours']), quantite(p['effectifs_presents']),
              _q(p['mortalite'], 2, ' %'), _q(p['sortis_kg'] / 1000, 2), str(p['feux']['rouge'])]
             for p in donnees['par_province']])]
    arr = donnees['arrivee']
    if arr['fournisseurs']:
        elements += [Paragraph(f'Mortalité à l\'arrivée des poussins (seuil {_q(arr["seuil"], 1, " %")})', SECTION),
                     _table([['Fournisseur', 'Livraisons', 'Reçus', 'Morts', 'Taux']] +
                            [[fo['fournisseur'], str(fo['livraisons']), quantite(fo['recus']), quantite(fo['morts']),
                              _q(fo['taux'], 2, ' %')] for fo in arr['fournisseurs']])]
    elements += [Paragraph('Alertes', SECTION),
                 Paragraph(f'Bandes au feu rouge : {t["feux"]["rouge"]} · au feu orange : {t["feux"]["orange"]} · '
                           f'alertes sanitaires confirmées : {alertes_sanitaires}', TEXTE)]
    return _document(elements)


def rapport_fin_bande(bande):
    b = bande.bilan or {}
    elements = [Paragraph(f'Fin de bande {bande.numero}', TITRE),
                Paragraph(f'{bande.ferme.nom} ({bande.ferme.numero}) · {bande.ferme.localite.nom}, '
                          f'{bande.ferme.province.nom} · bâtiment {bande.batiment.code} · du '
                          f'{bande.date_mise_en_place.strftime("%d/%m/%Y")} au '
                          f'{bande.date_cloture.strftime("%d/%m/%Y")} ({b.get("duree_jours", "—")} jours)'
                          + (' · indicateurs partiels (rattrapage)' if b.get('partiels') else ''), SOUS),
                _table([['Mis en place', 'Morts', 'Mortalité', 'Viabilité'],
                        [quantite(b.get('mis_en_place')), quantite(b.get('morts')), _q(b.get('mortalite'), 2, ' %'),
                         _q(b.get('viabilite'), 2, ' %')],
                        ['Poids moyen de sortie', 'GMQ', 'Indice de consommation', 'Poids vif produit'],
                        [_q(b.get('poids_moyen_sortie_kg'), 3, ' kg'), _q(b.get('gmq'), 1, ' g/j'),
                         _q(b.get('indice_consommation'), 2) + (' (incomplet)' if b.get('incomplet') else ''),
                         _q(b.get('poids_vif_produit_kg'), 1, ' kg')]],
                       [4.4 * cm] * 4),
                Paragraph('Sorties par destinataire', SECTION),
                _table([['Destinataire', 'Motif', 'Poulets', 'Poids (kg)']] +
                       [[s['destinataire'], s['motif'], quantite(s['nombre']), quantite(s['poids_kg'])]
                        for s in b.get('sorties_par_destinataire', [])] or [['—', '', '', '']]),
                Spacer(1, 8),
                Paragraph(f'Aliment consommé : {_q(b.get("aliment_kg"), 1, " kg")} · régularité des saisies : '
                          f'{_q(b.get("regularite"), 0, " %")}'
                          + (f' · {b.get("jours_non_saisis")} jour(s) non saisi(s) : mortalité et indice de '
                             f'consommation incomplets' if b.get('incomplet') else ''), TEXTE)]
    return _document(elements)
