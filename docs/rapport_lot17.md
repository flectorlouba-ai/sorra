# SORRA — Rapport du lot 17 : écrans du vétérinaire

**État :** terminé, en mode autonome, sur la branche `autonome-lots-15-18`, commit dédié. **Aucun déploiement.**

**Tests :** **373 tests réussis** et 1 réservé à PostgreSQL (suite complète, 10 min 40 ; les fichiers touchés par les deux corrections de gabarit ont été relancés après : 59 réussis), dont 6 nouveaux dans `tests/test_lot17.py`.

**Migration :** 0018 (`ecrans_veterinaire`), avec retour arrière testé sur une copie de la base de démo : montée, descente, montée, `db check` sans écart, chaîne du journal intacte.
- Tables `diagnostic` et `blocage_sorties`.
- `sortie.blocage_id`.
- Liste `maladies_suspectees`.

**Références :** maquettes `docs/maquettes/maquettes_lot17.md` ; décisions 17-1 à 17-8 dans `docs/decisions_autonomes.md` ; tuiles `docs/pilotage.md` ; mode sans réseau `docs/hors_ligne.md`.

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

### A. Signalements triés par gravité
- Chez le vétérinaire, la liste des signalements a une colonne **Gravité** : « grave », « à voir vite » ou « à voir ». La plus grave vient d'abord ; à gravité égale, la plus ancienne (décision 17-1).
- Points :
  - mortalité anormale 3 ;
  - déclaration de 10 poulets ou plus 2, sinon 1 ;
  - +1 sans réponse depuis 24 h.

### B. Diagnostics
- Carte **Diagnostic** sur la fiche du signalement :
  - maladie suspectée (liste, ou « Autre ») ;
  - prélèvement envoyé au laboratoire ;
  - observations.
- Chaque diagnostic est daté, gardé dans un historique, et inscrit au journal.
- **L'agent ne voit jamais le contenu** : sa fiche ferme dit seulement « diagnostic posé le … ». Il n'ouvre pas la fiche du signalement. La DGE ne le voit pas ; l'ADMIN le lit (décision 17-2).

### C. Surveillance et blocage des sorties
- **Tuile Surveillance** :
  - les bandes bloquées (motif, date, auteur, signalement lié) ;
  - les **sorties reçues après le blocage, à vérifier** (compteur sur la tuile) ;
  - « Bloquer les sorties d'une bande » ;
  - les derniers blocages levés.
- Le blocage se pose aussi depuis la fiche du signalement : « ⛔ Bloquer les sorties de cette bande ».
- **Effets** :
  - le serveur refuse la sortie, donc **pas de lot, pas de QR** ;
  - l'éleveur voit le bandeau rouge « ⛔ Le vétérinaire a bloqué les ventes de cette bande (B2) » avec **📞 Appeler le vétérinaire**, sur l'accueil et à la place du formulaire Sortie ;
  - **sans réseau**, l'écran Sortie gardé montre le même message, sans formulaire. C'est vérifié au navigateur, réseau coupé.
- **Sortie faite sans réseau avant de savoir, reçue après** : elle est gardée, mise de côté, à vérifier, sans lot. Le vétérinaire choisit « Les poulets sont bien sortis » (la sortie est comptée, toujours sans QR) ou « Pas sortis » (décision 17-3).
- **Levée** : par un vétérinaire seulement, avec motif obligatoire. L'agent, la DGE et l'ADMIN sont refusés (testé, décision 17-4). Après la levée, une sortie crée de nouveau son lot et son QR.
- Blocage et levée sont inscrits au journal.

### D. Paramètres sanitaires
- **Tuile Paramètres sanitaires** : les seuils sanitaires (feux, écart à la courbe, courbe de poids, réglages `sante.*`).
- « Proposer » demande un motif. La proposition s'applique après l'accord d'un **autre** vétérinaire, de la DGE ou de l'ADMIN (lot 15).
- Les autres réglages sont refusés (403).

### E. Recherche de lots, amont et aval
- **Tuile Recherche de lots** (vétérinaire, DGE, ADMIN). On cherche un numéro de lot QR, de bande, de livraison, ou un fournisseur.
- **Amont** : livraisons de poussins (fournisseur, date), aliments reçus, vaccins et traitements. **Aval** : sorties, destinataires, lots et nombre de lectures du QR.
- Un fournisseur ou une livraison mène à **toutes les bandes** qui ont reçu ces poussins.
- **Export CSV**. **Chaque recherche** (action « Recherche ») et chaque export sont au journal.
- Le vétérinaire reste dans sa province : les bandes hors de sa province sont comptées, pas montrées (décision 17-6).

### Corrections après les captures
- L'écran Sortie bloqué levait une erreur JavaScript, car le script cherchait le formulaire absent. Le script s'arrête maintenant quand il n'y a pas de formulaire.
- Surveillance : sans bande à bloquer, une phrase remplace le formulaire vide.

## Base de démo (veto, eleveur, agent.est)
- Signalement ALS-2026-0001 (EST-001-B2-01, 12 poulets) : diagnostic **Newcastle**, prélèvement envoyé.
- **Sorties de EST-001-B2-01 bloquées**, liées au signalement. Une sortie de 30 poulets, reçue après le blocage, attend la vérification.
- Un ancien blocage levé (EST-001-B1-01), pour l'historique.
- Téléphone du vétérinaire renseigné : le bouton 📞 s'affiche chez l'éleveur.

## Captures (`docs/captures/lot17/`)
- 360 px et bureau : accueil du vétérinaire, signalements (gravité), fiche du signalement (diagnostic, blocage), Surveillance, Paramètres sanitaires, Recherche de lots.
- 360 px :
  - fiche ferme de l'agent (« diagnostic posé le », sans contenu) ;
  - accueil de l'éleveur bloqué ;
  - Sortie bloquée, avec et sans réseau.

Aucune page ne dépasse 360 px de large.

## À tester à la main
1. En **veto** → Signalements : colonne Gravité ; ouvrir ALS-2026-0001 : diagnostic, bande bloquée.
2. Surveillance : vérifier la sortie de 30 poulets (« bien sortis ») ; lever le blocage sans motif (refusé), puis avec motif.
3. En **eleveur** (avant la levée) : bandeau rouge et 📞 ; Ventes et sorties → message, pas de formulaire. Couper le réseau : même message.
4. En **agent.est** → fiche EST-001 : « diagnostic posé le … », sans le nom de la maladie ; Surveillance non proposée.
5. En **veto** → Paramètres sanitaires : proposer un seuil. Se connecter avec un autre vétérinaire ou en **dge** → Paramètres à approuver.
6. Recherche de lots : « Couvoir SIAT », « EST-001-B2-01-S1 », « LIV-2026-000005 » ; Export CSV ; Journal → « Recherche ».
7. Rebloquer, puis en **admin** tenter de lever : impossible.

## Points ouverts
- Liste des maladies, barème de gravité, texte du message à l'éleveur : à valider (`docs/a_faire_valider.md`).
