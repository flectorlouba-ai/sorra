# SORRA — Interface de pilotage : tuile → écran → lot

L'accueil du pilotage est un panneau de tuiles par profil (`app/routes/accueil.py`, `TUILES` et `TUILES_PROFIL`).
Règles :
- **aucune tuile morte** : une tuile n'existe que si son écran existe (test `tests/test_accueil.py`) ;
- chaque écran est à **2 clics** au plus depuis l'accueil (tuile → écran ; Configuration → réglage) ;
- le **périmètre** est rappelé en tête (« · National », « · Estuaire », « · 12 fermes suivies ») ;
- un **compteur** rouge s'affiche sur les tuiles qui attendent une action ;
- charte YL.1 (`perform.css`, Bootstrap Icons).

L'éleveur garde son accueil à lui (phase 1, lots 9 à 13).

## Tuiles par profil

| Profil | Tuiles, dans l'ordre |
|---|---|
| ADMIN | Utilisateurs · Configuration · Paramètres à approuver · Sessions · Journal · Intégrité · Arbitrages · Tableau de bord · Fermes · Bandes · Livraisons de l'État · Signalements · Déclarations · Vaccins · Lots · Opérateurs · Carte · Rapports · Commandes d'intrants · Surveillance · Recherche de lots · Classement · Agents |
| DGE | Tableau de bord · Carte · Livraisons de l'État · Arbitrages · Rapports · Paramètres à approuver · Commandes d'intrants · Fermes · Bandes · Alertes sanitaires · Lots · Opérateurs · Recherche de lots · Classement · Agents |
| AGENT | **espace terrain** (lot 19 ter) : Ma tournée · Mes fermes · Saisir pour un éleveur · Visite · À vérifier · Stock et commandes · Nouvel éleveur · Moi (`docs/ergonomie.md`, section G). **Version bureau** (Moi → 🖥️, écran large) : Mes fermes · Tournée du jour · Saisies à vérifier · Livraisons et stock · Commandes d'intrants · Bandes · Indicateurs · Vaccins · Lots · Opérateurs |
| VETO | Signalements · Surveillance · Recherche de lots · Paramètres sanitaires · Vaccins et calendrier · Paramètres à approuver · Fermes · Bandes · Déclarations · Indicateurs · Lots |
| AUDITEUR | Journal · Intégrité |
| OPERATEUR | **espace terrain** (lot 19 ter, en-tête vert) : **Recevoir un lot** (grande tuile) · **Lots qui arrivent** · **Mes réceptions** · **Moi · aide · mon compte** ; ligne d'état |
| BCEG, MAEDR | aucune tuile pour l'instant : « Vos écrans arrivent bientôt » |

## Tuile → écran → lot

| Tuile | Écran (route) | Compteur | Lot |
|---|---|---|---|
| Mes fermes / Fermes | `fermes.liste` (agent : triée par urgence) | fermes en rouge (agent) | 1 (15 : tuile, 16 : urgence) |
| Tournée du jour | `agent.tournee` | lignes de la tournée | 16 |
| Surveillance | `veto.surveillance` (sorties bloquées ; ADMIN en lecture) | sorties à vérifier | 17 |
| Paramètres sanitaires | `veto.parametres` (quatre yeux) | — | 17 |
| Recherche de lots | `veto.recherche` (amont, aval, export CSV) | — | 17 |
| Commandes d'intrants | `agent.commandes` (DGE : « Créer la livraison ») | refus non lus (agent) · à décider (DGE, ADMIN) | 16 (18 : livraison) |
| Saisies à vérifier / Arbitrages | `hors_ligne.conflits` (DGE, ADMIN : par province) | saisies à trancher | 12 (18 : par province) |
| Livraisons et stock | `livraisons.liste` | — | 2 |
| Livraisons de l'État | `dge.planning` (Prévue → Livrée → Confirmée ; lien « Toutes les livraisons ») | prévues en retard | 2 (18 : planning) |
| Classement | `dge.classement` (pondérations sous quatre yeux, export CSV) | — | 18 |
| Agents | `dge.agents` (charge, « Confier une ferme ») | — | 18 |
| Bandes | `bandes.liste` | — | 3 |
| Indicateurs / Tableau de bord | `pilotage.tableau` (DGE, ADMIN : bloc « Traçabilité aval » et lien « Journal des scans ») | — | 5 (19 : traçabilité aval) |
| Carte | `pilotage.carte` | — | 5 |
| Rapports | `pilotage.rapports` (+ rapports mensuels gardés) | — | 5 (18 : gardés) |
| Signalements / Alertes sanitaires | `sante.alertes` (vétérinaire : triés par gravité ; fiche : diagnostic, blocage ; en tête, « Lots retenus à la réception » avec Libérer / Refuser) | à qualifier / confirmées (+ lots retenus, vétérinaire) | 4 (17 : gravité, diagnostic ; 19 : lots retenus) |
| Déclarations | `sante.declarations` | — | 4 |
| Vaccins et calendrier | `sante.vaccins` | — | 4 |
| Lots et QR codes | `tracabilite.lots` | — | 6 |
| Opérateurs | `operateurs.liste` | — | 1 |
| Utilisateurs | `utilisateurs.index` | — | 0 |
| Configuration | `controle.configuration` (regroupe les réglages) | — | 15 |
| Paramètres à approuver | `controle.approbations_ecran` | propositions à décider | 15 |
| Sessions | `controle.sessions` | — | 15 |
| Journal | `journal.index` (lien « Journal des scans » : `journal.scans`, aussi pour la DGE depuis le Tableau de bord) | — | 0 (19 : scans) |
| Intégrité | `controle.integrite` | — | 15 |

