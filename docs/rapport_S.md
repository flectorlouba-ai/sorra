# Lot S — Sécurité

Détail complet dans `docs/securite.md` (mis à jour). Ajouts de ce lot :
- **En-têtes** sur chaque réponse : CSP sans aucune ressource externe (`default-src 'self'`, `frame-ancestors 'none'`,
  `object-src 'none'`), Referrer-Policy, X-Content-Type-Options, X-Frame-Options, Permissions-Policy, HSTS derrière HTTPS.
- **Limite de débit** sur la connexion : 30 tentatives par adresse et par 10 minutes → 429 + journal.
- **Mots de passe courants** refusés (liste locale + suites trop simples) au changement et à la création d'un compte.
- **Test CSRF** automatique : un POST sans jeton est refusé.
- **Alerte « nouvel appareil »** : première connexion d'un compte depuis un type d'appareil → journal (`· nouvel appareil`) et
  message au pilotage.
- **Journal des consultations sensibles** (action CONSULTATION) : liste des comptes, sessions ouvertes, fermes financées (BCEG).
- **Export des droits** en Excel, journalisé (Profils et droits → « ⬇️ Exporter les droits »).
- **Sauvegardes** chiffrées (clé publique GPG `/etc/sorra/sauvegarde.pub`, copie en clair retirée) et copiées hors du serveur
  (`/etc/sorra/sauvegarde.conf` : `DISTANT=`) ; le script s'installe au déploiement.
- **deployer.sh** : refus si un secret apparaît dans un fichier suivi ; `pip-audit` sur `requirements.txt` (refus en cas de
  vulnérabilité connue, sauté si l'outil manque).
- Tests : `tests/test_lotS.py` (6).

## À faire par le propriétaire
Déposer la clé publique GPG et la destination distante sur le serveur (voir `docs/securite.md`, § À faire) ; installer `pip-audit`
dans le venv du poste.

## À tester
- `admin` : se connecter depuis un autre navigateur → message « Première connexion depuis cet appareil » ; Profils et droits →
  export Excel ; Journal → actions CONSULTATION après avoir ouvert Utilisateurs et Sessions.
- Changer son mot de passe en « motdepasse1 » → refusé.

Déployé sur la démo : **oui** — version 2026-11-10-db5c48c.
