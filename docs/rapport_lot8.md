# SORRA — Rapport du lot 8 : espace éleveur « illustré doux »

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1, et tout sera déployé ensemble avec le nom de domaine.

**Tests :** **257 tests réussis** et 1 réservé à PostgreSQL, dont 17 nouveaux dans `tests/test_eleveur.py` et 1 nouveau test de charte.

**Migration :** 0010 ajoute 4 paramètres :
- les 3 seuils des étoiles ;
- le conseil du feu rouge.

**Références :**
- description validée : `docs/maquettes/maquettes_lot8.md` ;
- aperçu de l'étape 1 : `docs/maquettes/apercu_lot8.html` ;
- règles : `docs/ergonomie.md`, section F.

**Ajouts techniques :**
- **Police** : Nunito (licence libre OFL), servie en local avec sa licence (`static/polices/LICENCE-nunito.txt`). Elle a été téléchargée une seule fois pendant la construction, et l'application ne charge rien depuis Internet.
- **Aucune autre bibliothèque.**

## Ce qui a été fait

**Une feuille dédiée**, `static/css/eleveur.css`, n'est chargée que pour l'éleveur connecté, la page publique du QR code et l'écran de connexion (écart 1, validé).
- Pesée, Sortie, Poulet malade, Reçu moins et Vacciner sont les mêmes écrans pour l'éleveur et pour l'agent. L'éleveur les voit en « illustré doux », l'agent dans la charte bleu nuit habituelle.
- Les couleurs ne sont écrites que dans le `:root` de la feuille, et un test le vérifie.

**Le poulet mascotte** reprend le dessin du logo SORRA, au trait fin, dans `app/utils/logo.py`. Il a 4 visages :

| Feu | Visage |
|---|---|
| vert | content |
| orange | inquiet |
| rouge | malade : corps rosé, thermomètre |
| pas de bande | il dort |

**Les 6 idées ludiques :**
1. Le poulet suit le feu de la bande.
2. Carte « Votre bande grandit » : un poussin dessiné avance sur une barre jaune. Messages : « C'est parti ! », « À mi-chemin ! », « Plus que N jours ».
3. Compteurs : le chiffre rebondit, avec une petite vibration.
   - « Bien reçu ! » au feu vert : 2 sauts, étincelles, série, record, les 2 dernières saisies.
   - Au feu orange ou rouge : seulement « Envoyé ✓ — Votre agent est prévenu ».
   - Sans réseau : « ◷ Sera envoyé dès que le réseau revient ».
4. Série « 🔥 N jours » par bande, et record personnel sur toutes les bandes.
5. Étoiles de 1 à 3, gardées au bilan. Seuils dans les Paramètres, à valider par les vétérinaires.
6. Messages vivants :
   - « Bonjour Jean ! 👋 » ;
   - « 💪 +210 g en 7 jours » après une pesée, au feu vert seulement.

**Plusieurs bandes à la fois** (ajout demandé) :
- des pastilles par bâtiment (« B2 · J15 », « B1 · vide »), avec la couleur du feu et un point orange tant que la saisie du jour n'est pas faite ;
- les bandes à saisir passent en premier ;
- « À faire aujourd'hui » est commun, chaque ligne préfixée par son bâtiment ;
- « ✓ Saisie du jour envoyée » remplace le bouton Envoyer ;
- après un envoi : « Il reste B3 à saisir → » ;
- sur un bâtiment vide : étoiles de la dernière bande et « 🐣 Ouvrir une bande ici ».

## Les 14 écrans et leurs captures

Les captures sont dans `docs/captures/lot8/`. Toutes ont été faites au format téléphone (360 px), sauf mention « ordinateur ».

