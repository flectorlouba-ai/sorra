# Lot D — bilan de bande, rapports standards, plans d'actions

- **Bilan de bande (PDF)** : produit et gardé à la clôture, et à la demande (téléphone : « 📄 Bilan de la bande » dans
  Mes bandes ; ordinateur : fiche de la bande). Identité, effectifs, indicateurs, pesées vs référence, intrants par
  article et origine, vaccins et traitements, sorties et lots, économie (jamais pour le vétérinaire), visites.
- **Rapports standards** : ferme (mensuel), agent (mensuel), national et provincial complétés (production vs objectif,
  atteinte par province et cohorte, actions). Produits le 1ᵉʳ du mois (commande `rapports-mensuels`) et à la demande ;
  liste « Rapports » (DGE, agent pour les siens) ; téléchargement et génération au journal.
- **Plans d'actions** : table `action` (origine, périmètre, responsable, échéance, priorité, avancement, état calculé,
  commentaire, photo), fonctionnalité « Plans d'actions » (DGE) avec fenêtre, « 🎯 Mes actions » sur l'accueil
  ordinateur de l'agent, « Créer une action » depuis une alerte, une visite, un arbitrage, un rapport ; action en retard
  signalée (pastille) ; tout au journal.
- Migration 0028 ; tests `tests/test_lotD.py` (8) ; captures `docs/captures/lotD/`.

## À tester
- **Ordinateur, `dge`** : Plans d'actions → « ＋ Nouvelle action » (confier à `agent.est`), puis Rapports →
  « ＋ Générer un rapport » (national, ferme EST-001) → PDF.
- **Ordinateur, `agent.est`** : l'accueil montre « 🎯 Mes actions » ; cliquer une ligne → avancement, « ✓ Marquer faite ».
- **Ordinateur, `admin`** : Bandes → une bande clôturée → « 📄 Bilan (PDF) ».
- **Téléphone, `eleveur`** : Mes bandes → « 📄 Bilan de la bande » sous une bande terminée.

Déployé sur la démo : voir `docs/rapport_suite.md`.
