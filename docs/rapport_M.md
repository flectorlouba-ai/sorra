# Lot M — BCEG (fermes financées) et MAEDR (vue agrégée, visa de diffusion)

- **BCEG** : accueil (fermes financées, avec accord, bandes en cours, mortalité, recettes et bénéfice 12 mois ; carte ; courbes),
  écran « 🏘️ Fermes financées » (N°, ferme, province, accord, bande, effectif, mortalité, recettes / dépenses / bénéfice 12 mois,
  marge, bilan PDF). Le périmètre reste celui du lot 13 : une ferme financée **et** dont l'éleveur a donné son accord ; accord retiré
  = plus rien (bilan PDF refusé).
- **MAEDR** : accueil agrégé national (production / cible, atteinte, provinces, élevages, mortalité, rapports à viser), carte sans
  ferme nommée, tableau « Situation par province (agrégats) » ; écran « 📑 Rapports à viser ».
- **Visa de diffusion** : la DGE soumet un rapport national ou provincial (fiche du tableau Rapports : « Soumettre au visa MAEDR ») ;
  le MAEDR valide ou refuse avec motif (fiche « Viser ») ; colonnes « Diffusion » et « Validé MAEDR » du cahier remplies ; tout au
  journal (APPROBATION / REFUS). Migration 0033 (`rapport.diffusion, soumis_le/par, vise_le/par, motif_visa`).
- Tests : `tests/test_lotM.py` (3) ; l'écart justifié DGE 7 (Diffusion, Validé MAEDR) du lot K est levé.

## À tester
- **Ordinateur, `bceg`** : accueil → Fermes financées (vide tant qu'aucun éleveur n'a donné son accord ; `eleveur` → Moi → Ma banque
  → accord si sa ferme est financée via Fermes → Banque (BCEG)).
- **Ordinateur, `dge`** : Rapports → cliquer un rapport national → « Soumettre au visa MAEDR » ; compte MAEDR (à créer par `admin`) :
  Rapports à viser → Viser → valider / refuser.

Déployé sur la démo : **oui** — version 2026-11-10-2438f27.
