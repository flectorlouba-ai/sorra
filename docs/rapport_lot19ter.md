# SORRA — Rapport du lot 19 ter : espace terrain (agent et opérateur au style de l'éleveur)

Maquettes validées le 09/11/2026, avec deux précisions :
- écart 1 : deux choix pour le nouvel éleveur, « Ferme déjà enregistrée » ou « Nouvelle ferme » (avec du réseau seulement, et le téléphone le dit) ;
- écart 6 : un paramètre « Téléphone de contact DGE ».

Branche `espace-terrain`, migration 0022 (**données seulement** : aucune table modifiée).

**Ce lot ne change que la présentation.** Les règles, services, contrôles, hors ligne et journal des lots 12 à 19 sont inchangés. Seuls quelques retours d'écran ont été ajoutés : après un compte rendu, un comptage ou une commande, l'agent revient à son écran terrain.

## 1. Base commune « terrain » (extraite, pas copiée)

- **La feuille.** `eleveur.css` devient `terrain.css` (git mv) : mêmes règles, sous la classe `theme-terrain`. Les couleurs restent dans le seul `:root` ; le test existant le vérifie.
- **L'en-tête.** Deux variables, `--t-entete-debut` et `--t-entete-fin` : bleu par défaut, vert pour `.terrain-operateur` (`#2fa36b` → `#1f7a4f`).
- **Les fêtes.** Elles restent à l'éleveur seul, sous `theme-eleveur` : le chiffre qui rebondit, « Bien reçu ! », les étincelles et `eleveur.js`. L'agent et l'opérateur n'en ont aucune ; un test le vérifie.
- **Les briques communes.** Macros `terrain/_macros.html` (tuile, ligne d'état) et en-tête `terrain/_entete.html`. L'accueil de l'éleveur utilise la même macro de tuile, avec le même HTML qu'avant.
- **Présentation et aides.** La présentation au premier lancement (une fois par compte, sur le serveur) et « Comment faire ? » reprennent le mécanisme du lot 13. Les textes sont propres à chaque profil (aides `ag_…` et `op_…`) et listés dans `docs/a_faire_valider.md`.
- **Qui a quel style.** C'est décidé à un seul endroit, `app/utils/terrain.py` : TERRAIN pour l'éleveur, l'agent et l'opérateur ; BUREAU pour tous les autres. Le vétérinaire reste en bureau.

**L'éleveur ne voit aucun changement.** Ses 20 écrans de référence ont été capturés à 360 px, animations coupées, sur `main` avant le lot puis sur la branche après :
- **les 20 sont identiques au pixel** ;
- deux passages successifs sur `main` avaient aussi donné des images identiques : la méthode est fiable ;
- trois paires sont gardées dans `docs/captures/lot19ter/` (fichiers `40_…` pour avant, `41_…` pour après).

## 2. Agent

- **Accueil.** En-tête « Bonjour Paul · Estuaire · 3 fermes », 🔔 et 👤 Moi. Sous les tuiles, l'encadré « 🔔 Alertes » reprend **les mêmes alertes que l'accueil de pilotage** : feux, livraisons non confirmées, pannes, vaccins en retard, visites prévues, saisies à vérifier. Rien n'est perdu ; le 🔔 en donne le nombre et y mène. La ligne d'état montre 2 alertes au plus, puis « 📶 Tout est envoyé ✓ » (ou « ◷ N saisies en attente », lu sur le téléphone). Ensuite, les 8 tuiles dans un ordre fixe.
- **Ma tournée.** Une petite carte avec les points numérotés, puis une carte par ferme : la raison en phrase, la distance (calculée par le téléphone, rien n'est enregistré) et « À faire ». Le bouton « 🧭 Y aller » ouvre l'application de cartes du téléphone (lien `geo:`). Sans réseau, la page affiche « 📶 Gardée sur le téléphone à 7 h 12 ».
- **Mes fermes, fiche.** Liste par urgence. La fiche montre la situation en une carte (feu, bâtiment, jour, poulets, blocage du vétérinaire), puis 4 tuiles, puis la position, la BCEG, la dernière visite, et 📞 l'éleveur. Le prénom affiché vient du compte de l'éleveur, sinon du nom de l'exploitant.
- **Saisir pour un éleveur.** On choisit la ferme (celles de la tournée d'abord, puis « Autre… » avec recherche) et le bâtiment, puis une des 4 tuiles. Elles ouvrent **les mêmes écrans que l'éleveur** : même formulaire, « — », « Aucun mort », « Comme hier ». La mention « saisi par » est conservée (journal POUR_ELEVEUR, testé).
- **Visite.** Une seule page :
  - les fermes en pastilles en haut ;
  - « Position relevée ✓ » (la distance à la ferme viendra avec le lot GPS) ;
  - « Pourquoi cette visite ? » ;
  - « Ce que vous avez vu » ;
  - les conseils en grosses cases ;
  - la carte « 🛡️ Biosécurité — 10 questions » (le vrai nombre de la grille) ;
  - la photo ;
  - « Envoyer le compte rendu ».

  Elle marche sans réseau, comme avant.
- **À vérifier.**
  - Une carte par cas, avec les deux versions en gros (« compte en attendant » / « gardée de côté »).
  - « Quelle version garder ? », puis « Pourquoi ? », avec les raisons de la liste réglable `motifs_verification` ; « Autre… » demande un texte.
  - Même règle et même journal qu'au lot 12.
  - Les écarts de réception du lot 19 y apparaissent, avec « Vu ✓ ».
- **Stock et commandes.** Une carte par intrant : « Reçu · Utilisé · Reste » et « 🟠 N sacs manquent » ou « ✓ ça correspond », sans pourcentage. On y trouve aussi « Compter » (dans la carte), les livraisons à confirmer (« ✓ Tout reçu » / « J'ai reçu moins ») et la commande avec son état en phrase.
- **Nouvel éleveur.** Deux choix :
  - « Ferme déjà enregistrée » : sans réseau possible, en 3 étapes dans le même écran avec une barre de progression (la personne, la ferme, le compte) ;
  - « Nouvelle ferme » : « 📶 Avec du réseau seulement ». Le lien se grise sans réseau, et le formulaire de la ferme le redit.
- **Moi.**
  - Nom, profil, province, nombre de fermes.
  - 📞 la DGE : le paramètre `contact.telephone_dge`, sinon le premier compte DGE avec un téléphone, sinon rien.
  - Mes visites du mois, avec une barre.
  - Comment faire ?, Revoir la présentation, Mon compte.
  - **« 🖥️ Version bureau »**, sur un écran large seulement.
  - Me déconnecter, avec l'avertissement des saisies en attente.
- **Version bureau.** Elle ouvre l'accueil de pilotage existant et tous les écrans détaillés. Rien n'est supprimé. Les écrans de pilotage ouverts depuis le terrain (« Ses chiffres », fiche détaillée…) gardent toujours le style bureau.

## 3. Opérateur

- **En-tête vert** avec le nom de l'établissement.
- **Ligne d'état** : lots à revoir, écarts à expliquer, accord du vétérinaire, « 2 lots arrivent cette semaine », « 1 lot attend le vétérinaire », envoi.
- **Tuiles** : 📷 Recevoir un lot (grande) · 🚚 Lots qui arrivent · 📦 Mes réceptions · 👤 Moi · aide · mon compte.
- **Les écrans du lot 19 avec de nouveaux mots.** Mêmes contrôles, mêmes règles :
  - la caméra s'ouvre tout de suite, avec un cadre jaune ;
  - les contrôles sont écrits en phrases (« ✅ Bien envoyé à votre abattoir », « ✅ Pesés il y a 3 jours », « ❌ Médicament donné récemment — attendre jusqu'au 12 novembre ») ;
  - les 3 compteurs 🐔 💀 ⚖️ partent de « — » ;
  - en cas d'écart, « Il manque 15 poulets » s'affiche et le bouton devient « Valider avec cet écart » ;
  - en cas de refus, une seule phrase ;
  - un contrôle qui manque donne « ◷ Gardez ces poulets à part » et les boutons « Je les reçois et je les garde à part » / « Je refuse ce lot » ;
  - les états des réceptions sont des phrases.
- **Les mots « réserve », « bloquant » et « événement » n'apparaissent dans aucun texte visible** des écrans de l'opérateur, messages compris. Un test les cherche.
- **Ce qui ne change pas.** Le motif enregistré au journal et dans le journal des scans garde la phrase du lot 19, lue par la DGE et l'auditeur.

## 4. Écarts et décisions pendant la construction

1. **Six tests existants modifiés**, pour la présentation seulement. La règle testée est la même.
   - Les tests de l'accueil de pilotage de l'agent (ses tuiles, le badge de l'encadré « Alertes ») passent par sa « Version bureau » (`test_accueil.py`, `test_intrants.py`, `test_lot16.py`, et un cas de `test_eleveur.py`).
   - Les noms de fichier `eleveur.css` → `terrain.css` sont mis à jour (`test_eleveur.py`, `test_migration_et_charte.py`, `test_mise_a_jour.py`).
   - Les phrases attendues chez l'opérateur sont les nouvelles (`test_lot19.py`).
   - Le nombre de paramètres passe de 47 à 48 (`contact.telephone_dge`).
   - Les comptes AGENT et OPÉRATEUR des tests ont la présentation déjà vue, comme l'éleveur.
2. **Écrans de pilotage de l'agent** (fiche détaillée, tableaux, tournée du lot 16…) : toujours au style bureau (`ECRANS_BUREAU_AGENT`). Ils sont faits pour l'ordinateur et deviennent illisibles s'ils sont mal habillés en terrain.
3. **Contraste des boutons pleins.** Le vert (3,2) et le bleu (4,1), avec un texte blanc gras de 17 px, sont ceux de l'éleveur depuis le lot 13. Je ne les ai pas changés, puisque l'éleveur ne doit voir aucun changement. Point ajouté à `docs/a_faire_valider.md`.
4. **Défaut repéré chez l'éleveur, laissé tel quel.** Le titre « Sorties de cette bande » (lot 19) fait 11,5 px chez l'éleveur, sous les 12 px du lot 13. Je l'ai corrigé pour l'agent seulement. Pour l'éleveur, la correction est à faire au prochain lot, avec ton accord, puisqu'elle change son écran.
5. **« Partis ce matin 7 h 40 »** : c'est l'heure d'enregistrement de la sortie (validé). **« Y aller »** : un lien `geo:` (application de cartes du téléphone), car un lien vers un site de cartes est interdit par la règle « aucun CDN ».
6. **Les données de démonstration** contiennent la liste, le paramètre et les aides du lot 19 ter. Le chargement remplace ces tables, voir `docs/exploitation.md`.

## 5. Tests (`tests/test_lot19ter.py`, 15 tests)

| Exigence | Test |
|---|---|
| Style terrain pour les 3 profils, bureau pour les autres | `test_style_terrain_pour_les_trois_profils_bureau_pour_les_autres` |
| En-tête vert de l'opérateur, par variable | `test_entete_verte_pour_l_operateur_sans_copie` |
| Aucune fête pour l'agent et l'opérateur | `test_aucune_fete_pour_l_agent_et_l_operateur` |
| Éleveur inchangé | captures avant / après identiques au pixel (section 1) et tous ses tests existants |
| Accueil de l'agent : 8 tuiles, ligne d'état, aucune tuile morte | `test_accueil_de_l_agent_huit_tuiles_et_ligne_d_etat` |
| Tournée, fermes, fiche | `test_tournee_fermes_et_fiche` |
| « Saisir pour » : écrans de l'éleveur, mention « saisi par » | `test_saisir_pour_un_eleveur_utilise_les_ecrans_de_l_eleveur` |
| À vérifier : même règle, raisons, « Autre » | `test_a_verifier_au_style_terrain_meme_regle` |
| Stock en mots, sans pourcentage | `test_stock_en_mots_sans_pourcentage` |
| Nouvel éleveur : deux choix, réseau | `test_nouvel_eleveur_ferme_enregistree_ou_nouvelle_avec_reseau` |
| Version bureau, téléphone DGE | `test_moi_version_bureau_et_telephone_dge` |
| Présentation et aides propres à chaque profil | `test_presentation_et_aides_propres_a_chaque_profil` |
| Aucun mot technique chez l'opérateur | `test_aucun_mot_technique_chez_l_operateur` |
| Écrans de l'opérateur en phrases | `test_ecrans_de_l_operateur_en_phrases` |
| Cache hors ligne complet (agent, opérateur) | `test_toutes_les_pages_terrain_sont_gardees_sans_reseau` (×2) |

Suite complète (SQLite, 09/11/2026) : **433 réussis, 1 ignoré** (le test réservé à PostgreSQL), 12 min 19.

## 6. Captures (`docs/captures/lot19ter/`, 360 px)

- **Agent (01 à 17)** : présentation, accueil, tournée, mes fermes, fiche, saisir pour, saisie du jour (même écran que l'éleveur), visite, à vérifier, stock, nouvel éleveur et ses 3 étapes, Moi, Comment faire.
- **Opérateur (20 à 31)** : présentation, accueil vert, recevoir un lot, lot reconnu, écart, refus, lot inexistant, lots qui arrivent, mes réceptions, Moi, lot à garder à part et ses boutons.
- **Éleveur (40 à 41)** : avant / après, identiques au pixel.

## 7. Tes tests à la main (téléphone Android, Chrome, https://sorra.performyl.com)

1. **Agent, premier lancement.** Connecte-toi en `agent.est` : la présentation en 4 écrans doit s'afficher, puis l'accueil. Vérifie l'en-tête bleu, « Bonjour Paul · Estuaire · N fermes », le 🔔, et qu'il n'y a ni saut ni étincelle.
2. **Ma tournée.** Accepte la localisation : la distance s'affiche. Touche « 🧭 Y aller » : l'application de cartes s'ouvre.
3. **Saisir pour un éleveur.** Choisis EST-002, puis « 📝 Jour », puis « Aucun mort », un aliment, Envoyer. Vérifie que c'est l'écran de l'éleveur, en 3 touchers.
4. **Visite.** Coche des conseils, ajoute une photo, envoie. Puis recommence en mode avion : le compte rendu doit partir au retour du réseau.
5. **À vérifier.** Touche une version, une raison, puis Valider.
6. **Stock.** Choisis une ferme, « Compter », tape un nombre : « 🟠 N sacs manquent » ou « ✓ ça correspond » s'affiche.
7. **Nouvel éleveur.**
   - Ferme déjà enregistrée : fais les 3 étapes et note le mot de passe affiché.
   - En mode avion, la tuile « Nouvelle ferme » doit dire qu'il faut du réseau.
8. **Moi.** Sur le téléphone, « Version bureau » ne s'affiche pas. Sur un ordinateur, elle s'affiche, ouvre le pilotage, puis « Version terrain » ramène au terrain.
9. **Opérateur.** Connecte-toi en `abattoir.owendo` :
   - présentation, puis en-tête **vert** ;
   - « Recevoir un lot » : la caméra s'ouvre avec un cadre jaune ;
   - lot vert, puis écart (« Il manque … », « Valider avec cet écart ») ;
   - un lot déjà reçu : une seule phrase rouge.
10. **Sans réseau, opérateur.** Mode avion, scanne un lot qui arrive, enregistre. L'accueil doit afficher « ◷ Réception enregistrée, en attente de vérification ». Remets le réseau.
11. **Éleveur.** Connecte-toi en `eleveur` ou `marie.nze` : rien ne doit avoir changé.
12. **Installation.** Ajoute l'application à l'écran d'accueil depuis le compte agent, puis depuis le compte opérateur.
