# SORRA — Rapport du lot 11 : accueil en 8 tuiles et « Mon argent »

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1.

**Tests :** **315 tests réussis** et 1 réservé à PostgreSQL. Nouveaux tests :
- `tests/test_argent.py` (15 tests) ;
- dans `tests/test_accueil_eleveur.py` : 8 tuiles, raccourcis, vaccin d'un toucher, en-tête et « Moi », tableau des clics.

Les anciens tests qui lisaient l'accueil du lot 9 ont été mis à jour.

**Migration :** 0013 :
- table `depense` ;
- colonnes facultatives `sortie.montant_fcfa` et `livraison.batiment_id` ;
- colonne `vaccination.annule` ;
- 7 catégories de dépenses de départ.

**Corrigé au passage dans la migration 0012 :** la valeur par défaut d'une colonne oui / non était écrite `'0'`. PostgreSQL l'aurait refusée au déploiement. Elle est maintenant écrite comme dans les autres migrations. SQLite n'est pas concerné.

**Références :** description dans `docs/maquettes/maquettes_lot11.md`, aperçu de l'étape 1 dans `docs/maquettes/apercu_lot11.html`, règles dans `docs/ergonomie.md` (règle des clics précisée, « Accueil en 8 tuiles », « Argent de l'éleveur »).

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

**En-tête de l'éleveur.**
- Deux boutons, toujours visibles : « 📞 Paul » (masqué si l'agent n'a pas de téléphone) et « 👤 Moi ».
- La tuile « Appeler mon agent » a disparu.
- Le mot de passe et la déconnexion sont passés dans « Moi » (écart 2).
- **Écran « Moi »** :
  - carte « Ma ferme », qui a quitté « Mon stock » ;
  - 🔑 Mon compte, qui ouvre l'écran existant du mot de passe ;
  - 🏦 Partage avec la BCEG et ❓ Comment faire ? : écrans « Bientôt disponible » ;
  - 🚪 Se déconnecter.

**Accueil : 8 tuiles, ordre fixe, qui ne disparaissent plus.**
- Ordre : Saisie du jour (pleine largeur) · Ma bande · Ventes et sorties · Vaccins et soins · Poulet malade · Mes produits · Mon argent · Entretien (pleine largeur).
- Sous la Saisie du jour, deux raccourcis, seulement quand c'est prévu :
  - « ⚖️ Pesée prévue dans B1 → Peser » ;
  - « 💉 Vaccin · B2 → ✓ C'est fait », qui enregistre d'un toucher.
- Sans bande en cours (écart 1), Saisie du jour, Ventes et sorties, Peser et Traitement ouvrent une petite page « Aucune bande en cours », avec « 🐣 Nouvelle bande » si des poussins attendent.

**Écrans de regroupement.**
- **Ma bande** : Nouvelle bande (si des poussins attendent) · Peser (si une bande est en cours) · Mes bandes. Pastille : poussins en attente.
- **Vaccins et soins** :
  - les vaccins en retard et du jour ont un bouton « ✓ C'est fait », qui enregistre directement (écart 3). Il reprend vaccin, mode, poulets présents et doses, comme l'écran du vaccin. Il est suivi de « Fait ✓ — Annuler (10) », et fonctionne sans réseau ;
  - les vaccins de demain sont affichés sans bouton ;
  - dessous : 💊 Traitement (bande la plus inquiétante, pastilles B1 / B2) · 💬 Mes signalements (« Mes déclarations » renommée, écart 14) ;
  - l'ancienne petite page « Vaccins » du lot 9 est retirée.
- **Mes produits** :
  - les livraisons à confirmer, avec « Tout reçu » et « J'ai reçu moins » ;
  - dessous : J'ai acheté · Mon stock · Mes livraisons ;
  - après « Tout reçu » ou un achat, l'éleveur revient ici, avec le bandeau « Annuler (10) » (écart 5).

**Ventes et sorties.**
- « Combien avez-vous reçu ? », facultatif, pour Abattoir et Vente ; caché pour « Autre ».
- « Il restera N poulets » et l'alerte du délai d'attente sont inchangés.

