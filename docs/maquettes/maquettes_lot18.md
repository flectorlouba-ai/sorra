# SORRA — Lot 18 : écrans de la DGE (mode autonome)

Lot construit en mode autonome. Les choix faits seul sont dans `docs/decisions_autonomes.md` (18-x).
Charte YL.1. Chaque écran est à 2 clics de l'accueil et vérifié à 360 px.

## A. Livraisons de l'État : planning (tuile « Livraisons de l'État » → « Planning »)

- Nouveau statut **Prévue**, avant les statuts existants : **Prévue → Livrée → Confirmée**.
  - « Livrée » est le statut existant « À confirmer » : l'éleveur doit confirmer.
  - « Confirmée » regroupe les statuts existants « Reçue » et « Reçue avec écart ».
- **Écran Planning** (DGE, ADMIN) :
  - 3 colonnes Prévue / Livrée / Confirmée (une liste par statut sur téléphone), pour les 4 semaines à venir et les 2 dernières ;
  - **« Prévoir une livraison »** : ferme, date, produit, quantité, fournisseur ;
  - **« Marquer livrée »** sur une livraison prévue : elle passe « À confirmer », et l'éleveur la voit comme avant ;
  - **« Annuler »** une prévue, avec motif.
- Une livraison **prévue** ne compte pas dans le stock, n'est pas visible de l'éleveur, et ne déclenche pas d'alerte de retard.

## B. Commandes à valider (tuile « Commandes d'intrants », lot 16)

- Sur une commande **validée** : **« Créer la livraison »** crée une livraison **prévue**, pré-remplie (ferme, produit, quantité ; date dans 7 jours, modifiable sur le planning). La commande passe **Livrée** et garde le lien vers la livraison.
- La livraison se suit ensuite sur le planning.

## C. Arbitrages au niveau national (tuile « Arbitrages »)

- Écran existant des saisies à vérifier (lot 12), vu de la DGE sur tout le pays. Ajouts :
  - **filtre par province** ;
  - **compteur par province** des saisies à trancher, avec les « en retard » (plus de 48 h) en rouge.
- La DGE tranche comme avant (décision et motif inscrits au journal).

## D. Classement des fermes (nouvelle tuile « Classement »)

- **Score sur 100** par ferme, calculé sur ses **bandes clôturées** des 12 derniers mois :
  - mortalité (plus elle est basse, mieux c'est) ;
  - indice de consommation (plus bas, mieux) ;
  - poids moyen à la sortie rapporté à l'âge (plus haut, mieux) ;
  - régularité des saisies (jours saisis ÷ jours de la bande).
- **Pondérations** : 4 paramètres `classement.poids_*`, sensibles, donc sous **quatre yeux** (lot 15). Valeurs de départ : 35 / 25 / 20 / 20.
- **Bande incomplète** (moins de 80 % des jours saisis, ou aucune pesée) : **ignorée** dans le calcul, et **signalée** (« 2 bandes incomplètes ignorées »). Une ferme sans aucune bande complète est listée à part, « non classée ».
- Filtres province et cohorte. Export CSV.

## E. Rapports mensuels automatiques (tuile « Rapports »)

- Le **rapport mensuel national** de chaque mois terminé est **produit automatiquement en PDF et gardé** :
  - à la première ouverture de l'écran Rapports après la fin du mois ;
  - et par la commande `flask --app performyl2 rapports-mensuels`, à mettre dans le cron du VPS (documenté, non installé).
- **Liste des rapports gardés** : mois, date de production, « Télécharger ». Un rapport gardé n'est jamais modifié.
- **Envoi par e-mail préparé mais coupé** :
  - destinataires dans le paramètre `rapports.email_destinataires` ;
  - interrupteur `rapports.email_actif`, à 0 par défaut ;
  - le message (objet, texte, PDF joint) est construit et inscrit au journal « préparé, non envoyé ». Aucun envoi tant que l'interrupteur est coupé et qu'aucun serveur de messagerie n'est configuré.

## F. Agents : affectation et charge (nouvelle tuile « Agents »)

- **Tableau des agents** :
  - provinces ;
  - nombre de fermes, de bandes en cours, de fermes en rouge ;
  - visites en retard ;
  - saisies à vérifier.
- La **charge** est colorée (les seuils sont dans `a_faire_valider.md`) : au-delà de 15 fermes, orange ; au-delà de 25, rouge.
- **Réaffecter une ferme** : ferme → nouvel agent (de la même province), motif. Inscrit au journal. Le nouvel agent la voit aussitôt dans « Mes fermes ».
