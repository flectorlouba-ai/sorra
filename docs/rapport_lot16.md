# SORRA — Rapport du lot 16 : écrans de l'agent technique

**État :** terminé, en mode autonome, sur la branche `autonome-lots-15-18`, commit dédié. **Aucun déploiement.**

**Tests :** **367 tests réussis** et 1 réservé à PostgreSQL (suite complète, 7 min 30), dont 8 nouveaux dans `tests/test_lot16.py`.

**Migration :** 0017 (`ecrans_agent`), avec retour arrière testé sur une copie de la base de démo : montée, descente, montée, `db check` sans écart, chaîne du journal intacte.
- Tables `commande_intrant` et `inventaire_stock`.
- `visite.biosecurite`, `score_biosecurite`, `mesures_correctives`.
- Liste `grille_biosecurite` (10 points) ; paramètre `intrants.seuil_ecart_stock_pct` (10 %, quatre yeux).

**Références :** maquettes `docs/maquettes/maquettes_lot16.md` ; décisions 16-1 à 16-9 dans `docs/decisions_autonomes.md` ; tuiles `docs/pilotage.md` ; mode sans réseau `docs/hors_ligne.md`.

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

### A. Mes fermes, triées par urgence
- Pour l'agent, la liste des fermes commence par une colonne **Urgence** : pastille « urgent », « à voir » ou « rien à faire », et les raisons en clair (🔴 / 🟠).
- La ferme la plus urgente vient en premier. Les filtres existants sont gardés. Les autres profils gardent la liste habituelle.
- La tuile « Mes fermes » affiche le nombre de fermes en rouge.
- Calcul unique (`services/agent.urgences`, décision 16-1). Il sert aussi pour la tournée et la fiche.

### B. Tournée du jour (nouvelle tuile)
- Elle contient les visites prévues aujourd'hui ou en retard, puis les fermes en rouge sans visite.
- Chaque ferme : localité, 📞 de l'éleveur, raisons, et les boutons Compte rendu, Biosécurité, Fiche.
- **Sans réseau** : la tournée et les fiches de ses fermes restent lisibles. C'est vérifié au navigateur, réseau coupé (décision 16-2).

