# Décisions prises seul (mode autonome, nuit du 10/11/2026)

Chaque ligne : lot · question · choix · autre option · comment revenir en arrière.

| Lot | Question | Choix | Autre option | Revenir en arrière |
|---|---|---|---|---|
| A2 | Origine des utilisations (aliment, vaccins, traitements, poussins) : stocker ou déduire ? | **Déduite** : imputée Programme d'abord, puis Externe (même règle que la reprise, point 2) ; rien n'est demandé au terrain | Colonne `origine` sur chaque utilisation, choisie par l'éleveur | Ajouter une colonne `origine` facultative : quand elle est remplie, elle prime sur la règle (`intrants.imputer`) |
| A2 | Types de fournisseur | Liste fixe dans le code : Aliment · Couvoir · Pharmacie vétérinaire · Matériel · Autre | Liste réglable (Listes) | Déplacer `TYPES_FOURNISSEUR` dans les listes déroulantes |
| A2 | Commandes de l'agent : origine ? | Toujours Programme (commande à l'État) | Choix Programme / Externe | Ajouter une colonne `origine` à `commande_intrant` |
| A2 | Achats de l'éleveur : lien au fournisseur ? | Le texte « Où ? » reste libre ; le fournisseur du catalogue est celui de l'article | Choisir un fournisseur du registre à l'achat | Ajouter `fournisseur_id` à `livraison` |
| A2 | Écran Catalogue : DGE en écriture ? | ADMIN et DGE écrivent, l'agent lit (texte du lot A) | ADMIN seul | Retirer DGE de `ECRIVAINS` dans `routes/catalogue.py` |
| A3 | Fermes existantes : au programme ? | **Oui** (elles viennent de la liste POUFA) ; la cohorte est vidée si « Non » | Toutes à revoir à la main | `UPDATE ferme SET programme_poufa = false WHERE …` ou modifier chaque fiche |
| A3 | Capacité à la création | Nombre de bâtiments × places identiques ; les bâtiments sont créés ; ensuite on les ajuste dans « Bâtiments » | Saisir chaque bâtiment dans le formulaire | Remplacer les deux champs par une liste de bâtiments |
| A3 | Production réelle (12 mois) | Poids vif de **toutes** les sorties comptées des bandes de **chair** (abattoir, vente, autre), ni archivées ni mises de côté | Abattoir et vente seulement | Filtrer `Sortie.motif` dans `indicateurs.production_reelle_t` |
| A3 | Origine des poussins | **Déduite** des livraisons des poussins (Programme / Externe) ; « non renseignée » pour une bande de rattrapage | Champ choisi à l'ouverture | Ajouter une colonne et un choix à l'ouverture |
| A3 | Durée d'une bande de ponte | 504 jours (72 semaines), paramètre `bandes.duree_ponte_jours` | 45 jours comme le chair | Changer le paramètre |
| A3 | Formulaires de la ferme et de l'opérateur « en fenêtre » | La page garde son adresse, son formulaire s'ouvre en fenêtre au centre (✕ ramène à la fiche ou à la liste) | Fenêtre posée sur la liste | Charger le formulaire dans la liste (fenetre.js) |
| A3 | Hors programme | Refus : livraison de l'État (création et planning DGE), commande de l'agent ; pas de cible ; filtre et comptage à part (liste, tableau de bord, carte) | Masquer ces fermes des écrans de livraison | Retirer le contrôle dans `routes/livraisons`, `services/dge.prevoir`, `services/agent.commander` |
