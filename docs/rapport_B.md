# Lot B — Moteur générique d'imports Excel / CSV (reprise de l'existant)

- **Écran « ⬆️ Imports Excel / CSV »** (`/imports`, ADMIN et DGE ; tuile dans Paramètres) : 1. quoi importer (modèle), 2. le
  fichier (.xlsx ou .csv, séparateur détecté), 3. aperçu (20 premières lignes) avec la **correspondance des colonnes** proposée
  par le nom et **mémorisée** d'un import à l'autre (`correspondance_import`), 4. vérification ligne à ligne par les règles
  existantes (ferme / bande / bâtiment connus, périmètre, dates, catalogue), 5. import des lignes prêtes en **un lot**.
- **Modèles livrés** : bandes (reprise de l'historique → `ouvrir_rattrapage`, origine « reprise »), saisies du jour (morts,
  aliment), dépenses « J'ai payé ». Le modèle Excel de chaque import se télécharge.
- **Lot d'import** (`lot_import`, `ligne_import`) : qui, quand, fichier, lignes importées / refusées, rapport Excel ; **annulable**
  avec motif : tout ce que le lot a créé est archivé (jamais supprimé) ; tout au journal (IMPORT, ARCHIVAGE).
- L'import POUFA des fermes du lot 0 reste tel quel (Fermes → Import).
- Migration 0032 ; tests `tests/test_lotB.py` (4).

## À tester
- **Ordinateur, `admin`** : Paramètres → Imports Excel / CSV → modèle « Bandes » → télécharger, remplir 2 lignes (EST-001, B1…),
  déposer → aperçu → vérifier → importer → lot n° 1 → rapport Excel → Annuler le lot (motif) → les bandes sont archivées.
- `dge` : même chose avec un .csv de saisies ; `veto` / `agent` : accès refusé.

Déployé sur la démo : **oui** — version 2026-11-10-594f224.
