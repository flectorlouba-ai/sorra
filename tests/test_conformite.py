"""Lot K — conformité aux maquettes, pilotée par docs/conformite/SORRA_cahier_conformite_maquettes.xlsx (openpyxl).
Pour chaque écran de bureau livré (sous-lots K1…K3) : connexion avec le profil, la page répond, le titre du tableau,
le libellé EXACT du bouton de création, CHAQUE en-tête de colonne dans l'ordre, les boutons « Excel » et « Imprimer »,
la carte sur les accueils ; pour chaque formulaire : les champs attendus, les champs calculés / automatiques en
lecture seule, « Archiver » seulement si le profil a le droit. Un écart justifié est déclaré dans ECARTS avec sa
raison : le test échoue sur tout écart non déclaré. Les données sont celles de la démonstration (fixture `demo`)."""
import html
import re

import pytest
from openpyxl import load_workbook

from app.services import cahier_bureau, conformite
from tests.conftest import connecter

XLSX = 'docs/conformite/SORRA_cahier_conformite_maquettes.xlsx'
PROFILS = {'DGE (POUFA)': 'DGE', 'Vétérinaire': 'VETO', 'Administrateur': 'ADMIN', 'Éleveur (ordinateur)': 'ELEVEUR',
           'Agent technique (ordinateur)': 'AGENT', 'Auditeur ANINF': 'AUDITEUR'}
MDP_DEMO = 'Demo-yl2-2026'
COMPTES = {'DGE': 'dge', 'VETO': 'veto', 'ADMIN': 'admin', 'ELEVEUR': 'eleveur', 'AGENT': 'agent.est', 'AUDITEUR': 'aninf'}
# Écrans livrés (sous-lots déployés) : les autres sont vérifiés quand leur sous-lot arrive
LIVRES = {('DGE', n) for n in range(1, 9)} | {('VETO', n) for n in range(1, 9)} | {('ELEVEUR', n) for n in range(1, 9)} | {('AGENT', n) for n in range(1, 9)} | {('ADMIN', n) for n in range(1, 8)} | {('AUDITEUR', n) for n in range(1, 7)}
# Titres dont une partie est vivante (code de bande, nombre, date) : on vérifie la partie fixe
TITRES = {('ELEVEUR', 3): 'Mes saisies · bande', ('ELEVEUR', 4): 'Mon argent mois par mois', ('AGENT', 2): r'Mes \d+ fermes?', ('AGENT', 4): 'Tournée du'}

# Écarts justifiés : (profil, n, quoi) → raison. Tout autre écart fait échouer le test.
ECARTS = {
    ('DGE', 6, 'colonne:Biosécurité'): 'critère absent du barème actuel (D77 : contrôles opérationnels) ; la colonne existe et affiche « — » ; sera alimentée au lot M',
    ('DGE', 6, 'colonne:Évolution'): 'les classements ne sont pas encore gardés d’un mois sur l’autre ; « — » ; lot M',
    ('DGE', 7, 'colonne:Diffusion'): 'diffusion et visa MAEDR = lot M ; « — »',
    ('DGE', 7, 'colonne:Validé MAEDR'): 'visa MAEDR = lot M ; « — »',
    ('DGE', 4, 'colonne:Bande'): 'la commande ne vise pas encore une bande (champ à venir avec les commandes par bande) ; « — »',
    ('DGE', 4, 'colonne:Mise en place'): 'date de mise en place prévue : champ à venir ; « — »',
    ('VETO', 6, 'colonne:Lots retenus'): 'rapprochement blocage ↔ lots reçus sous réserve : lot M ; « — »',
    ('VETO', 6, 'colonne:Prochain contrôle'): 'date de prochain contrôle : champ à venir ; « — »',
    ('VETO', 4, 'colonne:Lot du vaccin'): 'le numéro de lot du vaccin n’est pas saisi aujourd’hui (lot F/S) ; « — »',
    ('VETO', 4, 'archiver'): 'une ligne = une vaccination attendue d’une bande (calculée) ; l’étape du calendrier se modifie et se retire (décocher « Dans le calendrier ») par « ＋ Ajouter une étape » et la vue détaillée',
    ('AGENT', 4, 'archiver'): 'une ligne de tournée est une visite prévue ou une ferme proposée (calculée) : la visite prévue s’archive depuis « Visites »',
    ('ELEVEUR', 4, 'archiver'): 'les opérations (dépenses, achats, ventes) s’archivent une à une par leur fiche du lot A1 (écran Mon argent du téléphone / vue détaillée) ; la ligne du tableau est un mois (calculé)',
    ('ELEVEUR', 4, 'titre'): 'le bouton « 📄 Télécharger mon bilan » et le régime fiscal estimé du titre viennent avec le lot G (repris au sous-lot K4)',
}
# Écrans dont la fiche est celle d'un lot précédent (même règle : préremplie, boutons selon les droits)
FICHES_PROPRES = {('DGE', 8): 'id="form-action"'}


