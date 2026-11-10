# Lot C — indicateurs

- **C1** Mortalité et viabilité à 5 niveaux (national → province → cohorte → ferme → bande), un clic pour descendre
  d'un niveau : `/indicateurs/niveaux` (tuile « Indicateurs d'élevage » du pilotage ; pas pour l'éleveur).
- **C2** Participation à l'objectif national à chaque niveau : poids vif 12 mois, équivalent carcasse, cible,
  atteinte, part nationale (calculs du lot A3 réutilisés).
- **C3** « Mes indicateurs » par profil (5 à 8, dont 3 courbes hebdomadaires sur 52 semaines, SVG local, trou =
  pas de donnée) : éleveur, agent, vétérinaire (sans donnée financière), DGE, administrateur. Téléphone : lien dans
  « Moi » (tuiles inchangées) ; pilotage : tuile « Mes indicateurs ».
- Formules uniquement dans `app/indicateurs.py` ; choix par profil dans `app/services/mes_indicateurs.py`.
- Tests : `tests/test_lotC.py` (13) ; captures `docs/captures/lotC/`.
- Note : sur la démo, les courbes n'ont que les dernières semaines (données rechargées aux dates du jour).

## À tester
- **Téléphone, `eleveur` et `agent.est`** : Moi → « 📈 Mes indicateurs ».
- **Ordinateur, `dge`** : tuile « Mes indicateurs » ; tuile « Indicateurs d'élevage » → cliquer Estuaire → Cohorte →
  une ferme → ses bandes.
- **Ordinateur, `veto`** : « Mes indicateurs » sans aucun montant.
