# SORRA — Rapport du lot 9 : accueil de l'éleveur en tuiles et « J'ai acheté »

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1.

**Tests :** **270 tests réussis** et 1 réservé à PostgreSQL, dont 13 nouveaux dans `tests/test_accueil_eleveur.py`. Ils couvrent le tableau des clics.

**Migration :** 0011, qui ajoute à la table `livraison` les colonnes origine, prix payé et photo du reçu.

**Références :** description dans `docs/maquettes/maquettes_lot9.md`, aperçu de l'étape 1 dans `docs/maquettes/apercu_lot9.html`, règles dans `docs/ergonomie.md` (section F, « Accueil de l'éleveur en tuiles » et « Achats personnels »).

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

**Accueil de l'éleveur : une porte d'entrée.**
- Le bandeau rouge s'affiche seulement si une bande est au feu rouge.
- La ligne d'état montre le poulet du pire feu et l'âge de chaque bande, sans chiffres.
- La grande tuile verte « Saisie du jour » porte en pastille le nombre de bâtiments restant.
- La grille contient 9 tuiles, et « 📞 Appeler Paul, mon agent » est en bas.
- Une tuile sans objet disparaît ; avec un nombre impair de tuiles, la dernière prend toute la largeur.
- Les livraisons à confirmer ne sont plus en cartes sur l'accueil : seule la pastille de la tuile Livraisons les signale.

**Les écrans du lot 8 ne sont pas refaits : l'accès est réorganisé.**
- « Ma bande aujourd'hui » devient l'écran **Saisie du jour** (`/saisie-du-jour`). Il s'ouvre sur le premier bâtiment pas encore saisi et garde les pastilles B1 / B2, le poulet, la série, « Bien reçu ! » et « Il reste B2 ».
- Les tuiles **Peser, Sortie, Poulet malade et Vaccins** ouvrent directement la bande la plus utile, avec des pastilles pour changer de bâtiment. Sans vaccin à faire, Vaccins ouvre une petite page « vaccins à venir et Enregistrer un traitement ».
- **Livraisons** ouvre « Mes livraisons », avec les livraisons à confirmer en haut.
- **Mes bandes** montre les bandes en cours (chiffres et petite courbe) puis les bandes passées avec leurs étoiles.
- **Mon stock** affiche le stock par produit : unité, kg pour l'aliment, ce qui a été reçu de l'État et ce qui a été acheté. Il affiche aussi les poussins en attente de bande, la carte « Ma ferme » et « Mes derniers achats ».
- **« ‹ Accueil »** apparaît sur chaque écran de l'éleveur. Le bouton « Accueil » de l'en-tête disparaît pour lui, pour ne pas faire doublon.

**J'ai acheté :**
- **L'écran** :
  - produits les plus utilisés en grosses cases, puis « Autre produit… » ;
  - compteur dans l'unité du produit ;
  - morts à l'arrivée pour les poussins ;
  - prix, lieu et photo du reçu, tous facultatifs ;
  - date limitée à 3 jours en arrière ;
  - bouton bleu « Enregistrer ».
- **L'enregistrement** : l'achat est rangé comme une « livraison » d'origine **Achat personnel** (numéro **ACH-2026-…**), reçue d'emblée et non subventionnée. Il entre donc tout de suite dans le stock et dans les poussins en attente de bande, sans code nouveau.
- **« Enregistré ✓ — Annuler (10) »** (votre précision). L'annulation :
  - passe l'achat au statut annulé ;
  - l'inscrit au journal ;
  - le retire du stock.

  Elle n'est plus possible après 10 s, ni si les poussins ont déjà été mis en bande.
