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
| M — BCEG et MAEDR | `2438f27` | 734 | oui | 2026-11-10-2438f27 | migration 0033 ; compte MAEDR à créer dans la démo |
| S — sécurité | `db5c48c` | 740 | oui | 2026-11-10-db5c48c | clé GPG et destination distante à poser par le propriétaire |
| P — code du terrain, synchronisation, guides | `db36077` | 743 | oui | 2026-11-10-db36077 | migration 0034 |
| V express — habillage PERFORM YL.1 du bureau | `6b1349c` | 743 | oui | 2026-11-10-1cdcd22 | fait : barre bleu nuit (fil d'Ariane, cloche, déconnexion icône), colonne blanche (icône carrée, actif bleu nuit, synchronisation), en-tête de page (Excel / Imprimer remontés, bouton principal majuscules), indicateurs en pastilles colorées partout, barre FILTRES (« En alerte uniquement », Filtrer, Réinitialiser), tableaux (nombres à droite, codes, badges, lignes teintées, TOTAL), fenêtres (en-tête bleu nuit, cadenas « calculé / attribué par SORRA », Archiver à gauche, ENREGISTRER), carte cadrée sur le Gabon (étiquettes au survol, sélecteur de province), icônes SVG locales (`app/utils/icones.py`), responsive 900 / 560 px ; aucune route, page ni écran téléphone touché ; maquette `maquette_sorra_bureau_v2.html` absente du dépôt → `maquette_sorra_bureau.html` + les 10 points du prompt |
| J — jeu de données complet de la démonstration | `7569d74` | 745 | oui | 2026-11-11-7569d74 | `flask demo-jeu-complet` (graine fixe, daté par rapport à aujourd'hui) chargé sur la démo après sauvegarde vérifiée et base recréée : **150 élevages** (9 provinces au prorata, 8 en préparation, 3 hors programme, 293 bâtiments), **20 comptes** (dont `maedr`, 6 agents, 3 vétérinaires), **1 685 bandes** (1 680 chair, 5 ponte), **70 006 saisies**, 9 097 pesées, 6 187 vaccinations, 255 traitements, 2 092 livraisons, **3 829 sorties et lots QR**, 194 réceptions, 197 scans, 9 473 dépenses, 149 ventes d'œufs, 376 visites ; moyennes des bandes clôturées : mortalité 2,8 %, IC 1,78, 2,12 kg. Performances revues au volume réel (bandes légères, séries en un passage). **À regarder en premier** : accueil DGE (carte, pastilles, 3 courbes 52 semaines), Élevages (EST-007 en feu rouge, NGO-003 −300 poussins), Arbitrages (doublon EST-011 en attente depuis 49 h), écran de l'abattoir (3 scans refusés HOG-006, lot gardé à part), accueil MAEDR (1 rapport à viser), Mon argent de `eleveur` (chiffre d'affaires à 92 % du seuil ISL) |

## Bilan au 10/11/2026 (fin de la file du prompt unique)
Tous les lots sont livrés, testés (743 tests, 1 ignoré) et déployés : dernière version **2026-11-10-db36077**.
Migrations 0028 → 0034. Conformité : `docs/conformite/rapport_conformite.html` (0 non conforme).

### Reste à faire par le propriétaire (serveur, hors git)
- `.env` de la démo : fait (clés VAPID, `SORRA_DEMO_COMPTES=1`, cron `notifications-envoyer`).
- Lot S : déposer `/etc/sorra/sauvegarde.pub` (clé publique GPG) et `/etc/sorra/sauvegarde.conf` (`DISTANT=`) ; installer `pip-audit`
  dans le venv du poste.
- Jeu de démonstration : ajouter des ventes de poulets et une bande de ponte (`deploiement/demo/donnees_demo.json`) pour que
  Mon argent, le bilan et Mes œufs se présentent pleins ; créer un compte MAEDR.
- Suite possible : CSP par nonces (retirer `'unsafe-inline'`), colonnes « Biosécurité » et « Évolution » du classement.

## Décisions les plus importantes
(voir `docs/decisions_autonomes.md`)
