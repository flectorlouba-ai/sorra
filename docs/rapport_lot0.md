# KIMBA — Lot 0 : socle technique — rapport

Date : 8 novembre 2026. Dossier : `Desktop\KIMBA\kimba` (nouveau dépôt git).
État : construit et testé en local (77 tests automatiques réussis). Pas encore déployé.

## 1. Ce qui a été fait

| Fichier | Contenu |
|---|---|
| `kimba.py` | Point d'entrée. Lance l'application sur le port 5020. |
| `config.py` | Réglages lus dans le `.env` : clé secrète, base de données (SQLite par défaut, PostgreSQL par `DATABASE_URL`), cookies protégés. En production, refuse de démarrer sans clé ni base. |
| `.env.exemple`, `requirements.txt`, `README.md` | Modèle de réglages, bibliothèques (versions figées), mode d'emploi du démarrage. |
| `app/__init__.py` | Assemble l'application. Ferme la session après une période d'inactivité (paramètre). Oblige à changer le mot de passe tant que c'est demandé. Affiche des pages claires pour « accès refusé », « page introuvable » et « session expirée ». |
| `app/commandes.py` | Commande `flask init-kimba` : crée le compte `admin` avec un mot de passe tiré au hasard, affiché une seule fois et à changer à la première connexion. |
| `app/models/base.py` | Mixin `SaisieTerrainMixin` pour les futures saisies terrain : identifiant UUID créé par l'application, `numero_metier`, `numero_provisoire`, `cree_le`, `modifie_le`, `cree_par`, `modifie_par` (remplis automatiquement), `appareil_id`, `statut_synchro` (LOCAL, SYNCHRONISE, CONFLIT). |
| `app/models/utilisateur.py` | Les 9 profils, les comptes et le rattachement aux provinces. La table de rattachement aux fermes est prête ; son lien vers `Ferme` sera posé au lot 1. Un compte désactivé perd sa session à la requête suivante. |
| `app/models/referentiel.py` | Provinces (avec leur code) et localités. |
| `app/models/liste_deroulante.py` | Listes configurables, comme dans YL.1. |
| `app/models/parametre.py` | Paramètres : clé, valeur, type, description. Deux sont livrés : la longueur minimale du mot de passe (10) et la durée de session (60 min). |
| `app/models/compteur.py`, `app/services/numerotation.py` | `generer_numero(type, prefixe)` donne EST-000001, EST-000002… Option annuelle : DS-2026-000001. La ligne du compteur est verrouillée sous PostgreSQL et le compteur ne redescend jamais. |
| `app/models/journal.py`, `app/services/journal.py` | Journal d'audit automatique (créations, modifications, suppressions, annulations) avec les valeurs avant / après, et journal des connexions, échecs, déconnexions, changements de mot de passe et exports. Les mots de passe n'y figurent jamais. |
| `app/utils/permissions.py` | `@profil_requis(...)` et `filtre_perimetre(requete)`. ADMIN et DGE voient tout ; les autres profils ne voient que leurs provinces, et rien s'ils n'en ont aucune. |
| `app/utils/dates.py` | Dates enregistrées en UTC, affichées à l'heure du Gabon. |
| `app/routes/*.py`, `app/templates/**` | Écrans : connexion, mot de passe, accueil, utilisateurs, provinces et localités, listes, paramètres, journal. |
| `app/static/css/perform.css` | Charte de YL.1 regroupée dans un seul fichier, toutes les couleurs dans `:root`. |
| `app/static/vendor`, `app/static/polices` | Bootstrap 5.3.3, Bootstrap Icons 1.11.3, SortableJS 1.15.0, Space Grotesk et JetBrains Mono, tous en local. |
| `migrations/versions/0001_lot_0_socle.py` | Crée les tables, les 9 provinces, les 2 paramètres, et des déclencheurs qui interdisent de modifier ou d'effacer le journal (PostgreSQL et SQLite). |
| `tests/` | 77 tests automatiques (détail en § 6). |

Le journal est protégé à trois niveaux :
1. aucun écran ne permet de le modifier ;
2. l'application refuse toute modification ;
3. la base de données elle-même refuse UPDATE, DELETE et TRUNCATE.

## 2. Ce qui a été repris de PERFORM YL.1

**Code (adapté) :**
- structure de l'application ;
- connexion, avec le contrôle de la page de retour (`next`) ;
- protection CSRF et message « session expirée » ;
- écran et fonctionnement des listes : ajouter, modifier, activer / désactiver, supprimer, glisser-déposer pour l'ordre ;
- pastilles (`_macros.html`) ;
- principe de la numérotation.

**Charte, à l'identique :**
- bandeau kente (gardé tel quel sur chaque écran) ;
- barre du haut, en-tête de page avec icône, messages ;
- tableaux, badges, boutons, fenêtres, formulaires, filtres ;
- tuiles en dégradé et onglets de l'accueil ;
- carte de connexion.