| # | Écran | Capture | Chemin |
|---|---|---|---|
| 1 | Connexion | `01_connexion.png` | dégradé bleu, poulet, bouton vert, « Mot de passe oublié ? Appelez votre agent. » |
| 2 | Livraison à confirmer | `02_livraison_a_confirmer.png` | en haut de l'accueil : « ✓ Tout reçu » en vert, « J'ai reçu moins ». Le bandeau sombre « Reçue — merci ! · Annuler » est inchangé. |
| 3 | J'ai reçu moins | `03_recu_moins.png` | compteur prérempli (« livré : 40 »), raisons en grosses cases, « Envoyer » en bleu |
| 4 | Ouvrir une bande | `04_ouvrir_une_bande.png` | « 🐣 Nouveaux poussins », bâtiments en cases (les occupés grisés, avec leur raison), « Commencer la bande » en vert, « Fin prévue le … ». La capture montre le cas sans poussins en attente. |
| 5 | Ma bande aujourd'hui | `05_ma_bande_aujourdhui.png`, `05b_autre_batiment.png`, `05c_ordinateur.png` | pastilles, « À faire » commun, carte poulet, « Votre bande grandit » avec 🔥, compteurs, « Envoyer ✓ », « ⚖️ Peser » et « 🚚 Sortie » |
| 6 | Bien reçu ! | `06_bien_recu_il_reste.png` | « 15 jours d'affilée », « Nouveau record personnel ! », 2 dernières saisies ✓, « Il reste B3 à saisir → » |
| 7 | Pesée | `07_pesee.png` | « Poids moyen … — Dans la courbe ✓ » et « 💪 +N g en N jours » en direct, au feu vert |
| 8 | Sortie | `08_sortie.png` | « Pour qui ? » en cases, compteur, « Il restera N poulets » |
| 9 | Poulet malade | `09_poulet_malade.png` | « ＋ Ajouter une photo », « Qu'avez-vous vu ? » (sélection en rouge), « Poulets touchés », « 🎤 Ajouter un message vocal », bouton rouge |
| 10 | Feu rouge | `10_feu_rouge.png` | carte rosée, poulet malade, « Beaucoup de morts aujourd'hui », « 🩺 Signaler », « 📞 Appeler mon agent », « 📋 Conseil » |
| 11 | Vaccin du jour | `11_vaccin_du_jour.png` | vaccin en gros, mode et poulets, compteur et stock, « ✓ C'est fait », « Pas encore fait » |
| 12 | Bande terminée | `12_bande_terminee.png`, `12b_mes_bandes.png` | étoiles, phrase, 4 chiffres, « Voir mes bandes passées » vers « Mes bandes » |
| 13 | Pas de réseau | `13_pas_de_reseau.png` | « ◷ Sera envoyé dès que le réseau revient », bandeau « 📵 Pas de réseau », liste ◷ en attente puis ✓ envoyé |
| 14 | Page publique | `14_page_publique.png`, `14b_page_publique_ordinateur.png` | bandeau vert, poulet, « Élevé par · … · Lot … », mention, petit « SORRA » |
| — | Agent (charte sobre) | `agent_pesee_charte_sobre.png` | même page Pesée, sans la feuille de l'éleveur |

**Vérification au navigateur** (Chromium, 360 px et 1 366 px) :
- toutes les pages font 360 px de large, sans défilement horizontal ;
- aucune erreur ;
- le parcours sans réseau, puis au retour du réseau, a été rejoué.

En chemin, j'ai corrigé :
- le débordement de « Mes déclarations », dû à un tableau trop large ;
- le retour à la bande saisie après « Envoyer » ;
- les accords « 1 mort », « 1 sac » ;
- l'écran du vaccin du jour, simplifié pour l'éleveur.

## Décisions et écarts (tous validés : 1 à 12)