### Écran Configuration (ADMIN), 2ᵉ clic

Provinces et localités · Listes · Paramètres · Catalogue des intrants · Formules des indicateurs · Tâches d'entretien · Aides.

### Hors tuiles

- **Ma sécurité** (`auth.securite`, clé en haut à droite) : double authentification, codes de secours, sessions ouvertes. Lot 15.

### Depuis la fiche ferme (2ᵉ clic, lot 16)

À faire (raisons d'urgence) · Stock avec « Compter » et écart · Biosécurité → « Évaluer » · Commandes · Comptes des éleveurs → « Nouvel éleveur ».

## Opérateur : abattoir, marché (lot 19)

Un compte OPÉRATEUR est rattaché à **une** fiche du registre des opérateurs (écran Utilisateurs : « Établissement »). Il ne voit que les lots dont la sortie désigne cette fiche (`filtre_perimetre`, branche OPÉRATEUR), ses réceptions et ses scans.

| Écran | Route | Clics depuis l'accueil |
|---|---|---|
| Accueil de l'opérateur | `accueil.index` (gabarit `operateur/_accueil.html`) | 0 |
| Scanner un lot (caméra, ou numéro tapé) | `operateur.scanner` | 1 |
| Résultat du scan : vert, orange, rouge (`Valider la réception`, `Recevoir sous réserve`, `Refuser le lot`) | `operateur.lot` → `operateur.recevoir` | 2 (Scanner → lecture → Valider) |
| Lots attendus | `operateur.attendus` | 1 |
| Mes réceptions, détail d'une réception (raison d'un écart à compléter) | `operateur.receptions`, `operateur.reception` | 1, 2 |
| Décision du vétérinaire (Libérer / Refuser, motif obligatoire) | `operateur.decider`, depuis Signalements | 2 |
| Journal des scans (ADMIN, AUDITEUR, DGE), export CSV inscrit au journal | `journal.scans`, `journal.scans_export` | 2 |

Règles, contrôles et seuils : `app/services/receptions.py` ; indicateurs : `app/indicateurs.py` (`tracabilite`).

## Espace terrain de l'agent (lot 19 ter)

| Tuile | Écran (route) | Pastille |
|---|---|---|
| 🚗 Ma tournée | `terrain.tournee` (petite carte, une carte par ferme, « 🧭 Y aller ») | fermes de la tournée |
| 🏠 Mes fermes → fiche | `terrain.fermes` → `terrain.fiche` | fermes en rouge |
| ✍️ Saisir pour un éleveur | `terrain.saisir` → écrans de l'éleveur (`bandes.saisir`, `bandes.pesee`, `sante.vacciner`, `bandes.sortie`) | — |
| 📋 Visite | `terrain.visite` → `visites.compte_rendu` (style terrain) | — |
| ⚖️ À vérifier | `hors_ligne.conflits` (style terrain pour l'agent) | saisies à vérifier |
| 📦 Stock et commandes | `terrain.stock` | refus de commande non lus |
| ➕ Nouvel éleveur | `terrain.nouvel_eleveur` → `agent.nouvel_eleveur` (3 étapes) ou `fermes.nouvelle` (avec réseau) | — |
| 👤 Moi | `terrain.moi` (📞 DGE : paramètre `contact.telephone_dge`, sinon premier compte DGE avec téléphone) | — |
| Version bureau / terrain | `terrain.bureau`, `terrain.version_terrain` | — |

Écrans de pilotage de l'agent toujours au style bureau : `utils/terrain.ECRANS_BUREAU_AGENT`.

## Éléments archivés (lot A1)

- Un élément archivé (saisie, pesée, sortie, vaccin, traitement, dépense, achat, panne, entretien, signalement, visite, bande ou ferme vide) **ne compte dans aucun indicateur ni tableau de bord** : il est masqué de toutes les requêtes (`models/base.py`), sauf sur les écrans « Voir les archivées ».
- Une sortie archivée sort des ventes et des lots (son lot est annulé) ; un achat archivé sort du stock ; un vaccin ou un traitement archivé rend sa quantité au stock.
- Produits, opérateurs, utilisateurs, valeurs de liste et bâtiments archivés ne sont plus proposés ; leur histoire reste.
- **Fermes et bandes archivées** (ADMIN, seulement vides) : « 🗄️ Archivées » sur la liste des fermes et des bandes, avec « ↩️ Restaurer ».
