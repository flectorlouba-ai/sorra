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


# ── Terrain (téléphone) : K4 éleveur, K5 agent / opérateur ──────────────

TERRAIN_ROUTES = {
    ('maquettes_sorra_eleveur_epuree.html', 1): (None, '/auth/connexion'), ('maquettes_sorra_eleveur_epuree.html', 2): ('eleveur', '/'),
    ('maquettes_sorra_eleveur_epuree.html', 3): ('eleveur', '/livraisons/mes-livraisons'), ('maquettes_sorra_eleveur_epuree.html', 4): ('eleveur', '/bandes/ouvrir'),
    ('maquettes_sorra_eleveur_epuree.html', 5): ('eleveur', '/saisie-du-jour'), ('maquettes_sorra_eleveur_epuree.html', 6): ('eleveur', '/saisie-du-jour'),
    ('maquettes_sorra_eleveur_epuree.html', 7): ('eleveur', '/aller/peser'), ('maquettes_sorra_eleveur_epuree.html', 8): ('eleveur', '/aller/sortie'),
    ('maquettes_sorra_eleveur_epuree.html', 9): ('eleveur', '/aller/malade'), ('maquettes_sorra_eleveur_epuree.html', 10): ('eleveur', '/'),
    ('maquettes_sorra_eleveur_epuree.html', 11): ('eleveur', '/vaccins-et-soins'), ('maquettes_sorra_eleveur_epuree.html', 12): ('eleveur', '/bandes/mes-bandes'),
    ('maquettes_sorra_eleveur_epuree.html', 13): ('eleveur', '/'),
    ('maquette_sorra_multibandes.html', 1): ('eleveur', '/saisie-du-jour'), ('maquette_sorra_8tuiles.html', 1): ('eleveur', '/'),
    ('maquette_sorra_entretien.html', 1): ('eleveur', '/'), ('maquette_sorra_entretien.html', 2): ('eleveur', '/entretien'),
    ('maquette_sorra_entretien.html', 3): ('eleveur', '/entretien/panne'), ('maquette_sorra_entretien.html', 4): ('eleveur', '/entretien'),
    ('maquette_sorra_entretien.html', 5): ('eleveur', '/bandes/ouvrir'),
    ('maquettes_sorra_lotA.html', 1): ('eleveur', '/aller/peser'), ('maquettes_sorra_lotA.html', 2): ('eleveur', '/aller/peser'),
    ('maquettes_sorra_lotA.html', 3): ('eleveur', '/aller/peser'), ('maquettes_sorra_lotA.html', 4): ('eleveur', '/bandes/mes-bandes'),
    ('maquettes_sorra_lotA.html', 5): ('eleveur', '/bandes/ouvrir'),
    ('maquettes_sorra_terrain_ajouts.html', 7): ('eleveur', '/ma-bande'),
    ('maquette_argent.html', 1): ('eleveur', '/mon-argent?periode=tout'), ('maquette_argent.html', 2): ('eleveur', '/mon-argent/fiscalite'),
    ('maquette_argent.html', 3): ('eleveur', '/mon-argent/bilan'),
    ('maquettes_sorra_gps_terrain.html', 5): ('eleveur', '/mon-compte'),
    # K5 — agent, opérateur, GPS, notifications, actions
    ('maquettes_sorra_terrain.html', 1): ('agent.est', '/'), ('maquettes_sorra_terrain.html', 2): ('agent.est', '/terrain/tournee'),
    ('maquettes_sorra_terrain.html', 3): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_terrain.html', 4): ('agent.est', '/terrain/saisir'),
    ('maquettes_sorra_terrain.html', 5): ('agent.est', '/terrain/visite'), ('maquettes_sorra_terrain.html', 6): ('agent.est', '/hors-ligne/a-verifier'),
    ('maquettes_sorra_terrain.html', 7): ('agent.est', '/terrain/stock'), ('maquettes_sorra_terrain.html', 8): ('agent.est', '/terrain/nouvel-eleveur'),
    ('maquettes_sorra_terrain.html', 9): ('agent.est', '/terrain/moi'), ('maquettes_sorra_terrain.html', 10): ('abattoir.owendo', '/'),
    ('maquettes_sorra_terrain.html', 11): ('abattoir.owendo', '/operateur/scanner'), ('maquettes_sorra_terrain.html', 12): ('abattoir.owendo', '/operateur/scanner'),
    ('maquettes_sorra_terrain.html', 13): ('abattoir.owendo', '/operateur/scanner'), ('maquettes_sorra_terrain.html', 14): ('abattoir.owendo', '/operateur/scanner'),
    ('maquettes_sorra_terrain.html', 15): ('abattoir.owendo', '/operateur/scanner'), ('maquettes_sorra_terrain.html', 16): ('abattoir.owendo', '/operateur/attendus'),
    ('maquettes_sorra_terrain.html', 17): ('abattoir.owendo', '/operateur/receptions'),
    ('maquettes_sorra_lot19.html', 1): ('abattoir.owendo', '/'), ('maquettes_sorra_lot19.html', 2): ('abattoir.owendo', '/operateur/scanner'),
    ('maquettes_sorra_lot19.html', 3): ('abattoir.owendo', '/operateur/scanner'), ('maquettes_sorra_lot19.html', 4): ('abattoir.owendo', '/operateur/scanner'),
    ('maquettes_sorra_lot19.html', 5): ('abattoir.owendo', '/operateur/scanner'), ('maquettes_sorra_lot19.html', 6): ('abattoir.owendo', '/operateur/scanner'),
    ('maquettes_sorra_gps_terrain.html', 1): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_gps_terrain.html', 2): ('agent.est', '/terrain/fermes'),
    ('maquettes_sorra_gps_terrain.html', 3): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_gps_terrain.html', 4): ('agent.est', '/terrain/fermes'),
    ('maquettes_sorra_gps_terrain.html', 6): ('agent.est', '/terrain/visite'), ('maquettes_sorra_gps_terrain.html', 7): ('agent.est', '/terrain/tournee'),
    ('maquettes_sorra_gps_terrain.html', 8): ('agent.est', '/terrain/nouvelle-ferme'), ('maquettes_sorra_gps_terrain.html', 9): ('agent.est', '/terrain/nouvelle-ferme'),
    ('maquettes_sorra_gps_terrain.html', 10): ('agent.est', '/terrain/ferme-provisoire'), ('maquettes_sorra_gps_terrain.html', 11): ('agent.est', '/terrain/ferme-provisoire'),
    ('maquettes_sorra_gps.html', 1): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_gps.html', 2): ('agent.est', '/terrain/fermes'),
    ('maquettes_sorra_gps.html', 3): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_gps.html', 4): ('agent.est', '/terrain/fermes'),
    ('maquettes_sorra_gps.html', 5): ('agent.est', '/terrain/fermes'), ('maquettes_sorra_gps.html', 6): ('agent.est', '/terrain/visite'),
    ('maquettes_sorra_gps.html', 9): ('agent.est', '/terrain/tournee'),
    ('maquettes_sorra_terrain_ajouts.html', 1): ('eleveur', '/moi/notifications'), ('maquettes_sorra_terrain_ajouts.html', 2): ('eleveur', '/moi/notifications'),
    ('maquettes_sorra_terrain_ajouts.html', 3): ('agent.est', '/moi/notifications'), ('maquettes_sorra_terrain_ajouts.html', 4): ('agent.est', '/'),
    ('maquettes_sorra_terrain_ajouts.html', 5): ('agent.est', '/terrain/actions'), ('maquettes_sorra_terrain_ajouts.html', 6): ('agent.est', '/terrain/actions'),
}
# Boutons qui n'apparaissent que dans un état précis (après un geste, avec une donnée) : déclarés, avec la raison
ECARTS_TERRAIN = {
    ('maquettes_sorra_eleveur_epuree.html', 5, 'Envoyer ✓'): 'visible seulement quand la saisie du jour n’est pas encore faite (données de démo : déjà saisie)',
    ('maquettes_sorra_lotA.html', 1, '＋ Ajouter une saisie'): 'la liste générique de la maquette est illustrée par la pesée (« ＋ Ajouter une pesée ») ; les saisies du jour se font par l’écran dédié',
    ('maquettes_sorra_lotA.html', 1, '›'): 'chevron de ligne : présent sur les lignes (data-fiche)',
    ('maquettes_sorra_lotA.html', 2, '✕'): 'fenêtre : ✕ présent dans #fen-fiche',
    ('maquettes_sorra_lotA.html', 3, '✕'): 'fenêtre : ✕ présent dans #fen-fiche',
    ('maquettes_sorra_lotA.html', 4, '✕'): 'fenêtre : ✕ présent dans #fen-fiche',
    ('maquettes_sorra_lotA.html', 4, '📞 Appeler Paul'): 'nom fictif ; le bouton « 📞 Appeler <prénom de l’agent> » existe sur la fiche d’une bande clôturée',
    ('maquettes_sorra_lotA.html', 5, '✕'): 'fenêtre : ✕ présent dans #fen-fiche',
    ('maquettes_sorra_lotA.html', 5, 'Ouvrir la bande'): 'visible seulement quand des poussins attendent une bande (données de démo : aucun)',
    ('maquettes_sorra_lotA.html', 2, 'Enregistrer'): 'bouton de la fenêtre d’ajout : « Enregistrer » présent dans le formulaire ouvert',
    ('maquettes_sorra_lotA.html', 3, 'Enregistrer la modification'): 'présent dans la fiche préremplie (template) d’une ligne',
    ('maquette_argent.html', 1, '›'): 'chevron de la carte Ma fiscalité (carte-fleche)',
    # K5 — sous-états atteints après un geste (scan d'un lot, relevé GPS, étape 2 de l'enrôlement) ou valeurs fictives
    ('maquettes_sorra_terrain.html', 1, "🚗 Ma tournée 4 fermes aujourd'hui 4"): 'valeurs fictives : la tuile « 🚗 Ma tournée » affiche le vrai nombre',
    ('maquettes_sorra_terrain_ajouts.html', 4, "🚗 Ma tournée 4 fermes aujourd'hui 4"): 'valeurs fictives : la tuile « 🚗 Ma tournée » affiche le vrai nombre',
    ('maquettes_sorra_terrain.html', 6, 'Valider'): 'bouton de la feuille d’arbitrage, ouverte en touchant une saisie à vérifier',
    ('maquettes_sorra_terrain.html', 8, 'Suivant ›'): 'étape 2 de l’enrôlement (nouvelle ferme) après l’étape 1',
    ('maquettes_sorra_terrain.html', 12, '✓ Valider la réception'): 'après le scan d’un lot (écran du lot)',
    ('maquettes_sorra_terrain.html', 13, 'Valider avec cet écart'): 'après le scan, écart constaté ; libellé de la maquette plus récente : « Valider avec l’écart » (lot 19)',
    ('maquettes_sorra_terrain.html', 14, "📞 Appeler l'agent de la ferme"): 'après le scan d’un QR déjà reçu',
    ('maquettes_sorra_terrain.html', 15, 'Je les reçois et je les garde à part'): 'après le scan d’un lot non validable (écran du lot)',
    ('maquettes_sorra_lot19.html', 3, 'Valider la réception'): 'après le scan d’un lot',
    ('maquettes_sorra_lot19.html', 4, "Valider avec l'écart"): 'après le scan, écart constaté (scanner.js)',
    ('maquettes_sorra_lot19.html', 5, "Appeler l'agent de la ferme"): 'après le scan d’un QR déjà reçu',
    ('maquettes_sorra_lot19.html', 5, 'Scanner un autre lot'): 'après le scan d’un QR déjà reçu',
    ('maquettes_sorra_lot19.html', 6, 'Recevoir sous réserve'): 'après le scan d’un lot non validable ; libellé gardé : « Je les reçois et je les garde à part » (maquette terrain) — « sous réserve » est un mot technique interdit chez l’opérateur (règle du lot 19, testée)',
    ('maquettes_sorra_lot19.html', 6, 'Refuser le lot'): 'après le scan d’un lot non validable',
    ('maquettes_sorra_gps.html', 1, 'Relever la position ici'): 'fiche d’une ferme sans position (encadré orange)',
    ('maquettes_sorra_gps.html', 2, 'Utiliser cette position (précision insuffisante)'): 'écran du relevé ; libellé de la maquette plus récente : « ✓ Garder cette position » (gps_terrain)',
    ('maquettes_sorra_gps.html', 3, 'Garder quand même (motif obligatoire)'): 'écran du relevé après contrôle de province (bouton « Garder quand même »)',
    ('maquettes_sorra_gps.html', 3, 'Relever à nouveau'): 'écran du relevé, après un contrôle de province',
    ('maquettes_sorra_gps.html', 3, 'La province de la ferme est bien celle-ci'): 'écran du relevé, après un contrôle de province',
    ('maquettes_sorra_gps.html', 4, 'Enregistrer la correction'): 'écran de correction d’une position',
    ('maquettes_sorra_gps.html', 9, 'Y aller'): 'présent (« 🧭 Y aller ») quand la ferme a une position',
    ('maquettes_sorra_gps_terrain.html', 1, '📍 Relever la position ici'): 'fiche d’une ferme sans position',
    ('maquettes_sorra_gps_terrain.html', 2, '✓ Garder cette position'): 'écran du relevé (/terrain/fermes/<n°>/position)',
    ('maquettes_sorra_gps_terrain.html', 4, 'Enregistrer la correction'): 'écran de correction d’une position',
    ('maquettes_sorra_gps_terrain.html', 7, '🧭 Y aller'): 'présent quand la ferme de la tournée a une position',
    ('maquettes_sorra_gps_terrain.html', 8, 'Suivant ›'): 'étape 2 de l’enrôlement',
    ('maquettes_sorra_gps_terrain.html', 9, 'Oui → ajouter ce nouvel éleveur à EST-009'): 'valeur fictive ; proposition affichée quand une ferme proche existe',
    ('maquettes_sorra_gps_terrain.html', 10, 'Ferme P-0412'): 'valeur fictive (numéro provisoire)',
    ('maquettes_sorra_gps_terrain.html', 10, 'KANGO-4821'): 'valeur fictive (identifiant provisoire)',
    ('maquettes_sorra_terrain.html', 7, 'Voir'): 'bouton « Voir » des commandes : visible quand une commande existe pour la ferme choisie',
    ('maquettes_sorra_terrain.html', 10, '📷 Recevoir un lot scanner le QR'): 'texte de la tuile réparti sur deux lignes : « Recevoir un lot » + « scanner le QR » (présents)',
    ('maquettes_sorra_gps.html', 2, 'Utiliser cette position'): 'écran du relevé ; libellé de la maquette plus récente : « ✓ Garder cette position » (gps_terrain)',
    ('maquettes_sorra_gps.html', 3, 'La province de la ferme est fausse → corriger (ADMIN)'): 'écran du relevé après contrôle de province ; la correction passe par l’administrateur',
    ('maquettes_sorra_terrain_ajouts.html', 4, 'Voir'): 'encadré « 🎯 Mes actions » (« Voir tout › ») : visible quand l’agent a des actions',
    ('maquettes_sorra_terrain_ajouts.html', 6, 'Enregistrer'): 'bouton de la feuille d’une action : visible quand l’agent a des actions (template de la ligne)',
}
TERRAIN_LIVRE = {k for k in TERRAIN_ROUTES}


