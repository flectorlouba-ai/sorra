# SORRA — Relecture des lots 15 à 18 : les 4 points

Branche `autonome-lots-15-18`, **ni fusionnée ni poussée**, aucun déploiement.

## 1. Saisies de l'agent sans réseau — fait (commit dédié)

**Ce qui demandait le réseau avant :**
- **sans formulaire « hors ligne »** : vaccin et traitement pour l'éleveur, biosécurité, nouvel éleveur. Aussi : nouvelle bande, clôture, corrections, visites (planifier, annuler), comptage, commande, livraisons, fiche ferme, BCEG ;
- **avec formulaire « hors ligne », mais page jamais gardée sur le téléphone de l'agent** : saisie du jour, pesée, sortie, poulet malade, J'ai payé, entretien, réception, compte rendu.

**Maintenant hors ligne** (mécanisme existant : identifiant unique, file d'attente, règle des conflits du lot 12) :
- la saisie pour l'éleveur, dont le vaccin et le traitement ;
- le compte rendu de visite ;
- la biosécurité ;
- l'enrôlement d'un nouvel éleveur. L'identifiant et le mot de passe provisoire sont préparés sur le téléphone et montrés tout de suite.

Le téléphone de l'agent garde ses pages de saisie à chaque ouverture de l'accueil avec du réseau. Les décisions restent en ligne.

Règles et détail : `docs/hors_ligne.md` (« L'agent sans réseau ») ; décisions R-1, R-1b, R-1c.

**Tests** : `tests/test_agent_hors_ligne.py` (5) :
- chaque page gardée s'ouvre et porte son formulaire hors ligne ;
- saisie pour l'éleveur et conflit avec l'éleveur ;
- deux comptes rendus pour une visite ;
- biosécurité datée du téléphone ;
- nouvel éleveur : identifiant pris, doublon de téléphone, connexion avec le mot de passe noté.

**Navigateur**, réseau coupé : nouvel éleveur et biosécurité gardés (◷), puis envoyés au retour du réseau ; le compte se connecte. Captures : `docs/captures/agent_hors_ligne/`.

**Correction au passage** : le bandeau « ◷ en attente » se coupait ligne à ligne sur les écrans du pilotage.

## 2. Classement — confirmé et complété (commit à part)

- Les **pondérations** (`classement.poids_*`) sont réglables, sous quatre yeux.
- Le **barème des notes** et le **seuil « bande incomplète »**, jusque-là fixés dans le code, le sont aussi maintenant (`classement.*`, migration 0020).
- Un test de bout en bout vérifie : rien ne change avant l'approbation, jamais par l'auteur, et le classement change après.
- Les seuils des étoiles sont des paramètres (`bandes.etoiles_*`, lot 8), listés dans `a_faire_valider.md`.

## 3. Ancien nom dans l'historique — fait

- Étiquette de sauvegarde : `sauvegarde-autonome-lots-15-18-avant-reecriture` (ancien `f028e41`).
- Les commits ont été refaits avec `git commit-tree`, en gardant auteurs, dates et messages. Seul l'arbre du lot 15 change (une ligne de `docs/rapport_lot15.md`). `git diff` entre l'ancienne et la nouvelle fin de branche : **vide**.
- `git log -p` sur la branche depuis `1a759bb` (diffs et messages) : **0 occurrence**.
- La branche principale, avant `1a759bb`, contient encore le nom dans les commits d'avant le renommage. Ils n'ont pas été touchés (hors du périmètre demandé).

## 4. Suite complète

**385 tests réussis**, 1 réservé à PostgreSQL (16 min), sur l'état final : lots 15 à 18, retouches des lots 17 et 18, points 1 et 2. Aucun échec.
