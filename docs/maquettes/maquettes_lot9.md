# SORRA — Lot 9 : accueil de l'éleveur en tuiles et « J'ai acheté »

> Description fournie par le propriétaire le 09/11/2026. Aperçu indicatif de l'étape 1 :
> `docs/maquettes/apercu_lot9.html`.

**Avant tout :** relire `docs/ergonomie.md` (sections E et F). Tout l'existant du lot 8 est réutilisé : charte illustrée douce, poulet, écrans de l'éleveur, pastilles de bâtiments, série, étoiles. On **réorganise l'accès**, on ne refait pas les écrans.

## Objectif

L'accueil de l'éleveur n'est plus un tableau de bord rempli d'informations. C'est une **porte d'entrée**, avec une grosse tuile par action. Toute action se fait en **3 clics au plus** depuis l'accueil ; les « + » et « − » des compteurs ne comptent pas comme des clics.

## A. Nouvel accueil de l'éleveur (style illustré doux)

De haut en bas :

1. **En-tête** existant : poulet, « SORRA », « Bonjour {Prénom} ! 👋 ».
2. **Bandeau rouge**, seulement si une bande est au feu rouge : « ⚠️ B2 : beaucoup de morts aujourd'hui → Signaler ». Un clic ouvre « Poulet malade » avec B2 déjà choisi.
3. **Ligne d'état** (petite carte) :
   - un poulet de 44 px, avec l'expression du pire feu des bandes en cours ;
   - le texte « 2 bâtiments · tout va bien » ou « B2 demande votre attention » ;
   - en dessous, « B1 jour 23 · B2 jour 5 ».

   Rien d'autre : pas de chiffres, pas de graphique.
4. **Grande tuile verte**, pleine largeur, « ✏️ Saisie du jour ».
   - Sous-titre : « B2 à faire · morts et aliment ».
   - Pastille : nombre de bâtiments restant à saisir.
   - Quand tout est envoyé, la tuile devient plus calme : « ✓ Tout est envoyé aujourd'hui ». Elle reste cliquable, pour ajouter.
5. **Grille de tuiles sur 2 colonnes** : icône émoji en grand, nom, petit sous-titre, et pastille de couleur en haut à droite quand il faut agir.

   | Tuile | Contenu |
   |---|---|
   | 📦 Livraisons | pastille = nombre de livraisons à confirmer |
   | 🐣 Nouvelle bande | affichée seulement s'il y a des poussins en attente ; pastille = nombre de poussins |
   | ⚖️ Peser | sous-titre = bâtiment où une pesée est prévue aujourd'hui |
   | 🚚 Sortie | « vente, abattoir » |
   | 💉 Vaccins | pastille « aujourd'hui », « demain » ou « en retard » ; contient aussi « Enregistrer un traitement » |
   | 🩺 Poulet malade | tuile rose/rouge |
   | 🛒 J'ai acheté | nouvelle (voir C) |
   | 📈 Mes bandes | suivi des bandes en cours (chiffres, courbe) et bandes passées avec leurs étoiles ; réutilise la page « Mes bandes » du lot 8 |
   | 🧺 Mon stock | stock par produit : aliment en sacs et en kg, vaccins, médicaments, poussins en attente de bande |

6. **Tuile pleine largeur bleu clair** « 📞 Appeler mon agent » (lien `tel:`), affichée seulement si l'agent a un téléphone.

**Règles :**
- Une tuile sans objet disparaît (Nouvelle bande), et les autres se réorganisent sans laisser de trou.
- Les livraisons à confirmer ne s'affichent plus en grandes cartes sur l'accueil : seulement la pastille de la tuile Livraisons.

## B. « Ma bande aujourd'hui » (lot 8) devient l'écran « Saisie du jour »

- Il s'ouvre par la grande tuile verte, **directement sur le premier bâtiment pas encore saisi aujourd'hui**.
- Les pastilles B1 / B2 / B3 du lot 8 sont dans cet écran, en haut, pour changer de bâtiment.
- Il garde :
  - le poulet et la phrase du feu ;
  - « Votre bande grandit » et la série 🔥 ;
  - les compteurs et le bouton « Envoyer ✓ » ;
  - « Bien reçu ! Il reste B2 à saisir → ».
- Un lien « ‹ Accueil » en haut à gauche sur tous les écrans de l'éleveur.

## C. « J'ai acheté » (achats personnels de l'éleveur)

**L'écran :**
- Produit en grosses cases : d'abord les produits du catalogue les plus utilisés par cette ferme, puis « Autre produit », qui ouvre la liste complète du catalogue.
- Quantité par compteur + / −, dans l'unité du produit (sacs pour l'aliment).
- Prix payé total en FCFA (facultatif).
- Lieu ou fournisseur (facultatif, texte libre).
- Photo du reçu (facultative).
- Date : aujourd'hui, modifiable jusqu'à 3 jours en arrière.
- Gros bouton bleu « Enregistrer ».

**Chemin :** J'ai acheté → produit → Enregistrer = 3 clics.

**Règles :**
- **Poussins achetés** : on demande aussi les morts à l'arrivée. Ils deviennent des « poussins en attente de bande », et l'éleveur peut ouvrir une bande avec.
- **Stock de la ferme** = livraisons confirmées + achats personnels − utilisations. Chaque mouvement garde sa source : « Livraison de l'État » ou « Achat personnel ».
- **Pas de subvention** : les achats personnels ne doivent pas fausser les contrôles des intrants de l'État. Le futur recoupement livraisons / consommations ne porte que sur les livraisons de l'État : ce filtre est à prévoir dès maintenant.
- **Prix payé** : il est gardé pour le futur module Économie (charges).
- **Visibilité** :
  - l'agent voit les achats de ses fermes (carte « Achats de l'éleveur » sur la fiche ferme) et peut les corriger avec un motif, inscrit au journal ;
  - la DGE et l'ADMIN les voient en lecture.
- **Hors ligne** : la saisie fonctionne sans réseau, comme les autres saisies de l'éleveur.

## D. Tableau des clics à vérifier

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
| Mes bandes | 1 |
| Mon stock | 1 |
| Appeler mon agent | 1 |

## Étapes

1. **Étape 1** : présenter les écrans, les chemins de clics avec leur nombre, les tables et champs de « J'ai acheté », les écarts. **Attendre « validé ».**
2. **Étape 2** : construction.
3. **Étape 3** :
   - **tests automatiques** :
     - tuiles affichées ou cachées, pastilles ;
     - ouverture de la saisie sur le premier bâtiment à faire ;
     - bandeau rouge ;
     - achats : stock, source, poussins achetés en attente de bande, exclusion du futur recoupement, correction par l'agent, hors ligne ;
   - vérification à 360 px et sur ordinateur, avec captures ;
   - mise à jour de `docs/ergonomie.md` ;
   - liste des tests du propriétaire ;
   - commit dédié.

   **Pas de déploiement.**
