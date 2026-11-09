# SORRA — Rapport du travail autonome : lots 15 à 18 (interface de pilotage)

**Branche :** `autonome-lots-15-18`, partie de `1a759bb`. Elle n'est **ni fusionnée ni poussée**.
**Aucun déploiement**, aucune connexion au VPS. Aucune autre application touchée, aucune donnée supprimée, aucune migration déjà commitée modifiée.

## En bref

| Lot | Commit | Contenu | Tests (suite complète) | Migration |
|---|---|---|---|---|
| 15 | `0d473de` | Accueil en tuiles par profil, quatre yeux, journal chaîné + Intégrité, sessions, double authentification | 359 ✓ + 1 réservé PostgreSQL | 0016 |
| 16 | `4e636ac` | Agent : Mes fermes par urgence, Tournée (sans réseau), fiche regroupée, nouvel éleveur, écart de stock, commandes, biosécurité | 367 ✓ + 1 | 0017 |
| 17 | `c58680c` | Vétérinaire : gravité, diagnostics, blocage des sorties, paramètres sanitaires, recherche amont/aval | 373 ✓ + 1 | 0018 |
| 18 | dernier commit de la branche | DGE : planning des livraisons, « Créer la livraison », arbitrages par province, classement, rapports mensuels gardés, agents | 379 ✓ + 1 | 0019 |

Chaque lot est **un commit**, fait seulement après une suite complète verte. Chaque migration a son retour arrière, **testé** sur une copie de la base de démo : montée, descente, montée, `db check`, chaîne du journal intacte.

## À lire d'abord

1. **Les décisions prises seul** : `docs/decisions_autonomes.md`, 36 décisions. Les ★ sont à regarder en priorité :
   - 15-1 et 15-2 : journal chaîné à part ; interrupteur `YL2_2FA` ;
   - 15-3 : liste des réglages sensibles ;
   - 16-1 et 16-2 : calcul de l'urgence ; tournée gardée sans réseau, saisies de l'agent en ligne ;
   - 16-7 : la DGE décide des commandes ;
   - 17-2 à 17-4 : qui lit le diagnostic ; sortie reçue après un blocage ; qui lève un blocage ;
   - 18-1 : le statut « Prévue » ;
   - 18-4 à 18-6 : barème du classement ; rapports « automatiques » sans planificateur ; e-mail coupé.
2. **Les points à valider** par les vétérinaires et la DGE : `docs/a_faire_valider.md` (grille de biosécurité, maladies, barèmes, seuils, pondérations, destinataires, textes).
3. **Les rapports de lot**, chacun avec sa liste de tests à la main : `docs/rapport_lot15.md` à `docs/rapport_lot18.md`.
4. **La carte des écrans** (tuile → écran → lot) : `docs/pilotage.md`.

## Problèmes rencontrés (tous réglés, aucun commit rouge)

- **Lot 15** : la première suite complète avait 6 échecs, tous réparés en quelques minutes :
  - anciens tests qui cherchaient des tuiles déplacées ;
  - la clé 🔑 de l'éleveur menait vers une page non gardée sans réseau ;
  - nombre de paramètres ;
  - une couleur en dur ;
  - un mot du sous-titre.

  Aux captures : le QR code de la 2FA coupait la page à 360 px (SVG avec prologue XML), corrigé.
- **Lot 15, défaut trouvé au lot 16** : le réglage `securite.profils_2fa` ne pouvait pas être modifié. Corrigé et testé au lot 16.
- **Lot 15, rapport** : il citait le chemin de la base de démo, qui contient l'ancien nom interdit. Corrigé au lot 16, puis **historique de la branche réécrit** à la relecture : le commit du lot 15 ne le contient plus (voir « Après relecture »).
- **Lot 17** : l'écran Sortie bloqué levait une erreur JavaScript (formulaire absent). Corrigé, ainsi qu'un formulaire vide dans Surveillance.

## Ce que je n'ai pas fait (volontairement)

