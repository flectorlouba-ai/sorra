# SORRA — Règles communes à tous les lots (à relire au début de chaque lot)

Ordre des lots : **0 Préparation → E-b → C → R → D → T → G → F → B → M → S → P**.
À la reprise après un arrêt : relire ce fichier et le dernier rapport (`docs/rapport_suite.md`), puis reprendre au
premier lot non fusionné.

Références visuelles : `docs/maquettes/validees/` (captures de chaque écran dans `captures/`).

## Méthode
- Maquettes validées : pas d'étape 1 avec attente. Écrire `docs/maquettes/maquettes_<lot>.md` (écrans, tables, règles,
  écarts) puis construire. Chaque écart ou choix : `docs/decisions_autonomes.md` (lot, question, choix, autre option,
  retour arrière). Aucune décision irréversible.
- Réutiliser toujours l'existant avant de créer quoi que ce soit.

## Terrain (éleveur, agent, opérateur sur téléphone)
- On **ne touche pas** à ce qui est fait (tuiles, écrans, règles) ; on **ajoute** seulement.
- Style terrain, 3 clics maximum, aucun mot technique, case vide ≠ zéro, hors ligne.

## Ordinateur (tous profils)
- Organisation du lot R : zone titre en haut, boutons des fonctionnalités 2 par ligne à gauche, tableaux / graphiques /
  boutons à droite ; charte YL.1 **sans bande kente**.

## Formulaires
- Toujours en **fenêtre** appelée par un bouton « ＋ … » ; clic sur une ligne = même fenêtre préremplie
  (Enregistrer la modification · Archiver · Fermer). **Archiver, jamais supprimer.**
- La fenêtre ne dépasse jamais l'écran : titre et boutons fixes, champs qui défilent, 2 colonnes sur ordinateur,
  1 colonne sous 700 px. Maximum de listes déroulantes.

## Tableaux (ordinateur)
- Boutons « 🖨️ Imprimer » (aperçu A4 paysage : en-tête SORRA, titre, filtres, date, nom ; enregistrable en PDF) et
  « ⬇️ Excel » (.xlsx des lignes filtrées, toutes colonnes) ; uniquement les données du périmètre ; chaque impression
  et chaque export au journal.

## Responsive
- Aucun débordement horizontal de 360 à 1 920 px ; tableaux qui défilent dans leur cadre ; menu des fonctionnalités en
  haut et défilant sous 900 px.

## Droits
- Chaque profil ne voit que ses fonctionnalités et son périmètre (`filtre_perimetre`).
- Le vétérinaire ne voit **jamais** de données financières.
- Paramètres sensibles : quatre yeux. Tout au journal.

## Tests et livraison
- Toute la suite verte. Si un lot casse des tests non réparés en 30 min : annuler le travail non commité, le noter,
  **arrêter**. Jamais de commit rouge.
- Fin de lot : suite verte → fusion dans `main` → push → déploiement de la démo (`deploiement/demo/deployer.sh`).
  Si le déploiement échoue : retour arrière (automatique), ne plus redéployer dans la session, continuer en local.
- Rapport court `docs/rapport_<lot>.md` terminé par « Déployé sur la démo : oui / non », la version, et ce qu'il faut
  tester sur téléphone et ordinateur (comptes de démo). Tenir `docs/rapport_suite.md` à jour.

## Interdit
- Toucher aux autres applications du VPS, à nginx hors du bloc sorra-demo, supprimer des données, modifier une
  migration commitée, toute ressource externe dans l'application (CDN, fond de carte en ligne).
- Secrets (mot de passe de la base, clé secrète, clés VAPID…) : seulement dans le `.env` du serveur, jamais dans git ni
  dans un rapport.
