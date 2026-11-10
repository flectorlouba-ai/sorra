# Lot A2 — Catalogue des intrants et fournisseurs (maquette, mode autonome)

## Tables
- **fournisseur** (nouvelle) : nom, téléphone, ville, type (Aliment · Couvoir · Pharmacie vétérinaire · Matériel · Autre), actif + archivage (lot A1).
- **produit** = l'article du catalogue, enrichi : `reference` (facultative), `fournisseur_id` (facultatif : « fournisseur à préciser »), `conditionnement` (ex. « sac de 50 kg », « flacon de 1 000 doses »). Nouveau type **Matériel**.
- **inventaire_stock** : `externe` (stock Externe théorique au moment du comptage) pour que l'écart porte sur le Programme seulement.
- Aucune colonne supprimée ni renommée ; aucune donnée modifiée par la migration.

## Origine Programme / Externe
- Entrées : `livraison.origine` ETAT = **Programme** (livraisons de l'État), ACHAT = **Externe** (achats de l'éleveur). Seuls les libellés changent.
- Utilisations (aliment du jour, poussins mis en bande, vaccins, traitements) : **imputées d'abord sur le stock Programme, puis sur l'Externe** (point 2 validé). L'origine est calculée, jamais demandée au terrain ; elle s'affiche sur le stock et les inventaires.
- Commandes de l'agent : toujours Programme (commandes à l'État) — affiché « Programme ».
- **Stock par article ET par origine** : `intrants.stock_ferme` rend pour chaque article le stock Programme, le stock Externe et le total.
- **Écart (fonction 19)** = Programme livré − Programme utilisé − Programme compté, où Programme compté = compté − stock Externe théorique. Le pourcentage se calcule sur le Programme livré.

## Écrans
- **Catalogue des intrants** (bureau, ADMIN et DGE ; lecture pour l'agent) : tableau (article, type, conditionnement, fournisseur ou « fournisseur à préciser », référence), filtre type, « En service / Archivés (n) », « ＋ Nouvel article » et fiche en fenêtre au centre ; « 🗄️ Archiver » / « ↩️ Restaurer ».
- **Fournisseurs** (bureau, mêmes droits) : tableau (nom, type, ville, téléphone, nombre d'articles), « ＋ Nouveau fournisseur », fiche en fenêtre, archivage.
- **Stock** (éleveur, agent) : chaque article montre « Programme N · Externe M ».
- **Inventaire** (agent) : écart sur le Programme, avec rappel du stock Externe.
- **Saisie du jour** : déjà conforme (articles d'aliment en stock ; « Comme hier » reprend l'article et la quantité, lot 12) — vérifié par un test.

## Écarts au texte
- L'origine des utilisations n'est pas stockée ligne par ligne : elle est déduite (Programme d'abord). Voir `docs/decisions_autonomes.md`.
