# PERFORM YL.2 — Lot 2 : intrants (livraisons, confirmation, stock) — rapport

Date : 8 novembre 2026. État : construit et testé en local. Les **173 tests automatiques** passent. Un 174e, réservé à PostgreSQL, tournera sur le VPS. Pas encore déployé. Le lot 1, lui, est déployé depuis ce soir.

## 1. Ce qui a été fait

### Catalogue des intrants (ADMIN)

- Nouvelle tuile « Catalogue des intrants » dans l'onglet Configuration.
- Produits : nom (unique), type, unité, poids du sac, actif / inactif. Pas de suppression.
- Les types (Poussins, Aliment, Vaccin, Médicament, Autre) et les unités (têtes, sacs, kg, doses, flacons, litres, unités) sont fixés dans le code, comme convenu.
- Le poids du sac est obligatoire pour un aliment vendu en sacs.
- Lien « Gérer les fournisseurs » vers la nouvelle liste « Fournisseurs », que l'ADMIN remplit dans Listes.

### Livraisons (ADMIN, DGE, AGENT pour ses fermes)

**Accès :** la tuile « Intrants » de l'onglet Fermes et élevage est désormais ouverte.

**Liste :**
- filtres province, ferme, produit, statut et période ;
- pastilles de statut :
  - « À confirmer » en ambre ;
  - « Reçue » en vert ;
  - « Reçue avec écart » en rouge ;
  - « Annulée » en gris ;
- bouton principal « + Nouvelle livraison ».

