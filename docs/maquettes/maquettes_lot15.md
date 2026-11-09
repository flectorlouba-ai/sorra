# SORRA — Lot 15 : accueil du pilotage et socle de sécurité (mode autonome)

Lot construit en mode autonome. Les choix faits seul sont dans `docs/decisions_autonomes.md`.

## A. Accueil du pilotage (tous les profils sauf ÉLEVEUR)

- **En haut** : nom, profil, **périmètre** (« National » ou la liste des provinces), « Ma sécurité », déconnexion.
- **Une grille de tuiles par profil**, dans la charte YL.1 (`module-card`), avec un **compteur** sur les tuiles qui en ont un (alertes, à vérifier, à approuver). L'encadré Alertes est gardé.
- **Aucune tuile morte** : une tuile n'apparaît que si son écran existe. Les onglets « Bientôt » et « Option » des lots 1 à 14 disparaissent. La table tuile → écran → lot est dans `docs/pilotage.md`.
- **Toujours 2 clics au plus depuis l'accueil.** L'ancien onglet Configuration de l'ADMIN devient l'écran « Configuration » (`/configuration`).

| Profil | Tuiles disponibles au lot 15 (les autres arrivent avec leur écran) |
|---|---|
| AGENT | Mes fermes · Saisies à vérifier (n) · Livraisons et stock · + écrans existants : Bandes, Indicateurs, Vaccins et traitements, Lots et QR, Opérateurs |
| VETO | Signalements (n) · Vaccins et calendrier · + Fermes, Bandes, Déclarations, Lots et QR |
| DGE | Tableau de bord · Carte · Livraisons de l'État · Arbitrages (n) · Rapports · + Fermes, Bandes, Alertes sanitaires, Lots et QR, Opérateurs, Paramètres à approuver (n) |
| ADMIN | Utilisateurs · Configuration · Paramètres à approuver (n) · Sessions · Journal · Intégrité · Arbitrages (n) |
| AUDITEUR | Journal · Intégrité |
| OPERATEUR, BCEG, MAEDR | pas encore d'écran : « Vos écrans arrivent bientôt » (aucune tuile morte) |

## B. Double validation (« quatre yeux »)

- **Paramètres sensibles** : seuils d'alerte (`bandes.seuil_*`, `bandes.ecart_courbe_pct`, `intrants.seuil_*`, `sante.*`), courbe de croissance, formules des indicateurs, calendrier vaccinal, délai des doublons (`verifications.delai_rouge_heures`, nouveau), pondérations du classement (`classement.*`, lot 18), changement de profil d'un utilisateur, liste des profils à 2FA obligatoire (`securite.profils_2fa`, nouveau).
- Modifier l'un d'eux crée une **proposition** (avant, après, motif obligatoire). **L'ancienne valeur s'applique** jusqu'à l'approbation.
- Une **autre personne habilitée** approuve ou refuse, avec un motif pour le refus. L'auteur ne peut jamais approuver sa propre proposition.
- **Qui décide** : l'ADMIN et la DGE pour tout ; le VETO pour le sanitaire (seuils `sante.*`, calendrier vaccinal).
- **Écran « Paramètres à approuver »** (`/approbations`) : les propositions en attente, et l'historique.
- Tout est inscrit au journal : proposition, approbation, refus et application.

## C. Journal chaîné

- Chaque entrée du journal reçoit une **empreinte SHA-256** qui inclut l'empreinte de la précédente. Elle est rangée dans une table à part, **`journal_chaine`**, elle-même en écriture seule (déclencheurs).
- Le journal existant n'est donc **jamais modifié**. La migration chaîne les entrées existantes dans `journal_chaine`.
- Le chaînage se fait à chaque écriture en base, pour toutes les entrées : celles des événements et celles des modifications automatiques.
- **Écran « Intégrité »** (AUDITEUR, ADMIN) : « ✓ Journal intact (N entrées) » ou « ✗ Rupture à l'entrée n° X (date, action) ».

## D. Sessions

- Table **`session_utilisateur`** : appareil (navigateur résumé), adresse, ouverture, dernière activité, fermeture (par qui, motif).
- **ADMIN** : écran « Sessions », avec toutes les sessions ouvertes et « Fermer cette session ». **Chacun** voit les siennes dans « Ma sécurité ».
- **Pilotage** : déconnexion après **30 min** d'inactivité (paramètre existant `securite.duree_session_minutes`, ramené à 30).
- **ÉLEVEUR et AGENT** : jamais de déconnexion automatique ; les saisies en attente ne sont jamais effacées.
- Une session fermée par l'ADMIN est refusée à la requête suivante.

## E. Double authentification (TOTP)

- Application d'authentification (codes à 6 chiffres, 30 s), et **8 codes de secours** à usage unique, affichés une seule fois.
- **Obligatoire** : ADMIN, DGE, MAEDR, BCEG, AUDITEUR (paramètre `securite.profils_2fa`, quatre yeux). **Facultative** : VETO, AGENT, OPERATEUR (« Ma sécurité »). **Jamais** : ÉLEVEUR.
- **Première connexion** d'un profil obligatoire : mise en place guidée (QR code, clé à recopier, premier code, puis codes de secours).
- **Réinitialisation par l'ADMIN**, avec motif (journal) : à la connexion suivante, la mise en place recommence.
- **Interrupteur** : variable d'environnement `YL2_2FA`. Elle est active par défaut en production ; `YL2_2FA=0` sert pour la base de démo locale, et seulement là. En développement et en test, elle est inactive par défaut, et les tests de la 2FA l'activent.

## Tables (migration 0016)

`journal_chaine`, `proposition`, `session_utilisateur` ; `utilisateur` + `totp_secret`, `totp_active`, `codes_secours` ; nouveaux paramètres `securite.profils_2fa` et `verifications.delai_rouge_heures`.
