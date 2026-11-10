# SORRA — Sécurité (état au lot S, 10/11/2026)

## Ce qui est en place
| Mesure | Où | Depuis |
|---|---|---|
| Mots de passe hachés (Werkzeug), longueur minimale réglable (`securite.mdp_longueur_min`), changement obligatoire au premier accès | `models/utilisateur`, `routes/auth` | lot 0 |
| **Mots de passe courants refusés** (liste `app/utils/mots_de_passe_courants.txt` + suites trop simples) | `securite.mot_de_passe_courant` | **lot S** |
| Blocage après N échecs (`securite.echecs_avant_blocage`, `securite.blocage_minutes`) ; en démo, blocage par adresse | `routes/auth` | lot 15 |
| **Limite de débit** : 30 tentatives de connexion par adresse et par 10 minutes → 429, journalisé | `securite.connexion_trop_frequente` | **lot S** |
| Second facteur (TOTP) obligatoire pour les profils de `securite.profils_2fa`, codes de secours | lot 15 | lot 15 |
| Sessions nommées (appareil, adresse), fermeture par l'administrateur, expiration par inactivité (jamais pour le terrain) | lot 15 | lot 15 |
| **Alerte « nouvel appareil »** : première connexion d'un compte depuis un type d'appareil → journal + message (sauf éleveur) | `securite.appareil_inconnu` | **lot S** |
| CSRF (Flask-WTF) sur tous les POST ; en-tête `X-CSRFToken` accepté pour les appels JS ; **test automatique** | `tests/test_lotS` | lot 0 / **S** |
| **En-têtes** : CSP sans ressource externe (`default-src 'self'`, `frame-ancestors 'none'`, `object-src 'none'`), Referrer-Policy, X-Content-Type-Options, X-Frame-Options, Permissions-Policy, HSTS derrière HTTPS | `app/__init__.entetes_securite` | **lot S** |
| Aucune ressource externe (polices, scripts, cartes : tout est local) | règle permanente | — |
| Périmètre des données par profil (`filtre_perimetre`), vétérinaire sans donnée financière, BCEG avec accord seulement, MAEDR agrégé | `utils/permissions` | lots 1, 13, M |
| Paramètres sensibles à quatre yeux (`approbations.SENSIBLES`) | lot 15 | — |
| Journal chaîné (empreintes), vérification d'intégrité, exports journalisés ; **consultations sensibles** (comptes, sessions, fermes financées) journalisées | `services/journal` | lot 14 / **S** |
| **Export des droits** (profils × adresses) en Excel, journalisé | `/bureau/droits?format=xlsx` | **lot S** |
| Archiver, jamais supprimer | lot A | — |
| Secrets uniquement dans le `.env` du serveur (clé secrète, base, clés VAPID) ; jamais dans git ni dans un rapport | règle permanente | — |
| **Déploiement** : refus si un secret apparaît dans un fichier suivi ; `pip-audit` sur `requirements.txt` (refus en cas de vulnérabilité connue) ; déploiement à blanc des migrations ; retour arrière automatique | `deploiement/demo/deployer.sh` | **lot S** |
| **Sauvegardes** : pg_dump de nuit, 14 jours ; **chiffrées** avec la clé publique `/etc/sorra/sauvegarde.pub` (la copie en clair est retirée) et **copiées hors du serveur** si `/etc/sorra/sauvegarde.conf` définit `DISTANT` | `performyl2-demo-sauvegarde.sh` | **lot S** |

## À faire par le propriétaire
1. Générer une paire de clés GPG sur le poste (`gpg --quick-generate-key "SORRA sauvegardes"`), exporter la clé publique
   (`gpg --export -a > sauvegarde.pub`) et la déposer en `/etc/sorra/sauvegarde.pub` (600, root). La clé privée reste sur le poste.
2. Créer `/etc/sorra/sauvegarde.conf` avec `DISTANT=utilisateur@hote-distant:/chemin` (accès par clé SSH du compte root du serveur).
3. Installer `pip-audit` dans le venv du poste (`venv/Scripts/pip install pip-audit`) : le déploiement le lance.
4. Restauration d'essai à chaque trimestre (`docs/exploitation.md`).

## Limites connues
- La limite de débit est comptée par processus (3 workers gunicorn) : elle freine, elle ne garantit pas un plafond exact.
- La CSP autorise les scripts et styles en ligne (`'unsafe-inline'`) : les gabarits en contiennent ; le passage aux nonces est prévu.