**Mon argent.**
- 3 grosses cartes : Gagné · Dépensé · Reste. Le Reste est en rouge s'il est négatif.
- Période en cases : Ce mois · Cette bande (pastilles B1 / B2) · Tout.
- **« 💸 J'ai payé »** :
  - 7 catégories en images, gérées par l'ADMIN dans Configuration → Listes ;
  - montant ;
  - bâtiment facultatif ;
  - photo du reçu facultative ;
  - date jusqu'à 3 jours en arrière ;
  - puis « Enregistré ✓ — Annuler (10) ». Fonctionne sans réseau.
- **Derniers mouvements** : ventes, achats et dépenses. Une vente sans prix est « à compléter → ». L'éleveur complète le montant **une fois** ; ensuite, seul l'agent le corrige (écart 8).
- **Bilan de fin de bande** : chiffre d'affaires, dépenses et marge. Ils sont figés à la clôture et mis à jour si une vente est complétée plus tard.
- **Aide de l'État** : la phrase n'apparaît que si **toutes** les livraisons subventionnées rattachées à la bande ont une valeur (écart 11).

**Règle de rattachement** (`app/services/argent.py`) :
1. avec un bâtiment, la dépense va à la bande en cours de ce bâtiment ;
2. sans bâtiment, elle est partagée au prorata des poulets présents ce jour-là, sans erreur d'arrondi ;
3. les poussins vont à la bande qui les a reçus ;
4. sans bande concernée, la dépense est « hors bande ».

Pour cela, « J'ai acheté » a reçu un bâtiment facultatif, caché pour les poussins (écart 7).

**Agent (votre précision sur l'écart 12).**
- Carte **« Argent de l'éleveur »** sur la fiche de la ferme : totaux, derniers mouvements, colonne « Saisi par », photo du reçu, et « Corriger » ou « Indiquer » avec un motif inscrit au journal.
- Bouton **« J'ai payé (pour l'éleveur) »**. La dépense est marquée « Agent pour l'éleveur » dans la liste de l'éleveur, et la saisie est inscrite au journal.
- L'agent peut saisir une dépense plus ancienne que 3 jours, comme pour les achats.
- L'ADMIN voit la carte comme l'agent, sans le bouton de saisie.

**DGE :** un bloc « Argent des éleveurs » dans le tableau de bord, par province : fermes qui saisissent, chiffre d'affaires, dépenses. Une province de moins de 3 fermes affiche « — » (écart 13). Il n'y a aucun détail par ferme.

**BCEG, VETO :** rien.

## Tableau des clics, vérifié par un test (`test_tableau_des_clics`)

Règle : ouvrir un écran et valider comptent ; les choix dans le même écran et les + / − ne comptent pas.

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
| 📞 Paul | 1 |
| 👤 Moi → Se déconnecter | 2 |

## Captures (`docs/captures/lot11/`, 360 px sauf mention)

| Fichier | Écran |
|---|---|
| `01_accueil.png` | 8 tuiles, en-tête 📞 Paul · 👤 Moi, raccourci « ✓ C'est fait » |
| `02_ma_bande.png`, `03_vaccins_et_soins.png`, `04_mes_produits.png` | écrans de regroupement |
| `05_ventes_et_sorties.png` | Sortie avec « Combien avez-vous reçu ? » |
| `06_mon_argent_ce_mois.png`, `07_mon_argent_cette_bande.png` | Mon argent, avec la phrase de l'aide de l'État |
| `08_j_ai_paye.png`, `09_paye_annuler.png` | J'ai payé, puis « Enregistré ✓ — Annuler (10) » |
| `10_completer_vente.png` | compléter le montant d'une vente |
| `11_moi.png`, `12_bientot.png` | Moi, écran « Bientôt » |
| `13_accueil_ordinateur.png`, `14_mon_argent_ordinateur.png` | ordinateur |
| `15_agent_argent_fiche.png`, `16_agent_j_ai_paye.png` | agent, ordinateur |
| `17_dge_argent_agrege.png` | DGE : totaux par province, « — » sous 3 fermes |

**Vérification au navigateur** (Chromium, 360 px et 1 366 px) :
- toutes les pages font 360 px de large ;
- le parcours a été rejoué : J'ai payé et Annuler, compléter une vente, Moi, agent, DGE ;
- aucune erreur JavaScript.

## Décisions (écarts 1 à 15)

Les écarts 1 à 11 et 13 à 15 sont appliqués tels que décrits dans `docs/maquettes/maquettes_lot11.md`. L'écart 12 a été changé selon votre précision : l'agent saisit « J'ai payé » pour l'éleveur.