def _cahier():
    wb = load_workbook(XLSX, read_only=True)
    ecrans = {}
    for r in list(wb['Bureau - écrans'].iter_rows(values_only=True))[1:]:
        p = PROFILS[r[0]]
        ecrans[(p, r[1])] = {'fonction': r[2], 'bouton': r[3] if r[3] != '—' else None, 'carte': bool(r[7] and r[7].startswith('Oui')),
                             'titre': r[8], 'colonnes': [c.strip() for c in r[9].split('|')], 'indicateurs': [x.strip() for x in r[5].split('·')] if r[5] and r[5] != '—' else []}
    champs = {}
    for r in list(wb['Bureau - colonnes et champs'].iter_rows(values_only=True))[1:]:
        champs.setdefault((PROFILS[r[0]], r[1]), []).append((r[3], r[4]))
    return ecrans, champs


CAHIER, CHAMPS = _cahier()


def _page(client, profil, n):
    from app.services.bureau import FONCTIONS
    from app.models import Profil
    from flask import url_for
    client.post('/auth/deconnexion')
    connecter(client, COMPTES[profil], MDP_DEMO)
    if profil in ('ELEVEUR', 'AGENT'):
        client.post('/bureau/version-ordinateur')          # la version ordinateur des profils de terrain
    ep = FONCTIONS[Profil(profil)][n - 1][3]
    with client.application.test_request_context():
        chemin = url_for(ep)
    r = client.get(chemin, follow_redirects=True)
    return r.status_code, html.unescape(r.get_data(as_text=True))


def _entetes(page):
    return [re.sub(r'<[^>]+>', '', t).strip() for t in re.findall(r'<th[^>]*>(.*?)</th>', page, re.S)]


def test_le_module_cahier_reprend_le_xlsx():
    """Le module Python généré (cahier_bureau) est la copie exacte du classeur : colonnes, boutons, champs."""
    for (p, n), e in CAHIER.items():
        s = cahier_bureau.ecran(p, n)
        assert s['colonnes'] == e['colonnes'], (p, n)
        assert s['bouton'] == e['bouton'], (p, n)
        assert [c for c, _, _ in s['champs']] == e['colonnes'], (p, n)


@pytest.mark.parametrize('cle', sorted(LIVRES))
def test_ecran_de_bureau_conforme(client, demo, cle):
    profil, n = cle
    e = CAHIER[cle]
    code, page = _page(client, profil, n)
    assert code == 200, (cle, code)
    titre = TITRES.get(cle)
    if titre:
        assert re.search(titre, page), (cle, 'titre du tableau', titre)
    else:
        assert e['titre'] in page, (cle, 'titre du tableau', e['titre'])
    if e['bouton']:
        assert e['bouton'] in page, (cle, 'bouton de création', e['bouton'])
    ths = _entetes(page)
    manquantes = [c for c in e['colonnes'] if c not in ths and (profil, n, f'colonne:{c}') not in ECARTS]
    assert not manquantes, (cle, 'colonnes manquantes', manquantes)
    presentes = [c for c in e['colonnes'] if c in ths]
    # dans l'ordre : les positions croissent
    positions = [ths.index(c) for c in presentes]
    assert positions == sorted(positions), (cle, 'ordre des colonnes', presentes)
    assert 'Excel' in page and 'Imprimer' in page, (cle, 'outils Excel / Imprimer')
    if e['carte']:
        assert 'carte-fermes' in page or 'Carte du périmètre' in page, (cle, 'carte')
    for ind in e['indicateurs']:
        ind = re.sub(r' [A-Z]\d+$', '', ind)              # « Mortalité de la bande B4 » : le code de bande est vivant
        assert ind in page, (cle, 'indicateur', ind)


