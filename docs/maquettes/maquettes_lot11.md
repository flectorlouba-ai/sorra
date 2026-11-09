# SORRA — Lot 11 : accueil en 8 tuiles + ventes et dépenses (« Mon argent »)

Référence : `docs/maquettes/maquette_sorra_8tuiles.html` **n'existe pas** dans le dépôt ; ce document suit la description du lot. Aperçu : `docs/maquettes/apercu_lot11.html`.

**Principe : on réorganise l'accès et on ajoute l'argent ; les écrans des lots 8 à 10 ne sont pas refaits.**

**Règle des clics (appliquée partout et dans les tests) :**
- **comptent** : ouvrir un écran, valider (Envoyer, Enregistrer, C'est fait, Tout reçu…) ;
- **ne comptent pas** : les choix dans le même écran (bâtiment, produit, signe, catégorie, type de sortie) et les + / − ;
- **maximum 3**.

---

## 1. Écrans

### A. En-tête de l'éleveur (toutes ses pages)

```
[🐔 SORRA            ]   [📞 Paul]  [👤 Moi]
[   Bonjour Jean ! 👋]
```

- **📞 {Prénom de l'agent}** : lien `tel:`, masqué si l'agent n'a pas de téléphone.
- **👤 Moi** : ouvre l'écran « Moi ».
- Les icônes actuelles 🔑 (mot de passe) et ⏻ (déconnexion) **quittent l'en-tête de l'éleveur** ; elles vont dans « Moi ». Les autres profils gardent leur en-tête.
- La tuile « Appeler mon agent » disparaît.

**Écran « Moi »** (`/moi`) :

| Élément | Contenu |
|---|---|
| Carte **Ma ferme** | nom, numéro, bâtiments (B1 · 1 200 places…), total des places. Elle **quitte « Mon stock »**. |
| 🔑 Mon compte | écran existant « Changer mon mot de passe » (le code PIN viendra au lot 14) |
| 🏦 Partage avec la BCEG | écran « Bientôt » (lot 13) |
| ❓ Comment faire ? | écran « Bientôt » (lot 13) |
| 🚪 Se déconnecter | bouton (formulaire POST existant) |

### B. Accueil : 8 tuiles, ordre fixe

Au-dessus, **inchangés** : bandeau orange des saisies en attente (lot 10), bandeau rouge, ligne d'état.

```
┌──────────────────────────────────────┐
│ ✏️ Saisie du jour            (2)     │  pleine largeur, verte
│ B1, B2 à faire · morts et aliment    │
└──────────────────────────────────────┘
  ⚖️ Pesée prévue dans B1 → Peser          raccourcis, seulement
  💉 Vaccin du jour → C'est fait           s'ils sont prévus aujourd'hui
┌─────────────────┐┌─────────────────┐
│ 🐔 Ma bande  (500)││ 🚚 Ventes et     │
│                  ││    sorties       │
├─────────────────┤├─────────────────┤
│ 💉 Vaccins et    ││ 🩺 Poulet malade │  (rose)
│    soins (auj.)  ││                  │
├─────────────────┤├─────────────────┤
│ 📦 Mes produits (1)││ 💰 Mon argent  │
└─────────────────┘└─────────────────┘
┌──────────────────────────────────────┐
│ 🔧 Entretien                  (6)    │  pleine largeur
└──────────────────────────────────────┘
```

| # | Tuile | Ouvre | Pastille |
|---|---|---|---|
| 1 | ✏️ Saisie du jour | écran « Saisie du jour » (lot 9) | bâtiments restant à saisir |
| 2 | 🐔 Ma bande | **nouvel écran de regroupement** | poussins en attente |
| 3 | 🚚 Ventes et sorties | **directement** l'écran Sortie (lot 3/9) | — |
| 4 | 💉 Vaccins et soins | **nouvel écran de regroupement** | aujourd'hui / demain / en retard |
| 5 | 🩺 Poulet malade (rose) | **directement** le signalement (lot 4/9) | — |
| 6 | 📦 Mes produits | **nouvel écran de regroupement** | livraisons à confirmer |
| 7 | 💰 Mon argent | **nouvel écran** | — |
| 8 | 🔧 Entretien (pleine largeur) | écran Entretien (lot 10), inchangé | tâches + pannes |

**Les 8 tuiles ne disparaissent plus.** Seule l'entrée « Nouvelle bande », à l'intérieur de « Ma bande », apparaît et disparaît.

**Raccourcis sous la Saisie du jour**, seulement s'ils sont prévus aujourd'hui (ou en retard) :
- « ⚖️ Pesée prévue dans B1 → Peser » : ouvre la pesée de cette bande ;
- « 💉 Vaccin du jour → C'est fait » : ouvre l'écran du vaccin (lot 4), où l'on touche « C'est fait ».

### Écran « 🐔 Ma bande » (`/ma-bande`)

Grosses cases :
- 🐣 **Nouvelle bande** (« 500 poussins en attente »), seulement si des poussins attendent et qu'un bâtiment est libre ;
- ⚖️ **Peser** : ouvre la pesée la plus proche (règle du lot 9, pastilles B1 / B2 pour changer) ;
- 📈 **Mes bandes** : page du lot 8, inchangée.

### Écran « 💉 Vaccins et soins » (`/vaccins-et-soins`)

- **En haut** : les vaccins du jour, en retard ou de demain, chacun avec « ✓ C'est fait ». Ce bouton ouvre l'écran du vaccin (lot 4), qui demande seulement de confirmer. Sinon : « Aucun vaccin à faire · prochain : Gumboro le 18/11 ».
- **Dessous** :
  - 💊 **Traitement** : écran « Enregistrer un traitement » existant, sur la bande la plus utile (pastilles B1 / B2) ;
  - 💬 **Mes signalements** : la page « Mes déclarations » du lot 8, **renommée**. La réponse du vétérinaire viendra au lot 12.

Cet écran remplace la petite page « vaccins à venir » du lot 9.

### Écran « 📦 Mes produits » (`/mes-produits`)

- **En haut** : les livraisons à confirmer, en cartes (partie existante de « Mes livraisons »), avec « ✓ Tout reçu » et « J'ai reçu moins ».
- **Dessous** :
  - 🛒 **J'ai acheté** (lot 9) ;
  - 🧺 **Mon stock** (lot 9, sans la carte « Ma ferme ») ;
  - 📦 **Mes livraisons** (lot 9).

### C. Ventes et sorties (écran Sortie complété)

- **Inchangé** :
  - le type en grosses cases (Abattoir · Vente · Autre), le destinataire, le nombre, le poids ;
  - « Il restera N poulets » ;
  - l'alerte du délai d'attente d'un traitement.
- **Ajouté pour Abattoir et Vente** : « Combien avez-vous reçu ? », montant total en FCFA, **facultatif**. Il est caché pour « Autre ».
- Un montant laissé vide apparaît « **à compléter** » dans « Mon argent ». Un toucher ouvre une petite page « Combien avez-vous reçu pour cette vente ? » → Enregistrer.

### D. Mon argent (`/mon-argent`)

```
 [ Ce mois ] [ Cette bande ] [ Tout ]        ← cases (ne comptent pas comme clic)
┌────────────┐┌────────────┐┌────────────┐
│  Gagné     ││  Dépensé   ││   Reste    │
│ 1 250 000  ││  480 000   ││  770 000   │
└────────────┘└────────────┘└────────────┘
 [        💸 J'ai payé        ]               ← bouton principal
 Derniers mouvements
  🚚 Vente · 120 poulets · 12/11 ............ + 600 000
  🚚 Abattoir · 80 poulets · 10/11 ...... à compléter →
  👷 Main-d'œuvre · B1 · 08/11 .............. − 50 000
  🛒 Aliment croissance · 07/11 ............. − 90 000
 (Aide de l'État : phrase, voir plus bas)
```

- **Gagné** : total des ventes et sorties à l'abattoir dont le montant est renseigné.
- **Dépensé** : achats personnels (« J'ai acheté », prix payé) + dépenses « J'ai payé ».
- **Reste** = Gagné − Dépensé. Il peut être négatif, affiché en rouge doux.
- **Période** :
  - Ce mois : par date ;
  - Cette bande : la part rattachée à la bande (règle ci-dessous). Avec plusieurs bandes en cours, des pastilles B1 / B2 permettent de choisir ; sans bande en cours, c'est la dernière bande terminée ;
  - Tout.

**« 💸 J'ai payé »** (`/j-ai-paye`) :
- catégorie en grosses images : 👷 Main-d'œuvre · ⚡ Électricité · ⛽ Carburant · 🚚 Transport · 💧 Eau · 🔧 Réparation · 📦 Autre ;
- montant en FCFA ;
- bâtiment, facultatif ;
- photo du reçu, facultative ;
- date : aujourd'hui par défaut, jusqu'à 3 jours en arrière (paramètre existant des achats) ;
- « Enregistrer », puis le bandeau « **Enregistré ✓ — Annuler (10)** ».
- Fonctionne sans réseau, comme les autres saisies.

**Bilan de fin de bande** (lot 8), 3 chiffres ajoutés : chiffre d'affaires, dépenses de la bande, marge.

**Aide de l'État** : une phrase, seulement si la valeur des livraisons de l'État est renseignée.
> « Sans l'aide de l'État, cette bande vous aurait coûté **X FCFA** de plus. »

Sinon rien.

### Règle de rattachement (à valider)

Une dépense, un achat ou une livraison de l'État rattaché à une bande compte dans « Cette bande », dans le bilan et dans l'aide de l'État.

1. **Avec un bâtiment** : la part va à la **bande en cours de ce bâtiment** à la date de la dépense.
2. **Sans bâtiment** : le montant est **réparti entre les bandes en cours de la ferme** à cette date, **au prorata des poulets présents**.
   - Exemple : 90 000 FCFA d'électricité le 12/11, B1 a 1 000 poulets et B2 500 → B1 60 000, B2 30 000.
   - Les arrondis sont faits pour que la somme retombe exactement sur le montant payé.
3. **Poussins** : des poussins achetés (ou livrés par l'État) vont **à la bande qui les a reçus**, jamais en partage. Le lien existe déjà depuis le lot 3.
4. **Aucune bande concernée** (vide sanitaire, ou aucune bande ce jour-là) : la dépense compte dans « Ce mois » et « Tout », mais **dans aucune bande**. Elle apparaît « hors bande » dans la liste.
5. La répartition est **recalculée à l'affichage** (une correction de l'agent se répercute partout), puis **figée dans le bilan** au moment de la clôture, comme les autres chiffres du bilan.

**Aide de l'État pour une bande** : pour chaque ligne de livraison de l'État rattachée (même règle), quantité reçue × valeur unitaire × part subventionnée. La phrase n'apparaît que si **toutes** les lignes subventionnées rattachées ont une valeur. Une phrase partielle serait fausse.

### Visibilité

| Profil | Ce qu'il voit |
|---|---|
| Éleveur | tout, pour ses fermes |
| Agent | carte « Argent de l'éleveur » sur la fiche de la ferme : les 3 totaux (Tout), les derniers mouvements, et « Corriger » (montant, catégorie, date) avec un motif inscrit au journal |
| ADMIN | comme l'agent |
| DGE | **totaux agrégés seulement**, dans le tableau de bord : par province, chiffre d'affaires, dépenses, nombre de fermes qui saisissent. Pas de détail par ferme |
| BCEG, VETO, autres | rien (accord BCEG au lot 13) |

---

## 2. Chemins de clics (vérifiés par tests de navigation)

| Action | Clics |
|---|---|
| Saisie du jour → Envoyer | 2 |
| Ventes et sorties → Enregistrer | 2 |
| Vaccins et soins → C'est fait | 2 (*) |
| Poulet malade → Envoyer | 2 |
| Mes produits → Tout reçu | 2 |
| Ma bande → Nouvelle bande → Commencer | 3 |
| Ma bande → Peser → Enregistrer | 3 |
| Mes produits → J'ai acheté → Enregistrer | 3 |
| Mon argent → J'ai payé → Enregistrer | 3 |
| Vaccins et soins → Traitement → Enregistrer | 3 |
| Entretien → Fait ✓ | 2 (inchangé) |
| 📞 Paul | 1 |
| 👤 Moi → Se déconnecter | 2 |

(*) Voir l'écart 3 : pour tenir en 2 clics, « ✓ C'est fait » valide **directement** depuis l'écran « Vaccins et soins ».

---

## 3. Tables et champs (migration 0013)

Noms pensés pour être repris tels quels par le futur module Économie.

| Table | Champ | Type | Rôle |
|---|---|---|---|
| **`depense`** (nouvelle, mixin terrain, périmètre ferme) | `ferme_id` | UUID | |
| | `batiment_id` | entier, facultatif | rattachement |
| | `categorie` | texte 60 | valeur de la liste `categories_depenses` |
| | `montant_fcfa` | entier > 0 | |
| | `date` | date | |
| | `photo_recu` | texte, facultatif | même rangement que les reçus d'achat |
| | `saisi_par_agent` | booléen | |
| | `annule` | booléen | « Annuler (10) » → journal ANNULATION automatique |
| | `numero_metier` | DEP-AAAA-NNNNNN | numérotation existante |
| **`sortie`** | `montant_fcfa` | entier, facultatif | « Combien avez-vous reçu ? » |
| **`livraison`** | `batiment_id` | entier, facultatif | bâtiment d'un achat personnel (écart 7) |
| **`liste_deroulante`** | catégorie `categories_depenses` | 7 valeurs | gérée dans Configuration → Listes (ADMIN) |

- **Pas de table de répartition** : elle est calculée par une seule fonction (`app/services/argent.py`) et figée dans `bande.bilan` à la clôture. Le module Économie pourra la stocker si besoin.
- **Corrections par l'agent** : elles passent par le journal existant (avant / après, motif).

---

## 4. Écarts et choix à valider

1. **Tuiles toujours visibles, même sans bande** : la tuile reste, mais son écran explique simplement (« Aucune bande en cours » + « 🐣 Nouvelle bande » si des poussins attendent).
   - Saisie du jour et Ventes et sorties ouvrent cette petite page.
   - Dans « Ma bande », l'entrée **Peser** disparaît aussi sans bande, comme « Nouvelle bande » sans poussins : pas de bouton inutile.
2. **En-tête** : 🔑 et ⏻ quittent l'en-tête de l'éleveur (ils sont dans « Moi »). Sinon, cela ferait 4 boutons sur 360 px.
3. **Vaccins et soins → C'est fait = 2 clics** : « ✓ C'est fait » enregistre **directement**, sans passer par l'écran du vaccin. Un bandeau « Fait ✓ — Annuler (10) » suit. L'écran du vaccin (lot 4) reste accessible en touchant le nom du vaccin, par exemple pour l'agent.
   - Le raccourci de l'accueil « 💉 Vaccin du jour → C'est fait » fait de même : **1 clic**.
   - Les vaccins « de demain » sont affichés **sans** bouton (on ne valide pas à l'avance).
4. **Raccourci pesée** : il ouvre la pesée (2 clics : raccourci, Enregistrer).
5. **Mes produits → Tout reçu = 2 clics** : les cartes à confirmer et leur bouton « ✓ Tout reçu » sont repris de « Mes livraisons ». Après validation, retour sur « Mes produits » avec le bandeau « Annuler (10) » du lot 2.
6. **Ventes et sorties avec plusieurs bandes** : ouvre la bande la plus âgée, avec pastilles B1 / B2 (règle du lot 9).
7. **Bâtiment facultatif ajouté à « J'ai acheté »** : la règle de rattachement parle d'« un achat avec bâtiment ». Sans ce champ, tous les achats seraient répartis. Les poussins n'ont pas besoin de ce champ (règle 3).
8. **Compléter le prix d'une vente** : l'éleveur peut ajouter le montant **une fois**, tant qu'il est vide. Ensuite, seul l'agent corrige, avec motif. Pas de « à compléter » sur les achats sans prix (non demandé : proposé en option).
9. **Catégories de dépenses** : liste déroulante existante `categories_depenses`, gérée par l'ADMIN dans Configuration → Listes. L'image est l'émoji en tête de la valeur (« 👷 Main-d'œuvre »). Une catégorie ajoutée sans émoji prend 📦. Une catégorie désactivée reste sur les anciennes dépenses.
10. **« Hors bande »** : une dépense sans bande concernée n'est rattachée à aucune bande (règle 4). On ne la reporte pas sur la bande suivante.
11. **Aide de l'État** : la phrase n'apparaît que si **toutes** les lignes subventionnées rattachées ont une valeur. Elle s'affiche dans le bilan et dans « Mon argent » → Cette bande.
12. **L'agent ne saisit pas « J'ai payé » pour l'éleveur** (non demandé). Il lit et corrige.
13. **DGE** : un bloc « Argent des éleveurs » dans le tableau de bord, par province : chiffre d'affaires, dépenses, fermes qui saisissent.
    - Une province de moins de 3 fermes qui saisissent affiche « — », pour qu'on ne puisse pas deviner une ferme.
    - L'ADMIN voit la carte de la fiche ferme comme l'agent.
14. **« Mes déclarations » renommée « Mes signalements »** partout chez l'éleveur (titre, lien). Le nom technique de la page ne change pas.
15. **Ordre fixe** : le test `test_ordre_des_tuiles_fixe` est réécrit pour les 8 tuiles. Les anciennes clés (livraisons, peser, sortie, achat, bandes, stock, agent) disparaissent de l'accueil.
