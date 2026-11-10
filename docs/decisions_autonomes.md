# Décisions prises seul (mode autonome, nuit du 10/11/2026)

Chaque ligne : lot · question · choix · autre option · comment revenir en arrière.

| Lot | Question | Choix | Autre option | Revenir en arrière |
|---|---|---|---|---|
| A2 | Origine des utilisations (aliment, vaccins, traitements, poussins) : stocker ou déduire ? | **Déduite** : imputée Programme d'abord, puis Externe (même règle que la reprise, point 2) ; rien n'est demandé au terrain | Colonne `origine` sur chaque utilisation, choisie par l'éleveur | Ajouter une colonne `origine` facultative : quand elle est remplie, elle prime sur la règle (`intrants.imputer`) |
| A2 | Types de fournisseur | Liste fixe dans le code : Aliment · Couvoir · Pharmacie vétérinaire · Matériel · Autre | Liste réglable (Listes) | Déplacer `TYPES_FOURNISSEUR` dans les listes déroulantes |
| A2 | Commandes de l'agent : origine ? | Toujours Programme (commande à l'État) | Choix Programme / Externe | Ajouter une colonne `origine` à `commande_intrant` |
| A2 | Achats de l'éleveur : lien au fournisseur ? | Le texte « Où ? » reste libre ; le fournisseur du catalogue est celui de l'article | Choisir un fournisseur du registre à l'achat | Ajouter `fournisseur_id` à `livraison` |
| A2 | Écran Catalogue : DGE en écriture ? | ADMIN et DGE écrivent, l'agent lit (texte du lot A) | ADMIN seul | Retirer DGE de `ECRIVAINS` dans `routes/catalogue.py` |