@pytest.mark.parametrize('cle', sorted(LIVRES))
def test_formulaire_de_la_fiche(client, demo, cle):
    """La fiche (template unique du tableau) porte chaque champ du cahier ; calculés et automatiques en lecture seule ;
    « Archiver » seulement si le profil a le droit."""
    profil, n = cle
    code, page = _page(client, profil, n)
    if cle in FICHES_PROPRES:
        assert FICHES_PROPRES[cle] in page, (cle, 'fiche propre absente')
        return
    m = re.search(r'<template id="modele-%s-%d"(.*?)</template>' % (profil, n), page, re.S)
    if m is None:                                   # écran en lecture seule : le clic ouvre l'élément (lien)
        assert 'Lecture seule' in cahier_bureau.ecran(profil, n)['clic'] or 'ouvre' in cahier_bureau.ecran(profil, n)['clic'] \
            or 'Télécharger' in cahier_bureau.ecran(profil, n)['clic'] or 'Qualifier' in cahier_bureau.ecran(profil, n)['clic'] \
            or 'Modifier une étape' in cahier_bureau.ecran(profil, n)['clic'] or 'clore' in cahier_bureau.ecran(profil, n)['clic'], (cle, 'pas de fiche')
        return
    fiche = m.group(1)
    s = conformite.spec(profil, n)
    for nom, type_, _ in s['champs']:
        bloc = re.search(r'<label class="fiche-champ[^"]*">\s*<span>%s(.*?)</label>' % re.escape(nom), fiche, re.S)
        assert bloc, (cle, 'champ absent de la fiche', nom)
        if type_ in ('C', 'A'):
            assert '<output' in bloc.group(0), (cle, 'champ calculé/automatique saisissable', nom)
        else:
            assert '<input' in bloc.group(0) or '<select' in bloc.group(0), (cle, 'champ saisi non saisissable', nom)
    peut_archiver = 'data-bouton="archiver"' in fiche
    attendu = 'archiver' in cahier_bureau.ecran(profil, n)['clic'].lower() or 'annuler' in cahier_bureau.ecran(profil, n)['clic'].lower()
    if (profil, n, 'archiver') not in ECARTS:
        assert peut_archiver == attendu, (cle, 'bouton Archiver', peut_archiver, attendu)


def test_types_corriges_sont_notes():
    """Chaque correction de type (cahier → application) est consignée dans docs/decisions_autonomes.md."""
    texte = open('docs/decisions_autonomes.md', encoding='utf-8').read()
    for (p, n) in conformite.CORRECTIONS:
        if (p, n) in LIVRES:
            assert f'{p} {n}' in texte or f'{p}-{n}' in texte, (p, n)


def test_ecarts_justifies_affichent_un_tiret(client, demo):
    """Jamais de chiffre inventé : une colonne en écart justifié montre « — »."""
    code, page = _page(client, 'DGE', 6)
    ths = _entetes(page)
    i = ths.index('Biosécurité')
    lignes = re.findall(r'<tr class="tr-click[^"]*"(?:.*?)</tr>', page, re.S)
    for l in lignes[:3]:
        cellules = [re.sub(r'<[^>]+>', '', c).strip() for c in re.findall(r'<td>(.*?)</td>', l, re.S)]
        if len(cellules) > i:
            assert cellules[i] == '—', cellules
