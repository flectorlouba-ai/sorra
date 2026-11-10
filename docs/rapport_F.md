# Lot F — Suivi des œufs (bandes de ponte)

Rien de l'existant ne change : tout s'ajoute et n'apparaît que pour une bande **PONTE** (type du lot A3).

- **Saisie du jour** d'une bande de ponte : compteurs « 🥚 Œufs ramassés » (case vide refusée, « ✓ Aucun œuf » = 0) et « Œufs
  cassés », en plus des morts et de l'aliment (`saisie_jour.oeufs_ramasses / oeufs_casses`).
- **Stock en plateaux** de `ponte.oeufs_par_plateau` (30) : ramassés − cassés − vendus ; taux de ponte du jour et sur 7 jours.
- **🥚 Mes œufs** (`/oeufs`, tuile ajoutée sous les 8 tuiles quand une bande pond) : stock, taux, « ＋ J'ai vendu des œufs »
  (feuille, hors ligne ; plateaux + œufs à l'unité, prix, acheteur, jour), liste des ventes (fiche du lot A1 : modifier, archiver),
  « Réformer la bande » (clôture avec motif). Carte de la bande (saisie du jour) : taux de ponte et stock.
- **Mon argent** : une vente d'œufs est une recette (« 🥚 Vente d'œufs ») ; le bilan PDF remplit « Ventes d'œufs ».
- **Chute de ponte** : moyenne 7 jours contre 7 jours précédents, baisse ≥ `ponte.chute_pct` (15 %, quatre yeux) → raison
  d'alerte (accueils, carte, fiche ferme), encadré sur Mes œufs, notification immédiate à l'agent (type feu rouge).
- Table `vente_oeufs`, migration 0031 ; tests `tests/test_lotF.py` (5).

## À tester
- **Téléphone, `eleveur`** : il faut une bande de ponte (ouvrir une bande → « 🥚 Ponte ») : saisie du jour → compteurs d'œufs
  (case vide refusée) → tuile « 🥚 Mes œufs » → vendre 10 plateaux → Mon argent (recette) → fiche de la vente (modifier / archiver).
- **Ordinateur, `admin`** : Paramètres → `ponte.chute_pct` = proposition quatre yeux.
- Le jeu de démo n'a pas de bande de ponte : à ajouter dans `deploiement/demo/donnees_demo.json`.

Déployé sur la démo : voir `docs/rapport_suite.md`.
