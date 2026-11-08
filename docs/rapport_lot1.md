# PERFORM YL.2 — Lot 1 : référentiel des fermes et accueil — rapport

Date : 8 novembre 2026. État : construit et testé en local. Les **145 tests automatiques** passent. Un 146e, réservé à PostgreSQL, tournera sur le VPS. Pas encore déployé.

Maquettes suivies : [`docs/maquettes/maquettes_lot1.md`](maquettes/maquettes_lot1.md), avec les choix validés à l'étape 1.

## 1. Ce qui a été fait

### Accueil (maquette A)

Il reprend l'accueil de YL.1 : bandeau, barre bleu marine, « Bonjour, Prénom NOM », pastille du profil, onglets, tuiles en dégradé et encadré « Alertes » (« Aucune alerte active »).

**Les 9 onglets**, chacun avec ses tuiles : Configuration, Fermes et élevage, Santé animale, Traçabilité, Économie, Pilotage, puis Maintenance, QHSE et Comptabilité marqués « Option ».

**Tuiles disponibles dans ce lot :** tout l'onglet Configuration, Fermes et Opérateurs. Les autres sont atténuées, avec l'étiquette « Bientôt » ou « Option ». Un clic n'affiche qu'une phrase, par exemple « « Bandes » arrive bientôt : du poussin à la sortie. ».

**Ce que voit chaque profil :**

| Profil | Accueil |
|---|---|
| ADMIN | Tous les onglets |
| DGE | Tous les onglets sauf Configuration (voir § 5) |
| AGENT | Fermes et élevage, Traçabilité |
| VETO | Santé animale, et Fermes et élevage avec la seule tuile Fermes |
| AUDITEUR | Configuration, avec le Journal seul |
| ELEVEUR | Pas d'onglets : la carte « Ma ferme » (nom, numéro, statut, bâtiments, places, agent) et le gros bouton « Appeler mon agent » |
| BCEG, MAEDR, OPERATEUR | « Votre espace arrive bientôt » |

### Fermes (maquettes B, C, D)

**Liste** : filtres Province, Cohorte, Statut et recherche ; bouton « + Nouvelle ferme » selon les droits ; lien discret « Importer la liste POUFA » pour l'ADMIN.

**Fiche** :
- un seul bouton « Modifier » ;
- carte Exploitant, avec infrastructures et observations en bas ;
- carte Position : dessin de la province avec l'épingle, mention « Dans la province … ✓ » ou avertissement non bloquant ;
- carte Bâtiments : « + Bâtiment », codes B1, B2…, colonne « Bande en cours » vide, total des places des bâtiments actifs ;
- carte Historique du statut.