**Choix faits pendant la construction :**
- **« Cette bande »**, pour une dépense partagée, affiche « votre part : X ». Le jour où une bande se termine et où une autre commence dans le même bâtiment, les deux prennent leur part ce jour-là.
- **Bandes terminées avant le lot 11** : leur bilan reçoit les chiffres d'argent la première fois qu'on l'ouvre.
- **Annuler un vaccin** : la vaccination n'est pas effacée. Elle est marquée annulée, inscrite au journal, et n'entre plus ni dans le calendrier ni dans le stock.
- **Le bilan de l'agent** affiche aussi la marge, le chiffre d'affaires, les dépenses et l'aide de l'État. Il ne les affiche pas à la DGE ni au VETO.

## Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** par écran : J'ai payé sur Mon argent, Enregistrer, ✓ C'est fait.
- [x] **3 clics au plus**, avec la règle précisée, vérifié par un test.
- [x] **Aucune tuile ni bouton inutile** : les 8 tuiles restent à leur place, et les entrées sans objet disparaissent à l'intérieur.
- [x] **Aucun mot technique visible** : « Gagné », « Dépensé », « Reste », « hors bande », « à compléter ».
- [x] **360 px sans défilement horizontal**.
- [x] **Saisie du jour en moins de 30 s** : inchangée.
- [x] **Rien d'ajouté sans demande**, en dehors des écarts validés.

## Tests que vous ferez

Base de démonstration : `eleveur` / `Demo-yl2-2026`, sur `http://127.0.0.1:5020`.

1. **Accueil** :
   - les 8 tuiles sont dans l'ordre ;
   - « 📞 Paul » et « 👤 Moi » sont en haut ;
   - si un vaccin est prévu aujourd'hui, le raccourci « ✓ C'est fait » est sous la Saisie du jour.
2. **Vaccins et soins** :
   - touchez « ✓ C'est fait », puis « Annuler » : le vaccin redevient à faire ;
   - touchez de nouveau « ✓ C'est fait » sans annuler.
3. **Ventes et sorties** :
   - enregistrez une vente avec un montant, puis une autre sans montant ;
   - dans « Mon argent », la deuxième est « à compléter → » : complétez-la.
4. **Mon argent → 💸 J'ai payé** :
   - choisissez Électricité, puis 90 000, puis « Tous », puis Enregistrer ;
   - le bandeau « Enregistré ✓ — Annuler (10) » apparaît.
   - Avec deux bandes, regardez « Cette bande » et la part de chacune.
5. **Périodes** : passez de Ce mois à Cette bande, puis à Tout. Les trois chiffres changent.
6. **Mes produits** : « Tout reçu » sur une livraison à confirmer. Vous restez sur Mes produits, avec « Annuler ».
7. **Moi** : Ma ferme, Mon compte, les deux écrans « Bientôt », puis Se déconnecter.
8. **Agent** (`agent.est`) :
   - fiche de la ferme EST-001, carte « Argent de l'éleveur » ;
   - « J'ai payé (pour l'éleveur) » ;
   - « Corriger » une dépense avec un motif ;
   - « Indiquer » le montant d'une vente.
   - Revenez sur le compte de l'éleveur : la dépense porte « Agent pour l'éleveur ».
9. **DGE** (`dge`) : tableau de bord, bloc « Argent des éleveurs ». Il affiche « — » tant que moins de 3 fermes de la province ont saisi.
10. **Fin de bande** : clôturez une bande. Le bilan montre le chiffre d'affaires, les dépenses et la marge. Si la valeur des livraisons de l'État est renseignée, la phrase de l'aide de l'État apparaît.
11. **Sans réseau** (F12 → Réseau → Hors connexion) :
    - faites « J'ai payé » et « ✓ C'est fait » : « ◷ en attente » s'affiche ;
    - au retour du réseau, « ✓ envoyé » s'affiche.

## Points à valider

- **La liste des catégories de dépenses** (modifiable par l'ADMIN).
- **Le seuil de 3 fermes** pour les totaux de la DGE.
- **Option non codée** : « à compléter » aussi pour les achats sans prix.
- **Le test terrain** avec 3 à 5 éleveurs, avec les 8 tuiles.
