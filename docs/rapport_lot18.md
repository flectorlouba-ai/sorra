# SORRA — Rapport du lot 18 : écrans de la DGE

**État :** terminé, en mode autonome, sur la branche `autonome-lots-15-18`, commit dédié. **Aucun déploiement.**

**Tests :** **379 tests réussis** et 1 réservé à PostgreSQL (suite complète, 9 min 20), dont 6 nouveaux dans `tests/test_lot18.py`.

**Migration :** 0019 (`ecrans_dge`), avec retour arrière testé sur une copie de la base de démo : montée, descente, montée, `db check` sans écart, chaîne du journal intacte.
- Table `rapport_mensuel`.
- Paramètres `classement.poids_*` (4), `rapports.email_destinataires` et `rapports.email_actif`.
- Le statut « Prévue » ne change pas le schéma.

**Références :** maquettes `docs/maquettes/maquettes_lot18.md` ; décisions 18-1 à 18-8 dans `docs/decisions_autonomes.md` ; tuiles `docs/pilotage.md` ; cron et e-mail `docs/exploitation.md`.

**Bibliothèques :** aucune nouvelle. L'e-mail est construit avec la bibliothèque standard de Python.

## Ce qui a été fait

### A. Livraisons de l'État : planning
- La tuile « Livraisons de l'État » ouvre le **planning** en 3 colonnes : **Prévue → Livrée → Confirmée**. Il couvre 2 semaines passées et 4 à venir ; toutes les prévues y figurent.
- **Prévoir une livraison** : ferme, date, produit, quantité, fournisseur.
- Sur une prévue :
  - **Marquer livrée** : elle passe « à confirmer », et l'éleveur la confirme comme avant ;
  - **Annuler**, avec motif.
- Une prévue est « en retard » si sa date est passée ; la tuile les compte.
- Une prévue **n'existe pas encore** pour l'éleveur, l'agent, le stock et les alertes (décision 18-1). Le test vérifie tout le parcours, de « prévue » à « confirmée par l'éleveur ».

### B. Commandes à valider
- Sur une commande validée, la DGE voit **« Créer la livraison »**. Cela crée une livraison prévue dans 7 jours, pré-remplie, et la commande passe **Livrée** avec le lien vers la livraison (décision 18-3).

### C. Arbitrages au niveau national
- Pour la DGE et l'ADMIN, l'écran des saisies à vérifier gagne un **compteur par province**. Les provinces avec des saisies de plus de 48 h viennent d'abord. Un toucher **filtre** sur une province.

### D. Classement des fermes (nouvelle tuile)
- **Score sur 100**, calculé sur les bandes clôturées des 12 derniers mois.
- 4 notes : mortalité, indice de consommation, croissance, régularité des saisies. Elles sont pondérées par `classement.poids_*`, sensibles, donc sous **quatre yeux**.
- **Bandes incomplètes ignorées et signalées** (« 2 bandes incomplètes ignorées »). Une ferme sans bande complète est « non classée » (décision 18-4).
- Filtres province et cohorte ; **export CSV**, inscrit au journal.

### E. Rapports mensuels automatiques
- Le rapport mensuel national du mois terminé est **produit en PDF et gardé**, jamais régénéré, de deux façons :
  - à la première ouverture de l'écran Rapports ;
  - par la commande `flask --app performyl2 rapports-mensuels`, pour le cron. Le cron est documenté, **pas installé**.
- **Liste des rapports gardés**, avec « Télécharger » (inscrit au journal).
- **E-mail préparé, envoi coupé** : objet, texte et PDF joint sont construits, et le journal dit « préparé, non envoyé ». Destinataires et interrupteur sont dans les Paramètres (décisions 18-5 et 18-6).

### F. Agents (nouvelle tuile)
- Tableau des agents :
  - provinces ;
  - fermes, avec la charge en couleur ;
  - bandes en cours, fermes en rouge ;
  - visites en retard, saisies à vérifier.
- **Confier une ferme à un autre agent** : seulement vers un agent actif de la même province, avec motif. C'est inscrit au journal, et le nouvel agent la voit aussitôt (décision 18-7).

## Base de démo (dge)
- Planning : une livraison d'aliment **prévue en retard** (EST-002), des poussins prévus dans 5 jours, de l'aliment croissance dans 9 jours.
- La commande d'aliment de EST-002, **validée** au lot 16, montre « Créer la livraison ».
- **Classement** : bandes clôturées des cohortes précédentes (EST-002, EST-003, HOG-001, HOG-002), dont une incomplète, ignorée.
- **Second agent de l'Estuaire** (Sylvie Ondo, `agent.est2`), qui suit EST-004 : la réaffectation se teste dans la province.
- Destinataire du rapport : `dge.poufa@exemple.ga` (envoi coupé). Le rapport d'octobre est produit à la première ouverture.

## Captures (`docs/captures/lot18/`)
360 px et bureau : accueil de la DGE, Planning, Commandes, Arbitrages par province, Classement, Rapports (gardés), Agents.

Aucune page ne dépasse 360 px de large ; les tableaux larges défilent dans leur cadre.

## À tester à la main
1. En **dge** → Livraisons de l'État : la prévue en retard (rouge) → « Marquer livrée ». En **eleveur** (EST-001 seulement), prévoir puis marquer livrée une livraison pour EST-001 : la carte « Livraison à confirmer » apparaît.
2. Commandes → « Créer la livraison » sur la commande validée : elle passe Livrée ; la livraison est sur le planning.
3. Classement : 2 bandes incomplètes ignorées ; Export CSV. Paramètres → `classement.poids_mortalite` : la modification attend l'accord d'une autre personne.
4. Rapports : « 10/2026 · e-mail préparé, non envoyé » → Télécharger. Journal → « préparé, non envoyé ».
5. Agents : confier EST-003 à Sylvie Ondo (motif) ; en **agent.est2**, EST-003 est dans « Mes fermes ».
6. Saisies à vérifier : compteur par province, filtre.

## Points ouverts
- Pondérations, barème des notes, seuil « incomplète », seuils de charge, destinataires : à valider (`docs/a_faire_valider.md`).
- Cron des rapports et serveur de messagerie : à installer au déploiement.
