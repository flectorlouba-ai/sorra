# SORRA — démarrage

Application web de suivi technico-économique et de traçabilité des fermes avicoles
du Gabon (programme POUFA). Ce dépôt contient le **lot 0 : socle technique**.

## Lancer SORRA sur votre poste (Windows)

Dans PowerShell, depuis le dossier du dépôt :

```powershell
# 1. Environnement Python (une seule fois)
python -m venv venv
venv\Scripts\pip install -r requirements.txt

# 2. Réglages : copier le modèle puis remplir SECRET_KEY
copy .env.exemple .env
#    (sans DATABASE_URL, la base est le fichier performyl2_dev.db, créé à l'étape 3)

# 3. Créer la base et le compte administrateur (une seule fois)
venv\Scripts\flask db upgrade
venv\Scripts\flask init-yl2
#    → note le mot de passe affiché : il ne sera plus montré

# 4. Démarrer
venv\Scripts\python performyl2.py
```

Ouvrir ensuite <http://localhost:5020>, se connecter avec `admin` et le mot de passe
affiché à l'étape 3. SORRA demande aussitôt d'en choisir un nouveau.

## Commandes utiles

| Commande | Rôle |
|---|---|
| `venv\Scripts\flask db upgrade` | Met la base à jour (à faire après chaque nouveau lot) |
| `venv\Scripts\flask init-yl2` | Crée le compte `admin` s'il n'existe pas |
| `venv\Scripts\python -m pytest -q` | Lance les tests automatiques (≈ 2 min) |

## Production (PostgreSQL)

Dans le `.env` du serveur :

```
YL2_ENV=production
SECRET_KEY=<longue chaîne aléatoire>
DATABASE_URL=postgresql+psycopg2://performyl2:<mot de passe>@127.0.0.1:5432/performyl2
```

Puis `flask db upgrade`, `flask init-yl2`, et lancement par gunicorn derrière nginx.
Installation réelle sur le VPS (port public 5021, le 5020 étant pris par EPIKAÏZO),
commandes de redémarrage, journaux, sauvegarde et restauration : voir
[`docs/exploitation.md`](docs/exploitation.md). Fichiers serveur : dossier `deploiement/`.

## Organisation

```
performyl2.py         point d'entrée (flask --app performyl2, gunicorn performyl2:app)
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

## Données géographiques (contours des provinces)

`app/data/provinces_gabon.json` sert au contrôle « position hors province » et au petit
dessin de la province sur la fiche d'une ferme. Aucun service extérieur n'est appelé.

- **Source** : geoBoundaries, jeu « gbHumanitarian » GAB ADM1, issu de *Second
  Administrative Level Boundaries* (SALB) des Nations unies, diffusé sur HDX
  (<https://www.geoboundaries.org>).
- **Licence** : Creative Commons Attribution 3.0 IGO (CC BY 3.0 IGO) — réutilisation libre
  à condition de citer la source.
- Contours simplifiés à environ 500 m par `outils/construire_contours.py`.
- Tolérance du contrôle : 5 km (`app/services/geo.py`).

## Règles pour les lots suivants

**Avant tout lot : relire et appliquer [`docs/ergonomie.md`](docs/ergonomie.md).**

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
