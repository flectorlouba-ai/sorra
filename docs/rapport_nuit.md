# PERFORM YL.2 — Rapport de la nuit du 8 au 9 novembre 2026

## Résumé de la nuit

1. **Les 5 lots sont terminés**, un commit chacun, sans aucune action sur le VPS :
   - lot 3 : bandes ;
   - lot 4 : santé animale ;
   - lot 5 : tableaux de bord, carte, rapports ;
   - lot 6 : lots et QR codes ;
   - lot 7 : saisie sans réseau.
2. **Tests automatiques :** 233 tests réussis et 1 réservé à PostgreSQL. Les nouveaux écrans ont été vérifiés dans Chromium à 360 px et 1 366 px : pas de défilement horizontal, pas d'erreur.
3. **Bibliothèque ajoutée :** `reportlab` 5.1.0 seulement (libre, BSD), pour les PDF ; elle dessine aussi les QR codes. Rien de payant, aucun service extérieur.
4. **Migrations ajoutées :** 0005 à 0009. Le VPS est toujours au lot 1 (le lot 2 n'y est pas non plus).
5. **À valider en premier :**
   - le **passage en HTTPS avec un nom de domaine avant le pilote**. Sans lui, pas de saisie sans réseau sur les téléphones. C'est aussi l'adresse imprimée à vie sur les QR codes : à régler avant la première impression réelle.
   - les **seuils « à valider par les vétérinaires »** :
     - feu de mortalité 0,5 / 1 % ;
     - courbe de croissance ;
     - calendrier vaccinal J7 à J28 et retard de 2 jours ;
     - seuil de 2 % de mortalité à l'arrivée.
   - **l'agent doit-il voir les déclarations sanitaires** de ses fermes ? (aujourd'hui : non)
   - les règles choisies :
     - comparaison avec la province affichée seulement si elle est favorable ;
     - saisie sans réseau : « la plus récente gagne » plutôt qu'additionner. **→ Corrigé le 09/11 :** la même personne additionne, comme en ligne ; « la plus récente gagne » seulement entre deux personnes.
   - la page publique du QR code : ajouter le n° du lot ? Format des étiquettes : 21 par planche A4.
   - le dossier des photos (`instance/televersements`) à ajouter à la sauvegarde au déploiement.
6. **Point d'attention :** un test de vaccins a échoué une fois parce que minuit est passé pendant la suite ; relancé seul, il passe. La date « aujourd'hui » est lue une seule fois au début de ce test.

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

---

## Lot 4 — Santé animale (module M2)

**État : terminé.** Commit « Lot 4 : santé animale ». **207 tests réussis** et 1 réservé à PostgreSQL ; 14 tests nouveaux dans `tests/test_sante.py`. Migration **0006**.

### Ce qui a été fait

**A. Déclaration sanitaire**, depuis le bouton rouge « Signaler un poulet malade » (feu orange ou rouge), ou le lien discret « Poulet malade ? » de « Ma bande aujourd'hui ».
- **Photos :** 1 à 3, avec l'appareil photo du téléphone. Elles sont réduites dans le téléphone (1 600 px, JPEG) avant l'envoi.
- **Signes observés :** gros pictogrammes avec un mot, tirés de la liste configurable « Signes cliniques » et de ses 9 valeurs de départ.
- **Compteur** « Animaux touchés ».
- **Message vocal facultatif :** le bouton n'apparaît que si le navigateur le permet (HTTPS ou localhost). Sur le VPS en HTTP, il n'apparaît pas.
- Gros bouton « Envoyer au vétérinaire ».
- **Où sont les fichiers :**
  - photos et audio sont rangés hors du dossier public (`instance/televersements/sante`) ;
  - ils ne sont servis qu'aux personnes qui ont le droit de voir la déclaration ;
  - leur type est vérifié sur le contenu du fichier, pas sur son nom.
- **Destinataires :** les seuls vétérinaires de la province, plus l'éleveur qui l'a faite (« Mes déclarations ») et l'ADMIN.

**B. Alertes sanitaires**
- Une alerte naît d'une déclaration, ou d'un **feu rouge** de bande. Une seule alerte « feu rouge » reste ouverte à la fois par bande.
- Statuts : **Nouvelle → En analyse → Confirmée ou Infirmée → Close**. Chaque passage est daté, avec un commentaire obligatoire.
- **Seul le VETO change le statut.** L'ADMIN voit tout mais ne qualifie pas.
- **La DGE ne voit une alerte qu'une fois confirmée** par un vétérinaire. Jamais le public.
- **Encadré Alertes :**
  - VETO : les alertes nouvelles et en analyse de sa province ;
  - DGE : les alertes confirmées.

