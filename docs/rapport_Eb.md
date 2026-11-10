# Lot E-b — fin du lot E (GPS)

- **Nouvelle ferme sans réseau** (agent) : « Nouvel éleveur » → « Enregistrer une nouvelle ferme » marche sans réseau ;
  numéro provisoire P-xxxx ; écran « Ferme en attente d'envoi » (compte à noter, visite, dépense) ; au retour du réseau
  le serveur donne le vrai numéro et rattache les saisies faites sur P-xxxx.
- **Doublon** : sur le téléphone (fermes de l'agent, 200 m : « 🤔 Une ferme existe déjà tout près… ») et sur le serveur
  (toutes les fermes → « À vérifier »).
- **Punaise à glisser** pour corriger une position (carte zoomée autour de la ferme, sans fond en ligne).
- Captures des maquettes renommées sans accents (un test lisait mal les noms accentués).
- Tests : `tests/test_lotEb.py` (8) ; suite complète verte.

## À tester
- **Téléphone, `agent.est`** : Nouvel éleveur → Enregistrer une nouvelle ferme ; essayer en mode avion : numéro
  P-xxxx, écran « Ferme en attente d'envoi », faire une visite ; remettre le réseau : la ferme reçoit son numéro EST-0xx
  et la visite y est rattachée.
- **Téléphone, `agent.est`** : une ferme → relever à nouveau → « ✏️ Corriger à la main » → glisser la punaise.

Déployé sur la démo : voir `docs/rapport_suite.md`.
