# KIMBA — démarrage

Application web de suivi technico-économique et de traçabilité des fermes avicoles
du Gabon (programme POUFA). Ce dépôt contient le **lot 0 : socle technique**.

## Lancer KIMBA sur votre poste (Windows)

Dans PowerShell, depuis le dossier `kimba` :

```powershell
# 1. Environnement Python (une seule fois)
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 2. Réglages : copier le modèle puis remplir SECRET_KEY
copy .env.exemple .env
#    (sans DATABASE_URL, la base est le fichier kimba_dev.db, créé à l'étape 3)

# 3. Créer la base et le compte administrateur (une seule fois)
venv\Scripts\flask db upgrade
venv\Scripts\flask init-kimba
#    → note le mot de passe affiché : il ne sera plus montré

# 4. Démarrer
venv\Scripts\python kimba.py
```

Ouvrir ensuite <http://localhost:5020>, se connecter avec `admin` et le mot de passe
affiché à l'étape 3. KIMBA demande aussitôt d'en choisir un nouveau.

## Commandes utiles

| Commande | Rôle |
|---|---|
| `venv\Scripts\flask db upgrade` | Met la base à jour (à faire après chaque nouveau lot) |
| `venv\Scripts\flask init-kimba` | Crée le compte `admin` s'il n'existe pas |
| `venv\Scripts\python -m pytest -q` | Lance les tests automatiques (≈ 2 min) |

## Production (PostgreSQL)

Dans le `.env` du serveur :

```
KIMBA_ENV=production
SECRET_KEY=<longue chaîne aléatoire>
DATABASE_URL=postgresql+psycopg2://kimba:<mot de passe>@127.0.0.1:5432/kimba
```

Puis `flask db upgrade`, `flask init-kimba`, et lancement par gunicorn :
`gunicorn -w 3 -b 0.0.0.0:5020 kimba:app`.

## Organisation

```
kimba.py              point d'entrée (flask --app kimba, gunicorn kimba:app)
config.py             réglages lus dans le .env
app/
  models/             tables (base.py : mixin des futures saisies terrain)
  routes/             écrans
  services/           journal d'audit, numérotation, paramètres
  utils/              contrôle d'accès (profil_requis, filtre_perimetre), dates
  templates/          pages (charte PERFORM YL.1)
  static/css/perform.css   charte graphique — toutes les couleurs dans :root
  static/vendor/      Bootstrap 5.3.3, Bootstrap Icons 1.11.3, SortableJS (en local)
  static/polices/     Space Grotesk, JetBrains Mono (en local)
migrations/           migrations de la base (Flask-Migrate)
tests/                tests automatiques
```

## Règles pour les lots suivants

- Une table de saisie terrain hérite de `SaisieTerrainMixin` (identifiant UUID créé par
  l'application, numéro provisoire, appareil, état de synchronisation).
- Toute requête de données métier passe par `filtre_perimetre(...)` ; le modèle déclare
  `__perimetre__ = 'province_id'` (et `__perimetre_ferme__ = 'ferme_id'` à partir du lot 1).
- Les numéros se demandent à `generer_numero(type, prefixe)`.
- Le journal d'audit est automatique : rien à coder pour les créations, modifications
  et suppressions.
- Une nouvelle liste configurable = une ligne dans `CATEGORIES` (`app/routes/listes.py`).
- Toute modification de table = `flask db migrate -m "..."`, relire le fichier, puis
  `flask db upgrade`.
