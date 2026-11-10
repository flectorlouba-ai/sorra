"""Lot B — moteur générique d'imports Excel / CSV (reprise de l'existant) : modèles téléchargeables, lecture (.xlsx, .csv),
correspondance des colonnes proposée puis mémorisée, aperçu, vérification ligne à ligne, import en un lot annulable
(ce qu'il a créé est archivé, jamais supprimé), rapport Excel, origine « reprise », tout au journal."""
import csv
import io
import json
import re
import unicodedata
from datetime import date, datetime

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

from app import db
from app.models import Ferme
from app.models.base import maintenant
from app.models.imports import CorrespondanceImport, LigneImport, LotImport
from app.services.journal import enregistrer, Action


class RegleImport(Exception):
    pass


def normaliser(texte):
    t = unicodedata.normalize('NFKD', str(texte or '')).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', t).strip()


# ── Modèles d'import : (clé, libellé, obligatoire, type) ───────────────
MODELES = {
    'bandes': {
        'nom': 'Bandes (reprise de l’historique)', 'icone': '🐔',
        'colonnes': [('ferme', 'N° de ferme', True, 'texte'), ('batiment', 'Bâtiment (code)', True, 'texte'),
                     ('date_mise_en_place', 'Mise en place (AAAA-MM-JJ)', True, 'date'), ('effectif', 'Poussins mis en place', True, 'entier'),
                     ('morts_cumules', 'Morts déjà comptés', False, 'entier'), ('poids_g', 'Poids moyen au départ (g)', False, 'entier'),
                     ('type_production', 'Production (CHAIR / PONTE)', False, 'texte'), ('souche', 'Souche', False, 'texte')],
    },
    'saisies': {
        'nom': 'Saisies du jour (morts, aliment)', 'icone': '📝',
        'colonnes': [('bande', 'N° de bande', True, 'texte'), ('date', 'Jour (AAAA-MM-JJ)', True, 'date'), ('morts', 'Morts', True, 'entier'),
                     ('sacs', "Sacs d'aliment", False, 'decimal'), ('aliment', 'Aliment (nom du catalogue)', False, 'texte')],
    },
    'depenses': {
        'nom': 'Dépenses (J’ai payé)', 'icone': '💸',
        'colonnes': [('ferme', 'N° de ferme', True, 'texte'), ('date', 'Jour (AAAA-MM-JJ)', True, 'date'), ('categorie', 'Pour quoi ?', True, 'texte'),
                     ('montant', 'Montant (FCFA)', True, 'entier'), ('batiment', 'Bâtiment (code, facultatif)', False, 'texte')],
    },
}


def modele_xlsx(cle):
    m = MODELES[cle]
    wb = Workbook()
    ws = wb.active
    ws.title = cle.capitalize()
    ws.append([lib + (' *' if obl else '') for _, lib, obl, _ in m['colonnes']])
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.append(['' for _ in m['colonnes']])
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


# ── Lecture ─────────────────────────────────────────────────────────────

def _texte(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, (datetime, date)):
        return v.strftime('%Y-%m-%d')
    return str(v).strip()


def lire(contenu, nom_fichier):
    """(entêtes, lignes) ; lignes = liste de (n° de ligne, [valeurs texte]). .xlsx ou .csv (séparateur détecté)."""
    if (nom_fichier or '').lower().endswith('.csv'):
        texte = contenu.decode('utf-8-sig', errors='replace')
        try:
            dialecte = csv.Sniffer().sniff(texte[:4000], delimiters=';,\t')
        except csv.Error:
            dialecte = csv.excel
            dialecte.delimiter = ';'
        rangs = list(csv.reader(io.StringIO(texte), dialecte))
    else:
        try:
            wb = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
        except Exception:
            raise RegleImport("Ce fichier n'est pas un fichier Excel (.xlsx) ni un .csv lisible.")
        rangs = [list(r) for r in wb.worksheets[0].iter_rows(values_only=True)]
    rangs = [[_texte(v) for v in r] for r in rangs]
    rangs = [r for r in rangs if any(r)]
    if not rangs:
        raise RegleImport('Le fichier est vide.')
    entetes = [e.rstrip('* ').strip() for e in rangs[0]]
    lignes = [(i + 2, r + [''] * (len(entetes) - len(r))) for i, r in enumerate(rangs[1:])]
    return entetes, lignes


# ── Correspondance des colonnes (proposée, puis mémorisée) ──────────────

