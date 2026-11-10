"""Lot T — fiche papier de la semaine (pilote) : un PDF A4 à imprimer pour la bande en cours. En-tête SORRA, QR de
la bande, tableau des 7 jours à remplir au stylo (les jours déjà saisis sont pré-remplis et cochés), vaccins prévus,
total, signatures. Bande de ponte : colonne « œufs ramassés » (lot F)."""
from datetime import date, timedelta

from flask import has_request_context, url_for
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, KeepTogether

from app import indicateurs
from app.services import sante
from app.services.rapports_pdf import _document, NOIR, BLEU, FOND, TRAIT, TITRE, SOUS, SECTION, TEXTE
from app.utils.nombres import quantite

JOURS = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']


def _qr(url, taille):
    widget = QrCodeWidget(url, barLevel='M', barBorder=1)
    b = widget.getBounds()
    d = Drawing(taille, taille, transform=[taille / (b[2] - b[0]), 0, 0, taille / (b[3] - b[1]), 0, 0])
    d.add(widget)
    return d


def semaine_de(jour):
    """Du lundi au dimanche de la semaine du jour donné."""
    lundi = jour - timedelta(days=jour.weekday())
    return [lundi + timedelta(days=i) for i in range(7)]


def fiche_pdf(bande, jour=None, url_fiche=None):
    jour = jour or date.today()
    jours = semaine_de(jour)
    ferme = bande.ferme
    eleveur = ferme.responsable
    v = indicateurs.calculer(bande, jours[0] - timedelta(days=1))
    ponte = getattr(bande, 'type', None) == 'PONTE'
    saisies = {s.date: s for s in bande.saisies if jours[0] <= s.date <= jours[-1]}
    pesees = {p.date: p for p in bande.pesees if jours[0] <= p.date <= jours[-1]}
    sorties = {}
    for s in bande.sorties:
        if jours[0] <= s.date <= jours[-1]:
            sorties[s.date] = sorties.get(s.date, 0) + s.nombre
    vaccins = [x for x in sante.vaccins_de_la_bande(bande, jour) if jours[0] <= x['prevu'] <= jours[-1]]

    url = url_fiche or (url_for('bandes.fiche', numero=bande.numero, _external=True) if has_request_context()
                        else f'/bandes/{bande.numero}')
    titre = Paragraph(f'Fiche de la semaine — {ferme.nom}', TITRE)
    sous = Paragraph(f'Ferme {ferme.numero} · {ferme.localite.nom}, {ferme.province.nom}'
                     + (f' · Éleveur : {eleveur.nom_complet}' if eleveur else ''), SOUS)
    infos = Paragraph(f'<b>Bande {bande.numero}</b> · bâtiment {bande.batiment.code} · '
                      f'semaine du {jours[0]:%d/%m} au {jours[-1]:%d/%m/%Y} · âge le lundi : {indicateurs.age(bande, jours[0])} jours · '
                      f'effectif au début de la semaine : <b>{quantite(v["effectif_present"] or 0)}</b> '
                      f'(mis en place : {quantite(bande.effectif_initial)} le {bande.date_mise_en_place:%d/%m/%Y})', TEXTE)
    entete = Table([[[titre, sous, infos], _qr(url, 2.6 * cm)]], colWidths=[15 * cm, 3 * cm])
    entete.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 0)]))

    tete = ['Jour', 'Âge', 'Morts', 'Aliment (sacs)', 'Pesée (g)', 'Sorties'] + (['Œufs ramassés'] if ponte else []) + ['Observations', 'Saisi']
    lignes = [tete]
    total_morts = total_sacs = total_sorties = 0
    for d in jours:
        s, p = saisies.get(d), pesees.get(d)
        morts = str(s.morts) if s else ''
        sacs = quantite(s.sacs) if s and s.sacs else ('' if not s else '0')
        poids = quantite(round(p.poids_moyen_g)) if p else ''
        sortie = quantite(sorties[d]) if d in sorties else ''
        if s:
            total_morts += s.morts
            total_sacs += s.sacs or 0
        total_sorties += sorties.get(d, 0)
        ligne = [f'{JOURS[d.weekday()]} {d:%d/%m}', str(indicateurs.age(bande, d)), morts, sacs, poids, sortie]
        if ponte:
            ligne.append(quantite(getattr(s, 'oeufs', None)) if s and getattr(s, 'oeufs', None) is not None else '')
        ligne += ['', '✓' if s else '☐']
        lignes.append(ligne)
    total = ['Total', '', str(total_morts), quantite(total_sacs), '', quantite(total_sorties)] + ([''] if ponte else []) + ['', '']
    lignes.append(total)
    largeurs = [2.9 * cm, 1.1 * cm, 1.5 * cm, 2.3 * cm, 1.8 * cm, 1.6 * cm] + ([2.2 * cm] if ponte else []) + [None, 1.2 * cm]
    largeurs[-2] = 18 * cm - sum(x for x in largeurs if x)
    t = Table(lignes, colWidths=largeurs, rowHeights=[0.8 * cm] + [1.15 * cm] * 7 + [0.8 * cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NOIR), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'), ('BACKGROUND', (0, -1), (-1, -1), FOND),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#999999')), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (1, 1), (-2, -1), 'CENTER'), ('ALIGN', (-1, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (-1, 1), (-1, -2), 12),
    ]))
    elements = [entete, Spacer(1, 0.4 * cm), Paragraph('Écrire <b>0</b> s\'il n\'y a eu aucun mort. Une case vide veut dire « pas encore noté ».', TEXTE),
                Spacer(1, 0.2 * cm), t, Spacer(1, 0.4 * cm)]

    elements.append(Paragraph('Vaccins prévus cette semaine', SECTION))
    if vaccins:
        lv = [['Jour', 'Vaccin', 'Mode', 'Fait ?']]
        for x in vaccins:
            c = x['calendrier']
            lv.append([f'{JOURS[x["prevu"].weekday()]} {x["prevu"]:%d/%m}', c.produit.nom, c.mode.lower(),
                       '✓ fait' if x['etat'] == 'fait' else '☐'])
        tv = Table(lv, colWidths=[3.5 * cm, 8 * cm, 3.5 * cm, 3 * cm])
        tv.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), BLEU), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                                ('FONTSIZE', (0, 0), (-1, -1), 9), ('GRID', (0, 0), (-1, -1), 0.4, TRAIT),
                                ('TOPPADDING', (0, 0), (-1, -1), 4), ('BOTTOMPADDING', (0, 0), (-1, -1), 4)]))
        elements.append(tv)
    else:
        elements.append(Paragraph('Aucun vaccin prévu cette semaine.', TEXTE))

    sig = Table([['Signature de l\'éleveur', 'Signature de l\'agent'], ['', '']],
                colWidths=[9 * cm, 9 * cm], rowHeights=[0.7 * cm, 2.2 * cm])
    sig.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), 9), ('TEXTCOLOR', (0, 0), (-1, 0), BLEU),
                             ('LINEBELOW', (0, 1), (-1, 1), 0.5, NOIR), ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    elements += [Spacer(1, 0.5 * cm), KeepTogether([Paragraph('Signatures', SECTION), sig]),
                 Spacer(1, 0.3 * cm),
                 Paragraph('Le QR en haut à droite ouvre la fiche de la bande dans SORRA. L\'agent reporte la fiche dans '
                           'l\'application à sa prochaine visite.', SOUS)]
    return _document(elements)