**Nouvelle ferme, pensée pour le téléphone :**
- champs empilés, province préremplie quand l'agent n'en a qu'une ;
- gros bouton « Prendre la position », lien « Saisir à la main » ;
- gros bouton « Enregistrer la ferme », avec la note « Le numéro est donné automatiquement ».
- En HTTP (le VPS aujourd'hui), le bouton GPS affiche « Position automatique indisponible, saisissez-la à la main » et ouvre la saisie manuelle.

**Modifier** : même écran, plus un bloc « Compléments » : réf. AMI, cohorte, statut, infrastructures, observations. L'agent référent se choisit par ADMIN et DGE ; la province ne se change que par l'ADMIN, et le numéro ne change pas.

**Règles :**
- Numéro EST-001… : il n'est jamais réutilisé et ne peut pas être modifié.
- Le code d'une province est verrouillé dès qu'une ferme existe. Le cadenas apparaît dans l'écran Provinces, et le serveur refuse aussi le changement.
- Doublons bloqués avec un message clair (référence AMI, téléphone, ou même nom dans la même localité), par exemple : « Ce téléphone est déjà celui de l'exploitant de la ferme EST-004 (Ferme Mba) ».
- Pas de suppression : une ferme passe en « Suspendue », un bâtiment devient inactif.
- Chaque changement de statut est daté et conservé.

**Localité absente sur le terrain :**
- L'agent choisit « Autre localité » et tape le nom.
- Si ce nom ressemble à une localité existante de la province, il voit d'abord « Vouliez-vous dire « N'kok » ? », avec deux boutons.
- Une localité nouvelle est marquée « À vérifier ». L'ADMIN la retrouve avec le filtre « À vérifier » de l'écran Provinces et localités. Il peut la valider, ou la fusionner avec une localité existante : les fermes sont rattachées à la bonne localité et la fusion est inscrite au journal.

### Opérateurs

- Numéro OPE-0001. Liste, fiche et formulaire selon la même logique que les fermes.
- ADMIN et DGE créent et modifient ; l'AGENT lit les opérateurs de ses provinces.
- Pas de suppression (actif / inactif) et pas de compte de connexion.

### Import POUFA (ADMIN)

1. Télécharger le modèle Excel : une feuille « Fermes » et une feuille « Explications ».
2. Déposer le fichier, puis « Vérifier le fichier ». L'aperçu donne, ligne par ligne :
   - « OK » ou l'erreur en clair ;
   - « Localité nouvelle » ;
   - « ⚠ ressemble à « N'kok » ».
3. « Importer les lignes valides ». Le fichier déposé est alors effacé, le rapport Excel est téléchargeable pendant un jour, et l'import est inscrit au journal.

Les doublons sont refusés, qu'ils existent déjà en base ou qu'ils se répètent dans le fichier.

### Autres changements

- **Utilisateurs** : pour un éleveur, choix de la province, puis cases à cocher de ses fermes.
- **Listes** : « Statuts de ferme », « Types d'infrastructures » (sans « Bâtiment d'élevage ») et « Types d'opérateurs », avec leurs valeurs de départ.
- **Journal** : il parle des fermes, bâtiments et opérateurs en clair (numéro et nom, localité, agent, source de la position). Deux actions nouvelles : « Import » et « Fusion de localités ».
- **Contrôle « hors province »** :
  - contours simplifiés à environ 500 m, rangés dans `app/data/provinces_gabon.json`, avec une tolérance de 5 km ;
  - source : geoBoundaries (gbHumanitarian), d'après SALB des Nations unies via HDX, licence **CC BY 3.0 IGO**. La source est citée dans le README.
  - Les 9 chefs-lieux sont reconnus dans la bonne province. Libreville déclarée dans le Haut-Ogooué est signalée à 423 km.
  - **Note sur la licence** : le jeu « gbOpen » proposé à l'étape 1 est en réalité sous CC BY-SA 3.0, dont la clause de partage est plus contraignante. J'ai donc pris le jeu « gbHumanitarian », sous CC BY 3.0 IGO, qui demande seulement de citer la source.
- **Connexion** : nouveau sous-titre, « Suivi et traçabilité de la filière avicole ».
- **Nouvelle dépendance** : `openpyxl` 3.1.5.
- **Migration 0003** : nouvelles tables et valeurs de départ des listes. Elle est testée à la montée et à la descente.

## 2. Liste de contrôle d'ergonomie (docs/ergonomie.md)

- [x] **Un seul bouton mis en avant** par écran :
  - « + Nouvelle ferme », « Modifier », « Enregistrer la ferme » ;
  - « Vérifier le fichier », puis « Importer les lignes valides » ;
  - « + Nouvel opérateur », « + Nouvelle localité ».
  - « + Bâtiment » et « Saisir à la main » sont des boutons secondaires.
- [x] **3 clics au plus** :
  - créer une ferme : onglet Fermes et élevage → Fermes → « + Nouvelle ferme » ;
  - ouvrir une fiche : 3 clics ;
  - ajouter un bâtiment depuis la fiche : 2 clics.
- [x] **Rien d'inutilisable** :
  - pas de bouton « Modifier » pour le vétérinaire ;
  - pas de « + Nouvelle ferme » pour le vétérinaire ;
  - pas de bouton « Appeler » si l'agent n'a pas de téléphone ;
  - pas d'onglet Configuration pour la DGE (§ 5).
  - Les tuiles « Bientôt » sont affichées parce que la maquette le demande ; elles n'ouvrent rien et le disent.
- [x] **Aucun mot technique** : les fermes sont désignées par leur numéro (EST-001), y compris dans les adresses des pages. Le journal parle en clair.
- [x] **360 px** : vérifié dans un navigateur au format téléphone (360 px) : pas de défilement horizontal de la page, champs et boutons pleine largeur, d'au moins 46 à 52 px de haut.
- [ ] **Saisie du jour en moins de 30 secondes** : sans objet dans ce lot. L'écran « Ma bande aujourd'hui » viendra au lot Bandes. L'écran « Ma ferme » se lit d'un coup d'œil, avec un seul bouton.
- [x] **Rien d'ajouté sans demande.** Deux ajouts découlent de vos choix :
  - le filtre « Sans cohorte » dans la liste, puisque la cohorte peut rester vide à la création ;
  - la colonne « Fermes » dans les tableaux de localités, utile avant de fusionner.

## 3. Tests automatiques

