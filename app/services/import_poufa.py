"""Import de la liste POUFA (Excel) : modèle, vérification ligne par ligne, import, rapport.

Le fichier déposé est gardé dans <instance>/imports entre l'aperçu et l'import,
puis effacé. Le rapport d'import (vos lignes + une colonne « Résultat ») reste
téléchargeable un jour.
"""
import io
import os
import secrets
import time

from flask import current_app
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app import db
from app.models import Province, Utilisateur, Profil, FermeInfrastructure
from app.models.base import maintenant
from app.models.liste_deroulante import ld_choices
from app.services import fermes as regles
from app.services import geo
from app.services.fermes import normaliser_nom, normaliser_telephone

# (en-tête, clé, obligatoire, explication)
COLONNES = [
    ('Nom de la ferme', 'nom', True, 'Nom usuel de la ferme.'),
    ('Nom de l\'exploitant', 'exploitant_nom', True, 'Prénom et nom de l\'exploitant.'),
    ('Téléphone de l\'exploitant', 'exploitant_telephone', True,
     'Avec ou sans +241, espaces acceptés. Deux fermes ne peuvent pas avoir le même téléphone.'),
    ('Province', 'province', True, 'Nom (ex. Estuaire) ou code (ex. EST).'),
    ('Localité', 'localite', True,
     'Si elle n\'existe pas encore, elle sera créée. L\'aperçu signale les noms proches d\'une '
     'localité existante (ex. « N\'kok » et « Nkok ») : corrigez alors le fichier.'),
    ('Référence AMI', 'reference_ami', False, 'Facultative, mais unique.'),
    ('Cohorte (1 ou 2)', 'cohorte', False, '1 ou 2, ou vide.'),
    ('Statut', 'statut', False, 'Vide = En préparation. Sinon une valeur de la liste des statuts.'),
    ('Identifiant de l\'agent technique', 'agent', False,
     'Identifiant de connexion de l\'agent référent (ex. agent.est), ou vide.'),
    ('Latitude', 'latitude', False, 'En degrés décimaux (ex. 0,3921). Avec la longitude, ou vide.'),
    ('Longitude', 'longitude', False, 'En degrés décimaux (ex. 9,6103).'),
    ('Infrastructures', 'infrastructures', False,
     'Valeurs de la liste « Types d\'infrastructures », séparées par des points-virgules.'),
    ('Observations', 'observations', False, 'Texte libre.'),
]
ENTETES = [c[0] for c in COLONNES]
DUREE_RAPPORT = 24 * 3600


def ecrire(chemin, contenu):
    """Écrit le fichier et le date avec l'horloge de l'application : le ménage de
    dossier() compare ensuite deux heures de la même horloge."""
    with open(chemin, 'wb') as f:
        f.write(contenu)
    maintenant = time.time()
    os.utime(chemin, (maintenant, maintenant))


def dossier():
    d = os.path.join(current_app.instance_path, 'imports')
    os.makedirs(d, exist_ok=True)
    # Ménage : rapports et fichiers abandonnés de plus d'un jour
    for nom in os.listdir(d):
        chemin = os.path.join(d, nom)
        if time.time() - os.path.getmtime(chemin) > DUREE_RAPPORT:
            os.remove(chemin)
    return d


def chemin(jeton, suffixe):
    if not jeton or not jeton.replace('-', '').replace('_', '').isalnum():
        raise ValueError('jeton invalide')
    return os.path.join(dossier(), f'{jeton}{suffixe}')


# ── Modèle ──────────────────────────────────────────────────────────────

def modele():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Fermes'
    ws.append(ENTETES)
    gras = Font(bold=True, color='FFFFFF')
    fond = PatternFill('solid', fgColor='0C2461')   # bleu nuit de la charte
    for i, (titre, _, obligatoire, _) in enumerate(COLONNES, start=1):
        cellule = ws.cell(row=1, column=i)
        cellule.value = titre + (' *' if obligatoire else '')
        cellule.font, cellule.fill = gras, fond
        cellule.alignment = Alignment(wrap_text=True, vertical='center')
        ws.column_dimensions[cellule.column_letter].width = 24
    ws.freeze_panes = 'A2'
    ex = wb.create_sheet('Explications')
    ex.append(['Colonne', 'Obligatoire', 'Explication'])
    for titre, _, obligatoire, aide in COLONNES:
        ex.append([titre, 'Oui' if obligatoire else 'Non', aide])
    ex.append([])
    ex.append(['Une ligne par ferme. Ne changez pas l\'ordre des colonnes de la feuille « Fermes ».'])
    ex.append(['Valeurs possibles — Statut', ', '.join(v for v, _ in ld_choices('statuts_ferme'))])
    ex.append(['Valeurs possibles — Infrastructures',
               '; '.join(v for v, _ in ld_choices('types_infrastructures'))])
    for col, largeur in (('A', 34), ('B', 12), ('C', 110)):
        ex.column_dimensions[col].width = largeur
    for c in ex[1]:
        c.font = Font(bold=True)
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