**C. Calendrier vaccinal**
- Le VETO (et l'ADMIN) le définit : âge en jours, vaccin du catalogue, mode d'administration (liste configurable : eau de boisson, spray, injection, goutte oculaire).
- **Calendrier de départ, à valider par les vétérinaires**, avec un bandeau et un bouton « Valider le calendrier » réservé au VETO :

  | Jour | Vaccin | Mode |
  |---|---|---|
  | J7 | Newcastle + Bronchite (HB1/H120) | goutte oculaire |
  | J14 | Gumboro | eau de boisson |
  | J21 | Newcastle (La Sota) | eau de boisson |
  | J28 | Gumboro (rappel) | eau de boisson |

  Les 4 vaccins sont ajoutés au catalogue.
- **« À faire aujourd'hui »** affiche le vaccin du jour, celui du lendemain et ceux en retard, avec un lien direct vers l'enregistrement.
- **Vaccination :** date, vaccin, mode, nombre d'animaux, doses (1 par poulet par défaut). Les doses sont **déduites du stock**.
- **Vaccin en retard** (date prévue + 2 jours, réglable) : alerte chez l'agent et le VETO.

**D. Traitements**
- Début et fin, médicament, motif, nombre d'animaux, quantité. La quantité est déduite du stock.
- Le catalogue reçoit un champ « **délai d'attente avant abattage** (jours) » pour les médicaments.
- **Sortie vers l'abattoir pendant un délai d'attente :**
  - un encadré rouge l'annonce dès l'ouverture de l'écran de sortie ;
  - après l'enregistrement, un message « ATTENTION » s'affiche, l'enregistrement n'est pas bloqué ;
  - le journal reçoit l'action « Sortie pendant un délai d'attente ».

**E. Accueil :** l'onglet Santé animale ouvre Alertes sanitaires (VETO, DGE, ADMIN), Déclarations (VETO, ADMIN) et Vaccins et traitements (VETO, ADMIN, AGENT). Biosécurité reste « Bientôt ».

**F. Fiche bande :** nouvelles cartes « Vaccinations » (fait, aujourd'hui, demain, à venir, en retard) et « Traitements » (avec la date de fin du délai d'attente).

### Écrans et chemins de clics

| Écran | Chemin |
|---|---|
| Déclarer (téléphone) | « Ma bande aujourd'hui » → bouton rouge, ou « Poulet malade ? ». Photo → pictogrammes → compteur → « Envoyer au vétérinaire » (3 gestes + photo). |
| Mes déclarations (éleveur) | carte « Ma ferme » → lien « Mes déclarations » |
| Alertes (VETO, DGE, ADMIN) | onglet Santé animale → Alertes sanitaires → clic sur une alerte. Fiche : signes, nombre, photos, message vocal, lien vers la bande, suivi daté. Le VETO choisit le statut suivant en grosse case, écrit un commentaire, puis « Enregistrer ». |
| Déclarations (VETO, ADMIN) | onglet Santé animale → Déclarations |
| Vaccins et traitements | onglet Santé animale → Vaccins et traitements : calendrier (« + Ajouter au calendrier » pour VETO et ADMIN), vaccins en retard, délais d'attente en cours |
| Vacciner, Traiter (téléphone) | lien du vaccin dans « À faire aujourd'hui », ou lien discret « Traitement » du bloc de la bande |

### Décisions prises cette nuit (lot 4)

1. **L'agent technique ne voit pas les déclarations**, même celles qu'il saisit pour l'éleveur : le cahier dit « aux seuls services vétérinaires ». Il garde le lien avec ses fermes par les alertes de bande (feu) et les vaccins en retard. **→ À trancher par vous** : l'agent doit-il voir les déclarations de ses fermes ?
2. **ADMIN :** voit toutes les déclarations et alertes, mais ne qualifie pas.
3. **DGE :** l'onglet Santé animale avec la seule tuile Alertes sanitaires (alertes confirmées).
4. **L'agent** reçoit l'onglet Santé animale, avec la tuile « Vaccins et traitements ».
5. **Calendrier « à valider »** : c'est un paramètre oui / non, que seul le VETO bascule avec le bouton « Valider le calendrier ».
6. **Une bande de rattrapage** n'affiche pas comme « en retard » les vaccins prévus avant son début de suivi : ils sont marqués « Avant le suivi ».
7. **Doses de vaccin :** 1 dose par poulet par défaut, modifiable à la saisie.
8. **Fichiers :** 6 Mo au plus par fichier. Types acceptés : JPEG, PNG, WebP pour les photos ; webm, ogg, m4a pour le message vocal.
9. **Sauvegardes :** les photos et messages vocaux sont des fichiers sur le disque (`instance/televersements`), hors de la base. **→ Ce dossier devra entrer dans la sauvegarde quotidienne** au déploiement : j'ajouterai sa copie au script de sauvegarde.

### Tests que vous ferez demain (lot 4)

1. **Déclarer** (éleveur, téléphone) : « Poulet malade ? » → prenez une photo, touchez « Diarrhée » et « Abattement », 12 animaux → « Envoyer au vétérinaire ». Le message « Envoyé au vétérinaire ✓ » s'affiche.
2. **Visibilité :**
   - en **veto** de la province, l'encadré Alertes affiche « ALS-2026-0001 · Déclaration de l'éleveur · Nouvelle » ; la photo s'ouvre ;
   - en **veto** d'une autre province, et en **agent**, la déclaration n'est pas visible.
3. **Qualifier** (veto) : En analyse (avec commentaire), puis Confirmée. En **dge**, l'alerte apparaît seulement maintenant, dans la liste et dans l'encadré.
4. **Feu rouge** : envoyez plus de 1 % de morts. Une alerte « Mortalité anormale (feu rouge) » apparaît chez le vétérinaire.
5. **Vaccin du jour** : sur une bande au jour 14, « À faire aujourd'hui » affiche « Vaccin du jour : Vaccin Gumboro (eau de boisson) ». Un clic mène à l'enregistrement, puis vérifiez le stock de vaccins de la ferme.
6. **Traitement et délai d'attente :**
   - au catalogue (admin), créez un médicament avec un délai de 7 jours, et faites-le livrer ;
   - « Traitement » → enregistrez-le ;
   - « Sortie » : l'encadré rouge du délai d'attente s'affiche ; enregistrez une sortie vers l'abattoir, le message « ATTENTION » s'affiche et le journal contient « Sortie pendant un délai d'attente ».
7. **Calendrier** (veto) : Vaccins et traitements → modifiez un jour, puis « Valider le calendrier ».

### Points à valider (lot 4)

- **L'agent technique doit-il voir les déclarations de ses fermes ?** (aujourd'hui : non)
- Calendrier vaccinal de départ et délai « en retard » (2 jours) : à valider par les vétérinaires.
- Sauvegarde du dossier des photos au déploiement.

