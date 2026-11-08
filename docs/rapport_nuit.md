# PERFORM YL.2 — Rapport de la nuit du 8 au 9 novembre 2026

> Résumé et décisions prioritaires : voir la fin de nuit (complété après le dernier lot).

Règles suivies :
- aucun déploiement, aucune action sur le VPS ;
- un commit par lot ;
- tous les tests verts avant de passer au lot suivant ;
- écrans vérifiés dans un vrai navigateur, au format téléphone (360 px) et ordinateur ;
- `docs/ergonomie.md` relu au début de chaque lot.

---

## Lot 3 — Bandes d'élevage

**État : terminé.** Commit « Lot 3 : bandes d'élevage ». **193 tests réussis** et 1 réservé à PostgreSQL ; 20 tests nouveaux dans `tests/test_bandes.py`. Migration **0005**.

### Ce qui a été fait

Construit exactement ce qui avait été proposé à l'étape 1, avec vos choix : écarts 1 à 9 acceptés, pas d'ADMIN dans les alertes de bande.

**Bande :**
- numéro **EST-001-B1-07** (ferme, bâtiment, rang), jamais réutilisé ;
- une seule bande en cours par bâtiment ;
- date de fin prévue = mise en place + 45 jours (paramètre).

**Ouverture à partir des poussins en attente** (lot 2) :
- effectif = reçus − morts à l'arrivée, sans redemander ces morts ;
- on peut baisser l'effectif pour répartir une livraison sur plusieurs bâtiments ;
- les poussins quittent le stock « en attente de bande ».

**Ouverture de rattrapage** (AGENT, ADMIN) : date réelle, effectif de départ, morts à ce jour. Les indicateurs sont marqués « partiels ».

**Saisie du jour** (morts et sacs d'aliment, par compteurs + / −) :
- l'aliment se choisit en petites cases s'il y en a plusieurs en stock ;
- les sacs sont convertis en kg avec le poids du sac du produit ;
- la fonction `quantites_utilisees` du lot 2 est enfin remplie : le stock d'aliment baisse.

**Second envoi le même jour :** l'écran « Vous avez déjà envoyé… : ajouter ? » s'affiche, et l'envoi s'ajoute au premier.

**Contrôles :**
- morts ≤ effectif présent (bloquant) ;
- aliment > stock : avertissement non bloquant ;
- jour passé jusqu'à 3 jours pour l'éleveur, sans limite pour l'agent et l'ADMIN (lien « Oublié un jour ? »).

**Saisie par l'agent pour l'éleveur :**
- même bloc que l'éleveur ;
- la colonne « Saisi par » de la bande affiche « Agent pour l'éleveur » ;
- le journal d'audit reçoit l'action « Saisie de l'agent pour l'éleveur ».

**Pesée :** le poids moyen se calcule en direct, avec « Dans la courbe attendue ✓ » ou « En dessous de la courbe » (courbe et écart dans les Paramètres).

**Sortie :**
- Abattoir, Vente ou Autre (fixés dans le code) ;
- abattoir du registre obligatoire pour Abattoir, opérateur ou nom libre pour une vente ;
- « Il restera N poulets » se met à jour en direct.

**Indicateurs :**
- tous dans **`app/indicateurs.py`** et nulle part ailleurs ;
- les formules sont des expressions évaluées par un moteur sûr : lecture de l'arbre, sans `eval` ni `exec` ;
- seuils, courbe et durées sont dans les Paramètres.

**Feu tricolore :**
- vert, orange (> 0,5 % de morts dans la journée, ou pas de saisie hier), rouge (> 1 %) ;
- pas d'orange « pas de saisie hier » le jour de la mise en place ni le lendemain ;
- phrase simple sous le feu ;
- alerte dans l'encadré de l'agent référent, de la DGE et des vétérinaires de la province.

**À faire aujourd'hui :** pesée prévue (tous les 7 jours), fin de bande proche, saisie du jour, jour oublié.

**Clôture :**
- proposée à l'éleveur quand l'effectif est à 0 ;
- manuelle par l'agent ou l'ADMIN, avec motif s'il reste des poulets ;
- **bilan figé** : durée, mortalité, viabilité, poids moyen de sortie, GMQ, IC, poids vif, aliment, sorties par destinataire ;
- la bande passe en lecture seule et le bâtiment en « vide sanitaire depuis N jours ».

**Correction avec motif**, inscrite au journal :
- par l'agent pendant la bande ;
- par l'ADMIN toujours, y compris sur une bande clôturée (le bilan est alors recalculé).

**Fiche ferme :** la colonne « Bande en cours » des bâtiments, le vide sanitaire, et l'« Historique des bandes » (rien n'est jamais supprimé).

