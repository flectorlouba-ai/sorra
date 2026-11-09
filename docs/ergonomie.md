# SORRA — règles d'ergonomie

> **À relire et à appliquer au début de CHAQUE lot.** Tout écran nouveau ou modifié est
> vérifié contre ce document avant d'être livré. Le rapport de chaque lot indique
> comment ces règles ont été respectées.

## A. Principe

Les **éleveurs sont les premiers utilisateurs**.

L'innovation (calculs, alertes, synchronisation, journal) travaille en coulisses. L'éleveur ne voit qu'un écran simple :
- utilisable **d'une main**, sur un **téléphone Android d'entrée de gamme** ;
- aussi naturel que WhatsApp.

**La saisie quotidienne prend moins de 30 secondes.**

## B. Écran d'accueil de l'éleveur : « Ma bande aujourd'hui »

| Zone | Contenu |
|---|---|
| En haut | Un **feu tricolore** (vert / orange / rouge) et **une phrase simple**, par exemple « Jour 23 · Vos poulets grossissent bien ». |
| Au centre | De **gros compteurs avec + et −** : *Morts aujourd'hui*, *Sacs d'aliment*, *Pesée le jour prévu*. |
| En bas | **Un seul gros bouton « Envoyer »**. |

## C. Les 7 fonctions retenues

Le lot de réalisation est indiqué entre parenthèses.

1. **Saisie de l'aliment en sacs** : le système convertit en kg avec le poids du sac. Ce poids est propre à chaque produit du catalogue des intrants (25 kg, 50 kg…), et non un paramètre unique (décision du lot 2). *(lot Bandes)*
2. **« À faire aujourd'hui »** : vaccins, pesées, fin de bande, calculés automatiquement et affichés à l'éleveur. *(lots Bandes et Sanitaire)*
3. **Déclaration sanitaire par photo** et par **pictogrammes** des signes observés, sans texte à écrire. *(lot Sanitaire)*
4. **Coches comme WhatsApp** à côté de chaque saisie : ⏳ en attente de réseau, ✓ envoyé. *(lot Hors ligne)*
5. **Message vocal** de l'éleveur à son agent technique. *(lot Sanitaire)*
6. **Comparaison qui encourage**, par exemple « Votre mortalité est meilleure que la moyenne de la province ». *(lot Tableaux de bord)*
7. **Saisie par l'agent technique pour le compte d'un éleveur**, signalée clairement dans le journal. *(lot Bandes)*

**Reporté, à ne pas coder** : connexion des éleveurs par numéro de téléphone et code PIN.

## D. Règles générales (validées)

- **Une seule action principale par écran** : un seul bouton mis en avant.
- **Trois clics maximum** pour toute action courante.
- **Chacun ne voit que ce qu'il a le droit de faire** : pas de bouton grisé, pas de tuile inutile.
- **Mots simples, aucun terme technique** à l'écran (pas d'UUID, de synchro, d'enregistrement…).
- **Les fonctions techniques restent invisibles** (journal, numérotation, hors ligne) : l'utilisateur n'en voit que le résultat.
- **Rien d'ajouté sans demande** : une option utile se propose dans le rapport du lot, elle ne se code pas d'office.

## E. Validation terrain

Avant de figer le lot Bandes, l'écran éleveur sera **testé par 3 à 5 vrais éleveurs**. Leurs retours priment sur les choix faits au bureau.

## F. Charte illustrée douce (espace éleveur)

Depuis le lot 8, l'**éleveur** a son propre style, « illustré doux ». La **page publique du QR code** l'utilise aussi, et l'**écran de connexion** aussi, puisqu'il est commun à tous. Tous les autres profils gardent la charte bleu nuit. L'agent qui saisit pour l'éleveur aussi, même sur les mêmes écrans.

- **Feuille dédiée** : `app/static/css/eleveur.css`. Elle n'est chargée que pour l'éleveur connecté, la page publique et la connexion. Ses couleurs sont uniquement dans son `:root`, et un test le vérifie.
- **Couleurs** :

  | Nom | Code | Usage |
  |---|---|---|
  | nuit | `#1b2a5e` | textes |
  | bleu | `#2a7de1` | actions |
  | soleil | `#f7c948` | |
  | prairie | `#2fa36b` | tout va bien, bouton Envoyer |
  | orange | `#f08a24` | attention |
  | rouge | `#e5484d` | alerte |
  | crème | `#fbf8f2` | fond |
  | gris | `#6b7594` | textes secondaires |
  | trait | `#edf0f6` | bordure des cartes |

