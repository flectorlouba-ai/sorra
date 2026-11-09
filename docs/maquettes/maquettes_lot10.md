# SORRA — Lot 10 : entretien simple des installations (espace éleveur)

Ce lot comprend aussi l'ordre fixe des tuiles et la protection des saisies en attente.

> Description fournie par le propriétaire le 09/11/2026. Aperçu de l'étape 1 :
> `docs/maquettes/apercu_lot10.html`.

## Avant tout

- Relire `docs/ergonomie.md`.
- Réutiliser l'existant : accueil en tuiles du lot 9, charte illustrée douce, bandeau « Annuler (10) », encadré Alertes de l'agent, hors ligne et service worker corrigé, journal.
- Reprendre de la maintenance préventive de PERFORM YL.1 ce qui est utile, en beaucoup plus simple.

## Principe : le plus simple possible

Une tuile, un écran, un geste par tâche. L'éleveur ne prépare rien : il coche, il signale, il confirme, en 3 clics au plus.

Il n'y a pas de :
- liste détaillée d'équipements ;
- coûts ;
- pièces ;
- étapes multiples ;
- formulaire.

## A. Accueil de l'éleveur

1. **Nouvelle tuile « 🔧 Entretien »**. Pastille = nombre de tâches à faire aujourd'hui + pannes en cours.
2. **Ordre des tuiles fixe** : il ne change jamais selon les pastilles. Seules les tuiles sans objet disparaissent, les autres gardent leur ordre :
   1. Saisie du jour (pleine largeur)
   2. Livraisons
   3. Nouvelle bande
   4. Peser
   5. Vaccins
   6. Poulet malade
   7. Sortie
   8. J'ai acheté
   9. Entretien
   10. Mes bandes
   11. Mon stock
   12. Appeler {Prénom}, mon agent (pleine largeur, toujours en dernier)

   La règle du lot 9 reste : avec un nombre impair de tuiles, la dernière tuile de la grille prend toute la largeur. Un test vérifie cet ordre.

## B. Écran « Entretien » (un seul écran)

- **En haut, les pannes en cours** (carte rose). Exemple : « 🔥 Chauffage en panne · B1 — signalé ce matin · Paul est prévenu », avec un bouton « C'est réparé ».
- **Puis les tâches à faire**, une carte par tâche :
  - icône, nom ;
  - sous-titre avec les bâtiments concernés et la fréquence (« B1 et B2 · chaque jour ») ;
  - bouton vert « Fait ✓ ».

  Une tâche faite reste visible en grisé (« ✓ fait ») jusqu'à la fin de la période. Une tâche non faite à la fin de sa période apparaît « en retard ».
- **En bas**, un bouton rouge pâle pleine largeur : « ⚠️ Quelque chose est en panne ».
- **« Fait ✓ »** se fait en un seul geste, suivi du bandeau « Fait ✓ — Annuler (10) ».

## C. Signaler une panne (écran 2 de la tuile)

- **« Qu'est-ce qui ne marche pas ? »** : grille de 6 grosses images (liste système) :
  - 🔥 Chauffage
  - 💧 Eau
  - ⚡ Électricité
  - 🌀 Ventilation
  - 🍽️ Mangeoires
  - 🏠 Bâtiment
- **« Dans quel bâtiment ? »** en grosses cases, masqué s'il n'y a qu'un bâtiment.
- **Photo** facultative.
- **Bouton rouge** « Envoyer à mon agent ».
- **Statuts** : Signalée → Réparée, par l'éleveur ou l'agent, avec la date.
- L'agent reçoit une **alerte** dans son encadré Alertes.

## D. Les tâches et leur fréquence

Les tâches sont préparées par l'équipe, pas par l'éleveur.

**Table « modèle de tâche d'entretien »** :
- nom, icône ;
- fréquence : chaque jour, chaque semaine, chaque mois, ou à chaque vide sanitaire ;
- portée : par bâtiment, ou pour toute la ferme ;
- condition éventuelle : une infrastructure de la ferme ;
- actif.

**Liste de départ**, marquée « à valider par les vétérinaires » :