---

## Lot 5 — Tableaux de bord, carte, rapports

**État : terminé.** Commit « Lot 5 : tableaux de bord, carte et rapports ». **215 tests réussis** et 1 réservé à PostgreSQL (un test de vaccins a échoué une fois parce que minuit est passé pendant la suite ; relancé seul, il passe) ; 8 tests nouveaux dans `tests/test_pilotage.py`. Migration **0007** (un seul paramètre).

**Bibliothèque ajoutée : `reportlab` 5.1.0** (libre, licence BSD, sans service extérieur) pour les PDF. Notée dans `requirements.txt` ; elle s'installera au prochain déploiement.

### Ce qui a été fait

**A. Comparaison avec la province** (éleveur) : dans « Ma bande aujourd'hui », la phrase d'encouragement devient, quand la province compte **au moins 3 bandes en cours** :
- « Votre mortalité (0,8 %) est meilleure que la moyenne de l'Estuaire (1,4 %) » si elle est plus de 10 % sous la moyenne ;
- « Votre mortalité est dans la moyenne du Haut-Ogooué (1,2 %) » si elle est à ± 10 % ;
- **rien** si elle est au-dessus : on ne décourage pas l'éleveur (l'agent voit le feu).

**B. Tableaux de bord** (un seul écran, deux tuiles) :
- tuile **« Indicateurs d'élevage »** (onglet Fermes et élevage) : ADMIN, DGE, AGENT (ses fermes), VETO (sa province) ;
- tuile **« Tableau de bord national »** (onglet Pilotage) : ADMIN et DGE ;
- filtres : province, cohorte, statut de ferme, période (du… au…) ;
- 8 cartes chiffrées : fermes actives, bandes en cours (avec les feux), poulets présents, mortalité moyenne, poids vif produit, poulets sortis, aliment, régularité des saisies (+ nombre d'alertes sanitaires en cours) ;
- pour ADMIN et DGE : barres « Mortalité par province » et « Poulets présents par province », puis le tableau par province ;
- graphiques dessinés sur place (pas de bibliothèque, pas d'Internet).

**C. Carte des fermes** (ADMIN, DGE) : contours des 9 provinces (fichier local déjà utilisé sur la fiche ferme), un point par ferme qui a une position GPS, couleur du feu le plus grave de ses bandes en cours (gris : pas de bande). Filtre province. Un clic sur un point ouvre la fiche de la ferme. Quand deux fermes se superposent, la plus grave reste visible.

**D. Rapports PDF** (aux couleurs de la charte), tuile **« Rapports »** (ADMIN, DGE) :
- **hebdomadaire** (7 derniers jours), national ou d'une province ;
- **mensuel national** (mois au choix) ;
- **fin de bande** : bouton « Rapport PDF » sur le bilan de chaque bande clôturée (aussi pour l'agent et le VETO de la bande).
- Contenu : chiffres clés, tableau par province, mortalité à l'arrivée par fournisseur, nombre d'alertes sanitaires confirmées.
- **L'envoi automatique programmé (courriel) viendra dans un lot ultérieur.**

**E. Exports Excel et CSV** : liens discrets « Excel · CSV » en haut des listes Fermes, Intrants (livraisons) et Bandes.
- Chacun ne contient que le périmètre de la personne (agent : ses fermes ; VETO : sa province).
- Livraisons : ADMIN, DGE, AGENT (le VETO n'a pas accès aux intrants).
- Chaque export est **inscrit au journal** (« Export », nombre de lignes). Les rapports PDF aussi.
- CSV au séparateur « ; » avec accents lisibles par Excel.

**F. Mortalité à l'arrivée des poussins** : taux par livraison et par fournisseur, en bas du tableau de bord. Au-dessus du **seuil de 2 %** (paramètre « à valider par les vétérinaires »), la ligne est en rouge et **la DGE reçoit une alerte** dans son encadré (livraisons des 30 derniers jours).

**G. Formules des indicateurs** (ADMIN) : tuile « Formules des indicateurs » dans Configuration.
- 8 formules : effectif présent, mortalité, viabilité, GMQ, poids vif produit, indice de consommation, régularité, mortalité du jour.
- Moteur sûr : seulement + − × ÷, parenthèses, nombres et les variables listées (aucune exécution de code). Une division par zéro donne « pas de résultat ».
- « Tester la formule » calcule sur un exemple sans rien enregistrer ; « Enregistrer » ; « Revenir à la formule d'origine » (affiché seulement si la formule a changé).
- Chaque changement est inscrit au journal (table des paramètres). Une formule refusée n'est jamais enregistrée ; si une formule enregistrée devenait invalide, le calcul reprend la formule d'origine.

### Écrans et chemins de clics

| Écran | Chemin |
|---|---|
| Indicateurs d'élevage (agent, VETO) | onglet Fermes et élevage → Indicateurs d'élevage (1 clic) |
| Tableau de bord national | onglet Pilotage → Tableau de bord national (1 clic) ; filtres en haut |
| Carte des fermes | onglet Pilotage → Carte des fermes → clic sur un point → fiche ferme |
| Rapports | onglet Pilotage → Rapports → « Télécharger le PDF » (2 clics) |
| Rapport de fin de bande | Bandes → la bande clôturée → Bilan → « Rapport PDF » |
| Exports | Fermes / Intrants / Bandes → lien « Excel » ou « CSV » en haut de la liste |
| Formules | onglet Configuration → Formules des indicateurs → modifier → « Tester la formule » → « Enregistrer » |
| Alerte mortalité à l'arrivée (DGE) | encadré Alertes de l'accueil → lien vers le tableau de bord, partie « Mortalité à l'arrivée » |

### Décisions prises cette nuit (lot 5)

1. **Un seul écran de tableau de bord** pour tous ; le contenu suit le périmètre. Les deux tuiles demandées y mènent.
2. **Comparaison avec la province** : uniquement si elle est favorable ou neutre (cohérent avec « encourager l'éleveur »). Seuil « dans la moyenne » = ± 10 %.
3. **Moyenne de province** = mortalité des bandes en cours, pondérée par le nombre de poussins mis en place.
4. **Carte** : réservée à ADMIN et DGE (comme demandé) ; points gris pour les fermes sans bande.
5. **Rapport hebdomadaire** = 7 derniers jours glissants (aujourd'hui compris).
6. **Exports de livraisons** non ouverts au VETO (cohérent avec l'accueil : pas d'intrants pour lui).
7. **Formules** rangées comme paramètres (`formule.<nom>`), cachées de l'écran Paramètres pour ne pas les modifier sans le test.
8. **Tuile « Indicateurs d'élevage »** placée après Fermes, Bandes et Intrants, pour garder « Fermes » comme tuile principale.

### Tests que vous ferez demain (lot 5)

1. **dge** : onglet Pilotage → Tableau de bord national → changez la province, la cohorte et les dates. Les chiffres suivent.
2. **agent.est** : Indicateurs d'élevage. Seules ses fermes sont comptées, pas de barres par province.
3. **Carte** (dge) : les points sont aux bons endroits ; un clic ouvre la ferme ; filtrez sur Haut-Ogooué.
4. **Rapports** : téléchargez l'hebdomadaire national, celui d'une province et le mensuel ; ouvrez-les sur téléphone et sur ordinateur.
5. **Fin de bande** : clôturez une bande, puis Bilan → « Rapport PDF ».
6. **Exports** : liste des fermes → Excel ; ouvrez le fichier. En **admin**, Journal des opérations : la ligne « Export » est là.
7. **Mortalité à l'arrivée** : confirmez une livraison de 1 000 poussins avec 30 morts. En **dge**, l'encadré Alertes l'annonce.
8. **Formules** (admin) : mortalité → écrivez `morts_cumules / mis_en_place * 100 + 1` → « Tester la formule » (résultat affiché, rien n'est changé) ; essayez `open(1)` (refusé) ; enregistrez puis « Revenir à la formule d'origine ».

### Points à valider (lot 5)

- Seuil de 2 % de mortalité à l'arrivée : à valider par les vétérinaires.
- La comparaison « seulement si favorable » vous convient-elle ?
- Liste et ordre des chiffres du rapport PDF (je peux ajouter des graphiques au PDF).
- Envoi automatique des rapports (courriel) : à prévoir dans un lot ultérieur, avec un serveur de courriel.

---

## Lot 6 — Traçabilité : lots et QR codes

**État : terminé.** Commit « Lot 6 : lots et QR codes ». **222 tests réussis** et 1 réservé à PostgreSQL ; 7 tests nouveaux dans `tests/test_tracabilite.py`. Migration **0008** (table des lots + un paramètre).

**Aucune bibliothèque ajoutée** : le QR code est dessiné par `reportlab`, déjà ajouté au lot 5. Pas besoin de `qrcode`.

### Ce qui a été fait

**A. Un lot par sortie vers un abattoir ou par vente.**
- Numéro : celui de la bande suivi du rang de la sortie, par exemple **EST-001-B1-07-S2**.
- Jamais réutilisé, même après une annulation.
- Une sortie « Autre » ne crée pas de lot.
- Le lot naît **automatiquement** à l'enregistrement de la sortie : l'éleveur ne fait rien de plus. Quand c'est l'agent qui saisit, un message lui indique le numéro du lot.

**B. QR code.**
- Il ne contient qu'une adresse : `http://187.124.217.218:5021/q/<code>`.
- Le code est tiré au hasard : 22 caractères, impossible à deviner.
- L'adresse du site est un **paramètre** (« tracabilite.adresse_publique ») : à remplacer par le nom de domaine en HTTPS avant le pilote.
- Le code du QR est masqué (« *** ») dans le journal des opérations.

**C. Planche d'étiquettes PDF.**
- Format A4, **21 étiquettes** (3 × 7) avec traits de découpe.
- Chaque étiquette porte : le QR code, le n° du lot, la ferme, la localité et la province, la date de sortie, « Produit au Gabon ».
- Elle s'ouvre depuis la fiche du lot (bouton principal « Imprimer les étiquettes »), ou depuis la sortie sur la fiche de la bande (icône QR à côté du n° du lot).
- Chaque impression est inscrite au journal.
- Vérifié : le QR imprimé se lit et donne la bonne adresse.

**D. Page publique** (sans connexion), au format téléphone, aux couleurs de la charte :
- « Produit au Gabon » et « Consommons gabonais » ;
- ferme, localité, province, date de sortie ;
- « Ce QR code n'est pas un certificat sanitaire. »
- **Aucun téléphone, aucun nom de personne, aucun acheteur, aucun n° interne.**
- La page n'est pas référencée par les moteurs de recherche.

**E. Code inconnu ou lot annulé :** page « Code inconnu », avec le texte « Ce code ne correspond à aucun lot de poulets suivi par le programme ».

**F. Journal des lectures.** Chaque lecture, connue ou non, est inscrite au journal : « Lecture d'un QR code », date, adresse IP.

**G. Pages internes** (ADMIN, DGE, AGENT pour ses fermes, VETO pour sa province) :
- **Liste « Lots et QR codes »**, avec recherche par n° de lot.
- **Fiche du lot :**
  - la sortie : date, pour qui, poulets, poids, lien vers la bande et la ferme ;
  - l'historique : création et auteur, nombre de lectures du QR avec leurs dates (l'ADMIN voit aussi l'adresse IP), annulation ;
  - le QR code à l'écran.
- **Annulation par l'ADMIN seul**, avec un motif obligatoire, inscrite au journal. Le QR affiche ensuite « Code inconnu » et les étiquettes ne s'impriment plus.

**H. Accueil.**
- La tuile « Lots et QR codes » est ouverte.
- « Indicateurs de traçabilité » et « Recherche amont / aval » restent « Bientôt ».
- Le VETO reçoit l'onglet Traçabilité, avec cette seule tuile.

### Écrans et chemins de clics

| Écran | Chemin |
|---|---|
| Lots et QR codes | onglet Traçabilité → Lots et QR codes (1 clic) |
| Fiche du lot | liste → clic sur la ligne ; ou fiche de la bande → n° du lot dans la colonne Sortie |
| Étiquettes | fiche du lot → « Imprimer les étiquettes » (3 clics depuis l'accueil) ; ou fiche de la bande → icône QR de la sortie (2 clics depuis la liste des bandes) |
| Page publique | scanner le QR avec l'appareil photo du téléphone |
| Annuler un lot (ADMIN) | fiche du lot → cadre « Annuler ce lot » → motif → « Annuler le lot » |

### Décisions prises cette nuit (lot 6)

1. **QR dessiné par reportlab** plutôt qu'avec la bibliothèque `qrcode` : une dépendance de moins.
2. **Adresse courte `/q/<code>`** : un QR plus petit, donc plus facile à lire sur une petite étiquette.
3. **Pas de n° de lot sur la page publique** : seulement ce que le cahier demande. Le n° est imprimé sur l'étiquette.
4. **21 étiquettes A4 par planche** (3 × 7), toutes identiques.
5. **Annulation réservée à l'ADMIN**, avec motif. Une sortie corrigée garde son lot.
6. **Sorties enregistrées avant ce lot** : pas de lot créé après coup. Sur le VPS il n'y en a aucune (le lot 3 n'y est pas encore).
7. **Lectures du QR** rangées dans le journal des opérations (pas de table à part). L'IP n'est montrée qu'à l'ADMIN sur la fiche du lot.
8. **VETO** : onglet Traçabilité avec la seule tuile Lots et QR codes, sans tuile « Bientôt » (règle « pas de tuile inutile »).

### Tests que vous ferez demain (lot 6)

1. **Créer un lot** (agent.est) : fiche d'une bande en cours → Sortie → Vente, « Marché de Nkembo », 50 poulets, 110 kg. Le message « Lot EST-…-S1 créé » s'affiche.
2. **Fiche du lot** : onglet Traçabilité → Lots et QR codes → la ligne → le QR code et l'historique s'affichent.
3. **Étiquettes** : « Imprimer les étiquettes ». Imprimez la planche, ou ouvrez-la à l'écran.
4. **Scanner** : depuis un téléphone **sur le même réseau que le serveur**, scannez une étiquette. Vérifiez ferme, localité, province, date et les deux mentions, et qu'aucun nom ni téléphone n'apparaît.
5. **Retour sur la fiche du lot** : l'historique indique « QR code lu 1 fois ».
6. **Annuler** (admin) : motif, puis « Annuler le lot ». Rescannez : « Code inconnu ».
7. **Journal** (admin) : les lignes « Lecture d'un QR code » sont présentes, avec l'adresse IP.

### Points à valider (lot 6)

- **HTTPS et nom de domaine avant d'imprimer de vraies étiquettes** : l'adresse imprimée ne pourra plus changer sur les étiquettes déjà collées. Changez le paramètre « tracabilite.adresse_publique » avant la première impression réelle.
- Contenu de la page publique : faut-il ajouter le n° du lot (utile pour une réclamation) ?
- Taille et nombre d'étiquettes par planche : à adapter au papier autocollant que vous achèterez.
- La page publique est ouverte à tous. Un très grand nombre de lectures remplirait le journal ; un limiteur pourra être ajouté au déploiement si besoin.

---

## Lot 7 — Hors connexion

**État : terminé.** Commit « Lot 7 : saisie sans réseau ». **233 tests réussis et 1 réservé à PostgreSQL** ; 11 tests nouveaux dans `tests/test_hors_ligne.py`. Migration **0009** (deux tables). Règles détaillées dans **`docs/hors_ligne.md`**.

Aucune bibliothèque ajoutée : JavaScript du navigateur seulement (service worker, IndexedDB).

### Ce qui a été fait

**A. Application installable.**
- Manifeste, icônes 192 et 512 px aux couleurs de la charte, service worker servi à la racine (`/sw.js`).
- Le navigateur n'accepte tout cela qu'en **HTTPS ou sur l'ordinateur lui-même** (localhost). **En HTTP simple** (le VPS aujourd'hui, par son adresse IP), **rien ne change** : le site marche comme avant, sans saisie sans réseau.

**B. Saisie sans réseau**, pour :
- la saisie du jour ;
- la pesée ;
- la sortie ;
- la confirmation de livraison (« Tout reçu » et « J'ai reçu moins ») ;
- la déclaration sanitaire avec photos (et message vocal).

Sans réseau, « Envoyer » range la saisie sur le téléphone et revient à l'accueil. Un bandeau orange s'affiche, **« ◷ 1 saisie gardée sur le téléphone · Envoi dès le retour du réseau »**, avec la liste ◷ des saisies en attente.

**C. Envoi au retour du réseau.**
- Il part tout seul : au retour du réseau, à l'ouverture d'une page, puis toutes les 30 s.
- Le bandeau devient vert : **« ✓ Envoyé : 2 saisies gardées sur le téléphone »**.
- Chaque saisie porte un **identifiant unique (UUID) tiré sur le téléphone**. Le serveur le note dans la même transaction que la saisie : **un envoi rejoué n'est jamais compté deux fois**.
- Les lignes créées portent l'identifiant de l'appareil.
- Il n'y a **pas de numéro provisoire à afficher** :
  - les numéros (lot tracé, alerte sanitaire) sont donnés par le serveur à l'arrivée de la saisie ;
  - l'éleveur ne voit que ◷ puis ✓.

**D. Conflits : la plus récente gagne, l'agent est prévenu.** *(Règle corrigée le 09/11 : voir « Corrections du 9 novembre » en fin de rapport.)*
- **Saisie du jour déjà faite ce jour-là** (par l'agent, ou depuis un autre téléphone) : on compare les heures. La plus récente est gardée, sans addition.
- **Livraison déjà confirmée** : même règle.
- **Même saisie des deux côtés** : pas de conflit.
- Chaque conflit, et chaque saisie refusée à l'arrivée (par exemple plus de poulets sortis que de présents), crée une ligne dans le **nouvel écran « Saisies à vérifier »** de l'agent :
  - alerte sur son accueil ;
  - ce qui a été gardé et ce qui a été remplacé, avec les valeurs ;
  - bouton « Vu ».

**E. Saisie de lundi envoyée jeudi** : elle reste celle de lundi. La limite « 3 jours passés » de l'éleveur se compte depuis le jour de la saisie, pas depuis l'envoi.

### Écrans et chemins de clics

| Écran | Chemin |
|---|---|
| Saisie sans réseau (éleveur) | comme d'habitude : « Envoyer », « Enregistrer la pesée »… Le bandeau ◷ apparaît en haut de l'accueil. |
| Envoi | automatique au retour du réseau ; le bandeau passe au vert ✓ |
| Saisies à vérifier (agent) | encadré Alertes de l'accueil → « N saisies faites sans réseau à vérifier » → « Vu » |
| Installer l'application | menu du navigateur → « Ajouter à l'écran d'accueil » (seulement en HTTPS) |

### Décisions prises cette nuit (lot 7)

1. **Rejouer le formulaire d'origine** sur la même adresse, plutôt que créer une seconde porte de saisie : tous les contrôles, le journal, les alertes, les stocks et les lots tracés restent ceux des écrans existants.
2. **Avant chaque envoi, le téléphone vérifie que le serveur répond** (5 s au plus). Sur un réseau « présent mais muet », la saisie est gardée au lieu d'être perdue.
3. **Heure du téléphone dans le futur** : ramenée à l'heure du serveur.
4. **Saisie refusée à l'arrivée** : retirée du téléphone, montrée à l'éleveur et à l'agent. Elle n'est pas gardée indéfiniment.
5. **Session expirée pendant l'envoi** : la saisie reste sur le téléphone ; le bandeau demande de se reconnecter.
6. **À la connexion**, les pages gardées sur le téléphone sont effacées (confidentialité si le téléphone change de main). Les saisies en attente restent ; chacune ne part qu'avec la session de son auteur.
7. ~~Deux saisies du jour faites sans réseau sur le même téléphone, même bande, même jour : la seconde remplace la première.~~ **Corrigé le 09/11 :** elles s'additionnent, comme en ligne.
8. **Pages gardées** : l'accueil, et les pages Pesée, Sortie, Poulet malade et Reçu moins qu'il propose, chaque fois qu'il est ouvert avec du réseau.
9. **Écran « Saisies à vérifier »** : seul écran nouveau, réservé à l'agent (et l'ADMIN). Sans tuile : on y arrive par l'alerte.

### Tests que vous ferez demain (lot 7)

**Sur l'ordinateur** : l'adresse doit être `http://127.0.0.1:5020` ou `http://localhost:5020` (lancement local habituel). Avec une autre adresse en HTTP, le mode sans réseau ne s'active pas.

1. Connectez-vous en **eleveur** avec Chrome, et ouvrez l'accueil deux fois (la première installe le service worker).
2. F12 → Réseau → « Hors connexion ». Ajoutez 2 morts → « Envoyer ». L'accueil revient avec le bandeau orange **◷ 1 saisie gardée**.
3. Touchez « Peser » (la page s'ouvre sans réseau), puis enregistrez une pesée. Le bandeau affiche **◷ 2 saisies**.
4. Décochez « Hors connexion ». En quelques secondes, le bandeau vert **✓ Envoyé : 2 saisies** apparaît. Rechargez : la pesée et la saisie sont là, une seule fois chacune.
5. **Conflit** :
   - en **agent.est**, faites la saisie du jour d'une bande ;
   - en **eleveur**, hors connexion, faites une autre saisie du même jour, puis rétablissez le réseau ;
   - en **agent.est**, l'alerte « 1 saisie faite sans réseau à vérifier » apparaît ; l'écran dit laquelle est gardée → « Vu ».
6. **Téléphone** : à faire une fois le site en **HTTPS**. Mode avion pendant une saisie, puis réseau rétabli.

### Points à valider (lot 7)

- **HTTPS et nom de domaine** : indispensables pour la saisie sans réseau sur les téléphones, avant le pilote. C'est aussi l'adresse qui sera imprimée sur les QR codes (lot 6).
- ~~Règle « la plus récente gagne » pour la saisie du jour.~~ Tranché le 09/11 : addition pour la même personne, « la plus récente gagne » entre deux personnes.
- **Test terrain** sur un vrai Android d'entrée de gamme, avec un réseau faible.

---

## Liste de contrôle d'ergonomie (`docs/ergonomie.md`, relu au début de chaque lot)

| Règle | Lot 3 | Lot 4 | Lot 5 | Lot 6 | Lot 7 |
|---|---|---|---|---|---|
| Un seul bouton mis en avant | ✓ | ✓ | ✓ | ✓ (Imprimer les étiquettes) | ✓ (aucun bouton nouveau pour l'éleveur) |
| Action courante en 3 clics au plus | ✓ | ✓ | ✓ | ✓ | ✓ (rien de plus à faire) |
| Aucun bouton ni tuile inutilisable | ✓ | ✓ | ✓ | ✓ (VETO : seule tuile utile) | ✓ |
| Aucun mot technique visible | ✓ | ✓ | ✓ sauf écran Formules (1) | ✓ sauf adresse du QR (2) | ✓ (« gardée sur le téléphone », ◷, ✓) |
| 360 px sans défilement horizontal | ✓ | ✓ | ✓ | ✓ | ✓ |
| Saisie du jour de l'éleveur en moins de 30 s | ✓ | ✓ inchangée | inchangée | inchangée | ✓ mêmes gestes, avec ou sans réseau |
| Rien d'ajouté sans demande | ✓ | ✓ | ✓ | (3) | (4) |

1. L'écran Formules, réservé à l'ADMIN, montre les noms de variables (`mis_en_place`…) : on ne peut pas écrire une formule sans eux. Chaque nom a son libellé en clair à côté.
2. La fiche interne du lot affiche l'adresse contenue dans le QR, pour vérifier une étiquette. La page publique n'en montre aucune.
3. « Annuler ce lot » (ADMIN) : nécessaire pour qu'un code puisse devenir « annulé », comme le demande le cahier.
4. Écran « Saisies à vérifier » de l'agent : nécessaire pour « le conflit est signalé à l'agent ». Pas de tuile : on y arrive par l'alerte.

---

## Corrections du 9 novembre (après vos décisions)

| Décision | Fait |
|---|---|
| 1. HTTPS avant toute impression réelle | Sur la fiche du lot (écran d'impression), un encadré rouge **« Adresse provisoire : ne pas imprimer pour de vrai »** s'affiche tant que l'adresse publique est une adresse IP (ou `localhost`) en http. L'icône QR de la fiche de la bande mène maintenant à cette fiche, et non plus directement au PDF : l'avertissement ne peut pas être contourné. |
| 2. Seuils | Valeurs de départ gardées, marquées « à valider par les vétérinaires ». Rien à changer. |
| 3. Déclarations sanitaires | L'agent ne les voit pas (cahier des charges). Rien à changer. |
| 4a. Comparaison favorable seulement | Confirmé. Rien à changer. |
| 4b. Règle hors ligne | **Même personne** : les saisies du jour s'additionnent, comme en ligne, avec ou sans réseau, quel que soit l'ordre, sans signalement. **Deux personnes différentes** (éleveur et agent) : la plus récente gagne et l'agent est prévenu ; si les valeurs sont identiques, rien n'est signalé. Confirmation de livraison par la même personne : sa plus récente compte, sans signalement. `docs/hors_ligne.md` est mis à jour ; 4 tests ajoutés (14 au total). |
| 5. Tests indépendants de l'heure | Toute la suite tourne à une **date fixe** (15/06/2026 à 12 h), qui avance normalement pendant la suite : `tests/conftest.py`, avec la bibliothèque libre `freezegun` (tests seulement). Plus aucun test ne dépend du jour ni de l'heure réels, et la suite ne peut plus passer minuit. Un test le vérifie. La suite a aussi été relancée à une autre date (01/03/2027 à 12 h : 238 réussis. Elle a trouvé une vraie dépendance, corrigée : le ménage des fichiers d'import comparait l'heure de l'application à celle de Windows ; le fichier est maintenant daté par l'application) pour le prouver. |

Résultat : **238 tests réussis et 1 réservé à PostgreSQL**, à la date fixe comme au 01/03/2027.