def _page_terrain(client, ident, chemin):
    client.post('/auth/deconnexion')
    if ident:
        connecter(client, ident, MDP_DEMO)
    r = client.get(chemin, follow_redirects=True)
    return r.status_code, html.unescape(r.get_data(as_text=True))


def _ecrans_terrain():
    wb = load_workbook(XLSX, read_only=True)
    ecrans = []
    for r in list(wb['Terrain - écrans'].iter_rows(values_only=True))[1:]:
        cle = (r[2], r[4])
        if cle in TERRAIN_LIVRE:
            ecrans.append((cle, r[5], [b.strip() for b in (r[7] or '').split(',') if b.strip() and b.strip() != '—']))
    return ecrans


@pytest.mark.parametrize('cle,ecran,boutons', _ecrans_terrain(), ids=lambda x: str(x) if isinstance(x, tuple) else None)
def test_ecran_terrain_conforme(client, demo, cle, ecran, boutons):
    """Chaque écran du téléphone répond, en style terrain, avec ses boutons principaux (ou un écart déclaré)."""
    ident, chemin = TERRAIN_ROUTES[cle]
    code, page = _page_terrain(client, ident, chemin)
    assert code == 200, (cle, ecran, code)
    if ident:
        assert 'theme-terrain' in page, (cle, 'style terrain')
    for b in boutons:
        if (cle[0], cle[1], b) in ECARTS_TERRAIN:
            continue
        assert b in page, (cle, ecran, 'bouton', b)


