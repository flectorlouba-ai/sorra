# Lot K — Conformité totale aux maquettes (en cours)

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
| K1 — DGE + Vétérinaire | 16 | 16 (colonnes, boutons, indicateurs, carte, fiche) | 9 colonnes « — » (Biosécurité, Évolution, Diffusion, Validé MAEDR, Bande et Mise en place des commandes, Lots retenus, Prochain contrôle, Lot du vaccin) + archivage d'une étape vaccinale par la fenêtre dédiée | 0 | (au déploiement) |
| K3 — Éleveur + Agent (bureau) | 16 | | | | |
| K2 — Administrateur + Auditeur | 13 | | | | |
| K4 — téléphone Éleveur | | | | | |
| K5 — téléphone Agent, Opérateur, GPS, notifications, actions | | | | | |

Déployé sur la démo : voir `docs/rapport_suite.md` (une ligne par sous-lot).
