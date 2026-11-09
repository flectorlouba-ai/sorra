# SORRA — Rapport du lot 15 : socle du pilotage (tuiles, quatre yeux, journal chaîné, sessions, double authentification)

**État :** terminé, en mode autonome, sur la branche `autonome-lots-15-18`, commit dédié. **Aucun déploiement.**

**Tests :** **359 tests réussis** et 1 réservé à PostgreSQL (suite complète, 8 min), dont 10 nouveaux dans `tests/test_lot15.py` et `tests/test_accueil.py` réécrit.

**Migration :** 0016 (`socle_securite`), avec retour arrière testé (montée, descente, montée sur une copie de la base de démo ; chaîne intacte, 183 puis 186 entrées).
- Tables `journal_chaine` (empreintes, protégées par déclencheurs), `proposition` (quatre yeux), `session_utilisateur`.
- `utilisateur.totp_secret`, `totp_active`, `codes_secours`.
- Paramètres `securite.profils_2fa`, `verifications.delai_rouge_heures` ; durée de session 60 → 30 min.

**Références :** maquettes `docs/maquettes/maquettes_lot15.md` ; décisions 15-1 à 15-10 dans `docs/decisions_autonomes.md` ; tuiles `docs/pilotage.md`.

**Bibliothèques :** aucune nouvelle. Le TOTP (RFC 6238) est écrit avec `hmac` ; le QR code vient de reportlab, déjà présent.

## Ce qui a été fait

### A. Accueil du pilotage en tuiles
- Un seul panneau de tuiles par profil, sans onglets. Les tuiles visées viennent d'abord, dans l'ordre demandé, puis les écrans existants (décision 15-5).
- **Aucune tuile morte** : le test ouvre chaque tuile de chaque profil et attend 200.
- **Compteurs** rouges : saisies à vérifier, arbitrages, signalements à qualifier, alertes confirmées, paramètres à approuver (sans compter ses propres propositions).
- **Périmètre** en tête : « · National », « · Estuaire », « · 4 fermes suivies ».
- **Configuration** (ADMIN) regroupe les 7 réglages : chaque réglage est à 2 clics.
- BCEG, MAEDR, OPERATEUR : « Vos écrans arrivent bientôt » (décision 15-6). Pas de tuile Sauvegardes (décision 15-7).

