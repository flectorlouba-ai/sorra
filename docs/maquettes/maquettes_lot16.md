# SORRA — Lot 16 : écrans de l'agent technique (mode autonome)

Lot construit en mode autonome. Les choix faits seul sont dans `docs/decisions_autonomes.md` (16-x).
Charte YL.1 (`perform.css`, Bootstrap Icons). Chaque écran est à 2 clics de l'accueil, et vérifié à 360 px.

## A. Mes fermes, triées par urgence (tuile « Mes fermes »)

- Pour l'agent, la liste des fermes est **triée par urgence**. Chaque ferme a une pastille de couleur et la raison en clair :
  - 🔴 **signalement sanitaire sans réponse**, saisie à vérifier en rouge, **biosécurité < 50 %** ;
  - 🟠 pas de saisie hier (bande en cours), livraison à confirmer en retard, visite prévue en retard, écart de stock au-delà du seuil, commande refusée ;
  - 🟢 rien à faire.
- Le score d'urgence est la somme des poids des raisons (rouge 10, orange 3). En cas d'égalité, l'ordre du numéro.
- Les filtres existants (province, cohorte, statut, recherche) sont gardés.
- Le même calcul alimente la tournée et la fiche ferme : `services/agent.py`, une seule fonction.

## B. Tournée du jour (tuile « Tournée du jour », nouvelle)

- Elle contient :
  - les **visites prévues aujourd'hui ou en retard** (fonction existante `visites.du_jour_pour_agent`) ;
  - puis les **fermes en rouge** sans visite prévue.
- Chaque ligne : ferme, localité, 📞 de l'éleveur, raison, et des boutons « Compte rendu », « Biosécurité », « Fiche ».
- **Sans réseau** : la page est gardée par le service worker quand l'agent l'ouvre avec du réseau, et elle fait garder les fiches des fermes de la tournée. Les comptes rendus restent des saisies en ligne ; la consigne est dans `docs/hors_ligne.md`.
- Un bandeau « Version gardée du … » s'affiche quand la page vient du téléphone : c'est le mécanisme existant du lot 13.

## C. Fiche ferme (existante), regroupée sans doublon

- On part de la fiche existante, qui a déjà les cartes Bâtiments, Bandes, Stock, Achats, Argent, Visites, Signalements (sans contenu), BCEG et Entretien.
- **Ajouts** :
  - un **encadré « À faire »** en haut, avec les raisons d'urgence (même fonction qu'en A) ;
  - la carte **Biosécurité** (dernier score, mesures correctives) ;
  - la carte **Commandes** (dernières commandes) ;
  - la carte **Éleveurs** (comptes rattachés, « Nouvel éleveur »).
- **Pas de doublon** : chaque information n'apparaît que dans une carte. Les liens « voir tout » mènent aux écrans de liste.

## D. Nouvel éleveur (depuis la fiche ferme)

- Formulaire : nom, prénom, téléphone ; l'identifiant est proposé à partir du nom.
- Le compte est créé avec le profil ÉLEVEUR et rattaché à la ferme. Un **mot de passe provisoire** est généré (10 caractères lisibles, sans 0/O ni 1/l).
- Le mot de passe est **affiché une seule fois** sur l'écran suivant (« Notez-le et donnez-le à l'éleveur »). Il n'est ni gardé en clair ni envoyé.
- Le compte doit **changer son mot de passe à la première connexion** (`doit_changer_mdp`, mécanisme existant).
- Création inscrite au journal (« Création de compte éleveur par l'agent »).
- Seul l'agent de la ferme (ou l'ADMIN) peut le faire.

## E. Livraisons et stock (tuile existante, carte Stock de la fiche)

- **Inventaire** : sur la fiche ferme, « Compter le stock » pour l'aliment et les autres intrants en stock. L'agent saisit la quantité comptée.
- **Écart = livré − utilisé − compté.**
  - Il est affiché en quantité et en % du livré.
  - **Au-delà du seuil** (paramètre `intrants.seuil_ecart_stock_pct`, 10 % au départ), l'écart est rouge et la ferme passe en orange dans « Mes fermes ».
  - Le seuil est un **paramètre sensible : quatre yeux**.
- L'écart se lit sur la fiche ferme (colonne « Dernier comptage » de la carte Stock) et dans « Mes fermes » (raison orange). Pas de tableau à part (décision 16-5).

## F. Commandes d'intrants

- **L'agent** passe une commande pour une ferme : produit, quantité, motif. Statut **Envoyée**.
- **La DGE ou l'ADMIN** la **valide** ou la **refuse** (motif obligatoire pour refuser).
- Elle devient **Livrée** quand la livraison liée est créée ; « Créer la livraison » arrive au lot 18 B.
- Écran **Commandes** (tuile « Commandes d'intrants » de l'agent et de la DGE) : par statut, l'agent voit seulement ses fermes.
- Une commande refusée met la ferme en orange chez l'agent, jusqu'à ce qu'il la lise.
- Tout est inscrit au journal (modifications automatiques).

## G. Biosécurité

- **Grille** :
  - liste configurable `grille_biosecurite` (Listes, ADMIN), 10 points de départ à faire valider par les vétérinaires ;
  - chaque point : Oui / Non / Sans objet.
- **Score** = Oui ÷ (Oui + Non) × 100, arrondi. Il est rouge sous 50 %, orange sous 80 %, vert au-delà.
- **Mesures correctives** : une par point « Non », à choisir dans une liste ou à écrire, avec un délai facultatif.
- **Enregistrée avec la visite** : c'est une section de la visite, nouvelle ou celle du jour.
- **L'éleveur** voit dans « Mes visites » le score en gros, puis les mesures correctives. Il ne voit pas la grille complète.