- **Les livraisons de l'État restent seules contrôlées.** Une seule fonction, `intrants.livraisons_de_l_etat()`, sert à la liste des livraisons, aux alertes, à la mortalité à l'arrivée par fournisseur, à l'export et à « Mes livraisons ». C'est le filtre du futur recoupement.
- **Côté agent, DGE et ADMIN** : une carte **« Achats de l'éleveur »** sur la fiche ferme, avec lien vers la photo du reçu.
  - L'agent (et l'ADMIN) peut **corriger** un achat avec un motif, inscrit au journal.
  - DGE en lecture seule ; le VETO ne voit pas la carte.
- **Hors ligne** : comme pour les autres saisies, l'achat est gardé sur le téléphone, puis envoyé sans doublon.

## Tableau des clics, vérifié par un test (`test_tableau_des_clics`)

| Action | Clics | Remarque |
|---|---|---|
| Saisie du jour → Envoyer | 2 | |
| Livraisons → Tout reçu | 2 | |
| Nouvelle bande → bâtiment → Commencer | 3 | 2 si un seul bâtiment est libre |
| Peser → Enregistrer | 2 | |
| Sortie → type → Enregistrer | 3 | |
| Vaccins → C'est fait | 2 | |
| Poulet malade → signes → Envoyer | 3 | photo facultative |
| J'ai acheté → produit → Enregistrer | 3 | « Autre produit » : 4 |
| Mes bandes, Mon stock, Appeler mon agent | 1 | |

## Captures (`docs/captures/lot9/`, 360 px sauf mention)

| Fichier | Écran |
|---|---|
| `01_accueil.png` | accueil, tout va bien, 2 bâtiments à saisir |
| `13_accueil_feu_rouge.png` | bandeau rouge, « Enregistré ✓ — Annuler », tout envoyé, Nouvelle bande visible |
| `15_accueil_ordinateur.png` | accueil, version ordinateur |
| `02_saisie_du_jour.png`, `03_bien_recu.png` | saisie du jour ouverte sur B2, « Bien reçu ! » |
| `04_livraisons.png` | livraisons à confirmer en haut |
| `05_peser.png`, `06_sortie.png`, `08_poulet_malade.png` | avec les pastilles des autres bâtiments |
| `07_vaccins.png` | vaccin du jour ouvert directement |
| `09_mes_bandes.png` | bandes en cours (chiffres, courbe) et passées |
| `10_j_ai_achete.png`, `11_achat_enregistre_annuler.png`, `12_mon_stock.png` | achat, puis stock |
| `14_sans_reseau.png` | achat gardé sans réseau, puis « ✓ envoyé » |
| `16_agent_achats_fiche_ferme.png`, `17_agent_corriger_achat.png` | côté agent, ordinateur |

**Vérification au navigateur** (Chromium, 360 px et 1 366 px) :
- toutes les pages font 360 px de large ;
- le parcours complet a été rejoué : tuiles, saisie, « Il reste », accès directs, achat et annulation, feu rouge, achat sans réseau, correction par l'agent ;
- les seules erreurs de console viennent du préchargement des pages, au moment exact où le test coupe le réseau. Elles sont sans effet.

## Décisions (écarts 1 à 12, tous validés)

1. Les achats sont rangés avec les livraisons, en origine « Achat personnel ».
2. Les tuiles ouvrent la bande la plus utile ; des pastilles permettent de changer de bâtiment.
3. Vaccins : le vaccin du jour s'ouvre directement, sinon une petite page.
4. Livraisons : les livraisons à confirmer sont en haut de « Mes livraisons ».
5. Avec un nombre impair de tuiles, la dernière prend toute la largeur.
6. Sans bande : poulet qui dort, « Aucune bande en cours », et seules les tuiles utiles restent.
7. La carte « Ma ferme » est dans « Mon stock ».
8. « Autre produit… » fait 4 clics.
9. L'agent corrige un achat avec motif ; la DGE et l'ADMIN voient les achats en lecture ; le VETO ne les voit pas.
10. L'éleveur ne corrige pas lui-même, mais il peut **annuler dans les 10 s** (votre précision). Ses 5 derniers achats sont dans « Mon stock ».
11. Hors ligne : comme les autres saisies.
12. La date d'achat est limitée à 3 jours en arrière (paramètre existant).