Les couleurs écrites en dur dans YL.1 sont devenues des variables, avec la même valeur. Un test vérifie qu'aucune couleur n'a été inventée. Un autre vérifie qu'aucune couleur n'est écrite hors de `:root`. Seules les transparences (ombres, voiles blancs) restent écrites en place.

**Changements de nom et d'emplacement du logo :**
- le nom affiché est « KIMBA » ;
- le texte « KIMBA » remplace l'image du logo, au même emplacement et avec la même ombre.

**Corrigé au passage :**
- déconnexion par un bouton (POST) au lieu d'un lien ;
- cookies protégés ;
- dates en UTC ;
- plus de mot de passe admin écrit dans le code.

**Non repris :** tout ce qui concerne les DAB, et les rôles de YL.1.

## 3. Lancer l'application en local

Voir `README.md`. En bref, dans PowerShell, depuis `Desktop\KIMBA\kimba` :

```powershell
copy .env.exemple .env          # puis remplacer SECRET_KEY par une longue chaîne
venv\Scripts\flask db upgrade
venv\Scripts\flask init-kimba   # noter le mot de passe affiché
venv\Scripts\python kimba.py
```

Ouvrir ensuite <http://localhost:5020>. L'environnement `venv` est déjà installé sur ce poste.

## 4. Tests à faire vous-même, écran par écran

**Préparation :** connectez-vous en `admin` et créez deux comptes (test 4) :
- `agent.est` : profil *Agent technique*, province *Estuaire* ;
- `agent.hog` : profil *Agent technique*, province *Haut-Ogooué*.

Ajoutez ensuite deux localités (test 5) : *Libreville* dans l'Estuaire et *Franceville* dans le Haut-Ogooué.

### Test 1 — Connexion
- Saisissez un mauvais mot de passe. Résultat attendu : « Identifiant ou mot de passe incorrect. »
- Saisissez `admin` et le bon mot de passe. Vous arrivez sur « Changer mon mot de passe », avec le message « Pour continuer, choisissez votre propre mot de passe ».
- Essayez d'aller à l'adresse `/` : vous revenez sur cet écran.

### Test 2 — Changer le mot de passe
- Saisissez un nouveau mot de passe de moins de 10 caractères : refus, avec le message « au moins 10 caractères ».
- Saisissez une confirmation différente : refus.
- Saisissez un nouveau mot de passe correct : vous arrivez sur l'accueil avec « Votre mot de passe a été changé ».
- Plus tard, la clé 🔑 de la barre du haut ramène à cet écran.

### Test 3 — Accueil
- Vous voyez « Bonjour, … », votre profil, la date et l'onglet *Mon espace* (zone « en construction » et encadré des provinces).
- Pour l'ADMIN : l'onglet *Administration* contient 4 tuiles (Utilisateurs, Provinces et localités, Paramètres, Journal des opérations).

### Test 4 — Utilisateurs (Accueil → Administration → Utilisateurs)
- Cliquez sur « + Nouvel utilisateur », remplissez la fenêtre, puis cliquez sur Enregistrer. Le message « Compte … créé » s'affiche (3 clics).
- Choisissez *DGE* comme profil : la liste des provinces disparaît (« Ce profil voit toutes les provinces »).
- Créez un *Agent* sans province : refus avec « Cochez au moins une province ».
- Cliquez sur ✏️ d'un compte, décochez « Compte actif », puis enregistrez. Le compte passe en « Désactivé » (filtre *Comptes : Désactivés*) et la personne ne peut plus se connecter.
- Essayez de désactiver votre propre compte : refus.
- Remplissez « Nouveau mot de passe provisoire » sur un compte : à sa connexion suivante, la personne doit le changer.

### Test 5 — Provinces et localités (Administration → Provinces et localités)
- Les 9 provinces apparaissent avec leurs codes : EST, HOG, MOG, NGO, NYA, OGI, OGL, OGM, WNT.
- Cliquez sur une province : ses localités s'affichent à droite.
- Cliquez sur « + Nouvelle localité », saisissez un nom, puis enregistrez.
- Saisissez de nouveau le même nom : refus avec « existe déjà ».
- Cliquez sur ✏️ d'une localité pour la renommer ou la désactiver.

### Test 6 — Paramètres (Administration → Paramètres)
- Deux réglages s'affichent, en mots simples.
- Cliquez sur ✏️ de « Nombre minimal de caractères », saisissez « douze » : refus avec « Un nombre entier est attendu ».
- Saisissez 12 : la valeur est enregistrée, avec la date et votre nom.