| Tâche | Fréquence | Portée |
|---|---|---|
| 💧 Laver les abreuvoirs | chaque jour | par bâtiment avec bande en cours |
| 🍽️ Nettoyer les mangeoires | chaque jour | par bâtiment avec bande en cours |
| 🦶 Changer l'eau du pédiluve | chaque semaine | ferme, si infrastructure Pédiluve |
| 🛏️ Vérifier la litière | chaque semaine | par bâtiment avec bande en cours |
| ⚡ Vérifier le groupe électrogène | chaque mois | ferme, si Groupe électrogène |
| 🚰 Vérifier la pompe du forage | chaque mois | ferme, si Forage ou puits |
| 🧽 Nettoyer et désinfecter | à chaque vide sanitaire | le bâtiment dont la bande vient d'être clôturée |

**Regroupement** : les tâches de plusieurs bâtiments se regroupent en une seule carte (« B1 et B2 »), et « Fait ✓ » les marque toutes. Une meilleure solution peut être proposée à l'étape 1.

**Configuration** : l'ADMIN gère cette liste dans Configuration, avec un écran simple (liste, modifier, activer ou désactiver). C'est le seul écran ajouté côté pilotage pour l'entretien.

## E. Vide sanitaire et ouverture de bande

- À la clôture d'une bande, la tâche « Nettoyer et désinfecter B3 » apparaît seule.
- À l'ouverture d'une bande dans un bâtiment où cette tâche n'est pas faite, un **avertissement non bloquant** s'affiche : « ⚠️ B3 n'a pas été marqué « nettoyé et désinfecté ». Continuer quand même ? », avec « Commencer la bande » et « Je nettoie d'abord ».
- Si l'éleveur continue, c'est inscrit au journal et visible par l'agent.

## F. Côté agent (minimum pour ce lot)

- Alerte « Panne signalée » dans son encadré Alertes, avec un lien vers la ferme.
- Sur la fiche ferme, une carte « Entretien » :
  - pannes en cours ;
  - tâches en retard ;
  - dernière désinfection par bâtiment ;
  - « Bande ouverte sans désinfection », le cas échéant.
- L'agent peut cocher une tâche ou déclarer « C'est réparé » pour l'éleveur. C'est alors marqué « Agent pour l'éleveur ».

## G. Hors ligne

« Fait ✓ », « Envoyer » (panne, photo comprise) et « C'est réparé » fonctionnent sans réseau, comme les autres saisies.

## H. Protection des saisies en attente

- Quand des saisies sont « ◷ en attente » sur le téléphone depuis plus de 24 heures, l'accueil de l'éleveur affiche un bandeau orange discret : « ◷ N saisies attendent le réseau. Ne videz pas les données de l'application. »
- Côté agent, sur la fiche ferme : « Dernière synchronisation du téléphone de l'éleveur : il y a X jours », à partir de la date de la dernière saisie reçue. Cela permet de repérer un téléphone qui n'envoie plus rien.
- Dans `docs/exploitation.md`, une consigne pour les agents : ne jamais vider les données de l'application sur le téléphone d'un éleveur sans avoir vérifié qu'il n'y a aucune saisie en attente.

## I. Clics à vérifier par tests de navigation

| Chemin | Clics |
|---|---|
| Entretien → Fait ✓ | 2 |
| Entretien → panne → Envoyer | 3 (l'image et le bâtiment sont des touchers dans le même écran) |
| Entretien → C'est réparé | 2 |

## Étapes

**Étape 1** : montrer les écrans, les chemins de clics, les tables, la liste de départ des tâches et les écarts, puis attendre « validé ».

**Étape 3** — tests automatiques sur :
- la génération des tâches par période et par bâtiment ;
- les conditions d'infrastructure ;
- le regroupement ;
- le retard ;
- la tâche de désinfection à la clôture ;
- l'avertissement à l'ouverture ;
- la panne et la réparation ;
- l'alerte de l'agent ;
- l'annulation en 10 s ;
- le hors ligne ;
- l'ordre fixe des tuiles ;
- le bandeau des saisies en attente ;
- la date de dernière synchronisation.

À faire aussi :
- vérification à 360 px et sur ordinateur, avec captures ;
- mise à jour de `docs/ergonomie.md` et `docs/exploitation.md` ;
- liste des tests du propriétaire ;
- commit dédié.

**Ne pas déployer.**
