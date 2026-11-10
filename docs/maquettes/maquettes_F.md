# Lot F — Suivi des œufs (bandes de ponte) : maquette

Référence : règles communes du cahier (style terrain, 3 clics, case vide ≠ zéro, hors ligne). Rien de l'existant ne change ;
tout s'ajoute et n'apparaît que pour une bande **PONTE** (lot A3).

## Téléphone (éleveur, agent qui saisit pour lui)
- **Saisie du jour** d'une bande de ponte : après « Morts », deux compteurs « 🥚 Œufs ramassés » et « Œufs cassés » (case
  vide refusée : « — » tant que rien n'est noté ; « ✓ Aucun œuf » met 0). Le reste (aliment, Envoyer ✓) est inchangé.
- **Carte de la bande** (Ma bande aujourd'hui) : « 🥚 taux de ponte 82 % · 12 plateaux en stock » quand la bande pond.
- **Écran « 🥚 Mes œufs »** (`/oeufs`, tuile ajoutée sous les tuiles existantes de l'accueil quand une bande de ponte est en
  cours) : stock en plateaux de 30 (« 12 plateaux + 7 œufs »), taux de ponte du jour et sur 7 jours, « ＋ J'ai vendu des œufs »
  (feuille : plateaux, œufs à l'unité, prix total, acheteur facultatif ; hors ligne), liste des ventes (fiche du lot A1 :
  modifier / archiver), « Réformer la bande » → clôture avec le motif « Réforme » (fenêtre existante).
- **Mon argent** : une vente d'œufs est une recette (« 🥚 Vente d'œufs · 12 plateaux ») ; le bilan PDF remplit la ligne
  « Ventes d'œufs ».

## Alerte de chute de ponte
- Moyenne des 7 derniers jours comparée aux 7 jours précédents : baisse ≥ `ponte.chute_pct` (15 %, paramètre sensible,
  quatre yeux) → raison d'alerte « chute de ponte » (accueil éleveur, fiche ferme de l'agent, carte et liste « Fermes en
  alerte » du bureau), et notification 🔴 à l'agent (type feu rouge, non désactivable).
- `ponte.oeufs_par_plateau` = 30 (paramètre).

## Ordinateur
- La fiche d'une bande de ponte montre la courbe du taux de ponte (SVG existant) et le stock d'œufs ; le tableau
  « Mes bandes » du cahier garde ses colonnes (IC « sans objet » pour la ponte).
