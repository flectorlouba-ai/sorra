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
| G | — | — | — | — | en pause (rien de commencé au 10/11) ; reprend après K |
| K — conformité aux maquettes | | | | | |
| F | | | | | |
| B | | | | | |
| M | | | | | |
| S | | | | | |
| P | | | | | |

## Décisions les plus importantes
(voir `docs/decisions_autonomes.md`)
