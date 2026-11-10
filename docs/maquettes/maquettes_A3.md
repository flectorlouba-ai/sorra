# Lot A3 — Programme POUFA, capacité, production, ponte (maquette, mode autonome)

## Tables
- **ferme** : `programme_poufa` (oui / non, oui pour les fermes existantes : elles viennent de la liste POUFA), `bandes_par_an` (défaut 6). La cohorte n'a de sens que si la ferme est au programme (vidée sinon). Les **places** restent la somme des bâtiments en service (lot 2).
- **bande** : `type_production` (CHAIR par défaut, PONTE), `souche` (liste réglable « Souches »). L'**origine des poussins** est déduite de leurs livraisons (Programme / Externe, lot A2) ; « non renseignée » pour une bande de rattrapage.
- **paramètres** (quatre yeux, préfixe `production.`) : poids de sortie 2,1 kg, rendement carcasse 75 %, objectif national 100 000 t / an.

## Calculs (app/indicateurs.py, une seule source)
- **Production théorique** (t / an) = places × bandes par an × poids de sortie.
- **Cible** = production théorique, **seulement pour une ferme du programme** (hors programme : pas de cible).
- **Production réelle sur 12 mois glissants** (t) = poids vif des sorties des bandes de chair (sorties comptées, non archivées) des 365 derniers jours.
- **Taux d'atteinte** = réelle / cible ; pastille verte ≥ 80 %, orange 50–80 %, rouge < 50 % ; « — » sans cible.
- **Part de l'objectif national** = réelle / objectif national ; **équivalent carcasse** = poids vif × rendement.
- **Capacité à compléter** : aucun bâtiment en service, aucune place, ou bandes par an vide.

## Écrans
- **Ferme, création et modification** (bureau, ADMIN · DGE · AGENT) : le formulaire s'ouvre **en fenêtre au centre** ; « Membre du programme POUFA ? Oui / Non » (cohorte seulement si Oui) ; capacité : à la création, nombre de bâtiments et places par bâtiment (les bâtiments sont créés), et bandes par an ; en modification, places (lecture, gérées dans « Bâtiments ») et bandes par an. **Production théorique affichée en direct** (« ≈ 12,6 t de poulet vif par an »).
- **Opérateur, création et modification** : formulaire en fenêtre au centre.
- **Liste des fermes** (bureau) : filtre Programme / Hors programme / Toutes ; colonnes Cible (t), Produit 12 mois (t), Atteinte (pastille) ; mention « capacité à compléter ».
- **Agent (terrain)** : « 🏗️ capacité à compléter » sur la fiche de la ferme et dans « Mes fermes ».
- **Tableau de bord, carte** (DGE) : filtre Programme / Hors programme / Toutes ; les fermes hors programme sont comptées à part.
- **Hors programme** : la DGE ne peut ni créer une livraison de l'État ni valider une commande pour elle ; l'agent ne peut pas lui commander d'intrants.
- **Bande** (ouverture) : 🐔 Chair / 🥚 Ponte, souche ; ponte : GMQ, IC, poids attendu et courbe « sans objet » ; sortie comme le chair, sans cible ; pas de saisie des œufs (lot F).

## Démo
- 2 fermes hors programme, 1 bande de ponte, une ferme « capacité à compléter », fournisseurs fictifs (A2).
