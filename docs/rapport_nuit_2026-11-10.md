# Rapport de la nuit du 10/11/2026 (mode autonome)

## 1. Lots

| Lot | Commit de fusion | Déployé sur la démo | Version |
|---|---|---|---|
| A2 — catalogue, fournisseurs, origines | `85c4a9e` | oui | 2026-11-10-85c4a9e |
| A3 — programme POUFA, capacité, production, ponte | `fbf03ae` | oui | 2026-11-10-fbf03ae |
| E — carte, GPS, tournées (**partie a**) | `9a16679` | oui | 2026-11-10-9a16679 |
| C — indicateurs | **non commencé** (temps) | — | — |

- Chaque lot : suite complète verte avant la fusion (A2 : 463 tests, A3 : 477, E-a : 491).
- Les autres applications du VPS ont répondu avec les mêmes codes avant et après chaque déploiement.
- Aucune migration commitée n'a été modifiée ; aucune donnée supprimée.
- **Lot E livré en deux parties** (décision prise seul, faute de temps) : E-a cette nuit, **E-b reste à faire** :
  la punaise à glisser sur la carte (E4), la nouvelle ferme sans réseau avec numéro provisoire et doublon à moins de
  200 m (E8), les villes, les boutons + / − et le résumé de province au survol sur la carte (E10).
- **Lot C** : rien n'a été fait.

## 2. Décisions prises seul (détail : `docs/decisions_autonomes.md`)

Les plus importantes d'abord :
1. **Origine des utilisations déduite** (Programme d'abord, puis Externe), jamais demandée au terrain (A2).
2. **Écart d'inventaire sur le Programme** = livré Programme − utilisé Programme − (compté − stock Externe) (A2).
3. **Toutes les fermes existantes sont « au programme »** (elles viennent de la liste POUFA) (A3).
4. **Production réelle** = poids vif de toutes les sorties des bandes de chair sur 12 mois (A3).
5. **Lot E coupé en E-a / E-b** (E).
6. **Relevé GPS envoyé sans réseau et hors de la province** : gardé et marqué « à vérifier » (E).
7. **Correction de position à la main** : coordonnées tapées ; au-delà de 1 km, quatre yeux DGE (E).
8. **Itinéraire complet** : lien vers Google Maps, rien n'est chargé dans SORRA (E).
9. **DGE en écriture sur le catalogue** et l'agent en lecture (A2, texte du lot A).
10. **Page publique du QR** : localité et province, le référentiel n'a pas de département (E).

## 3. À tester (comptes de démo, mot de passe habituel)

### A2 — catalogue et fournisseurs
- **Ordinateur, `dge`** : Accueil → Catalogue des intrants : colonnes Conditionnement, Fournisseur, Référence ;
  « Fournisseurs » → fiche d'un fournisseur en fenêtre, « 🗄️ Archiver » puis « Archivés (1) » → « ↩️ Restaurer ».
- **Ordinateur, `dge`** : Fermes → EST-001 → Stock d'intrants : colonne « Programme · Externe ».
- **Téléphone, `eleveur`** : Mon stock → l'aliment croissance montre « il reste … de l'État · … à vous ».
- **Téléphone, `agent.est`** : Stock et commandes (EST-001) → « Programme N · Externe M ».

### A3 — programme, capacité, production, ponte
- **Ordinateur, `dge`** : Fermes → colonnes Cible, Produit 12 mois, Atteinte (pastilles) ; filtre « Hors programme (2) » ;
  « Nouvelle ferme » → fenêtre, « Membre du programme POUFA ? », taper 2 bâtiments × 1 000 places : la production
  théorique s'affiche en direct.
- **Ordinateur, `dge`** : Tableau de bord → « Production 12 mois » et « Atteinte de la cible (programme) » ; filtre programme.
- **Ordinateur, `admin`** : Bandes → HOG-001-B3-01 : « 🥚 Ponte · souche ISA Brown », croissance et IC « sans objet ».
- **Téléphone, `eleveur`** : Ma bande → Nouvelle bande (si des poussins attendent) : choix 🐔 Chair / 🥚 Ponte et souche.
- **Ordinateur, `dge`** : essayer une livraison de l'État pour HOG-002 (hors programme) : refusée.

### E — GPS et visites (partie a)
- **Téléphone, `agent.est`** (localisation autorisée) : Mes fermes → une ferme → « Relever la position ici » / « relever
  à nouveau » : la précision s'affiche (« ± 7 m ✓ »), « Garder cette position » ne s'active que sous ± 30 m.
  Essayer « ✏️ Corriger à la main » avec un motif.
- **Téléphone, `agent.est`** : Visite → « 📍 Vous êtes à … de la ferme » ; loin de la ferme, « Pourquoi si loin ? ».
- **Téléphone, `agent.est`** : Ma tournée → ordre par proximité et « 🗺️ Itinéraire complet ».
- **Téléphone, `eleveur`** : Moi → Mon compte : « 📍 Position relevée ✓ le … ».
- **Ordinateur, `dge`** : Carte → « Couleur : Mortalité / Régularité / Atteinte », survoler une ferme (infobulle),
  cliquer une province (zoom, numéros des fermes), « À localiser » et « Position à vérifier ».
- **Ordinateur, `dge`** : Agents → « Contrôle des visites » (filtres « Position éloignée », « Sans position », taux par agent).
- **Ordinateur, `dge`** : Fermes → EST-001 → « Positions (aucune n'est effacée) ».

## 4. Ce qui reste

- **E-b** : punaise à glisser, nouvelle ferme sans réseau (numéro provisoire, rattachement, doublon < 200 m), carte
  (villes, + / −, résumé de province au survol, biosécurité comme indicateur).
- **C** : tout le lot (mortalité et viabilité à 5 niveaux, participation à l'objectif, « Mes indicateurs » par profil
  avec courbes sur 52 semaines). Les calculs de production d'A3 (`app/indicateurs.py`) sont prêts à être réutilisés.
- **F** : saisie des œufs pour les bandes de ponte (la ponte est déjà distinguée depuis A3).
- **B, D** : leur contenu ne m'a pas été donné dans les consignes de cette nuit ; à préciser.
- Toujours en suspens depuis le lot A1 : création et modification d'une ferme et d'un opérateur restent des pages
  présentées en fenêtre (et non une fenêtre posée sur la liste) ; d'autres écrans à mettre à la règle des formulaires
  sont listés dans `docs/ergonomie.md`.
