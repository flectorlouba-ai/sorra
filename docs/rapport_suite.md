# SORRA — Suite du projet : où on en est

Règles : `docs/regles_lots.md`. Décisions prises seul : `docs/decisions_autonomes.md`.

| Lot | Commit de fusion | Tests | Déployé | Version | Reste à faire |
|---|---|---|---|---|---|
| A1, A2, A3, E-a | (nuit du 10/11) | 491 | oui | 2026-11-10-9a16679 | — |
| 0 Préparation | (ce commit) | — | sans objet | — | — |
| E-b | `b058685` | 499 | oui | 2026-11-10-b058685 | — |
| L — comptes de démo en un clic | `046d42b` | 504 | oui | 2026-11-10-046d42b | ajouter `SORRA_DEMO_COMPTES=1` au `.env` du serveur (voir `rapport_L.md`) |
| C — indicateurs | `b7f7723` | 517 | oui | 2026-11-10-b7f7723 | — |
| R — version ordinateur | `a2ed0f4` | 534 | oui | 2026-11-10-a2ed0f4 | tableaux hors Élevages : colonnes existantes |
| D — bilan, rapports standards, plans d'actions | `b50ee43` (avec T) | 551 | oui | 2026-11-10-b50ee43 | — |
| T — notifications push, actions agent, fiche papier | `b50ee43` | 551 | oui | 2026-11-10-b50ee43 | clés VAPID + cron `notifications-envoyer` à poser sur le serveur (voir `rapport_T.md`) |
| Activation démo (10/11) | — | — | faite | 2026-11-10-b50ee43 | `.env` sauvegardé (600), clés VAPID et `SORRA_DEMO_COMPTES=1` ajoutés par redirection (jamais affichés), cron `*/15` de `performyl2-demo` → `/var/log/performyl2-demo/notifications.log`, service actif, encadré démo et activation des notifications vérifiés |
| G — Mon argent 12 mois, bilan, fiscalité, rappels | `f6056e5` | 722 | oui | 2026-11-10-f6056e5 | cœur livré au K4 ; rappels fiscaux ajoutés ; jeu de démo à enrichir en ventes |
| K — étape 1 (correspondance, captures avant) | `33fd308` | — | sans objet | — | — |
| K1 — bureau DGE + vétérinaire | `b7b943f` | 586 | oui | 2026-11-10-b7b943f | 16 écrans conformes, 9 colonnes « — » justifiées (voir `tests/test_conformite.ECARTS`) |
| K3 — bureau éleveur + agent | `1595e4d` | 618 | oui | 2026-11-10-1595e4d | 16 écrans conformes ; bilan PDF et régime fiscal de Mon argent = lot G (K4) |
| K2 — bureau administrateur + auditeur | `3f2d408` | 644 | oui | 2026-11-10-3f2d408 | 13 écrans conformes ; « Modifié le » de la matrice des droits « — » |
| K4 — téléphone éleveur (+ Mon argent du lot G) | `926e3cf` | 675 | oui | 2026-11-10-926e3cf | 30 écrans + Mon argent 12 mois, bilan PDF, fiscalité ; migration 0030 ; jeu de démo sans ventes → graphique presque vide (à enrichir) |
| K5 — téléphone agent, opérateur, GPS, notifications, actions + preuve visuelle | `992b803` | 721 | oui | 2026-11-10-992b803 | 54 écrans ; rapport_conformite.html (91 conformes, 41 écarts justifiés, 0 non conforme), controle_rempli.xlsx |
| F — œufs des bandes de ponte | `7ec1e19` | 727 | oui | 2026-11-10-7ec1e19 | migration 0031 ; jeu de démo sans bande de ponte (à ajouter) |
| B — imports Excel / CSV | `594f224` | 731 | oui | 2026-11-10-594f224 | migration 0032 ; 3 modèles |
| M | | | | | |
| S | | | | | |
| P | | | | | |

## Décisions les plus importantes
(voir `docs/decisions_autonomes.md`)