`venv\Scripts\python -m pytest -q` donne **145 réussis, 1 ignoré** (le test réservé à PostgreSQL), en environ 3 min 30. Les 56 tests nouveaux couvrent :

| Fichier | Contenu |
|---|---|
| `test_fermes.py` (35) | numéros, verrou du code de province, création par l'agent, droits de création, champs obligatoires, doublons, statut et historique, changement de province par l'ADMIN, bâtiments, position (hors province, manuelle, incomplète), localité nouvelle, validation et fusion, cloisonnement de chaque profil, rattachement d'un éleveur |
| `test_accueil.py` (10) | onglets et tuiles de chaque profil, phrase « arrive bientôt », écran de l'éleveur avec le lien d'appel |
| `test_operateurs.py` (7) | numéros OPE, création et modification, lecture seule de l'agent limitée à ses provinces, refus pour les autres profils |
| `test_import.py` (6) | modèle, aperçu (12 lignes dont 7 refusées, avec chaque type d'erreur), import, fichier effacé, rapport, journal, accès ADMIN seul |

J'ai aussi tout essayé dans un vrai navigateur, au format ordinateur et téléphone, sans aucune erreur de page :
- avec une position GPS simulée sur `localhost` : « Position enregistrée ✓ — 0.3921, 9.6103 · précision 8 m » ;
- par l'adresse réseau du poste, non sécurisée comme le VPS : le message « Position automatique indisponible… » s'affiche et la saisie manuelle s'ouvre.

## 4. Tests à faire vous-même

**Préparation** (avec `admin`) :
1. Dans Provinces et localités → Estuaire, ajoutez les localités **Ntoum**, **Owendo**, **Libreville** et **N'kok**. Dans le Haut-Ogooué, ajoutez **Franceville** et **Moanda**.
2. Dans Utilisateurs, créez :
   - `agent.est` : Agent technique, Estuaire, **avec un téléphone** ;
   - `agent.hog` : Agent technique, Haut-Ogooué ;
   - `veto` : Services vétérinaires, Estuaire ;
   - `aninf` : Auditeur ;
   - `bceg` : BCEG ;
   - `dge` : DGE.

### Test 1 — Accueil avec chaque profil

Connectez-vous successivement. Résultats attendus :

| Compte | Onglets | Tuiles qui s'ouvrent |
|---|---|---|
| admin | les 9 | Journal, Utilisateurs, Provinces et localités, Listes, Paramètres, Fermes, Opérateurs |
| dge | 8 (sans Configuration) | Fermes, Opérateurs |
| agent.est | Fermes et élevage, Traçabilité | Fermes, Opérateurs |
| veto | Fermes et élevage (la seule tuile Fermes), Santé animale | Fermes |
| aninf | Configuration | Journal des opérations |
| bceg | aucun | « Votre espace arrive bientôt » |

Clic sur une tuile « Bientôt », par exemple Bandes : la phrase « « Bandes » arrive bientôt : du poussin à la sortie. » s'affiche sous les tuiles.

### Test 2 — Créer une ferme sur téléphone, avec le GPS (en local)

Sur l'ordinateur, ouvrez `http://localhost:5020` avec la fenêtre réduite à la taille d'un téléphone (outil « appareil mobile » du navigateur, touche F12), puis connectez-vous en `agent.est`.
1. Onglet Fermes et élevage → Fermes → « + Nouvelle ferme ». La province Estuaire est déjà remplie.
2. Remplissez le nom, l'exploitant et le téléphone, choisissez **Ntoum**.
3. Cliquez sur « Prendre la position » et acceptez la demande du navigateur. L'encadré vert « Position enregistrée ✓ » apparaît.
4. Cliquez sur « Enregistrer la ferme ». La fiche **EST-001** s'ouvre, avec la province dessinée et l'épingle.

Faites le même essai avec un vrai téléphone sur le même réseau Wi-Fi, à l'adresse `http://192.168.1.66:5020` (l'adresse de votre poste). Le bouton GPS doit afficher « Position automatique indisponible, saisissez-la à la main ». C'est ce qui se passera sur le VPS tant qu'il n'est pas en HTTPS.

### Test 3 — Doublons

Créez une deuxième ferme :
- avec le **même téléphone** : refus avec « Ce téléphone est déjà celui de l'exploitant de la ferme EST-001 (…) » ;
- avec le **même nom** dans **Ntoum** : refus ;
- avec le même nom dans **Owendo** : accepté.

### Test 4 — Localité absente (en agent)