**Nouvelle livraison**, pensée pour le téléphone :
- ferme, date (aujourd'hui par défaut, pas de date future), fournisseur ;
- une carte par produit : quantité, subventionné, part en %, valeur unitaire en FCFA (facultative) ;
- « Ajouter un produit », puis gros bouton « Enregistrer la livraison ».
- Numéro automatique **LIV-2026-000001**.

**Fiche :** un seul bouton principal selon le cas :
- « Confirmer pour l'éleveur » pour l'agent ;
- « Modifier » tant que la livraison est à confirmer ;
- « Annuler la livraison » (ADMIN, DGE, avec motif, seulement si elle est à confirmer) ;
- « Corriger » (agent ou ADMIN, avec motif, après confirmation).

### Confirmation par l'éleveur (écran « Ma ferme »)

**La carte « Livraison à confirmer »**, en haut de l'écran :
- produits et quantités en gros caractères ;
- pour les poussins, un compteur « Morts à l'arrivée » avec + et −, à 0 par défaut ;
- deux gros boutons, « **Tout reçu** » et « **J'ai reçu moins** ».

**« Tout reçu »** confirme en un geste. Le bandeau « **Reçue ✓ — Annuler (10)** » reste ensuite affiché 10 secondes avec un décompte :
- « Annuler » remet la livraison « À confirmer » et l'inscrit au journal ;
- passé ce délai, le bouton disparaît, et seule une correction par l'agent ou l'ADMIN est possible.

Le serveur accepte l'annulation jusqu'à 30 secondes, pour couvrir un réseau lent, et seulement de la part de celui qui a confirmé.

**« J'ai reçu moins »** : pour chaque produit, un compteur prérempli avec la quantité livrée, un motif d'écart, et le compteur des morts pour les poussins. Puis le gros bouton « Envoyer ».

**Lien « Mes livraisons »** : l'historique de l'éleveur.

**L'agent** confirme avec le même écran. La livraison et le journal indiquent alors « confirmé par l'agent Paul Ndong pour l'éleveur ».

### Stock et alertes

- **Stock :** nouvelle carte « Stock d'intrants » sur la fiche ferme.
  - L'aliment en sacs s'affiche en sacs et en kg (40 · 1 000 kg).
  - Les poussins s'affichent « en attente de bande » : reçus moins morts à l'arrivée.
  - Les livraisons à confirmer ou annulées ne comptent pas.
  - Le calcul « − quantités utilisées » est prêt et vaut 0 en attendant le lot Bandes.
- **Alertes** (ADMIN, DGE, et l'AGENT pour ses fermes) :
  - « N livraisons non confirmées depuis plus de 3 jours » ;
  - « N livraisons reçues avec écart » (30 derniers jours).
  - Les deux durées se règlent dans Paramètres. Un clic ouvre la liste déjà filtrée.

### Journal

Trois nouvelles actions : « Confirmation de réception », « Confirmation annulée » et « Correction » (avec le motif). Les livraisons, leurs lignes et les produits y sont nommés en clair.

### Autres changements

- `docs/ergonomie.md`, fonction 1 : le poids du sac est propre à chaque produit, plus un paramètre unique.
- Migration **0004** : tables `produit`, `livraison`, `livraison_ligne` ; listes « Fournisseurs » et « Motifs d'écart » ; 2 paramètres. Testée à la montée et à la descente.

## 2. Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** :
  - « + Nouvelle livraison » ;
  - « Enregistrer la livraison » ;
  - « Confirmer pour l'éleveur » ou « Modifier » ;
  - « Tout reçu », avec « J'ai reçu moins » en bouton secondaire à contour ;
  - « Envoyer » ;
  - « + Nouveau produit ».
- [x] **3 clics au plus** :
  - éleveur : « Tout reçu » en 1 geste depuis l'accueil, « J'ai reçu moins » en 2 ;
  - agent : onglet → Intrants → « + Nouvelle livraison » ;
  - confirmer pour l'éleveur : liste → livraison → « Confirmer pour l'éleveur » → « Tout reçu ».
- [x] **Rien d'inutilisable** :
  - pas de bouton de confirmation pour l'ADMIN ni la DGE ;
  - « Annuler » seulement sur une livraison à confirmer ;
  - « Corriger » seulement après confirmation ;
  - le bandeau « Annuler » disparaît après 10 secondes.
- [x] **Aucun mot technique** : numéros LIV-…, statuts en clair, journal lisible.
- [x] **360 px** : vérifié dans un navigateur (360 px de large), sans défilement horizontal. Compteurs et boutons font au moins 52 px de haut, pour une utilisation au pouce.
- [x] **Saisie en moins de 30 secondes** : confirmer une livraison prend 1 geste (« Tout reçu »), plus quelques appuis sur « + » pour les morts. C'est le premier geste quotidien de l'éleveur dans l'application.
- [x] **Rien d'ajouté sans demande.** Deux petits ajouts découlent des règles validées :
  - la date de livraison ne peut pas être dans le futur ;
  - un même produit ne peut figurer qu'une fois dans une livraison.

## 3. Tests automatiques

`venv\Scripts\python -m pytest -q` donne **173 réussis, 1 ignoré** (le test réservé à PostgreSQL). Les 28 nouveaux (`tests/test_intrants.py`) couvrent :
- le catalogue : poids du sac obligatoire, doublon, pas de suppression, accès ADMIN seul ;
- la création de livraison et ses contrôles : date future, nombre entier de poussins, part de subvention, produit en double ;
- le cloisonnement :
  - l'agent ne livre et ne voit que ses fermes ;
  - VETO, BCEG, MAEDR, OPERATEUR et AUDITEUR sont refusés ;
  - l'éleveur ne voit que sa ferme ;
- « Tout reçu » avec morts à l'arrivée, puis « Annuler » dans le délai :
  - refusé passé le délai ;
  - refusé à une autre personne que celle qui a confirmé ;
- « J'ai reçu moins » :
  - motif obligatoire ;
  - quantité supérieure à la livraison refusée ;
  - statut « Reçue avec écart » ;
- la confirmation par l'agent (« pour l'éleveur », sur la fiche et au journal) ; ADMIN et DGE ne confirment pas ;
- l'annulation : motif obligatoire, seulement si la livraison est à confirmer ;
- la correction avec motif, par l'agent ou l'ADMIN (pas par la DGE) ;
- le stock : sacs et kg, poussins moins morts, livraisons à confirmer et annulées exclues ;
- les alertes : retard selon le paramètre, écarts sur 30 jours, limitées aux fermes de l'agent, liens filtrés, aucune pour l'éleveur.

Parcours vérifié dans un vrai navigateur, sans erreur :
- trois appuis sur « + » donnent 3 morts ;
- le bandeau « Reçue ✓ — LIV-2026-000001 Annuler (10) » s'affiche, et le bouton a disparu au bout de 11 secondes ;
- en « reçu moins » côté agent, la fiche affiche « confirmé par l'agent Paul Ndong pour l'éleveur » ;
- le stock affiche 997 poussins en attente de bande (1 000 moins 3 morts) et l'aliment en sacs et en kg.

## 4. Tests à faire vous-même

**Préparation** (en `admin`, base locale mise à jour par `venv\Scripts\flask db upgrade`) :
1. Dans Listes → Fournisseurs, ajoutez « Couvoir SIAT » et « SMAG Aliments ».
2. Dans Configuration → **Catalogue des intrants**, créez :
   - « Poussins chair » : Poussins, têtes ;
   - « Aliment démarrage 25 kg » : Aliment, sacs, poids 25 ;
   - « Vaccin Newcastle » : Vaccin, doses.

   Essayez de créer un aliment en sacs sans poids : c'est refusé.
3. Reprenez les comptes du lot 1 : `agent.est`, référent de la ferme EST-001, et un éleveur rattaché à EST-001. Donnez un prénom à l'agent, par exemple « Paul ».

### Test 1 — Livraison de poussins et d'aliment

En `agent.est`, sur téléphone (ou fenêtre réduite) : Fermes et élevage → **Intrants** → « + Nouvelle livraison ».
1. Choisissez la ferme EST-001, le fournisseur Couvoir SIAT.
2. Produit « Poussins chair », 1000, cochez « Subventionné », 50 %.
3. « Ajouter un produit » : « Aliment démarrage 25 kg », 40.
4. Cliquez sur « Enregistrer la livraison ».

Résultat attendu : la fiche **LIV-2026-000001** s'ouvre, « À confirmer ».

### Test 2 — L'éleveur confirme « Tout reçu »

1. Connectez-vous en éleveur. La carte « Livraison à confirmer » est en haut.
2. Appuyez 3 fois sur « + » de « Morts à l'arrivée », puis sur « **Tout reçu** ».
3. Le bandeau « Reçue ✓ — Annuler (10) » décompte les secondes.
4. Appuyez sur « Annuler » : la carte revient.
5. Recommencez sans annuler et attendez 10 secondes : le bouton « Annuler » disparaît.

### Test 3 — L'éleveur confirme « J'ai reçu moins »

1. En agent, créez une 2e livraison de 40 sacs pour EST-001.
2. En éleveur, appuyez sur « **J'ai reçu moins** ».
3. Ramenez 40 à 37 avec « − ».
4. Appuyez sur « Envoyer » sans motif : refus avec « choisissez le motif ».
5. Choisissez « Abîmé », puis « Envoyer ».

Résultat attendu : dans « Mes livraisons », la livraison est « Reçue avec écart » (37, livré 40).

### Test 4 — L'agent confirme pour l'éleveur

1. En agent, créez une 3e livraison (« Vaccin Newcastle », 500).
2. Sur sa fiche, cliquez sur « **Confirmer pour l'éleveur** », puis « Tout reçu ».

Résultat attendu :
- la fiche affiche « Confirmée le … — **confirmé par l'agent Paul … pour l'éleveur** » ;
- dans le journal (en admin), la ligne « Confirmation de réception » contient la même mention.

### Test 5 — Stock sur la fiche ferme

Ouvrez la fiche EST-001, carte « **Stock d'intrants** ». Résultats attendus :
- **Poussins chair : 997**, en attente de bande (1 000 moins 3 morts) ;
- **Aliment démarrage 25 kg : 77 sacs · 1 925 kg** (40 + 37) ;
- **Vaccin Newcastle : 500 doses**.

### Test 6 — Alerte « non confirmée depuis plus de 3 jours »

1. En agent, créez une livraison pour EST-001 en mettant une **date d'il y a 5 jours**. Ne la confirmez pas.
2. À l'accueil (admin ou agent), l'encadré Alertes affiche « **1 livraison non confirmée depuis plus de 3 jours** ».
3. Un clic ouvre la liste filtrée, qui ne contient que cette livraison.
4. Dans Paramètres, passez le délai à 7 jours : l'alerte disparaît. Remettez 3.

L'alerte « reçue avec écart » (test 3) apparaît aussi.

### Test 7 — Cloisonnement

1. Créez une livraison pour une ferme de `agent.hog` (en admin ou en `agent.hog`).
2. En **agent.est** : la liste Intrants ne la montre pas, et son adresse donne « Vous n'avez pas accès à cette page ». L'alerte de `agent.hog` n'apparaît pas chez `agent.est`.
3. En **veto** ou **bceg** : pas de tuile Intrants, et l'adresse `/livraisons/` est refusée.

### Test 8 — Annulation et correction

1. En **dge**, sur une livraison à confirmer, cliquez sur « Annuler la livraison ». Le motif est obligatoire ; la livraison passe « Annulée » et ne compte pas dans le stock.
2. En **agent**, sur une livraison reçue, cliquez sur « Corriger ». Changez une quantité et donnez un motif : le journal affiche « Correction » avec ce motif.

## 5. Points d'attention et propositions (non codés)

1. **Écart et morts à l'arrivée sont deux choses distinctes.** L'écart compare reçu et livré. Les poussins morts à l'arrivée sont comptés dans le reçu et notés à part ; ils ne créent pas d'« écart ». Si un poussin manque à la livraison, c'est « J'ai reçu moins » avec le motif « Manquant ».
2. **Proposition :** un bouton « + Livraison » sur la fiche ferme, qui ouvrirait le formulaire avec la ferme déjà choisie. Le formulaire sait déjà le faire (`/livraisons/nouvelle?ferme=EST-001`) ; seul le bouton manque.
3. **Proposition :** un tableau de stock de toutes les fermes, pour la DGE. Aujourd'hui, le stock n'est visible que ferme par ferme.
4. **Préparation du lot Bandes :** le nombre de morts à l'arrivée est enregistré sur la ligne de livraison et ne sera pas redemandé. La fonction `quantites_utilisees` est le seul point à compléter.
