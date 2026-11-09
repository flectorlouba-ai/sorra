# SORRA — Chiffres (9 novembre 2026)

Tous les chiffres sont tirés du dépôt (`main`, commit `2d9a43a`) et du serveur de démonstration.

## Code et tests

| Élément | Nombre |
|---|---|
| Tests automatiques (suite complète) | **434** : 433 réussis, 1 ignoré (le test réservé à PostgreSQL, joué sur le serveur à chaque déploiement). Dernière suite complète : 13 min 23. |
| Fonctions de test | 382, dans 37 fichiers (certaines sont jouées plusieurs fois, une par profil ou par cas) |
| Lignes de Python de l'application | 15 045 (`app/`) |
| Lignes de Python des tests | 7 620 (`tests/`) |
| Adresses (routes) de l'application | 198 (voir `matrice_droits.csv`) |
| Écrans (pages affichées) | 122 adresses qui affichent une page, hors exports CSV et PDF, images et fichiers ; 142 gabarits HTML |
| Profils | 9 : ADMIN, DGE, AGENT, VETO, ELEVEUR, AUDITEUR, BCEG, MAEDR, OPÉRATEUR. L'opérateur se décline en 4 types : abattoir, marché, acheteur, distributeur. |
| Styles d'écran | 2 : terrain (éleveur, agent, opérateur) et bureau (les autres) |
| Migrations de base de données | 22 (0001 à 0022) |
| Commits sur `main` | 44, du 8 au 9 novembre 2026 |

## Lots livrés

21 lots : 0, 0 bis, 1 à 13, 15 à 19, 19 ter. Il n'y a pas de lot 14. S'y ajoutent des correctifs (cache des mises à jour, relecture des lots 15 à 18, contraste des boutons) et la mise en ligne de la démonstration.

## Cahier des charges (68 fonctions)

| Priorité du cahier | Fonctions | Fait | Partiel | Prévu | Feuille de route |
|---|---|---|---|---|---|
| Obligatoire MVP | 36 | 34 | 2 | — | — |
| Phase ultérieure | 18 | 15 | 1 | 1 | 1 |
| À arbitrer | 5 | 2 | — | — | 3 |
| Évolutive | 9 | 1 | 1 | — | 7 |
| **Total** | **68** | **52** | **4** | **1** | **11** |

Détail : `fonctions_etat.csv`.

## Démonstration

- **Adresse** : https://sorra.performyl.com (HTTPS, données fictives, bandeau sur toutes les pages)
- **Dernier déploiement** : 9 novembre 2026 à 21 h 20 UTC, version `2026-11-09-2d9a43a`, étiquette GitHub `demo-20261109-2219`. Contrôles réussis : connexion d'un compte de chaque profil, autres applications du serveur inchangées, journaux sans erreur.
- **13 comptes de démonstration**, mot de passe commun `Demo-yl2-2026` (public, protégé : changement de mot de passe, de téléphone et activation de la 2FA bloqués ; verrouillage par compte et adresse IP) :

| Profil | Comptes |
|---|---|
| ADMIN | `admin` |
| DGE | `dge` |
| AGENT | `agent.est`, `agent.est2`, `agent.hog` |
| VETO | `veto` |
| ELEVEUR | `eleveur`, `marie.nze` |
| AUDITEUR | `auditeur`, `aninf` |
| BCEG | `bceg` |
| OPÉRATEUR | `abattoir.owendo` (abattoir), `marche.montbouet` (marché) |

- **Données fictives** : 6 fermes (Estuaire et Haut-Ogooué), des bandes en cours et clôturées, des livraisons de l'État, des lots avec QR code, des réceptions (validées, avec écart, gardées à part) et des scans refusés.