def correspondance(cle, entetes):
    """{entête du fichier: clé de colonne du modèle ou ''} : mémoire d'abord, puis rapprochement des noms."""
    memoire = {c.entete: c.colonne for c in CorrespondanceImport.query.filter_by(modele=cle)}
    cibles = {normaliser(lib): k for k, lib, _, _ in MODELES[cle]['colonnes']}
    cibles.update({normaliser(k): k for k, _, _, _ in MODELES[cle]['colonnes']})
    resultat = {}
    for e in entetes:
        if not e:
            continue
        if e in memoire:
            resultat[e] = memoire[e]
            continue
        n = normaliser(e)
        trouve = cibles.get(n) or next((k for lib, k in cibles.items() if n and (n in lib or lib in n)), '')
        resultat[e] = trouve
    return resultat


def memoriser(cle, corresp, user):
    for entete, colonne in corresp.items():
        if not colonne:
            continue
        c = CorrespondanceImport.query.filter_by(modele=cle, entete=entete).first()
        if c is None:
            db.session.add(CorrespondanceImport(modele=cle, entete=entete, colonne=colonne, cree_par=user.id))
        else:
            c.colonne = colonne


# ── Vérification et import ──────────────────────────────────────────────

def _convertir(type_, texte):
    if texte == '':
        return None
    if type_ == 'entier':
        return int(float(texte.replace(' ', '').replace(',', '.')))
    if type_ == 'decimal':
        return float(texte.replace(' ', '').replace(',', '.'))
    if type_ == 'date':
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y'):
            try:
                return datetime.strptime(texte[:10], fmt).date()
            except ValueError:
                continue
        raise ValueError('date')
    return texte


def verifier(cle, entetes, lignes, corresp, user):
    """Chaque ligne → {'n', 'brut', 'v', 'erreurs'} ; les règles métier sont celles des services existants (contrôle à blanc)."""
    m = MODELES[cle]
    position = {k: entetes.index(e) for e, k in corresp.items() if k and e in entetes}
    resultats = []
    for n, valeurs in lignes:
        brut, v, erreurs = {}, {}, []
        for k, lib, obligatoire, type_ in m['colonnes']:
            texte = valeurs[position[k]] if k in position and position[k] < len(valeurs) else ''
            brut[k] = texte
            if obligatoire and texte == '':
                erreurs.append(f'« {lib} » manque')
                continue
            try:
                v[k] = _convertir(type_, texte)
            except ValueError:
                erreurs.append(f'« {lib} » : valeur illisible ({texte})')
        if not erreurs:
            erreurs += CONTROLES[cle](v, user)
        resultats.append({'n': n, 'brut': brut, 'v': v, 'erreurs': erreurs, 'ok': not erreurs})
    return resultats


def _ferme(numero, user):
    from app.utils.permissions import filtre_perimetre
    return filtre_perimetre(Ferme.query, utilisateur=user).filter(Ferme.du_numero(numero or '')).first()


def _controle_bande(v, user):
    f = _ferme(v['ferme'], user)
    if f is None:
        return ['ferme inconnue ou hors périmètre']
    bat = next((b for b in f.batiments if b.code.upper() == (v['batiment'] or '').upper()), None)
    if bat is None:
        return [f'bâtiment « {v["batiment"]} » inconnu pour {f.numero}']
    e = []
    if v['effectif'] <= 0:
        e.append('effectif ≤ 0')
    if v['date_mise_en_place'] > date.today():
        e.append('mise en place dans le futur')
    if v.get('type_production') and v['type_production'].upper() not in ('CHAIR', 'PONTE'):
        e.append('production : CHAIR ou PONTE')
    v['_ferme'], v['_batiment'] = f, bat
    return e


def _controle_saisie(v, user):
    from app.models.bande import Bande
    from app.utils.permissions import filtre_perimetre
    b = filtre_perimetre(Bande.query, utilisateur=user).filter(Bande.numero_metier == v['bande']).first()
    if b is None:
        return ['bande inconnue ou hors périmètre']
    e = []
    if v['date'] < b.date_mise_en_place or v['date'] > date.today():
        e.append('jour hors de la bande')
    if v['morts'] < 0:
        e.append('morts < 0')
    if v.get('sacs') and not v.get('aliment'):
        e.append("aliment manquant pour les sacs")
    if v.get('aliment'):
        from app.models import Produit
        p = Produit.query.filter(Produit.nom.ilike(v['aliment'])).first()
        if p is None:
            e.append(f'aliment « {v["aliment"]} » absent du catalogue')
        v['_aliment'] = p
    v['_bande'] = b
    return e


def _controle_depense(v, user):
    f = _ferme(v['ferme'], user)
    if f is None:
        return ['ferme inconnue ou hors périmètre']
    e = []
    if v['montant'] <= 0:
        e.append('montant ≤ 0')
    if v['date'] > date.today():
        e.append('jour dans le futur')
    v['_ferme'] = f
    v['_batiment'] = next((b for b in f.batiments if b.code.upper() == (v.get('batiment') or '').upper()), None)
    return e