Nouvelle ferme → Localité « Autre localité » → tapez **Nkok**.
- **Vouliez-vous dire « N'kok » ?** : « Oui » rattache la ferme à N'kok. « Non » crée « Nkok », marquée « À vérifier ».
- En `admin` : Provinces et localités → **« à vérifier »**. Cliquez sur « Fusionner », choisissez N'kok et enregistrez. La ferme passe sur N'kok, et une ligne « Fusion de localités » apparaît dans le journal.

### Test 5 — Fiche, bâtiments, statut (en admin)

1. Sur la fiche EST-001, cliquez sur « + Bâtiment », capacité 1200 : vous obtenez B1. Ajoutez B2 avec 800. Le total est de 2 000 places.
2. Désactivez B1 avec ✏️ : le total passe à 800.
3. Cliquez sur « Modifier », passez le statut à **Opérationnelle**, cochez deux infrastructures et enregistrez. L'historique du statut s'allonge et la pastille devient verte.
4. Essayez de changer le code de l'Estuaire dans Provinces et localités : le champ est verrouillé avec un cadenas.

### Test 6 — Position hors province (en admin)

Modifiez EST-001, « Saisir à la main », latitude **-1,63**, longitude **13,58**, puis enregistrez. Un avertissement ambre « … à environ 400 km de la province Estuaire (elle semble dans la province Haut-Ogooué) » s'affiche. La ferme est tout de même enregistrée.

### Test 7 — Import Excel (en admin)

1. Fermes → lien « Importer la liste POUFA (Excel) » → « Télécharger le modèle Excel ». Vérifiez les deux feuilles.
2. Déposez le fichier d'essai **`docs/exemples/essai_import_poufa.xlsx`** (10 lignes), puis « Vérifier le fichier ». Résultat attendu :
   - **6 valides** ;
   - **4 refusées** : téléphone en double avec la ligne 2, nom vide, province « Lagune » et cohorte 3, statut et infrastructure inconnus ;
   - « Localité nouvelle » pour **Nkok** et **Bikélé** ;
   - **« ⚠ « Nkok » ressemble à « N'kok » »** ;
   - un avertissement de position pour « Ferme Loin ».

   Si la ferme créée au test 2 porte le même téléphone qu'une ligne du fichier, une refusée de plus apparaît : c'est normal.
3. Cliquez sur « Importer les lignes valides », puis « Télécharger le rapport (Excel) ». Chaque ligne y porte le numéro attribué ou la raison du refus.
4. Le journal contient une ligne « Import » avec les comptes.

### Test 8 — Cloisonnement

1. En `admin`, donnez la ferme EST-001 à `agent.est` et une ferme du Haut-Ogooué à `agent.hog` (« Modifier » → Agent technique référent).
2. En **agent.hog** : la liste ne montre que sa ferme. Ouvrez l'adresse de la fiche EST-001 (`/fermes/EST-001`) : « Vous n'avez pas accès à cette page ».
3. En `admin`, Utilisateurs → « + Nouvel utilisateur », profil **Éleveur**, province Estuaire, cochez **EST-001**.
4. En **éleveur** : pas d'onglets, la carte « Ma ferme » de EST-001, et le bouton « Appeler mon agent ». Sur un téléphone, il lance l'appel. L'adresse `/fermes/` donne « Vous n'avez pas accès ».
5. En **veto** : la liste montre les fermes de l'Estuaire, sans « + Nouvelle ferme » ni « Modifier ».
6. En **agent.est**, onglet Traçabilité → Opérateurs : il voit les opérateurs de l'Estuaire (créez-en un d'abord en `dge`), sans bouton de création.

## 5. Points d'attention et propositions (non codés)

1. **DGE et onglet Configuration** : vous aviez écrit « ADMIN et DGE voient tous les onglets ». Or les écrans de Configuration sont réservés à l'ADMIN (lot 0), et pour l'Auditeur au seul Journal. Pour respecter « pas de tuile inutile », la DGE n'a pas cet onglet. Si vous le souhaitez, je peux donner à la DGE la lecture du Journal : l'onglet réapparaîtrait avec cette seule tuile.
2. **Épingle hors de la province** : quand le point est très loin, le dessin s'élargit pour montrer à la fois la province et l'épingle. La province paraît alors petite, ce qui rend l'erreur visible.
3. **Proposition** : afficher dans l'encadré « Alertes » de l'ADMIN le nombre de localités à vérifier et de fermes « hors province ». L'encadré servirait dès maintenant.
4. **Proposition** : sur la fiche, un lien « Voir sur une carte » qui ouvrirait OpenStreetMap avec la position. C'est un simple lien sortant, pas un service appelé par l'application.
