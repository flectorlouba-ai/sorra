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
| ADMIN | Utilisateurs · Configuration · Paramètres à approuver · Sessions · Journal · Intégrité · Arbitrages · Tableau de bord · Fermes · Bandes · Livraisons de l'État · Signalements · Déclarations · Vaccins · Lots · Opérateurs · Carte · Rapports · Commandes d'intrants · Surveillance · Recherche de lots |
| DGE | Tableau de bord · Carte · Livraisons de l'État · Arbitrages · Rapports · Paramètres à approuver · Commandes d'intrants · Fermes · Bandes · Alertes sanitaires · Lots · Opérateurs · Recherche de lots |
| AGENT | Mes fermes · Tournée du jour · Saisies à vérifier · Livraisons et stock · Commandes d'intrants · Bandes · Indicateurs · Vaccins · Lots · Opérateurs |
| VETO | Signalements · Surveillance · Recherche de lots · Paramètres sanitaires · Vaccins et calendrier · Paramètres à approuver · Fermes · Bandes · Déclarations · Indicateurs · Lots |
| AUDITEUR | Journal · Intégrité |
| BCEG, MAEDR, OPERATEUR | aucune tuile pour l'instant : « Vos écrans arrivent bientôt » |

## Tuile → écran → lot

| Tuile | Écran (route) | Compteur | Lot |
|---|---|---|---|
| Mes fermes / Fermes | `fermes.liste` (agent : triée par urgence) | fermes en rouge (agent) | 1 (15 : tuile, 16 : urgence) |
| Tournée du jour | `agent.tournee` | lignes de la tournée | 16 |
| Surveillance | `veto.surveillance` (sorties bloquées ; ADMIN en lecture) | sorties à vérifier | 17 |
| Paramètres sanitaires | `veto.parametres` (quatre yeux) | — | 17 |
| Recherche de lots | `veto.recherche` (amont, aval, export CSV) | — | 17 |
| Commandes d'intrants | `agent.commandes` | refus non lus (agent) · à décider (DGE, ADMIN) | 16 |
| Saisies à vérifier / Arbitrages | `hors_ligne.conflits` | saisies à trancher | 12 |
| Livraisons et stock / Livraisons de l'État | `livraisons.liste` | — | 2 |
| Bandes | `bandes.liste` | — | 3 |
| Indicateurs / Tableau de bord | `pilotage.tableau` | — | 5 |
| Carte | `pilotage.carte` | — | 5 |
| Rapports | `pilotage.rapports` | — | 5 |
| Signalements / Alertes sanitaires | `sante.alertes` (vétérinaire : triés par gravité ; fiche : diagnostic, blocage) | à qualifier / confirmées | 4 (17 : gravité, diagnostic) |
| Déclarations | `sante.declarations` | — | 4 |
| Vaccins et calendrier | `sante.vaccins` | — | 4 |
| Lots et QR codes | `tracabilite.lots` | — | 6 |
| Opérateurs | `operateurs.liste` | — | 1 |
| Utilisateurs | `utilisateurs.index` | — | 0 |
| Configuration | `controle.configuration` (regroupe les réglages) | — | 15 |
| Paramètres à approuver | `controle.approbations_ecran` | propositions à décider | 15 |
| Sessions | `controle.sessions` | — | 15 |
| Journal | `journal.index` | — | 0 |
| Intégrité | `controle.integrite` | — | 15 |

### Écran Configuration (ADMIN), 2ᵉ clic

Provinces et localités · Listes · Paramètres · Catalogue des intrants · Formules des indicateurs · Tâches d'entretien · Aides.

### Hors tuiles

- **Ma sécurité** (`auth.securite`, clé en haut à droite) : double authentification, codes de secours, sessions ouvertes. Lot 15.

### Depuis la fiche ferme (2ᵉ clic, lot 16)

À faire (raisons d'urgence) · Stock avec « Compter » et écart · Biosécurité → « Évaluer » · Commandes · Comptes des éleveurs → « Nouvel éleveur ».