CONTROLES = {'bandes': _controle_bande, 'saisies': _controle_saisie, 'depenses': _controle_depense}


def _creer_bande(v, user):
    from app.services import bandes
    b = bandes.ouvrir_rattrapage(v['_ferme'], v['_batiment'], v['date_mise_en_place'], v['effectif'], v.get('morts_cumules') or 0,
                                 v.get('poids_g'), user)
    if v.get('type_production') or v.get('souche'):
        bandes.typer(b, (v.get('type_production') or 'CHAIR').upper(), v.get('souche'))
    return b


def _creer_saisie(v, user):
    from app.services import bandes
    s, _ = bandes.saisir(v['_bande'], v['date'], v['morts'], {v['_aliment']: v['sacs']} if v.get('sacs') and v.get('_aliment') else {}, user)
    return s


def _creer_depense(v, user):
    from app.services import argent
    return argent.payer(v['_ferme'], v['categorie'], v['montant'], v['_batiment'], v['date'], user)


CREATIONS = {'bandes': _creer_bande, 'saisies': _creer_saisie, 'depenses': _creer_depense}


def importer(cle, nom_fichier, resultats, user):
    """Crée les lignes valides dans un lot annulable ; chaque objet créé est noté (table, id) ; origine « reprise »."""
    lot = LotImport(modele=cle, fichier=(nom_fichier or '')[:150], cree_par=user.id, nb_lignes=len(resultats))
    db.session.add(lot)
    db.session.flush()
    for r in resultats:
        if not r['ok']:
            continue
        try:
            with db.session.begin_nested():
                o = CREATIONS[cle](r['v'], user)
                db.session.flush()
                if hasattr(o, 'statut_synchro'):
                    pass
                db.session.add(LigneImport(lot_id=lot.id, table_nom=o.__tablename__, enregistrement_id=str(o.id), ligne=r['n']))
                r['numero'] = getattr(o, 'numero', None) or str(o.id)
                lot.nb_importees += 1
        except Exception as e:
            r['ok'], r['erreurs'] = False, [str(e) or 'refusée par la règle métier']
    lot.rapport = json.dumps([{'ligne': r['n'], 'ok': r['ok'], 'erreurs': r['erreurs'], 'numero': r.get('numero')} for r in resultats])
    enregistrer(Action.IMPORT, table='lot_import', enregistrement_id=lot.id,
                detail=f'Import « {MODELES[cle]["nom"]} » · {lot.fichier} · {lot.nb_importees} / {lot.nb_lignes} ligne(s) importée(s) ({user.nom_complet})')
    return lot


def annuler(lot, user, motif):
    """Archive tout ce que le lot a créé (jamais supprimé) ; le lot est marqué annulé."""
    if lot.annule_le is not None:
        raise RegleImport('Ce lot est déjà annulé.')
    if not (motif or '').strip():
        raise RegleImport("Indiquez le motif de l'annulation.")
    import uuid
    from app.models.bande import Bande, SaisieJour
    from app.models.argent import Depense
    modeles = {'bande': Bande, 'saisie_jour': SaisieJour, 'depense': Depense}
    n = 0
    for l in lot.lignes:
        m = modeles.get(l.table_nom)
        if m is None:
            continue
        o = db.session.get(m, uuid.UUID(l.enregistrement_id))
        if o is not None and getattr(o, 'archive_le', None) is None:
            o.archive_le, o.archive_par = maintenant(), user.id
            if hasattr(o, 'statut') and l.table_nom == 'bande':
                pass
            n += 1
    lot.annule_le, lot.annule_par, lot.motif_annulation = maintenant(), user.id, motif.strip()[:300]
    enregistrer(Action.ARCHIVAGE, table='lot_import', enregistrement_id=lot.id,
                detail=f'Lot d\'import {lot.id} annulé par {user.nom_complet} — {motif.strip()[:300]} · {n} enregistrement(s) archivé(s)')
    return n


def rapport_xlsx(lot):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapport'
    ws.append([f'SORRA — import « {MODELES[lot.modele]["nom"]} » · {lot.fichier} · {lot.cree_le:%d/%m/%Y %H:%M}'])
    ws['A1'].font = Font(bold=True)
    ws.append(['Ligne', 'Résultat', 'Numéro créé', 'Erreurs'])
    for c in ws[2]:
        c.font = Font(bold=True)
    for r in json.loads(lot.rapport or '[]'):
        ws.append([r['ligne'], 'importée' if r['ok'] else 'refusée', r.get('numero') or '', ' ; '.join(r['erreurs'])])
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()
