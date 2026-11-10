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
  **Exception « action rare et sensible » (validée au lot 13)** : deux actions peuvent demander 4 touchers.
  - « Retirer mon accord » à la BCEG : Moi → Ma banque → Retirer mon accord → Oui, retirer. La confirmation est obligatoire.
  - « Changer son mot de passe » : Moi → Mon compte → Changer mon mot de passe → Enregistrer. L'écran reste séparé de Mon compte (ancien mot de passe, nouveau deux fois, règles en clair).
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

### Réponses, visites, conflits, case vide (lot 12)

**Case vide ≠ zéro** (saisie du jour, éleveur et agent) :
- les morts et l'aliment démarrent à **« — »** ;
- grosses cases **« ✓ Aucun mort »** et **« Pas d'aliment donné »** (0, explicite), et **« Comme hier (N sacs) »** si la veille a été saisie. Ce sont des choix dans l'écran, jamais un pré-remplissage ;
- le premier « + » met 1, et « − » à 0 revient à « — » ;
- « Envoyer » est refusé tant qu'une case est à « — », sur le téléphone (même sans réseau) et sur le serveur : « Touchez « Aucun mort » s'il n'y a pas eu de mort ».

La saisie du jour reste à **2 clics**.

**Calculs** : un jour non saisi n'est **jamais** compté comme 0 mort ou 0 aliment. Il est compté « non saisi » (régularité). La mortalité cumulée et l'indice de consommation portent la mention **« incomplet »** sur la fiche de la bande, le bilan, le rapport PDF et le tableau de bord (« Jours non saisis »).

**Mes signalements** (Vaccins et soins → 💬) :
- quatre états simples : Envoyé ✓ · Le vétérinaire regarde · 💬 Réponse du vétérinaire · Terminé. Jamais « confirmée » ni « infirmée » ;
- les conseils et le message du vétérinaire sont affichés en gros ;
- une réponse non lue met la pastille 💬 sur la tuile et la ligne « 💬 Le vétérinaire vous a répondu → » sur l'accueil (1 toucher).

**Visites** :
- la ligne d'état de l'accueil affiche « 📅 Visite de Paul jeudi 12 » ;
- 👤 Moi → 📋 Mes visites donne les recommandations en gros ;
- une pastille « nouveau » reste sur 👤 Moi tant que le dernier compte rendu n'est pas ouvert.

**À vérifier** : l'éleveur voit seulement « ◷ À vérifier par votre agent », jamais un message d'erreur. Règle complète dans `docs/hors_ligne.md`, section 5.

| Qui | Action | Clics |
|---|---|---|
| Éleveur | Accueil → « 💬 Le vétérinaire vous a répondu » | 1 |
| Éleveur | Vaccins et soins → Mes signalements | 2 |
| Éleveur | 👤 Moi → Mes visites | 2 |
| Vétérinaire | Alertes → alerte → Envoyer à l'éleveur | 3 |
| Agent | fiche ferme → Planifier une visite → Enregistrer | 2 |
| Agent | fiche ferme → Compte rendu → Enregistrer | 2 |
| Agent | Alertes → Saisies à vérifier → Retenir cette version | 2 |

### Tutoriel, aides, Mon compte, Ma banque (lot 13)

- **Tutoriel** : 4 écrans au premier lancement, une fois par compte (gardé sur le serveur). « Suivant » et « Passer » sur chaque écran. On le revoit depuis 👤 Moi → « 🎬 Revoir la présentation ». Le prénom affiché est celui de l'agent réellement affecté. Sans agent ou sans téléphone d'agent, pas de bouton 📞.
- **« ? »** : un bouton rond de 44 px en haut des 9 écrans principaux (saisie du jour, sortie, pesée, vaccin, poulet malade, achat, dépense, entretien, Mon argent).
  - 1 toucher ouvre **l'aide de cet écran** : 3 étapes au plus, chacune avec le vrai bouton reproduit en petit ; « ‹ Retour » ramène à l'écran.
  - La liste complète est dans 👤 Moi → « ❓ Comment faire ? ». Les aides marchent sans réseau.
  - Les textes se modifient dans Configuration → Aides (ADMIN), et chaque modification est inscrite au journal.
  - Le « ? » n'est montré qu'à l'éleveur.
