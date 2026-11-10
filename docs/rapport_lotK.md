# Lot K — Conformité totale aux maquettes

Critère d'acceptation de tous les écrans : `docs/conformite/SORRA_cahier_conformite_maquettes.xlsx`.
Correspondance écrans ↔ routes : `docs/conformite/correspondance.csv` ; captures « avant » : `docs/conformite/avant/`.

## Socle (K1)
- `app/services/cahier_bureau.py` : le cahier recopié en Python (généré du xlsx, 45 écrans, 352 champs).
- `app/services/conformite.py` : un fournisseur de lignes par écran, types corrigés (`CORRECTIONS`), fiche au clic
  (valeurs, droits, pied « créé par · le · n modifications · inscrit au journal »), gestes (`GESTES`) et créations
  (`CREATIONS`) par les règles existantes.
- `app/templates/_tableau.html` + `static/js/tableaux.js` : titre, filtres Toutes / Province / Période / recherche,
  « 🖨️ Imprimer » et « ⬇️ Excel » côté serveur, colonnes exactes, un `<template>` de fiche par tableau (champs
  calculés / automatiques en lecture seule, Enregistrer la modification · Archiver · Fermer selon les droits),
  fenêtre de création vide (champs saisis seuls) ; `_carte.html` : carte du périmètre réutilisable.
- Les anciens tableaux restent, repliés en « Vue détaillée » (la maquette est un minimum).
- `tests/test_conformite.py` : piloté par le xlsx ; écarts déclarés dans `ECARTS` (raison + lot) ; `demo` fixture.

## Sous-lots
| Sous-lot | Écrans | Conformes | Écarts justifiés | Non conformes | Version |
|---|---|---|---|---|---|
| K1 — DGE + Vétérinaire | 16 | 16 (colonnes, boutons, indicateurs, carte, fiche) | 9 colonnes « — » (Biosécurité, Évolution, Diffusion, Validé MAEDR, Bande et Mise en place des commandes, Lots retenus, Prochain contrôle, Lot du vaccin) + archivage d'une étape vaccinale par la fenêtre dédiée | 0 | 2026-11-10-b7b943f |
| K3 — Éleveur + Agent (bureau) | 16 | 16 | tournée : pas d'archivage d'une ligne calculée ; Mon argent : opérations archivées une à une (fiche du lot A1), bouton bilan PDF et régime fiscal au lot G (K4) | 0 | 2026-11-10-1595e4d |
| K2 — Administrateur + Auditeur | 13 | 13 | « Modifié le » de la matrice des droits : « — » (pas d'historique) | 0 | 2026-11-10-3f2d408 |
| K4 — téléphone Éleveur | 30 écrans + Mon argent (3) | 33 | boutons d'un état précis déclarés (`ECARTS_TERRAIN`) ; nom fictif « Paul » | 0 | 2026-11-10-926e3cf |
| K5 — téléphone Agent, Opérateur, GPS, notifications, actions | 54 | 54 | sous-états après un geste (scan, relevé GPS, étape 2 de l'enrôlement, feuille d'une action) et valeurs fictives déclarés ; « Je les reçois et je les garde à part » gardé (mot technique interdit) | 0 | (au déploiement) |

Déployé sur la démo : voir `docs/rapport_suite.md` (une ligne par sous-lot).

## Bilan (étape 4 — preuve visuelle)
- `docs/conformite/rapport_conformite.html` : 132 écrans, maquette à gauche / application à droite — **91 conformes, 41 écarts
  justifiés, 0 non conforme**. Les écarts sont tous déclarés dans `tests/test_conformite.py` (`ECARTS`, `ECARTS_TERRAIN`) : un
  écart non déclaré fait échouer la suite.
- `docs/conformite/controle_rempli.xlsx` : l'onglet « Contrôle » rempli (état, justification, capture).
- `docs/conformite/apres/` : 131 captures (bureau 1440 × 900, téléphone 390 × 844) ; la 132ᵉ (page publique du QR) n'a pas
  de numéro de démo.
- Migrations ajoutées : 0030 (seuils fiscaux et rappel). Tests de conformité : 203 (`tests/test_conformite.py`).
- À regarder en priorité dans `rapport_conformite.html` : les accueils (DGE, vétérinaire, éleveur, agent), « Élevages », « Mon
  argent » (téléphone) et « Mes actions » de l'agent — ce sont les écrans que le jury verra d'abord.
- Limite connue : le jeu de démonstration n'a presque pas de ventes ; le graphique et le bilan de l'éleveur sont donc presque
  vides (à enrichir : `deploiement/demo/donnees_demo.json`).

Déployé sur la démo : oui (chaque sous-lot) — dernière version : voir `docs/rapport_suite.md`.
