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
| E | Lot E trop long pour la nuit | Livré en deux parties : **E-a** (relevé, province, correction tapée, historique, visites, tournée, carte, contrôle DGE, page publique) ; **E-b** à faire (punaise à glisser, nouvelle ferme sans réseau, villes et boutons + / − de la carte) | Tout le lot en une fois | — (E-b s'ajoute sans rien défaire) |
| E | Relevé envoyé sans réseau et hors de la province | Gardé et marqué « position à vérifier » (on ne peut pas poser la question après coup) | Refusé et signalé à l'agent | `routes/terrain.position` : ne plus forcer `garder_quand_meme` sans réseau |
| E | Contrôle de province sur le téléphone | Fait par le serveur à l'envoi (les contours ne sont pas sur le téléphone) ; la question « Garder quand même » s'affiche alors | Contours envoyés au téléphone | Servir les contours de la province avec la page |
| E | Correction à la main | Coordonnées tapées + motif ; au-delà de 1 km, proposition aux quatre yeux (DGE / ADMIN) | Punaise sur la carte (E-b) | — |
| E | « Itinéraire complet » | Lien vers Google Maps (étapes = fermes du jour, ordre par proximité) ; rien n'est chargé dans SORRA | Lien `geo:` (une seule étape possible) | Changer l'adresse dans `terrain/agent/tournee.html` |
| E | Page publique du QR | Localité et province (le référentiel n'a pas de département) | Ajouter les départements | Ajouter une colonne `departement` aux localités |
| E | Couleurs de la carte | Mortalité : < 3 % vert, 3–5 % orange, > 5 % rouge ; régularité : ≥ 90 % vert, 70–90 % orange ; atteinte : comme la liste des fermes | Seuils réglables | Déplacer les seuils dans les paramètres (`pilotage.infos_ferme`) |
| E-b | Saisies possibles sur une ferme provisoire (sans réseau) | **Compte rendu de visite et dépense** (« J'ai payé ») ; une bande ne peut pas exister sans poussins livrés | Toutes les saisies | Ajouter d'autres formulaires à `terrain/agent/ferme_provisoire.html` (adressés au numéro P-xxxx) |
| E-b | Rattachement des saisies | Le serveur garde le numéro provisoire sur la ferme (`numero_terrain`) et le reconnaît partout où une ferme est cherchée par son numéro ; la file du téléphone part dans l'ordre (la ferme d'abord) | Réécrire les saisies en attente sur le téléphone | — |
| E-b | Places à la création | « Places au total » réparties également entre les bâtiments (arrondi au-dessus) | Places de chaque bâtiment | Ajuster ensuite dans « Bâtiments » |
| E-b | Doublon trouvé par le serveur | La ferme est créée et un message part dans « À vérifier » (avec la réponse de l'agent) | Refuser la création | Lever une erreur dans `routes/terrain.nouvelle_ferme` |
| 0 | Noms des captures des maquettes | Sans accents (git les cite autrement et un test les lit) | Accents | — |
| L | Condition de l'encadré | **Les deux** : `YL2_DEMO=1` **et** `SORRA_DEMO_COMPTES=1` (le réglage seul ne suffit pas hors démo) | Le réglage seul | Retirer `active() and` dans `utils/demo.comptes_en_un_clic` |
| L | Source des comptes | Lus **en base** à chaque affichage (comptes actifs), jamais une liste écrite dans le code | Liste dans le code | — |
| L | Mot de passe public | Lu dans `SORRA_DEMO_MDP` du `.env`, à défaut la valeur publique déjà dans `deployer_serveur.sh` | Toujours dans le `.env` | Retirer la valeur par défaut dans `config.py` |
| L | Version du service worker | Automatique : l'empreinte change avec le gabarit de connexion | Numéro à la main | — |
