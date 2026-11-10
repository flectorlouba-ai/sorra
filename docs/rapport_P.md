# Lot P — Code du terrain, file de synchronisation, guides PDF

- **🔢 Mon code** (éleveur, agent, opérateur ; Moi → Mon code) : 4 à 6 chiffres, réglé avec le mot de passe, codes trop simples
  refusés (identiques, qui se suivent), haché (`utilisateur.pin_hash`). Sur l'écran de connexion : identifiant (repris du dernier
  usage sur le téléphone) + « 🔢 Entrer avec mon code ». Après 5 erreurs, le code est coupé (journal BLOCAGE) et le mot de passe
  redevient obligatoire ; le code se retire d'un toucher. Limite de débit du lot S appliquée. Migration 0034.
- **🔄 File de synchronisation** (`/bureau/synchronisation`, ADMIN et DGE, tuile Paramètres) : envois reçus des téléphones
  (saisies faites sans réseau) : reçu le, saisi le, délai, qui, profil, appareil, écran, objet ; indicateurs 7 jours (envois,
  délai moyen, appareils, reçus plus de 48 h après) ; consultation journalisée.
- **📘 Guides PDF par profil** (`/aide/guide/<PROFIL>.pdf`) : fonctions du profil (version ordinateur) + « Comment faire ? »
  (téléphone) + rappels de sécurité ; lien sur Moi (téléphone) et dans la zone titre (ordinateur) ; le sien seulement, tous pour
  l'ADMIN et la DGE ; export journalisé.
- Tests : `tests/test_lotP.py` (3) ; captures `docs/captures/lotP/`.

## À tester
- **Téléphone, `eleveur`** : Moi → Mon code → 2719 / mot de passe → se déconnecter → « Entrer avec mon code » ; 5 codes faux →
  mot de passe obligatoire. Moi → Mon guide (PDF).
- **Ordinateur, `admin`** : Paramètres → File de synchronisation (envoyer une saisie en mode avion depuis le téléphone pour la voir).

Déployé sur la démo : voir `docs/rapport_suite.md`.