# ── Lecture et vérification ─────────────────────────────────────────────

def _texte(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def lire(contenu):
    """Lignes du fichier : liste de (numéro de ligne Excel, {clé: texte}). Lève ValueError."""
    try:
        wb = load_workbook(io.BytesIO(contenu), read_only=True, data_only=True)
    except Exception:
        raise ValueError('Ce fichier n\'est pas un fichier Excel (.xlsx) lisible.')
    ws = wb['Fermes'] if 'Fermes' in wb.sheetnames else wb.worksheets[0]
    lignes = list(ws.iter_rows(values_only=True))
    if not lignes:
        raise ValueError('Le fichier est vide.')
    entetes = [normaliser_nom(_texte(v).rstrip('*')) for v in lignes[0]]
    attendues = [normaliser_nom(e) for e in ENTETES]
    if entetes[:len(attendues)] != attendues:
        raise ValueError('Les colonnes ne correspondent pas au modèle : téléchargez le modèle '
                         'et recopiez-y vos lignes.')
    resultat = []
    for n, valeurs in enumerate(lignes[1:], start=2):
        valeurs = list(valeurs) + [None] * len(COLONNES)
        ligne = {cle: _texte(valeurs[i]) for i, (_, cle, _, _) in enumerate(COLONNES)}
        if any(ligne.values()):
            resultat.append((n, ligne))
    return resultat


def _reference():
    provinces = Province.query.all()
    par_province = {}
    for p in provinces:
        par_province[normaliser_nom(p.nom)] = p
        par_province[normaliser_nom(p.code)] = p
    return {
        'provinces': par_province,
        'statuts': {normaliser_nom(v): v for v, _ in ld_choices('statuts_ferme')},
        'infrastructures': {normaliser_nom(v): v for v, _ in ld_choices('types_infrastructures')},
        'agents': {u.identifiant: u for u in Utilisateur.query.filter_by(profil=Profil.AGENT,
                                                                         actif=True)},
    }


def verifier(lignes):
    """Chaque ligne reçoit : erreurs (bloquantes), avertissements, et les valeurs converties."""
    ref = _reference()
    vus = {'ami': {}, 'tel': {}, 'nom': {}}
    nouvelles = {}   # (province_id, nom normalisé) → nom de la localité nouvelle
    resultats = []
    for n, l in lignes:
        r = {'ligne': n, 'brut': l, 'erreurs': [], 'avertissements': [], 'v': {}}
        e, v = r['erreurs'], r['v']
        for titre, cle, obligatoire, _ in COLONNES:
            if obligatoire and not l[cle]:
                e.append(f'« {titre} » est vide.')
        if len(normaliser_telephone(l['exploitant_telephone'])) < 7 and l['exploitant_telephone']:
            e.append('Téléphone incomplet (au moins 7 chiffres).')
        province = ref['provinces'].get(normaliser_nom(l['province'])) if l['province'] else None
        if l['province'] and province is None:
            e.append(f'Province inconnue : « {l["province"]} ».')
        v['province'] = province

        if province and l['localite']:
            existante = regles.localite_identique(province.id, l['localite'])
            if existante:
                v['localite'] = existante
            else:
                cle_loc = (province.id, normaliser_nom(l['localite']))
                nouvelles.setdefault(cle_loc, l['localite'])
                v['localite_nouvelle'] = nouvelles[cle_loc]
                r['avertissements'].append(f'Localité nouvelle : « {nouvelles[cle_loc]} » sera créée.')
                for s in regles.localites_semblables(province.id, l['localite']):
                    r['avertissements'].append(
                        f'⚠ « {l["localite"]} » ressemble à « {s.nom} » (déjà dans la province '
                        f'{province.nom}) : si c\'est la même, corrigez le fichier.')

        if l['cohorte'] and l['cohorte'] not in ('1', '2'):
            e.append('La cohorte doit être 1 ou 2.')
        v['cohorte'] = int(l['cohorte']) if l['cohorte'] in ('1', '2') else None
        if l['statut']:
            v['statut'] = ref['statuts'].get(normaliser_nom(l['statut']))
            if v['statut'] is None:
                e.append(f'Statut inconnu : « {l["statut"]} ».')
        if l['agent']:
            v['agent'] = ref['agents'].get(l['agent'].lower())
            if v['agent'] is None:
                e.append(f'Aucun agent technique actif n\'a l\'identifiant « {l["agent"]} ».')
        infras = []
        for brut in filter(None, (i.strip() for i in l['infrastructures'].split(';'))):
            valeur = ref['infrastructures'].get(normaliser_nom(brut))
            if valeur is None:
                e.append(f'Infrastructure inconnue : « {brut} ».')
            elif valeur not in infras:
                infras.append(valeur)
        v['infrastructures'] = infras

        try:
            lat = float(l['latitude'].replace(',', '.')) if l['latitude'] else None
            lon = float(l['longitude'].replace(',', '.')) if l['longitude'] else None
        except ValueError:
            lat = lon = None
            e.append('Latitude et longitude doivent être des nombres (ex. 0,3921).')
        if (lat is None) != (lon is None):
            e.append('Indiquez la latitude et la longitude, ou aucune des deux.')
        elif lat is not None:
            v['latitude'], v['longitude'] = lat, lon
            if province:
                c = geo.verifier(lat, lon, province.code)
                if c and not c['ok']:
                    r['avertissements'].append(
                        f'Position à {c["distance_km"]} km de la province {province.nom} : vérifiez-la.')

        # Doublons : avec les fermes déjà enregistrées, puis avec les lignes précédentes
        if not e:
            loc_id = v['localite'].id if v.get('localite') else None
            e += regles.doublons(l['nom'], l['exploitant_telephone'], loc_id, l['reference_ami'])
            cles = {'ami': l['reference_ami'].upper() or None,
                    'tel': normaliser_telephone(l['exploitant_telephone']),
                    'nom': (province.id if province else None,
                            normaliser_nom(l['localite']), normaliser_nom(l['nom']))}
            libelles = {'ami': 'la même référence AMI', 'tel': 'le même téléphone',
                        'nom': 'le même nom dans la même localité'}
            for k, cle in cles.items():
                if cle and cle in vus[k]:
                    e.append(f'Doublon dans le fichier : {libelles[k]} que la ligne {vus[k][cle]}.')
            if not e:
                for k, cle in cles.items():
                    if cle:
                        vus[k][cle] = n
        r['ok'] = not e
        resultats.append(r)
    return resultats


def importer(resultats, auteur):
    """Crée les fermes des lignes valides. Renvoie (fermes créées, localités créées)."""
    creees, localites = 0, {}
    for r in resultats:
        if not r['ok']:
            continue
        l, v = r['brut'], r['v']
        localite = v.get('localite')
        if localite is None:
            cle = (v['province'].id, normaliser_nom(v['localite_nouvelle']))
            if cle not in localites:
                localites[cle] = regles.creer_localite(v['province'].id, v['localite_nouvelle'],
                                                       par_admin=True)
            localite = localites[cle]
        ferme = regles.creer_ferme(
            v['province'], auteur, nom=l['nom'], exploitant_nom=l['exploitant_nom'],
            exploitant_telephone=l['exploitant_telephone'], localite=localite,
            reference_ami=l['reference_ami'].upper() or None, cohorte=v['cohorte'],
            statut=v.get('statut'), agent_id=v['agent'].id if v.get('agent') else None,
            observations=l['observations'] or None,
            latitude=v.get('latitude'), longitude=v.get('longitude'),
            gps_source='MANUELLE' if v.get('latitude') is not None else None,
            gps_date=maintenant() if v.get('latitude') is not None else None)
        ferme.infrastructures = [FermeInfrastructure(infrastructure=i) for i in v['infrastructures']]
        r['numero'] = ferme.numero
        creees += 1
    db.session.flush()
    return creees, len(localites)


def rapport(resultats):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Rapport d\'import'
    ws.append(['Ligne'] + ENTETES + ['Résultat', 'Remarques'])
    for c in ws[1]:
        c.font = Font(bold=True)
    for r in resultats:
        if r.get('numero'):
            resultat = f'Importée : {r["numero"]}'
        elif r['ok']:
            resultat = 'Valide, non importée'
        else:
            resultat = 'Refusée : ' + ' '.join(r['erreurs'])
        ws.append([r['ligne']] + [r['brut'][c[1]] for c in COLONNES]
                  + [resultat, ' '.join(r['avertissements'])])
    tampon = io.BytesIO()
    wb.save(tampon)
    return tampon.getvalue()


def nouveau_jeton():
    return secrets.token_urlsafe(16)