1. La connexion est en style illustré pour tout le monde.
2. La série ne tombe pas à 0 le matin : si rien n'est envoyé aujourd'hui, on compte jusqu'à hier.
3. Le record se recalcule à partir des saisies existantes.
4. Indice de consommation inconnu : 2 étoiles au plus. Une bande de rattrapage reçoit aussi ses étoiles.
5. Les raisons de « J'ai reçu moins » viennent de la liste réglable « Motifs d'écart » (4 valeurs aujourd'hui).
6. Le vaccin se compte dans l'unité du catalogue. « Pas encore fait » n'enregistre rien. Le retard reste fixé à 2 jours.
7. Le conseil du feu rouge est un paramètre. L'ADMIN le modifie dans Paramètres, le VETO depuis une carte sur Vaccins et traitements. Chaque changement est journalisé.
8. Au feu rouge, les compteurs restent sous la carte rosée.
9. Bilan de l'éleveur : « Poulets vendus » compte les sorties Abattoir et Vente. Nouvelle page « Mes bandes ».
10. Le numéro de lot est affiché sur la page publique, avec « Élevé par » suivi du nom de la ferme.
11. « Bien reçu ! » ne s'affiche qu'après la saisie du jour, avec le feu recalculé après l'envoi.
12. Les bâtiments occupés sont grisés à l'ouverture d'une bande, avec leur raison.

**Choix faits pendant la construction :**
- **« Nouveau record personnel ! »** ne s'affiche qu'à partir de 3 jours, pour éviter « record » dès le 1er jour de la première bande.
- **« Il reste B2 à saisir → »** : l'écran ne se ferme pas tout seul tant qu'il reste une bande. Il se ferme avec le bouton ou « Plus tard ». Sinon, il se ferme seul après environ 2 s.
- **Lignes de « À faire »** : un toucher ouvre la bonne bande. Pour un vaccin du jour, il ouvre directement l'écran du vaccin de cette bande.
- **Sur un bâtiment vide**, les étoiles de la dernière bande renvoient vers son bilan.
- **Encouragement « comparaison avec la province »** : affiché seulement au feu vert.

## Liste de contrôle d'ergonomie (`docs/ergonomie.md`)

- [x] **Un seul bouton mis en avant par écran** : Envoyer ✓, Tout reçu, Commencer la bande, C'est fait (en vert) ; Envoyer, Enregistrer (en bleu) ; Signaler (en rouge au feu rouge).
- [x] **3 clics au plus** :
  - saisie du jour : 2 touchers ;
  - changer de bâtiment : 1 toucher ;
  - vaccin du jour : 2 touchers ;
  - « Il reste B3 » : 1 toucher.
- [x] **Aucun bouton ni tuile inutilisable** : pas de pastilles avec un seul bâtiment ; « Ouvrir une bande ici » seulement s'il y a des poussins en attente. Seule exception : les bâtiments occupés grisés (écart 12, validé).
- [x] **Aucun mot technique visible.**
- [x] **360 px sans défilement horizontal** sur toutes les pages de l'éleveur.
- [x] **Saisie du jour en moins de 30 s** : mêmes gestes qu'avant, avec ou sans réseau.
- [x] **Rien d'ajouté sans demande**, à deux nécessités près :
  - la page « Mes bandes », pour « Voir mes bandes passées » ;
  - la carte « Conseil » du VETO, pour que le conseil soit modifiable par lui.

## Tests automatiques ajoutés (`tests/test_eleveur.py`)

- **Étoiles** : règle de départ, indice inconnu, jamais 0, seuils réglables ; étoiles gardées au bilan, visibles dans « Mes bandes » ; l'agent garde son bilan.
- **Série** : jours consécutifs, jour manqué et « On repart » ; record sur toutes les bandes ; saisie sans réseau comptée à sa date.
- **Poulet** : le visage suit le feu (vert, orange, rouge, vide).
- **Conseil du feu rouge** : modifiable par le VETO (et l'ADMIN), refusé à l'éleveur et à l'agent.
- **« Bien reçu ! »** :
  - étincelles au feu vert seulement ;
  - rien de joyeux en orange ni en rouge ;
  - jamais montré à l'agent.
- **Nombre de bâtiments** :
  - 1 bâtiment : pas de pastilles ;
  - 2 bâtiments : le point orange disparaît après l'envoi, « Il reste B2 à saisir », les saisies restent séparées, l'ajout passe par la confirmation ;
  - 4 bâtiments : ordre des pastilles, « À faire » commun préfixé.
- **Bâtiment vide** : étoiles et « Ouvrir une bande ici ».
- **Vaccin** : « Pas encore fait » n'enregistre rien, le vaccin reste à faire, puis passe en retard et l'agent est prévenu.
- **Pesée** : « 💪 +210 g en 7 jours » au feu vert, rien au feu rouge.
- **Feuille `eleveur.css`** : chargée pour l'éleveur, la page publique et la connexion ; jamais pour l'agent, même sur les écrans communs.

Plus, dans `tests/test_migration_et_charte.py` : les couleurs d'`eleveur.css` ne sont écrites que dans son `:root`.

## Tests que vous ferez

Relancez l'application locale, puis connectez-vous en `eleveur` / `Demo-yl2-2026` sur un téléphone ou en mode téléphone (F12, 360 px).

1. **Connexion** : nouvel écran bleu avec le poulet.
2. **Accueil** :
   - les pastilles B2, B1 apparaissent ;
   - touchez-en une : sa bande s'affiche ;
   - le point orange signale une bande pas encore saisie.
3. **Envoyer** sur une bande au vert : écran « Bien reçu ! » avec étincelles. S'il reste une bande : « Il reste … à saisir → », qui l'ouvre.
4. **Feu rouge** : envoyez beaucoup de morts. Pas d'étincelles, « Envoyé ✓ — Votre agent est prévenu », puis la carte rosée avec le conseil.
5. **Pesée** : tapez le poids. « 💪 +N g » s'affiche au feu vert, s'il y a une pesée précédente.
6. **Vaccin du jour** depuis « À faire » : « ✓ C'est fait », ou « Pas encore fait » (le vaccin reste dans la liste).
7. **Mes bandes** : étoiles des bandes terminées, puis bilan « Bande terminée ».
8. **Sans réseau** (Chrome, F12 → Réseau → Hors connexion) : « ◷ Sera envoyé dès que le réseau revient », puis « ✓ envoyé » au retour du réseau.
9. **Page publique** : scannez une étiquette ou ouvrez `/q/<code>`. Vous voyez le bandeau vert, « Élevé par » et le numéro de lot.
10. **Agent** (`agent.est`) : sa pesée et son accueil restent dans la charte bleu nuit.
11. **VETO** (`veto`) : Santé animale → Vaccins et traitements → carte « Conseil affiché à l'éleveur ». Modifiez le texte, puis vérifiez-le chez l'éleveur au feu rouge.
12. **Réduire les animations** (paramètre d'accessibilité du téléphone) : plus de sauts ni d'étincelles.

## Points à valider

- **Seuils des étoiles** (3 %, 1,7 et 5 %) et **texte du conseil du feu rouge** : à valider par les vétérinaires.
- **Le test terrain avec 3 à 5 éleveurs** (`docs/ergonomie.md`, partie E) prend tout son sens avec ce lot.
- **Liste « Motifs d'écart »** : faut-il la réduire à Manquant / Abîmé / Autre ? C'est réglable par l'ADMIN.