### C. Fiche ferme regroupée
- Nouvelles cartes : **À faire** en haut (les raisons d'urgence), **Biosécurité**, **Commandes d'intrants**, **Comptes des éleveurs**.
- La carte Stock gagne une colonne « Dernier comptage » avec « Compter ».
- Chaque carte n'apparaît qu'une fois (test). L'ADMIN gère comme l'agent ; la DGE lit seulement.

### D. Nouvel éleveur
- Depuis la fiche → « Nouvel éleveur » : nom, prénom, téléphone.
- Le compte ÉLEVEUR est rattaché à la ferme. Un **mot de passe provisoire** est **affiché une seule fois** : il n'est jamais gardé en clair, et il est masqué au journal.
- L'éleveur doit changer son mot de passe à la première connexion.
- La fiche signale « mot de passe provisoire » tant qu'il ne l'a pas changé.
- Seuls l'agent de la ferme et l'ADMIN peuvent le faire.

### E. Livraisons et stock : écart
- « Compter » enregistre la quantité comptée et fige le livré et l'utilisé. **Écart = livré − utilisé − compté.**
- Au-delà du seuil (10 % du livré), l'écart est rouge sur la fiche, la ferme passe en orange chez l'agent, et un message le dit au moment du comptage.
- Le seuil est **sensible** : il passe par les quatre yeux (test : rien ne change avant l'approbation par une autre personne).

### F. Commandes d'intrants
- **L'agent** commande (ferme, produit, quantité, motif) depuis l'écran Commandes : statut **Envoyée**.
- **La DGE ou l'ADMIN** valide, ou refuse avec un motif obligatoire. La tuile de la DGE compte les commandes à décider.
- Un refus met la ferme en orange chez l'agent jusqu'à ce qu'il ouvre l'écran Commandes.
- **Livrée** : la fonction est prête (`marquer_livree`, testée). Le bouton « Créer la livraison » arrive au lot 18 B (décision 16-7).

### G. Biosécurité
- **Grille** de 10 points (liste modifiable par l'ADMIN, à valider par les vétérinaires) : Oui / Non / Sans objet. Une mesure corrective est obligatoire pour chaque « Non » ; son champ n'apparaît que pour un « Non ».
- **Score** = Oui ÷ (Oui + Non). Il est rouge sous 50 % (la ferme passe en rouge), orange sous 80 %, vert au-delà.
- Elle est enregistrée comme une visite « Biosécurité ». **L'éleveur** voit dans « Mes visites » le score en gros et la liste « À corriger » ; il ne voit pas la grille (décision 16-3).

### Correctif du lot 15
Le réglage `securite.profils_2fa` (texte) ne pouvait pas être modifié : l'écran Paramètres exigeait un nombre pour tout réglage « securite. ». Le contrôle ne vaut plus que pour les réglages numériques ; un test le vérifie.

### Correctif du rapport du lot 15
Le rapport du lot 15 citait le chemin complet de la base de démo, qui contient l'ancien nom interdit. Le test « ancien nom absent » ne lit que les fichiers suivis par git ; il n'a donc vu le problème qu'après le commit du lot 15. Le chemin est retiré.

### Correction après les captures
Les boutons de la tournée étaient trop pâles sur fond blanc (style de la barre du haut). Ils prennent le style des boutons des cartes.

## Base de démo (agent.est)
- EST-001 : visite de suivi aujourd'hui, biosécurité 80 %, aliment compté avec 20 % d'écart, commande d'aliment croissance **envoyée**.
- EST-002 : biosécurité **40 %** → rouge, commande d'aliment **validée**.
- EST-003 : visite de vaccination **en retard**, commande de vaccin **refusée** (motif), commande d'aliment envoyée, éleveuse **Marie Nzé** créée avec un mot de passe provisoire.
- L'éleveur de démo (EST-001) voit sa biosécurité 80 % et 2 mesures dans « Mes visites ».

## Captures (`docs/captures/lot16/`)
- 360 px et bureau : accueil de l'agent, Mes fermes, Tournée, fiche EST-002, Biosécurité, Commandes (agent et DGE), Nouvel éleveur.
- 360 px : compte créé (mot de passe provisoire), tournée et fiche **sans réseau**, Mes visites de l'éleveur.

Aucune page ne dépasse 360 px de large.

## À tester à la main
1. En **agent.est** → Mes fermes : EST-001 et EST-002 en « urgent », EST-003 « à voir », EST-004 « rien à faire », dans cet ordre.
2. Tournée du jour : EST-003 (en retard), EST-001 (aujourd'hui), EST-002 (rouge). Couper le réseau du téléphone et rouvrir la tournée et une fiche.
3. Fiche EST-002 → Biosécurité → Évaluer : un « Non » fait apparaître la mesure ; enregistrer et lire le score.
4. Fiche EST-001 → Stock → Compter l'aliment avec une valeur très basse : message « au-delà du seuil ».
5. Fiche EST-003 → Nouvel éleveur : noter le mot de passe, se connecter avec : le changement est demandé.
6. Commandes : en agent, commander ; en **dge**, valider une commande et en refuser une sans motif (refusé), puis avec motif. En agent, le refus s'affiche et l'orange disparaît.
7. En **eleveur** → Moi → Mes visites : score 80 % et mesures.
8. En **admin** → Paramètres → seuil d'écart de stock : la modification attend l'approbation.

## Points ouverts
- Grille de biosécurité, seuils du score, seuil d'écart, poids de l'urgence : à valider (`docs/a_faire_valider.md`).
- Saisies de l'agent sans réseau : non (décision 16-2).
