# SORRA — Décisions prises en mode autonome (lots 15 à 18)

Chaque décision : la question, le choix fait, l'autre option, et comment revenir en arrière. Les plus importantes sont marquées ★.

## Lot 15

| # | Question | Choix fait | Autre option | Revenir en arrière |
|---|---|---|---|---|
| 15-1 ★ | Comment chaîner le journal sans modifier les entrées existantes (déclencheur anti-modification) ? | Empreintes dans une **table séparée `journal_chaine`** (une ligne par entrée, en écriture seule), remplie à chaque écriture en base, et par la migration pour l'existant. | Ajouter une colonne au journal : il aurait fallu modifier les lignes existantes, ce qui est interdit. | Migration 0016 : son retour arrière supprime la table, et le journal reste intact. |
| 15-2 ★ | 2FA : comment la couper pour la démo locale ? | Variable d'environnement **`YL2_2FA`**. Elle est active par défaut en production ; le serveur de démo local est lancé avec `YL2_2FA=0`. En développement et en test, elle est inactive par défaut. | Un paramètre en base : risque de la couper par erreur en production. | Changer la valeur de la variable au lancement. |
| 15-3 ★ | Quels écrans passent par les quatre yeux ? | Les paramètres sensibles (liste de préfixes dans `services/approbations.SENSIBLES`), les formules, le calendrier vaccinal et le **changement de profil** d'un utilisateur. Les autres paramètres (durées, adresse publique…) restent directs. | Tous les paramètres. | Modifier la liste `SENSIBLES`. |
| 15-4 | Durée d'inactivité du pilotage | Le paramètre existant `securite.duree_session_minutes` est **ramené de 60 à 30** par la migration 0016 (s'il valait encore 60), et ne vaut plus que pour le pilotage. | Un nouveau paramètre. | Retour arrière de la migration (remet 60), ou changer la valeur dans Paramètres. |
| 15-5 | Tuiles des écrans existants qui ne sont pas dans votre liste (Bandes, Indicateurs, Lots et QR, Opérateurs…) | **Gardées** après les tuiles visées, pour ne perdre aucun accès. | Les retirer. | Retirer la clé dans `TUILES_PROFIL` (`routes/accueil.py`). |
| 15-6 | OPERATEUR, BCEG, MAEDR n'ont encore aucun écran | Accueil avec la phrase « Vos écrans arrivent bientôt », et **aucune tuile**. | Des tuiles « bientôt » : interdit (tuile morte). | Ajouter les tuiles quand les écrans existent. |
| 15-7 | Sauvegardes (tuile ADMIN) | **Pas de tuile** : il n'existe pas d'écran (les sauvegardes sont des scripts du VPS, `docs/exploitation.md`). | Créer un écran de lecture des sauvegardes : il demanderait l'accès au VPS. | Lot ultérieur. |
| 15-8 | Où l'utilisateur du pilotage gère sa 2FA et ses sessions ? | Un écran **« Ma sécurité »** (`/auth/securite`), ouvert par l'icône 🔑 de l'en-tête : mot de passe, 2FA, mes sessions. | Les mettre dans l'écran Utilisateurs. | — |
| 15-9 | Secret TOTP stocké comment ? | En clair (base 32) dans `utilisateur.totp_secret`, comme le fait la plupart des applications ; les codes de secours sont **hachés**. | Chiffrer le secret avec une clé serveur. | Ajouter le chiffrement plus tard (migration de données). |
| 15-10 | Chaînage avec plusieurs écritures simultanées (PostgreSQL) | Simple : la dernière empreinte est lue au moment de l'écriture. Deux transactions exactement simultanées pourraient produire une fausse « rupture » ; elle serait visible à l'écran Intégrité, sans perte de données. | Un verrou de table à chaque écriture du journal. | Ajouter `LOCK` dans `journal.chainer` si cela arrive. |
| 15-11 | L'éleveur a-t-il « Ma sécurité » ? | **Non** : l'éleveur n'a ni 2FA ni gestion de sessions. Sa clé 🔑 ouvre toujours « Changer mon mot de passe » (phase 1 inchangée), et `/auth/securite` le renvoie à « Mon compte ». | Lui montrer l'écran avec ses sessions. | Retirer la redirection dans `routes/auth.py`. |