- **Cartes** : blanches, bordure très fine, ombre légère, coins arrondis de 16 à 18 px. Pas de contours épais.
- **Boutons** : plats et arrondis.
  - Le bouton principal est plein, avec une ombre douce de sa couleur : vert pour Envoyer, Tout reçu, Commencer la bande et C'est fait ; bleu pour les autres actions ; rouge pour le vétérinaire.
  - Les boutons secondaires sont blancs, à bordure fine et texte bleu.
  - Compteurs ronds de 44 px : « − » gris clair, « + » bleu.
- **Police** : Nunito seule (licence OFL), servie en local depuis `static/polices`. Polices de secours sans empattement.
- **En-tête** : dégradé bleu, le poulet, « SORRA » et « Bonjour {Prénom} ! 👋 ».
- **Émojis** : seulement comme pictogrammes simples (📦 ⚖️ 🚚 🩺 💉 📋 🔥 💪 🎤 📞 📵 🐣).
- **Animations** : en CSS seulement (transform, opacity), sans bibliothèque et sans son. Toutes sont coupées si l'appareil demande de réduire les animations.
- **Hors connexion** : la feuille, le script et la police sont gardés par le service worker.

### Les 6 idées ludiques retenues

1. **Le poulet qui réagit** : c'est le même dessin que le logo, au trait fin (`app/utils/logo.py`). Il est content au feu vert, inquiet à l'orange, malade au rouge (corps rosé, thermomètre). Il dort quand le bâtiment n'a pas de bande.
2. **La bande qui grandit** : une barre jaune va de J0 à la durée de référence, avec un petit poussin dessiné qui avance. Messages : « C'est parti ! », « À mi-chemin ! », « Plus que N jours ».
3. **L'envoi agréable** :
   - le chiffre des compteurs rebondit, avec une petite vibration si le téléphone le permet ;
   - après « Envoyer » au feu vert, l'écran « Bien reçu ! » s'affiche environ 2 s : 2 petits sauts, la série, quelques étincelles ;
   - au feu orange ou rouge, ni saut ni étincelle : seulement « Envoyé ✓ — Votre agent est prévenu » ;
   - sans réseau : « ◷ Sera envoyé dès que le réseau revient ».
4. **La série de jours** : la pastille « 🔥 N jours » compte les jours consécutifs avec une saisie, par bande.
   - Si rien n'est encore envoyé aujourd'hui, on compte jusqu'à hier.
   - Une saisie faite sans réseau compte à sa date.
   - Après un jour manqué : « On repart : 1 jour ! ».
   - Le record personnel se calcule sur toutes les bandes de l'éleveur ; « Nouveau record personnel ! » s'affiche quand il est battu, à partir de 3 jours.
5. **Le bilan en étoiles**, de 1 à 3, jamais 0. Il est gardé dans le bilan à la clôture.
   - 3 étoiles si la mortalité est d'au plus 3 % **et** l'indice de consommation d'au plus 1,7 ;
   - 2 étoiles si la mortalité est d'au plus 5 % ;
   - sinon 1 étoile.

   Si l'indice de consommation est inconnu, c'est 2 étoiles au plus. Les seuils sont dans les Paramètres, à valider par les vétérinaires. Les étoiles apparaissent dans « Mes bandes » et sur la dernière bande d'un bâtiment vide.
6. **Les messages vivants** :
   - « Bonjour {Prénom} ! » ;
   - après une pesée, « 💪 +210 g en 7 jours » (écart avec la pesée précédente) ;
   - **jamais de message joyeux quand le feu est orange ou rouge**.

Il n'y a pas de badges, pas de classement et pas de son.

### Plusieurs bandes à la fois

- Une seule bande ouverte par bâtiment (« tout plein, tout vide »). Un compartiment séparé se déclare comme un bâtiment (B1-A, B1-B).
- **À partir de 2 bâtiments**, une rangée de pastilles s'affiche (« B1 · J23 », « B3 · vide »).
  - Chaque pastille a la couleur du feu de sa bande, et un point orange tant que la saisie du jour n'est pas envoyée.
  - Un toucher affiche la bande de ce bâtiment.
  - Les bandes à saisir passent d'abord, et les pastilles vont à la ligne au lieu de défiler.
- **« À faire aujourd'hui »** est commun à la ferme. Chaque ligne commence par son bâtiment (« B2 : … »), et un toucher ouvre la bonne bande.
- **Bande déjà saisie** : « ✓ Saisie du jour envoyée » remplace le bouton Envoyer. On peut encore ajouter, avec la confirmation du lot 3.
- **Après l'envoi**, s'il reste une bande à saisir : « Il reste B2 à saisir → ».
- Les saisies restent toujours séparées par bande. La série se compte par bande ; le record, sur toutes les bandes.