**Paramètres :** les seuils, l'écart à la courbe et la courbe portent la mention « à valider par les vétérinaires ».

### Écrans et chemins de clics

| Écran | Chemin | Contenu |
|---|---|---|
| **Ma bande aujourd'hui** (éleveur, téléphone) | accueil | En haut, les livraisons à confirmer et la carte « Nouveaux poussins ». Puis un bloc par bâtiment : feu, « Jour N · Bâtiment B1 », phrase, poulets présents, « À faire aujourd'hui », compteurs, gros bouton **Envoyer**, « Oublié un jour ? », boutons Peser et Sortie, 7 derniers jours « ✓ envoyé », encouragement. En bas, « Ma ferme » avec « Appeler mon agent ». |
| Feu orange ou rouge (A5) | dans le bloc | Encadré rouge « 15 morts aujourd'hui — Votre agent Paul a été prévenu » ; bouton rouge « Signaler un poulet malade » (« arrive bientôt » en attendant le lot 4). |
| Bâtiment vide (A6) | dans le bloc | Feu gris, « vide sanitaire · depuis N jours », bilan de la dernière bande et comparaison avec la précédente. |
| Nouveaux poussins (A1) | carte « Commencer une bande » | Livraison à choisir, bâtiment en grosses cases (les occupés sont grisés), effectif, date, poids d'un poussin, gros bouton « Commencer la bande », note « fin prévue le … ». |
| Pesée (A3), Sortie (A4) | boutons du bloc | Comme les maquettes. |
| Liste des bandes (ordinateur) | onglet Fermes et élevage → Bandes | Filtres province, ferme, en cours ou clôturées, feu. Bouton « + Ouvrir une bande » (agent, ADMIN). |
| Fiche bande (B) | clic sur une bande | Feu et phrase ; 4 cartes chiffres ; courbe dessinée sur place ; « Intrants de la bande » ; « Journal de la bande » avec ✏️ de correction. Boutons « Saisir pour l'éleveur » (agent) et « Clôturer la bande ». |
| Bilan (C) | après clôture, ou « Bilan » | 4 cartes, sorties par destinataire, mention de lecture seule. |

### Décisions prises cette nuit (lot 3)

1. **Ouverture d'une bande :** l'éleveur, l'agent et l'ADMIN peuvent ouvrir une bande normale ; seuls l'agent et l'ADMIN ouvrent une bande de rattrapage. Le cahier liste l'ouverture pour l'éleveur et l'agent, et le rattrapage pour l'agent et l'ADMIN : j'ai donné l'ouverture normale à l'ADMIN aussi, par cohérence.
2. **Une bande provient d'une seule livraison de poussins.** Une livraison peut, elle, être répartie sur plusieurs bâtiments.
3. **Une mise en place ne peut pas être antérieure à la date de livraison** des poussins.
4. **« Jours écoulés »** pour la régularité compte à partir du début du suivi (la mise en place, ou l'ouverture d'un rattrapage). Le jour même compte s'il a été saisi.
5. **« Morts du jour »** du feu : aujourd'hui si la saisie du jour est faite, sinon hier.
6. **Pesée le jour de la mise en place :** le GMQ reste vide (« — »), pour éviter une division par zéro.
7. **Phrase verte :**
   - « Vos poulets grossissent bien » si la dernière pesée est dans la courbe ;
   - « Vos poulets sont un peu légers » si elle est en dessous ;
   - « Tout va bien aujourd'hui » sans pesée.