- **Pas de cron ni de serveur de messagerie** : ils sont sur le VPS, donc interdits. Commande et cron documentés dans `docs/exploitation.md`.
- ~~Pas de saisie sans réseau pour l'agent~~ : **refusé à la relecture, corrigé** (voir « Après relecture »).
- **Pas d'écrans pour BCEG, MAEDR, OPERATEUR** : ils ne faisaient pas partie des lots 15 à 18. Leur accueil dit « Vos écrans arrivent bientôt », sans tuile morte.
- **Pas de tuile Sauvegardes** : il n'y a pas d'écran, et les sauvegardes sont sur le VPS (décision 15-7).
- **Secret TOTP en clair en base** (codes de secours hachés), décision 15-9 ; à chiffrer si vous le souhaitez.

## Base de démo et serveur local

- Base `demo_performyl2.db` (dossier parent du dépôt), migrée en **0019**, avec les données de chaque lot. Une copie a été faite avant chaque lot : `demo_performyl2_avant_lot15.db` … `_avant_lot18.db`.
- **Serveur local relancé** sur cette base : `http://127.0.0.1:5020`, double authentification coupée (`YL2_2FA=0`). Mot de passe des comptes : `Demo-yl2-2026`.

| Compte | Profil | À regarder |
|---|---|---|
| `admin` | Administrateur | Configuration, Paramètres à approuver, Sessions, Intégrité, Surveillance (lecture) |
| `dge` | DGE | Planning, Commandes, Arbitrages, Classement, Rapports gardés, Agents, Paramètres à approuver (1 proposition) |
| `agent.est` | Agent | Mes fermes (EST-001 et 002 urgentes), Tournée, fiches, Commandes |
| `agent.est2` | Agent | Ferme EST-004 (réaffectation) |
| `veto` | Vétérinaire | Signalements, Surveillance (EST-001-B2-01 bloquée, 1 sortie à vérifier), Recherche de lots |
| `eleveur` | Éleveur | Bandeau « ⛔ ventes bloquées » + 📞, Mes visites (biosécurité 80 %) |
| `auditeur` | Auditeur | Journal, Intégrité |

## Pour la suite

1. Relire les décisions ★ et `a_faire_valider.md`.
2. Tester à la main avec les listes des rapports de lot.
3. Si tout convient : fusionner `autonome-lots-15-18` dans la branche principale, puis déployer.
   - Au déploiement : `YL2_2FA=1` (c'est la valeur par défaut en production) ;
   - migrations 0016 à 0019 ;
   - cron des rapports ;
   - ajouter `instance/rapports/` aux sauvegardes.

## Après relecture (09/11/2026)

1. **Saisies de l'agent sans réseau** : la liste de ce qui demandait le réseau et les nouvelles règles sont dans `docs/hors_ligne.md` (« L'agent sans réseau ») et les décisions R-1, R-1b, R-1c.
   - Rendus hors ligne : saisie pour l'éleveur (dont vaccin et traitement), compte rendu, biosécurité, nouvel éleveur.
   - Tests : `tests/test_agent_hors_ligne.py` (5) ; vérifié au navigateur.
   - Correction au passage : le bandeau « ◷ en attente » était mal mis en page sur les écrans du pilotage.
2. **Classement** : pondérations, barème des notes et seuil « incomplète » sont des paramètres `classement.*` sous **quatre yeux** (migration 0020, décision R-2). Les seuils des étoiles sont des paramètres (`bandes.etoiles_*`), listés dans `a_faire_valider.md`.
3. **Ancien nom dans l'historique** : la branche a été réécrite (contenu final identique, auteurs, dates et messages gardés). Une recherche sur `git log -p` de la branche (diffs et messages, depuis `1a759bb`) ne trouve plus le nom. L'ancienne version est gardée sous l'étiquette `sauvegarde-autonome-lots-15-18-avant-reecriture`. L'historique de la branche principale (avant `1a759bb`) le contient encore, dans les commits d'avant le renommage : non touché.
4. **Suite complète** relancée après tout cela : voir le rapport de relecture `docs/rapport_relecture_lots15-18.md`.