### B. Quatre yeux
- Les réglages sensibles deviennent une **proposition** avec un motif obligatoire. L'ancienne valeur s'applique jusqu'à l'approbation.
  - Paramètres sensibles (seuils sanitaires et d'élevage, délais) ;
  - formules des indicateurs ;
  - calendrier vaccinal ;
  - changement de profil d'un utilisateur.
- **Paramètres à approuver** : avant / après, motif, « Approuver » ou « Refuser » (motif obligatoire pour refuser), historique des décisions.
- **Jamais par l'auteur.** ADMIN et DGE décident tout ; un vétérinaire décide seulement le sanitaire.
- Proposition, approbation et refus sont inscrits au journal.

### C. Journal chaîné et Intégrité
- Chaque entrée du journal a une empreinte **SHA-256** de son contenu et de l'empreinte précédente (`journal_chaine`, décision 15-1). Le journal existant a été chaîné par la migration sans être modifié.
- **Intégrité** (ADMIN, AUDITEUR) : « ✓ Journal intact — N entrées vérifiées », ou « ✗ Rupture à l'entrée n° … » avec sa date et son action.

### D. Sessions
- Chaque connexion ouvre une session enregistrée : appareil, adresse, ouverture, dernière activité.
- **Sessions** (ADMIN) : liste des sessions ouvertes, « Fermer cette session » avec motif. La session est refusée à la requête suivante.
- Pilotage : déconnexion après **30 min** d'inactivité (paramètre). **Éleveur et agent : jamais** (terrain sans réseau). Les saisies gardées sur le téléphone ne sont pas perdues si la session est fermée (`docs/hors_ligne.md`).
- **Ma sécurité** (icône 🔑) : mot de passe, 2FA, mes sessions (décision 15-8).

### E. Double authentification (TOTP)
- **Obligatoire** : ADMIN, DGE, MAEDR, BCEG, AUDITEUR (paramètre `securite.profils_2fa`). **Facultative** : VETO, AGENT, OPERATEUR (depuis Ma sécurité). **Jamais** : éleveur.
- Mise en place : QR code et clé, puis code à 6 chiffres ; ensuite **8 codes de secours** montrés une seule fois. Chacun ne sert qu'une fois ; ils sont gardés hachés.
- **Réinitialisation par l'ADMIN** (Utilisateurs → « Réinitialiser la 2FA »), avec motif, inscrite au journal.
- **Interrupteur** `YL2_2FA` (décision 15-2) : actif par défaut en production. La démo locale tourne avec `YL2_2FA=0`, donc les comptes de démo marchent sans téléphone.

### Correction pendant les captures
Le QR code s'affichait mal à 360 px : le SVG de reportlab porte un prologue XML qui coupait la suite de la page. Il est maintenant servi comme image (data URI). Le bouton « Refuser » a pris la taille normale.

### Corrections après la première suite complète (6 échecs, tous réparés)
- Deux anciens tests cherchaient des tuiles déplacées (Journal, Tâches d'entretien → Configuration) : mis à jour.
- La clé 🔑 de l'éleveur pointait vers « Ma sécurité », une page qui n'est pas gardée sans réseau. L'éleveur garde son lien vers le mot de passe (décision 15-11).
- Nombre de paramètres (24 → 26), couleur `#fff` remplacée par `var(--blanc)`, sous-titre « Arbitrages » sans le mot « doublons » (un test vérifie son absence avant 48 h).

## Base de démo
- Migrée en 0016. Copie d'avant : `demo_performyl2_avant_lot15.db`, à côté de la base de démo.
- Nouveau compte **auditeur** (Claire Mintsa, profil Auditeur), même mot de passe `Demo-yl2-2026`.
- Une **proposition en attente** : seuil du feu rouge de 1 à 4 %, proposée par l'admin. La DGE ou le vétérinaire peut l'approuver.
- Une session « Android · Chrome » de la DGE, pour l'écran Sessions.
- Serveur local : port 5020, `YL2_2FA=0`.

## Captures (`docs/captures/lot15/`)
360 px et bureau :
- accueil de l'admin, de la DGE, de l'agent, du vétérinaire et de l'auditeur ;
- Paramètres à approuver ; Ma sécurité ; Configuration ; Sessions ; Intégrité ; Paramètres ;
- mise en place de la 2FA (serveur d'essai avec `YL2_2FA=1`).

Aucune page ne dépasse 360 px de large. La table des sessions défile dans son cadre, comme les autres tables.

## À tester à la main
1. Se connecter en **dge** : tuiles Tableau de bord, Carte, Livraisons de l'État, Arbitrages, Rapports, puis « Paramètres à approuver » avec un compteur 1. Ouvrir chaque tuile.
2. Approuver la proposition du feu rouge. Vérifier dans Paramètres que la valeur est 4, et la ligne au Journal.
3. En **admin**, modifier un seuil sensible (Paramètres) : le motif est demandé, la valeur ne change pas, « en attente d'approbation ». L'admin ne peut pas l'approuver lui-même.
4. En **veto**, ajouter une ligne au calendrier vaccinal : elle n'apparaît qu'après l'approbation par la DGE.
5. En **admin**, Sessions → fermer la session de la DGE : dans le navigateur de la DGE, la page suivante renvoie à la connexion.
6. En **auditeur** : seulement Journal et Intégrité ; Intégrité affiche « Journal intact ».
7. Relancer le serveur avec `YL2_2FA=1` sur une copie de la base. Se connecter en admin : mise en place avec l'application du téléphone, codes de secours, puis reconnexion avec un code de secours (il ne marche qu'une fois).
8. En **veto**, Ma sécurité → activer la 2FA (facultative). En **admin** → Utilisateurs → réinitialiser la 2FA du veto, avec un motif.
9. En **eleveur** : aucune demande de code ; pas de déconnexion après 30 min d'inactivité.
10. Laisser une page du pilotage ouverte plus de 30 min sans rien faire, puis cliquer : retour à la connexion.

## Points ouverts
- Liste des réglages sensibles et profils à 2FA obligatoire : à valider (`docs/a_faire_valider.md`).
- Secret TOTP en clair en base (décision 15-9) ; chaînage sans verrou (décision 15-10).