8. **Encouragement**, tiré des propres chiffres de l'éleveur : « N jours envoyés sur N : bravo ! », ou « Mortalité x % : mieux que la bande précédente ».
9. **Paramètres lus une seule fois par requête web**, pour la rapidité de la liste des bandes et des alertes.
10. **Correction d'une saisie :** les champs « morts » et « sacs par aliment » sont modifiables, mais on ne peut pas ajouter d'aliment à une saisie existante. Pour cela, il faut un nouvel envoi du même jour.

### Tests que vous ferez demain (lot 3, au format téléphone)

**Préparation :**
- base locale à jour : `venv\Scripts\flask db upgrade` ;
- une ferme EST-001 avec deux bâtiments (B1 1 500 places, B2 800), l'agent référent et un éleveur rattaché ;
- une livraison de 1 000 poussins (3 morts à l'arrivée) et de 40 sacs d'aliment de 25 kg, confirmée par l'éleveur.

1. **Ouvrir une bande** (éleveur) :
   - à l'accueil, carte « Nouveaux poussins : 997 » → « Commencer une bande » ;
   - choisissez B1, puis « Commencer la bande ».

   Résultat attendu : le bloc « Jour 0 · Bâtiment B1 · 997 poulets présents » apparaît, et le stock de poussins de la fiche ferme passe à 0.
2. **3 jours de saisie :**
   - aujourd'hui, + + morts et + + sacs, puis « Envoyer » ;
   - « Oublié un jour ? » pour hier et avant-hier ;
   - sur la fiche ferme (en agent), le stock d'aliment passe de 40 à 34 sacs (850 kg).

   Renvoyez ensuite pour aujourd'hui : la question « Vous avez déjà envoyé… ajouter ? » s'affiche.
3. **Pesée et sortie :**
   - « Peser » : 10 poulets, 9,8 kg. Le poids moyen de 980 g s'affiche, avec le verdict selon l'âge.
   - « Sortie » : Abattoir, choisissez l'abattoir, 100 poulets, 200 kg. La note « Il restera … » se met à jour.
4. **Feu orange puis rouge :**
   - envoyez 6 morts (environ 0,6 %) : feu orange, « Plus de morts que d'habitude » ;
   - ajoutez 9 morts (15 en tout, environ 1,5 %) : feu rouge, avec l'encadré « Votre agent … a été prévenu » ;
   - en agent, l'alerte « EST-001-B1-01 · Plus de morts que d'habitude » est dans l'encadré Alertes ; en DGE et en VETO de l'Estuaire aussi, en ADMIN non.
5. **Saisie par l'agent :** fiche bande → « Saisir pour l'éleveur » → « Envoyer ». Le journal de la bande indique « Agent pour l'éleveur », et le journal d'audit contient « Saisie de l'agent pour l'éleveur ».
6. **Clôture et bilan :**
   - en agent, « Clôturer la bande », avec un motif puisqu'il reste des poulets ;
   - le bilan s'affiche ; la fiche n'offre plus de saisie ;
   - l'éleveur voit « Bâtiment B1 · vide sanitaire · depuis 0 jour », avec le bilan de la dernière bande.
7. **Vérifier le feu « pas de saisie hier » :** il n'apparaît pas le jour de la mise en place ni le lendemain. On ne peut le voir que le surlendemain (test automatique `test_pas_de_saisie_hier`).

### Points à valider (lot 3)

- Seuils orange et rouge (0,5 % et 1 %) et courbe de croissance : à faire fixer par les vétérinaires, dans Paramètres.
- La DGE voit les alertes de bande de toutes les provinces ; l'ADMIN ne les voit pas (votre choix).