**Choix faits pendant la construction :**
- **Après la saisie du jour**, l'éleveur revient sur l'écran « Saisie du jour », où s'affichent « Bien reçu ! » et « Il reste B2 ». Après les autres actions, il revient à l'accueil, où s'affichent le message et le bandeau d'annulation.
- **« Mon stock »** indique ce qui a été « reçu en tout » de chaque source. On ne peut pas dire quelle source a été utilisée, donc il n'y a pas de stock par source.
- **L'agent peut aussi enregistrer un achat pour l'éleveur** depuis `/j-ai-achete` (écart 12 : au-delà de 3 jours), dans la charte bleu nuit habituelle.
- **Le service worker passe en version 4**, pour que les téléphones prennent la nouvelle feuille de style.

## Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** : la tuile verte sur l'accueil, un bouton principal par écran.
- [x] **3 clics au plus** (tableau ci-dessus, vérifié par un test) ; seul « Autre produit » en demande 4.
- [x] **Aucune tuile inutile** : Nouvelle bande, Saisie, Peser, Sortie, Vaccins et Appeler disparaissent quand elles sont sans objet.
- [x] **Aucun mot technique visible** : « reçu en tout », « acheté par vous », « livré par l'État ».
- [x] **360 px sans défilement horizontal** sur toutes les pages de l'éleveur.
- [x] **Saisie du jour en moins de 30 s** : la tuile, puis Envoyer.
- [x] **Rien d'ajouté sans demande**, en dehors des écarts validés.

## Tests que vous ferez

Base de démonstration : `eleveur` / `Demo-yl2-2026`, sur `http://127.0.0.1:5020`.

1. **Accueil** : la ligne d'état, la tuile verte (pastille 2), les tuiles. Toutes tiennent sur un téléphone, sans défilement de côté.
2. **Saisie du jour** : elle s'ouvre sur le premier bâtiment à faire. Envoyez, puis vérifiez « Il reste … à saisir → ».
3. **Peser, Sortie, Poulet malade** : la bonne bande s'ouvre, et les pastilles en haut changent de bâtiment.
4. **Vaccins** : le vaccin du jour s'ouvre directement ; sinon, vous voyez les vaccins à venir et « Enregistrer un traitement ».
5. **J'ai acheté** :
   - choisissez un produit, mettez 10, puis « Enregistrer » ;
   - le bandeau « Enregistré ✓ — Annuler (10) » apparaît ;
   - essayez « Annuler » une fois.
6. **Mon stock** : la quantité augmente, avec « reçu en tout : … de l'État · … achetés ».
7. **Poussins achetés** : achetez des poussins avec 2 morts. La tuile « Nouvelle bande » apparaît, et vous pouvez ouvrir la bande.
8. **Agent** (`agent.est`) : fiche de la ferme EST-001, carte « Achats de l'éleveur », puis « Corriger » avec un motif. Vérifiez la ligne « Correction » dans le journal (admin).
9. **Feu rouge** : envoyez beaucoup de morts. Le bandeau rouge apparaît sur l'accueil et ouvre « Poulet malade » sur la bonne bande.
10. **Sans réseau** (F12 → Réseau → Hors connexion) : faites un achat. « ◷ en attente » s'affiche, puis « ✓ envoyé » au retour du réseau.

## Points à valider

- **Le test terrain avec 3 à 5 éleveurs**, avec l'accueil en tuiles.
- **Ordre des tuiles** : aujourd'hui Livraisons, Nouvelle bande, Peser, Sortie, Vaccins, Poulet malade, J'ai acheté, Mes bandes, Mon stock. Faut-il en remonter certaines ?
- **Prix des achats** : ils sont gardés pour le futur module Économie, mais pas encore exploités.