### Test 7 — Journal (Administration → Journal des opérations)
- Vous retrouvez vos connexions, l'échec de connexion du test 1, les comptes et localités créés.
- Cliquez sur la ligne de modification d'un compte : le détail montre « Avant » et « Après », champ par champ. Le mot de passe s'affiche en « *** ».
- Filtrez par date, personne, élément ou action.
- Cliquez sur « Exporter (CSV) » : un fichier s'ouvre dans Excel avec les accents corrects, et une ligne « Export » apparaît en tête du journal.
- Aucun bouton ne permet de modifier ou de supprimer une ligne.

### Test 8 — CLOISONNEMENT entre deux provinces
1. Déconnectez-vous (bouton ⎋), puis connectez-vous en `agent.est`. Dans l'encadré « Mon périmètre », vous ne voyez que l'**Estuaire** et Libreville. Ni le Haut-Ogooué ni Franceville n'apparaissent.
2. Déconnectez-vous, puis connectez-vous en `agent.hog`. Vous ne voyez que le **Haut-Ogooué** et Franceville.
3. Toujours en `agent.hog`, ouvrez l'adresse `localhost:5020/administration/utilisateurs/` : page « Vous n'avez pas accès à cette page ».
4. Il n'y a pas d'onglet Administration ni de tuile Journal pour un agent.
5. Reconnectez-vous en `admin` : l'encadré s'intitule « Toutes les provinces » et montre les 9 provinces.

### Test 9 — Auditeur
- Créez un compte au profil *Auditeur (ANINF)*.
- Connecté avec ce compte, l'accueil montre la tuile « Journal des opérations » : la consultation et l'export fonctionnent, mais il n'y a pas d'administration.

### Test 10 — Comparaison visuelle avec YL.1
Ouvrez YL.1 et KIMBA côte à côte (YL.1 sur `localhost:5010` ou sur le serveur).

| À comparer | Résultat attendu |
|---|---|
| Écran de connexion | Même dégradé bleu, même carte, même bouton « Se connecter », même pied de page. Seuls le nom et le texte du logo changent. |
| Accueil | Même barre du haut (« Quitter » en rouge), même salutation, mêmes onglets, mêmes tuiles en dégradé (navy, cobalt, bleu, ambre). |
| Écran Utilisateurs de KIMBA face à « Suivi DI/OT » ou « Comptes » de YL.1 | Même bandeau kente, même barre du haut, même en-tête avec icône carrée, même barre de filtres, mêmes en-têtes de tableau bleu nuit, même bouton « + NOUVEAU… », mêmes ✏️. |
| Fenêtres | Même en-tête bleu nuit, mêmes boutons Annuler / ENREGISTRER. |
| Téléphone | Ouvrez KIMBA sur un téléphone (ou réduisez la fenêtre) : pas de défilement horizontal de la page, et les tableaux défilent à l'intérieur de leur cadre comme dans YL.1. |

## 5. Points d'attention

- **Listes configurables** : comme dans YL.1, les catégories sont écrites dans le code. Le lot 0 n'en contient aucune, donc la tuile *Listes* n'apparaît pas encore (pas de tuile inutile). L'écran existe et a été testé automatiquement avec une liste d'essai ; la tuile apparaîtra avec la première liste du lot 1.
- **Logo** : « KIMBA » apparaît deux fois côte à côte, une fois à la place du logo et une fois comme nom. C'est ce que vous avez demandé ; cela disparaîtra avec le vrai logo.
- **Déploiement en HTTP simple sur le port 5020** : sans HTTPS, les mots de passe circulent en clair sur le réseau. Les cookies « sécurisés » sont donc désactivés par défaut (`COOKIE_SECURE=0`), sinon la connexion ne marcherait pas en HTTP.

## 6. Tests automatiques

`venv\Scripts\python -m pytest -q` donne **77 réussis** (environ 2 minutes). Ils couvrent :
- la connexion, les échecs et la première connexion ;
- la fin de session et la déconnexion en POST ;
- les droits de chaque profil et le cloisonnement ;
- le journal : avant / après, annulation de transaction, refus de modification, export ;
- la numérotation et le mixin hors ligne ;
- les écrans d'administration ;
- la migration : base vide, provinces, déclencheurs, concordance avec les modèles ;
- la charte : aucun lien vers un CDN, aucune couleur hors de `:root`, uniquement des couleurs de YL.1.

J'ai aussi ouvert chaque écran dans un vrai navigateur, au format ordinateur et au format téléphone (390 px) : aucune ressource manquante et aucun débordement de page.

## 7. Options proposées (non codées)

1. **HTTPS** pour KIMBA, avec un nom de domaine et nginx devant le port 5020. Cela permettrait ensuite `COOKIE_SECURE=1`.
2. **Blocage temporaire après plusieurs échecs de connexion**, par exemple 5 échecs donnent 15 minutes d'attente, contre les essais de mots de passe en série.
3. **Sauvegarde automatique chiffrée** de la base `kimba`, sur le modèle de celle de PERFORM YL.
4. **Libellés dans le détail du journal** : afficher « Agent technique » au lieu de « AGENT », et le nom de la province au lieu de son numéro.