- **Mon compte** :
  - affiché en gros : nom, téléphone, fermes et bâtiments, agent 📞, vétérinaires de la zone. Au-delà de 3 vétérinaires, d'abord ceux qui ont répondu à l'éleveur, puis « Voir les autres » ;
  - **seuls le téléphone et le mot de passe** se modifient. Pour le reste : « Pour changer cela, appelez Paul » ;
  - les règles du mot de passe sont affichées en clair.
- **Me déconnecter** : s'il reste des saisies gardées sans réseau, un avertissement s'affiche (« 1 saisie n'est pas encore partie… Elle partira quand vous vous reconnecterez ») et il faut un second toucher. Les saisies ne sont **jamais effacées**. Elles gardent leur auteur et ne partent **jamais** sous le compte d'une autre personne connectée sur le même téléphone.
- **Ma banque** (consentement BCEG) :
  - seulement pour le **responsable** d'une ferme **financée par la BCEG** (case et responsable sur la fiche ferme, réglés par l'agent ou l'ADMIN). Sinon, rien ne s'affiche ;
  - ce que la BCEG verra (ventes, dépenses, marge, régularité) et ne verra pas ; « J'accepte » ou « Je refuse » ; « Retirer mon accord » avec confirmation ;
  - historique daté, inscrit au journal ;
  - un changement de responsable fait tomber l'accord, et le nouveau doit répondre (pastille sur Moi).

### Contrôle de l'interface de l'éleveur (lot 13)

- **Contrastes (WCAG AA)** : 4,5 pour le texte courant, 3 pour le gros texte gras. Couleurs de texte : `--e-gris` #5c6683 (5,4 sur crème), `--e-orange-fonce` #a8520f pour « attention » en texte (5,4), `--e-prairie-fonce` #17734a (5,2 sur vert pâle), et le bleu foncé de la charte pour les liens.
  - **Pastilles orange** : fond orange, texte bleu nuit (5,4). Elles restent distinctes des pastilles rouges, où le texte est blanc : l'orange reste « attention », le rouge « alerte ».
- **Tailles** : textes de 12 px (0,75 rem) au moins, boutons et cases de 44 px de haut au moins. C'est vérifié par un contrôle automatique au navigateur sur toutes les pages de l'éleveur (rapport du lot 13).
- **Sans réseau** : toutes les pages de l'éleveur viennent d'**une seule liste** (`routes/hors_ligne.PAGES_ELEVEUR`, servie par `/hors-ligne/pages`). Le téléphone la garde à chaque ouverture de l'accueil. Un test vérifie qu'aucune page de l'éleveur n'y manque.

## G. Deux styles : TERRAIN et BUREAU (lot 19 ter)

| Style | Qui | Charte |
|---|---|---|
| **TERRAIN** | **éleveur**, **agent technique**, **opérateur** (abattoir, marché, acheteur, distributeur) | « illustrée douce » de la section F : grandes tuiles, mascotte, 3 clics au plus, aucun mot technique |
| **BUREAU** | DGE, ADMIN, AUDITEUR, MAEDR, BCEG, **vétérinaire** (lisible au téléphone) | YL.1 (`perform.css`) |

- **Une seule base commune** (pas de copie) :
  - la feuille `app/static/css/terrain.css` (ex-`eleveur.css`) ;
  - les macros `templates/terrain/_macros.html` (tuile, ligne d'état) ;
  - l'en-tête `templates/terrain/_entete.html` ;
  - la présentation au premier lancement et « Comment faire ? » (mécanisme du lot 13, textes propres à chaque profil, clés `ag_…` et `op_…`).
- **Classes du corps** : `theme-terrain` + `terrain-eleveur`, `terrain-agent` ou `terrain-operateur`. `theme-eleveur` reste posée pour l'éleveur seul : ses fêtes (sauts, étincelles, « Bien reçu ! », chiffre qui rebondit) et `eleveur.js`. **L'agent et l'opérateur n'ont aucune fête.**
- **En-tête** : dégradé **bleu** pour l'éleveur et l'agent, **vert** (prairie `#2fa36b` → `#1f7a4f`) pour l'opérateur. C'est la même règle, avec deux variables (`--t-entete-debut`, `--t-entete-fin`).
- **L'éleveur ne voit aucun changement** : ses 20 écrans de référence à 360 px sont identiques au pixel avant et après le lot 19 ter.
- **Agent, « Version bureau »** (👤 Moi, sur un écran large seulement) : son accueil de pilotage et ses écrans détaillés (tableaux, carte, fiches). Ses écrans de pilotage ouverts depuis le terrain (« Ses chiffres »…) gardent toujours le style bureau. Retour : « Version terrain ».

### Agent : accueil et clics

En-tête : « Bonjour Paul · Estuaire · 14 fermes », 🔔 (fermes en rouge + saisies à vérifier), 👤 Moi. Ligne d'état : 2 lignes au plus, la plus urgente d'abord, puis « 📶 Tout est envoyé ✓ » ou « ◷ N saisies en attente ». Tuiles, ordre fixe : 🚗 Ma tournée (grande) · 🏠 Mes fermes · ✍️ Saisir pour un éleveur · 📋 Visite · ⚖️ À vérifier · 📦 Stock et commandes · ➕ Nouvel éleveur · 👤 Moi.

| Action | Clics |
|---|---|
| Ma tournée → 🧭 Y aller | 2 |
| Saisir pour un éleveur → (ferme, bâtiment) → 📝 Jour → Envoyer | 3 |
| Saisir pour → ⚖️ Pesée / 💉 Vaccin / 🚚 Sortie → Enregistrer | 3 |
| Visite → (ferme) → Envoyer le compte rendu | 2 |
| Visite → Biosécurité « Faire » → Enregistrer | 3 |
| À vérifier → (version, raison) → Valider | 2 |
| Stock → (ferme) → Compter → Enregistrer | 3 |
| Stock → Commander → Envoyer à la DGE | 3 |
| Nouvel éleveur → ferme → Créer le compte (« Suivant » reste dans l'écran) | 3 |
| Moi → Version bureau | 2 |

Le chemin par la fiche ferme (Mes fermes → ferme → Saisir pour → Jour → Envoyer, 5 clics) est secondaire. La tuile « Saisir pour un éleveur » reste à 3.

### Opérateur : accueil et clics

En-tête vert, avec le nom de l'établissement. Ligne d'état : lots à revoir, écarts à expliquer, accord du vétérinaire, « N lots arrivent cette semaine », « N lots attendent le vétérinaire », envoi. Tuiles : 📷 Recevoir un lot (grande, « scanner le QR ») · 🚚 Lots qui arrivent · 📦 Mes réceptions · 👤 Moi · aide · mon compte.

| Action | Clics |
|---|---|
| Recevoir un lot → (lecture du QR) → Valider la réception | 2 |
| Recevoir un lot → Chercher le numéro → Valider | 3 |
| Écart : … → Valider avec cet écart | 2 |
| Lot à garder à part → Je les reçois et je les garde à part | 2 |
| Lots qui arrivent, Mes réceptions | 1 |

**Mots** : jamais « sous réserve », « bloquant » ni « événement » à l'écran de l'opérateur (un test les cherche). On écrit : « Gardez ces poulets à part — Le vétérinaire doit donner son accord avant l'abattage ».

### Contrôle (lot 19 ter)

Tailles et contrastes sont vérifiés au navigateur sur toutes les pages gardées sans réseau : 81 pour l'agent, 11 pour l'opérateur.
- Plus aucune case ni pastille de moins de 44 px.
- Plus aucun texte de moins de 12 px sur les écrans terrain.
- **Boutons pleins à la norme** (décision du 09/11/2026, pour les trois profils terrain, éleveur compris) : mêmes teintes, un peu plus foncées, réservées aux boutons à texte blanc.
  - Vert `--e-prairie-bouton` `#268356` : 4,7.
  - Bleu `--e-bleu-bouton` `#1e73d8` : 4,7.
  - Rouge `--e-rouge-bouton` `#e1292f` : 4,6.
  - Rouge des textes (sur blanc, crème ou rose) `--e-rouge-texte` `#d21e24` : 4,6 au moins.

  Les teintes claires restent pour les feux, les pastilles et la mascotte. Le titre « Sorties de cette bande » passe à 12 px. Captures avant / après : `docs/captures/contrastes/`.

## K. Règle des formulaires (lot A1)

**Un écran = une liste + « ＋ Ajouter ».** Le formulaire s'ouvre **toujours en fenêtre**. Un seul composant par style (`.modal-overlay > .modal-box`, `static/js/fenetre.js`) :
- **terrain** : une feuille qui monte du bas, avec une poignée (glisser vers le bas pour fermer), ✕, et le fond grisé qui la referme ;
- **bureau** : une fenêtre au centre.

Quand on arrive sur un écran pour saisir (Pesée, Sortie…), la fenêtre d'ajout est **ouverte d'office** ; ✕ la ferme sur la liste. Un écran sans liste derrière (vaccin, traitement, J'ai payé, J'ai acheté, panne, poulet malade, compte rendu) ramène à son écran de liste. La **saisie du jour reste à 2 clics** : sa carte est sur l'accueil de l'éleveur (et sur « Saisir pour » de l'agent) ; ses saisies passées s'ouvrent en fiche.

**Une ligne touchée** ouvre la même fiche **préremplie**, avec « Enregistrer la modification » · « 🗄️ Archiver » · ✕ (`templates/_fiches.html`, `services/fiches.py`). Le formulaire est déjà dans la page : il s'ouvre et s'envoie **sans réseau** (file d'attente du téléphone).

**ARCHIVER remplace SUPPRIMER.**
- L'élément archivé est masqué des listes et **exclu des calculs** (`models/base.py` : masquage de toutes les requêtes), mais **conservé**.
- Lien « 🗄️ Voir les archivées (n) » sous chaque liste ; « ↩️ Restaurer » pour l'agent de la ferme ou l'ADMIN.
- Journal : ARCHIVAGE et RESTAURATION, avec l'avant / après et le motif.
- **Aucune suppression physique.**
- Les écrans de bureau (catalogue, opérateurs, utilisateurs, listes, bâtiments) : « 🗄️ Archiver » / « ↩️ Restaurer » remplace la case « actif » ; la colonne `actif` reste et suit l'archivage.
- Fermes et bandes : l'ADMIN archive seulement une ferme ou une bande **restée vide** (créée par erreur), avec un motif ; « 🗄️ Archivées » sur leur liste.

**Qui modifie quoi.**
- Chacun modifie ou archive **ses propres saisies** tant que la bande est ouverte. La ligne modifiée porte ✏️ ; la fiche dit « Saisie par … · modifiée N fois ».
- **Bande terminée** : lecture seule, « 🔒 Cette bande est terminée. Pour corriger, appelez votre agent. » + 📞. Seul un profil habilité (agent de la ferme, ADMIN) corrige, **avec un motif**.
- **Correction par une autre personne** (point 3 validé) : la saisie du jour garde la règle des deux versions (lot 12) ; ailleurs, motif obligatoire, avant / après au journal, et un message « Votre agent a corrigé… » dans « À vérifier ».
- **Sortie** (point 4 validé) : archiver une sortie dont le lot a été reçu est refusé ; sinon la sortie est archivée et son lot annulé (la restauration le réactive).
- Achat de poussins déjà mis en bande, signalement déjà suivi par le vétérinaire, bâtiment avec une bande en cours : non archivables.

**Écrans à la règle (lot A1).**

| Style | Écran | Liste | Ajout en fenêtre | Fiche (modifier / archiver) |
|---|---|---|---|---|
| Terrain | Saisie du jour | 3 dernières saisies (accueil) | carte de l'accueil (2 clics) | ✓ |
| Terrain | Pesées | pesées de la bande | ✓ ouverte d'office | ✓ |
| Terrain | Sorties / ventes | sorties de la bande | ✓ ouverte d'office | ✓ |
| Terrain | Vaccins et soins | « Déjà faits » | ✓ | ✓ |
| Terrain | Dépenses (Mon argent) | mouvements | ✓ | ✓ (dépense, vente, achat) |
| Terrain | Achats (Mon stock) | derniers achats | ✓ | ✓ |
| Terrain | Entretien | pannes, « Faits récemment » | ✓ (panne) | ✓ |
| Terrain | Signalements | mes signalements | ✓ | ✓ |
| Terrain (agent) | Visites / comptes rendus | fiche de la ferme | ✓ | ✓ |
| Bureau | Fiche de bande (journal) | saisies, pesées, sorties, traitements | — | ✓ (bouton ✏️) |
| Bureau | Fermes, bandes | listes | pages existantes | 🗄️ ADMIN (vides) |
| Bureau | Bâtiments, catalogue, utilisateurs, listes | tableaux | fenêtre au centre | « Archiver » remplace « Désactiver » |
| Bureau | Opérateurs | liste | page existante | « Archiver » / « Restaurer » |

**Lot A2.** « Catalogue des intrants » et « Fournisseurs » (bureau ; ADMIN et DGE écrivent, l'agent lit) : tableau, « ＋ Nouvel article » / « ＋ Nouveau fournisseur », fiche en fenêtre au centre, « 🗄️ Archiver » / « ↩️ Restaurer ». Le stock montre l'origine : « Programme · Externe » (agent, fiche de la ferme), « il reste N de l'État · M à vous » (éleveur). L'écart d'inventaire porte sur le Programme seulement.

**Autres écrans, pas encore à la règle** (à reprendre dans un lot suivant) : création et modification d'une ferme et d'un opérateur (pages entières), livraisons de l'État (confirmation, « reçu en moins »), ouverture d'une bande et rattrapage, clôture, tâches d'entretien (ADMIN), aides, paramètres, provinces, consentement BCEG, biosécurité, nouvel éleveur, planification des visites, réception de l'opérateur, alertes et décisions du vétérinaire, À vérifier.

**Petits défauts corrigés (relevés au dossier).** Pastilles des bâtiments à 44 px ; numéro de ferme sous le nom à 12,8 px (« J'ai acheté », « J'ai payé », « Mes produits ») ; bouton « Retour à l'accueil » des pages d'erreur à 13,6 px ; « ✓ envoyé » en vert foncé (5,2) ; numéro de bande en majuscules dans « À vérifier ».

## Liste de contrôle d'un écran (à cocher dans chaque rapport de lot)

- [ ] Un seul bouton mis en avant ?
- [ ] L'action courante se fait en 3 clics au plus ?
- [ ] Aucun bouton ni tuile que l'utilisateur ne peut pas utiliser ?
- [ ] Aucun mot technique visible ?
- [ ] Utilisable d'une main sur un écran de 360 px de large, sans défilement horizontal de la page ?
- [ ] Écran éleveur : saisie du jour en moins de 30 secondes ?
- [ ] Rien d'ajouté qui n'ait été demandé ?
