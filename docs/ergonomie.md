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
- **Trois clics maximum** pour toute action courante. **Comptent** comme clics : ouvrir un écran, et valider (Envoyer, Enregistrer, C'est fait, Tout reçu…). **Ne comptent pas** : les choix faits dans le même écran (bâtiment, produit, signe, catégorie, type de sortie) et les + / − des compteurs (règle précisée au lot 11).
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

### Accueil de l'éleveur en tuiles (lot 9, remplacé par les 8 tuiles du lot 11 ci-dessous)

L'accueil de l'éleveur est une **porte d'entrée**, pas un tableau de bord. Une grosse tuile par action, et toute action se fait en **3 clics au plus** depuis l'accueil. Les « + » et « − » des compteurs ne comptent pas.

De haut en bas :
- **en-tête** ;
- **bandeau rouge**, seulement si une bande est au feu rouge (« ⚠️ B2 : beaucoup de morts aujourd'hui → Signaler ») ;
- **ligne d'état** : poulet du pire feu, « 2 bâtiments · tout va bien » ou « B2 demande votre attention », « B1 jour 23 · B2 jour 5 » ; pas de chiffres ;
- **grande tuile verte « Saisie du jour »**, avec en pastille le nombre de bâtiments restant ; « ✓ Tout est envoyé aujourd'hui » quand tout est fait ;
- **grille de 2 colonnes, dans un ordre FIXE** (décision du 09/11) : Livraisons · Nouvelle bande · Peser · Vaccins · Poulet malade · Sortie · J'ai acheté · Entretien · Mes bandes · Mon stock. L'ordre ne dépend jamais des pastilles. La tuile Entretien est affichée depuis le lot 10 ;
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
| Entretien → Fait ✓ | 2 |
| Entretien → Quelque chose est en panne → Envoyer | 3 |
| Entretien → C'est réparé | 2 |
| Mes bandes, Mon stock, Appeler mon agent | 1 |

### Accueil en 8 tuiles (lot 11)

**En-tête de l'éleveur**, sur toutes ses pages, deux boutons à droite :
- **« 📞 {Prénom de l'agent} »** : lien d'appel, masqué si l'agent n'a pas de téléphone ;
- **« 👤 Moi »** : carte « Ma ferme » (nom, numéro, bâtiments, places), 🔑 Mon compte (mot de passe), 🏦 Partage avec la BCEG (bientôt, lot 13), ❓ Comment faire ? (bientôt, lot 13), 🚪 Se déconnecter.

Le mot de passe et la déconnexion ne sont plus dans l'en-tête de l'éleveur. La tuile « Appeler mon agent » a disparu.

**Accueil**, de haut en bas :
- au-dessus, inchangés : bandeau orange des saisies en attente, bandeau rouge, ligne d'état ;
- **✏️ Saisie du jour**, pleine largeur, verte. Dessous, seulement s'ils sont prévus aujourd'hui (ou en retard) :
  - « ⚖️ Pesée prévue dans B1 → Peser » ;
  - « 💉 Vaccin · B2 → ✓ C'est fait », qui enregistre d'un toucher ;
- **6 tuiles, ordre FIXE** : 🐔 Ma bande · 🚚 Ventes et sorties · 💉 Vaccins et soins · 🩺 Poulet malade (rose) · 📦 Mes produits · 💰 Mon argent ;
- **🔧 Entretien**, pleine largeur.

**Les 8 tuiles ne disparaissent plus** : l'éleveur les retrouve toujours aux mêmes places. Un test vérifie l'ordre.
- Sans bande en cours, Saisie du jour, Ventes et sorties, Peser et Traitement ouvrent une petite page « Aucune bande en cours » (avec 🐣 Nouvelle bande si des poussins attendent, et 📈 Mes bandes).
- À l'intérieur des écrans de regroupement, une entrée sans objet disparaît : « Nouvelle bande » sans poussins en attente, « Peser » sans bande.

**Écrans de regroupement** (grosses cases) :

| Tuile | Contenu | Pastille |
|---|---|---|
| 🐔 Ma bande | 🐣 Nouvelle bande · ⚖️ Peser · 📈 Mes bandes | poussins en attente |
| 💉 Vaccins et soins | en haut, vaccins en retard / du jour (avec « ✓ C'est fait ») / de demain (sans bouton) ; dessous 💊 Traitement · 💬 Mes signalements | aujourd'hui, demain, en retard |
| 📦 Mes produits | en haut, livraisons à confirmer (« ✓ Tout reçu », « J'ai reçu moins ») ; dessous 🛒 J'ai acheté · 🧺 Mon stock · 📦 Mes livraisons | livraisons à confirmer |

- **Ventes et sorties** et **Poulet malade** ouvrent directement leur écran (bande la plus utile, pastilles B1 / B2).
- « Mes déclarations » s'appelle **« Mes signalements »** chez l'éleveur.
- **« ✓ C'est fait »** d'un vaccin enregistre directement (vaccin, mode, poulets présents, doses : comme l'écran du vaccin), puis « Fait ✓ — Annuler (10) ». Le nom du vaccin ouvre l'écran complet.

| Action | Clics |
|---|---|
| Saisie du jour → Envoyer | 2 |
| Ventes et sorties → Enregistrer | 2 |
| Vaccins et soins → C'est fait | 2 (1 depuis le raccourci de l'accueil) |
| Poulet malade → Envoyer | 2 |
| Mes produits → Tout reçu | 2 |
| Ma bande → Nouvelle bande → Commencer | 3 |
| Ma bande → Peser → Enregistrer | 3 |
| Mes produits → J'ai acheté → Enregistrer | 3 |
| Mon argent → J'ai payé → Enregistrer | 3 |
| Vaccins et soins → Traitement → Enregistrer | 3 |
| Entretien → Fait ✓ | 2 |
| 📞 {Prénom} | 1 |
| 👤 Moi → Se déconnecter | 2 |

### Argent de l'éleveur (lot 11)

- **Mon argent** :
  - 3 grosses cartes : **Gagné** (ventes) · **Dépensé** (achats personnels + dépenses) · **Reste** (en rouge s'il est négatif) ;
  - période en cases : **Ce mois** · **Cette bande** (pastilles B1 / B2 ; sans bande en cours, la dernière terminée) · **Tout** ;
  - bouton **« 💸 J'ai payé »** ;
  - derniers mouvements ; une vente sans montant est **« à compléter → »** (un toucher pour l'ajouter).
- **J'ai payé** :
  - catégorie en grosses images (liste `categories_depenses`, Configuration → Listes ; l'émoji en tête du nom sert d'image, 📦 sinon) ;
  - montant en FCFA ;
  - bâtiment facultatif ;
  - photo du reçu facultative ;
  - date jusqu'à 3 jours en arrière ;
  - « Enregistrer », puis « Enregistré ✓ — Annuler (10) ». Fonctionne sans réseau.
- **Ventes et sorties** : « Combien avez-vous reçu ? », montant facultatif, pour Abattoir et Vente seulement. L'éleveur le complète **une fois** plus tard ; ensuite, seul l'agent le corrige, avec un motif.
- **J'ai acheté** : bâtiment facultatif (caché pour les poussins).
- **Rattachement aux bandes** :
  1. avec bâtiment : à la bande en cours de ce bâtiment ;
  2. sans bâtiment : partagé entre les bandes en cours au prorata des poulets présents, sans erreur d'arrondi ;
  3. poussins : à la bande qui les a reçus ;
  4. aucune bande ce jour-là : « hors bande ».

  Calculé par `app/services/argent.py`, figé dans le bilan à la clôture et mis à jour à chaque saisie d'argent.
- **Bilan de fin de bande** : chiffre d'affaires, dépenses, marge.
- **Aide de l'État** : la phrase « Sans l'aide de l'État, cette bande vous aurait coûté X FCFA de plus » n'apparaît que si **toutes** les livraisons subventionnées rattachées ont une valeur. Sinon rien.
- **Qui voit quoi** :
  - l'éleveur : tout ;
  - l'agent, et l'ADMIN : carte « Argent de l'éleveur » sur la fiche ferme, avec correction et motif inscrit au journal. L'agent peut aussi saisir « J'ai payé » pour l'éleveur, marqué « Agent pour l'éleveur » dans la liste et au journal ;
  - la DGE : totaux par province dans le tableau de bord seulement, et « — » sous 3 fermes ;
  - BCEG et VETO : rien.

### Achats personnels de l'éleveur (« J'ai acheté »)

- **Rangement** : ils sont rangés avec les livraisons, en origine « Achat personnel ». Numéro ACH-AAAA-NNNNNN, non subventionné.
- **Stock** : le stock de la ferme = livraisons de l'État confirmées + achats − utilisations. « Mon stock » montre ce qui a été reçu de chaque source.
- **Poussins achetés** : les morts à l'arrivée sont demandés, et les poussins deviennent « en attente de bande ».
- **Contrôles** : les achats n'entrent **jamais** dans les contrôles des intrants de l'État. Ces contrôles passent tous par une seule fonction, `intrants.livraisons_de_l_etat()` : listes, alertes, mortalité à l'arrivée, exports, et le futur recoupement livraisons / consommations.
- **Annulation** : « Enregistré ✓ — Annuler (10) » juste après l'enregistrement. Ensuite, seule une correction par l'agent est possible, avec un motif inscrit au journal.

### Entretien des installations (lot 10)

- **Tuile « 🔧 Entretien »** : la pastille compte les tâches à faire aujourd'hui + les pannes en cours. Elle est rouge s'il y a une panne.
- **Écran Entretien**, de haut en bas :
  - les **pannes en cours**, en cartes roses, avec « C'est réparé » ;
  - les **tâches** à faire, avec un bouton « Fait ✓ » ;
  - les tâches faites, grisées « ✓ fait » jusqu'à la fin de leur période (jour, semaine, mois) ;
  - le bouton **« ⚠️ Quelque chose est en panne »**.
- **Regroupement** : une seule carte par tâche, « B1 et B2 ». Un seul « Fait ✓ » coche tous les bâtiments de la carte.
- **Retard** : « pas fait la semaine dernière », « pas fait le mois dernier ». **Jamais de retard pour les tâches du jour** (pas de « pas fait hier », décision du 09/11). Les tâches en retard passent en tête.
- **Tâches selon la ferme** :
  - celles de la bande, seulement pour les bâtiments avec une bande en cours ;
  - celles de la ferme, seulement si la ferme a l'installation (pédiluve, groupe électrogène, forage ou puits) ;
  - « Nettoyer et désinfecter » apparaît à la **clôture** d'une bande, pour le bâtiment vidé.
- **Nouvelle bande dans un bâtiment pas désinfecté** : un avertissement **non bloquant**, « Je nettoie d'abord » ou « Commencer la bande ». Continuer est inscrit au journal, et la bande est marquée sur la fiche de la ferme.
- **Panne** :
  - 6 images (Chauffage, Eau, Électricité, Ventilation, Mangeoires, Bâtiment) ;
  - le bâtiment, ou « Toute la ferme » ; ce choix est caché s'il n'y a qu'un bâtiment ;
  - photo facultative ;
  - gros bouton rouge « Envoyer à mon agent ». Il n'y a **pas d'annulation** après Envoyer.
- **Annuler** : « Fait ✓ — Annuler (10) » après « Fait ✓ », et « Réparé ✓ — Annuler (10) » après « C'est réparé ». Annuler une réparation remet la panne en « Signalée », fait revenir l'alerte de l'agent, et l'annulation est inscrite au journal.
- **Agent** :
  - alerte « Panne signalée » sur son accueil ;
  - carte « Entretien » sur la fiche de la ferme : dernière synchronisation du téléphone, pannes, bandes ouvertes sans désinfection, retards, dernière désinfection de chaque bâtiment ;
  - il peut cocher ou réparer pour l'éleveur.
- **Sans réseau** : « Fait ✓ », « Envoyer » et « C'est réparé » sont gardés sur le téléphone, puis envoyés au retour du réseau.
- **Liste des tâches** : Configuration → « Tâches d'entretien » (ADMIN). On ne supprime pas une tâche, on la désactive. La liste de départ est **à valider par les vétérinaires**.

### Protection des saisies en attente (lot 10)

- Sur l'accueil, si des saisies attendent le réseau depuis plus de 24 h, un bandeau orange s'affiche : « ◷ N saisies attendent le réseau. Ne videz pas les données de l'application. »
- Fiche de la ferme : « Dernière synchronisation du téléphone de l'éleveur : il y a X jours ». La mention « à vérifier » s'ajoute à partir de 3 jours.
- La consigne pour les agents est dans `docs/exploitation.md`.

## Liste de contrôle d'un écran (à cocher dans chaque rapport de lot)

- [ ] Un seul bouton mis en avant ?
- [ ] L'action courante se fait en 3 clics au plus ?
- [ ] Aucun bouton ni tuile que l'utilisateur ne peut pas utiliser ?
- [ ] Aucun mot technique visible ?
- [ ] Utilisable d'une main sur un écran de 360 px de large, sans défilement horizontal de la page ?
- [ ] Écran éleveur : saisie du jour en moins de 30 secondes ?
- [ ] Rien d'ajouté qui n'ait été demandé ?