### Accueil de l'éleveur en tuiles (lot 9)

L'accueil de l'éleveur est une **porte d'entrée**, pas un tableau de bord. Une grosse tuile par action, et toute action se fait en **3 clics au plus** depuis l'accueil. Les « + » et « − » des compteurs ne comptent pas.

De haut en bas :
- **en-tête** ;
- **bandeau rouge**, seulement si une bande est au feu rouge (« ⚠️ B2 : beaucoup de morts aujourd'hui → Signaler ») ;
- **ligne d'état** : poulet du pire feu, « 2 bâtiments · tout va bien » ou « B2 demande votre attention », « B1 jour 23 · B2 jour 5 » ; pas de chiffres ;
- **grande tuile verte « Saisie du jour »**, avec en pastille le nombre de bâtiments restant ; « ✓ Tout est envoyé aujourd'hui » quand tout est fait ;
- **grille de 2 colonnes, dans un ordre FIXE** (décision du 09/11) : Livraisons · Nouvelle bande · Peser · Vaccins · Poulet malade · Sortie · J'ai acheté · Entretien · Mes bandes · Mon stock. L'ordre ne dépend jamais des pastilles. Entretien a sa place réservée, mais sa tuile reste cachée tant que l'écran n'existe pas ;
- **« 📞 Appeler {Prénom}, mon agent »**, pleine largeur, toujours en dernier, si l'agent a un téléphone. Un test vérifie l'ordre complet.

**Règles :**
- Une tuile sans objet disparaît : Nouvelle bande sans poussins en attente ; Saisie, Peser, Sortie et Vaccins sans bande en cours.
- Les autres tuiles se resserrent ; avec un nombre impair, la dernière prend toute la largeur.
- Une pastille de couleur en haut à droite signale une action à faire.
- **La tuile ouvre directement la bande la plus utile** :
  - Saisie du jour : le premier bâtiment pas encore saisi ;
  - Peser : la pesée prévue la plus proche ;
  - Sortie : la bande la plus âgée ;
  - Poulet malade : la bande au feu rouge ;
  - Vaccins : le vaccin en retard ou du jour.

  Des pastilles B1 / B2 en haut de l'écran permettent de changer de bâtiment.
- **« ‹ Accueil »** en haut à gauche de chaque écran de l'éleveur.

| Action | Clics |
|---|---|
| Saisie du jour → Envoyer | 2 |
| Livraisons → Tout reçu | 2 |
| Nouvelle bande → bâtiment → Commencer | 3 |
| Peser → Enregistrer | 2 |
| Sortie → type → Enregistrer | 3 |
| Vaccins → C'est fait | 2 |
| Poulet malade → signes → Envoyer | 3 |
| J'ai acheté → produit → Enregistrer | 3 |
| Mes bandes, Mon stock, Appeler mon agent | 1 |

### Achats personnels de l'éleveur (« J'ai acheté »)

- **Rangement** : ils sont rangés avec les livraisons, en origine « Achat personnel ». Numéro ACH-AAAA-NNNNNN, non subventionné.
- **Stock** : le stock de la ferme = livraisons de l'État confirmées + achats − utilisations. « Mon stock » montre ce qui a été reçu de chaque source.
- **Poussins achetés** : les morts à l'arrivée sont demandés, et les poussins deviennent « en attente de bande ».
- **Contrôles** : les achats n'entrent **jamais** dans les contrôles des intrants de l'État. Ces contrôles passent tous par une seule fonction, `intrants.livraisons_de_l_etat()` : listes, alertes, mortalité à l'arrivée, exports, et le futur recoupement livraisons / consommations.
- **Annulation** : « Enregistré ✓ — Annuler (10) » juste après l'enregistrement. Ensuite, seule une correction par l'agent est possible, avec un motif inscrit au journal.

## Liste de contrôle d'un écran (à cocher dans chaque rapport de lot)

- [ ] Un seul bouton mis en avant ?
- [ ] L'action courante se fait en 3 clics au plus ?
- [ ] Aucun bouton ni tuile que l'utilisateur ne peut pas utiliser ?
- [ ] Aucun mot technique visible ?
- [ ] Utilisable d'une main sur un écran de 360 px de large, sans défilement horizontal de la page ?
- [ ] Écran éleveur : saisie du jour en moins de 30 secondes ?
- [ ] Rien d'ajouté qui n'ait été demandé ?
