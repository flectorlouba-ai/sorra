# SORRA — Matériel pour le dossier de présentation

Préparé le 9 novembre 2026 à partir de la démonstration https://sorra.performyl.com (**données fictives**) et du code de la branche `main`. Aucun code n'a été modifié pour ce dossier.

| Fichier | Contenu |
|---|---|
| `captures/` | Écrans en PNG, nommés `telephone_…` (390 × 844, échelle 2) et `ordinateur_…` (1440 × 900). |
| `matrice_droits.csv` | Droits par écran et par action, **extraits automatiquement du code** (point-virgule, UTF-8). |
| `securite.md` | Chaque mécanisme de sécurité en place, avec son fichier et le test qui le prouve, puis ce qui manque. |
| `fonctions_etat.csv` | Les 68 fonctions du cahier des charges, leur priorité, leur état réel et le lot. |
| `chiffres.md` | Tests, écrans, profils, migrations, lots, déploiement, comptes de démonstration. |

## Captures

- **Prises sur la démonstration en ligne.** Le bandeau « DÉMONSTRATION — données fictives » y est visible.
- **Quatre cas pris sur une copie locale des mêmes données fictives**, parce que la démonstration n'avait pas l'état voulu :
  - `telephone_06_…` et `telephone_06b_…` : la réponse du vétérinaire à l'éleveur. Aucune réponse n'existait dans les données de la démo ; une réponse fictive a été ajoutée sur la copie.
  - `telephone_24_…` : « Gardez ces poulets à part ». Aucun lot attendu de la démo ne manquait de contrôle ; un lot fictif sans pesée a été ajouté sur la copie.
  - `ordinateur_40_connexion_double_authentification` : la démo coupe la double authentification (mot de passe public). La copie locale tourne avec la 2FA en marche, sans le bandeau de démonstration.
  - `telephone_13_agent_a_verifier_deux_versions` : la démo n'avait pas de saisie en deux versions à trancher ; une saisie de `marie.nze` (12 morts) et une de l'agent (17 morts) ont été ajoutées sur la copie.
- **Mode sans réseau** (`telephone_08_…` et `telephone_08b_…`) : le téléphone a été mis hors réseau dans le navigateur. La saisie est gardée sur le téléphone (« Gardé ✓ — ◷ Sera envoyé dès que le réseau revient », puis le bandeau « Pas de réseau — vos saisies sont gardées sur le téléphone · ◷ en attente »). La session a été fermée sans la renvoyer : rien n'a été ajouté à la démo.
- **Effets sur la démo** : les scans de l'opérateur ont été inscrits au journal des scans. Les connexions ont été espacées pour respecter la limite de débit.

## Matrice des droits : comment elle est construite

- **Une ligne par adresse de l'application** (198), avec la description tirée du code, les méthodes et l'accès déclaré.
- **Colonnes** : les 9 profils (ADMIN, DGE, AGENT, VETO, ELEVEUR, AUDITEUR, BCEG, MAEDR, OPÉRATEUR). L'opérateur est décliné par type : Abattoir, Marché, Acheteur, Distributeur.
- **D'où viennent les profils** : ils sont lus dans le décorateur `@profil_requis` de chaque route (dans l'application en marche, pas à la main). `@login_required` donne « tout compte connecté ».
- **Valeurs** :
  - « Voir » : page en lecture ;
  - « Voir (son périmètre) » : la vue applique `filtre_perimetre` ou une règle de ferme, et le profil n'est pas national ;
  - « Saisir » : la route accepte un envoi de formulaire ;
  - « Valider » : envoi dont la fonction décide (approuver, trancher, libérer, confirmer, bloquer, corriger…) ;
  - « — » : refusé (403).
- **Limites de l'extraction** :
  - les règles plus fines dans les vues ne sont pas toutes visibles (par exemple : « seul le vétérinaire de la province de la ferme décide d'un lot gardé à part », « l'éleveur saisit un jour passé jusqu'à 3 jours ») ; elles sont décrites dans `securite.md` et les documents du dépôt ;
  - les adresses `/auth/2fa…` sont publiques par construction : elles servent pendant la connexion, avant l'ouverture de la session.
- **Les types d'opérateur** ont les mêmes écrans. Leur différence est une règle de contrôle à la réception, réglable sous quatre yeux : vaccins et pesée sont **bloquants à l'abattoir**, **pour information** au marché, chez l'acheteur et le distributeur. Le délai d'attente des traitements et le blocage vétérinaire sont bloquants pour tous.