def test_mon_argent_douze_mois_bilan_fiscalite(client, demo):
    """Lot G / K4 : 12 mois, Gagné / Dépensé / Bénéfice, graphique, bilan PDF (2 pages, journalisé), fiscalité ; jamais le vétérinaire."""
    from app.models import JournalAudit
    _page_terrain(client, 'eleveur', '/')
    page = html.unescape(client.get('/mon-argent?periode=tout').get_data(as_text=True))
    for t in ('12 mois', 'Gagné', 'Dépensé', 'Bénéfice', 'Mois par mois', 'data-graphe-argent', '📄 Télécharger mon bilan (PDF)', '🏛️ Ma fiscalité', 'Régime estimé'):
        assert t in page, t
    page = html.unescape(client.get('/mon-argent/fiscalite').get_data(as_text=True))
    for t in ("Chiffre d'affaires de l'année", 'Mon régime estimé', 'Impôt synthétique libératoire', '📅 Mes rappels', 'Déclaration annuelle',
              'Estimation indicative, seuils réglables, à valider avec la DGI. SORRA ne remplace pas un comptable.'):
        assert t in page, t
    page = html.unescape(client.get('/mon-argent/bilan').get_data(as_text=True))
    assert '⬇️ Enregistrer le PDF' in page and '⤴ Partager' in page and 'À montrer à la banque, au comptable ou à la DGE' in page
    r = client.get('/mon-argent/bilan.pdf')
    assert r.status_code == 200 and r.data[:4] == b'%PDF' and r.data.count(b'/Type /Page') >= 2
    assert JournalAudit.query.filter(JournalAudit.detail.contains('Mini bilan')).count() == 1
    client.post('/auth/deconnexion')
    connecter(client, 'veto', MDP_DEMO)
    assert client.get('/mon-argent/bilan.pdf?ferme=EST-001').status_code == 403
    assert client.get('/mon-argent/fiscalite?ferme=EST-001').status_code == 403
    client.post('/auth/deconnexion')
    connecter(client, 'agent.est', MDP_DEMO)                      # l'agent, pour une ferme de son périmètre
    assert client.get('/mon-argent/bilan.pdf?ferme=EST-001').status_code == 200
    from app.services import bilan
    assert bilan.fiscalite(0)['code'] == 'ISL' and bilan.fiscalite(45_000_000)['code'] == 'RSI' and bilan.fiscalite(90_000_000)['code'] == 'réel'
    assert bilan.fiscalite(28_165_000)['pct'] == 94 and bilan.fiscalite(28_165_000)['proche']
