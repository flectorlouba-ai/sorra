"""Lots tracés et QR codes.

Le QR code est dessiné par reportlab (déjà utilisé pour les PDF) : aucune
bibliothèque ni aucun service de plus. Il ne contient que l'adresse publique
du site suivie d'un code tiré au hasard.
"""
import io
import ipaddress
import re
import secrets
from urllib.parse import urlsplit

from reportlab.graphics.barcode import qrencoder
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app import db
from app.models.bande import MotifSortie
from app.models.journal import JournalAudit
from app.models.tracabilite import LotTrace
from app.services import parametres
from app.services.journal import enregistrer, Action
from app.services.numerotation import prochain_rang
from app.services.rapports_pdf import NOIR, BLEU

MOTIFS_TRACES = (MotifSortie.ABATTOIR, MotifSortie.VENTE)
FORME_CODE = re.compile(r'^[A-Za-z0-9_-]{8,40}$')


def creer_lot(sortie, user):
    """Lot d'une sortie vers un abattoir ou d'une vente ; rien pour « Autre »."""
    if sortie.motif not in MOTIFS_TRACES:
        return None
    bande = sortie.bande
    rang = prochain_rang('LOT', bande.numero)
    lot = LotTrace(numero=f'{bande.numero}-S{rang}', code=secrets.token_urlsafe(16), sortie=sortie,
                   ferme_id=bande.ferme_id, cree_par=user.id if user else None)
    db.session.add(lot)
    return lot


def adresse(lot):
    base = (parametres.obtenir('tracabilite.adresse_publique') or '').rstrip('/')
    return f'{base}/q/{lot.code}'


def adresse_provisoire():
    """Vrai tant que l'adresse publique est en http avec une adresse IP (ou sans nom de
    domaine) : les étiquettes ne doivent pas être imprimées pour de vrai."""
    url = urlsplit((parametres.obtenir('tracabilite.adresse_publique') or '').strip())
    hote = url.hostname or ''
    try:
        ipaddress.ip_address(hote)
        est_ip = True
    except ValueError:
        est_ip = hote in ('', 'localhost')
    return url.scheme != 'https' and est_ip


def lot_du_code(code):
    """Lot actif correspondant au code lu, ou None (code inconnu ou lot annulé)."""
    if not code or not FORME_CODE.match(code):
        return None
    lot = LotTrace.query.filter_by(code=code).first()
    return lot if lot and not lot.annule else None


def noter_lecture(code, lot):
    """Chaque lecture est inscrite au journal (date et adresse IP)."""
    if lot:
        enregistrer(Action.LECTURE_QR, table='lot_trace', enregistrement_id=lot.id,
                    detail=f'Lecture du QR code du lot {lot.numero}')
    else:
        enregistrer(Action.LECTURE_QR, table='lot_trace',
                    detail=f'Code inconnu ou lot annulé : « {(code or "")[:40]} »')


def lectures(lot):
    return (JournalAudit.query.filter_by(action=Action.LECTURE_QR, table_nom='lot_trace',
                                         enregistrement_id=str(lot.id))
            .order_by(JournalAudit.horodatage.desc()))


def annuler(lot, motif):
    lot.annule = True
    lot.motif_annulation = motif


# ── Dessin du QR code ───────────────────────────────────────────────────

def svg(texte, marge=4):
    """QR code en SVG (carrés noirs sur fond blanc), pour l'écran."""
    qr = qrencoder.QRCode(None, qrencoder.QRErrorCorrectLevel.M)
    qr.addData(texte)
    qr.make()
    n = qr.getModuleCount()
    cote = n + 2 * marge
    carres = ''.join(f'M{c + marge},{r + marge}h1v1h-1z'
                     for r, ligne in enumerate(qr.modules) for c, noir in enumerate(ligne) if noir)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {cote} {cote}" shape-rendering="crispEdges">'
            f'<rect width="{cote}" height="{cote}" fill="#fff"/><path d="{carres}" fill="#000"/></svg>')


def etiquettes(lot, colonnes=3, lignes=7):
    """Planche A4 d'étiquettes (21 par défaut) : QR code, n° du lot, ferme, date."""
    tampon = io.BytesIO()
    c = canvas.Canvas(tampon, pagesize=A4)
    c.setTitle(f'Étiquettes {lot.numero}')
    largeur_page, hauteur_page = A4
    marge_x, marge_y = 8 * mm, 10 * mm
    w = (largeur_page - 2 * marge_x) / colonnes
    h = (hauteur_page - 2 * marge_y) / lignes
    url = adresse(lot)
    s = lot.sortie
    ferme = lot.ferme
    for i in range(colonnes * lignes):
        x = marge_x + (i % colonnes) * w
        y = hauteur_page - marge_y - (i // colonnes + 1) * h
        c.setStrokeColor(BLEU)
        c.setLineWidth(0.3)
        c.setDash(2, 2)
        c.rect(x, y, w, h)
        c.setDash()
        taille = h - 6 * mm
        widget = QrCodeWidget(url, barLevel='M', barBorder=1)
        b = widget.getBounds()
        d = Drawing(taille, taille, transform=[taille / (b[2] - b[0]), 0, 0, taille / (b[3] - b[1]), 0, 0])
        d.add(widget)
        renderPDF.draw(d, c, x + 2 * mm, y + 3 * mm)
        tx = x + taille + 4 * mm
        c.setFillColor(NOIR)
        c.setFont('Helvetica-Bold', 7.5)
        c.drawString(tx, y + h - 8 * mm, lot.numero)
        c.setFont('Helvetica', 7)
        c.drawString(tx, y + h - 12 * mm, ferme.nom[:24])
        c.drawString(tx, y + h - 15.5 * mm, f'{ferme.localite.nom[:16]} · {ferme.province.nom[:14]}')
        c.drawString(tx, y + h - 19 * mm, f'Sortie du {s.date.strftime("%d/%m/%Y")}')
        c.setFillColor(BLEU)
        c.setFont('Helvetica-Bold', 7)
        c.drawString(tx, y + 6 * mm, 'Produit au Gabon')
    c.showPage()
    c.save()
    return tampon.getvalue()
