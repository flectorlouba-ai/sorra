# SORRA — Rapport du lot 19 : opérateur (abattoir, marché) et traçabilité aval

Fonctions 58 (écart à la réception), 63 (contrôles automatiques), 65 (refus), 66 (indicateurs de traçabilité).
Maquettes validées le 09/11/2026, avec deux ajustements :
- écart : motifs à toucher, seul « Autre » demande un texte ;
- vaccins : une tolérance de 2 jours.

Branche `lot-19`, migration 0021. **Rien n'est déployé.**

## 1. Ce qui a été construit

### Opérateur (téléphone d'abord, charte YL.1)

**Compte.** Un compte OPÉRATEUR est rattaché à **une** fiche du registre des opérateurs. Côté données, c'est la colonne `utilisateur.operateur_id`. Côté écran, c'est le champ « Établissement » de l'écran Utilisateurs, obligatoire pour ce profil ; la province du compte est celle de l'établissement. `filtre_perimetre` a une branche OPÉRATEUR : le compte ne voit que les lots dont la sortie désigne sa fiche, ses réceptions et ses scans, rien d'autre.

**Accueil.** De haut en bas :
- une grande tuile **Scanner un lot** ;
- deux tuiles **Lots attendus** (avec compteur) et **Mes réceptions** ;
- un encadré **À traiter** : lots sous réserve, décisions du vétérinaire, réceptions refusées à la vérification, écarts à expliquer ;
- un encadré **Attendus cette semaine** : numéro, nombre, ferme, « parti le … · en route ».

**Scan.** La caméra utilise d'abord le lecteur intégré à Chrome Android. En secours, elle utilise jsQR 1.4.0 (licence Apache 2.0, copié dans `static/vendor/jsqr-1.4.0`, sans CDN, chargé seulement s'il le faut). On peut aussi taper le numéro du lot (« Chercher ce numéro »). Le QR imprimé contient une adresse `…/q/<code>` : le code est extrait de l'adresse.

**Résultat.** Trois issues :
- **vert** : « Valider la réception » ;
- **orange** : « Recevoir sous réserve » ou « Refuser le lot » ;
- **rouge** : gros écran avec le pourquoi en clair, et les boutons « 📞 Appeler l'agent de la ferme » (s'il a un téléphone) et « Scanner un autre lot ».

Chaque scan, accepté ou refusé, est inscrit :
- dans la table `scan` : qui, quand, opérateur, lot, empreinte du QR, caméra / numéro / sans réseau, résultat, motif ;
- au journal chaîné, sous l'action « Scan d'un lot à la réception ».

Le code du QR n'est jamais gardé en clair.

**Contrôles** (`app/services/receptions.py`), affichés en ✓ / ✗ dans cet ordre :
1. QR connu et jamais reçu ;
2. destiné à votre établissement ;
3. vaccins obligatoires faits ;
4. aucun traitement en délai d'attente ;
5. bande non bloquée par le vétérinaire ;
6. pesée récente.

Le caractère bloquant des contrôles 3, 4 et 6 est réglable : paramètres `reception.controle_*`, valeurs TOUS / ABATTOIR / INFO / NON, sous quatre yeux. Par défaut :
- délai d'attente : bloquant pour tous ;
- vaccins et pesée : bloquants à l'abattoir, pour information au marché, chez l'acheteur et le distributeur.

**Comptage.** Trois chiffres : vivants, morts à l'arrivée, poids total. Les cases sont vides au départ (« — ») et « 0 » doit être tapé, sur le téléphone comme sur le serveur.

**Écart** (fonction 58). Dès que les chiffres sont tapés, l'écran affiche côte à côte : annoncé · reçus vivants · morts (%). Un motif devient obligatoire si le nombre diffère de l'annoncé, même d'un poulet, ou si les morts dépassent 2 %. Les motifs se touchent : Erreur de comptage · Morts au transport · Poulets échappés · Autre (seul « Autre » demande un texte). Qui est prévenu :
- **l'agent de la ferme**, dans « Saisies à vérifier » ;
- **la DGE**, dans Arbitrages ;
- **le vétérinaire de la zone**, au-delà du seuil, quel que soit le motif : un signalement d'origine « Morts à la réception du lot ».

La sortie de la ferme n'est **jamais** modifiée : l'annoncé est recopié dans la réception, à côté du reçu.

**Refus** (fonction 65) : QR inconnu, lot annulé, déjà reçu (date, par qui), refusé par le vétérinaire, destiné à un autre opérateur, ventes bloquées. Un lot rouge ne peut pas être reçu. Quand le même QR atteint 3 refus en 24 h (tous opérateurs confondus), une seule alerte part vers la DGE.

**Sous réserve.** Le lot porte « ne pas abattre, ne pas vendre ». Il apparaît en tête des **Signalements** du vétérinaire (« Lots retenus à la réception », avec Libérer / Refuser et un motif obligatoire, inscrit au journal), dans le compteur de sa tuile, et dans « À traiter » chez l'opérateur. Seul le vétérinaire de la province de la ferme décide : l'ADMIN lit, la DGE, l'agent et l'opérateur ne peuvent pas décider.

**Sans réseau.** Voir `docs/hors_ligne.md` et le point G de la section 3.

### Pilotage (ordinateur)

**Tableau de bord** de la DGE et de l'ADMIN, sans nouvelle tuile : un bloc « Traçabilité aval ». Il contient quatre chiffres :
- % de lots sortis avec QR ;
- % de ventes rattachées à un lot ;
- % de lots reçus et scannés ;
- écart moyen à la réception.

En dessous, un tableau par province : lots sortis, avec QR, reçus et scannés, écarts au-delà du seuil, refus de scan. Les formules sont dans `app/indicateurs.py` (`tracabilite`). Les mêmes chiffres sont dans le **rapport mensuel** automatique.

**Journal des scans** (ADMIN, AUDITEUR, DGE) : filtres par opérateur, résultat et période ; l'export CSV est inscrit au journal des exports.

### Éleveur et public

- **Éleveur, écran « Ventes et sorties » existant** (aucune tuile, aucun clic en plus) : la liste « Sorties de cette bande » s'ajoute sous le formulaire. Elle affiche :
  - « ✓ Partis › ✓ Reçus par l'abattoir », puis « L'abattoir a compté 114 vivants et 4 morts au transport » ;
  - ou « ◷ En attente du vétérinaire » ;
  - ou « ✗ Le vétérinaire n'a pas accepté ces poulets — appelez votre agent ».

  Jamais « sous réserve ».
- **Page publique du QR** : une étape « Reçus à l'abattoir » (ou « Reçus au marché ») avec la date, le nom de l'établissement et « contrôle validé ✓ ». Elle n'apparaît que si le lot est reçu **et** validé. Toujours aucune donnée personnelle.

### Démonstration

Les données fictives contiennent maintenant :
- l'Abattoir d'Owendo et le Marché de Mont-Bouët, avec leurs comptes **`abattoir.owendo`** et **`marche.montbouet`** (mot de passe `Demo-yl2-2026`, mêmes protections) ;
- deux lots attendus, deux réceptions validées, une réception avec écart (4 morts au transport, vétérinaire alerté) et une sous réserve ;
- trois scans refusés : lot d'un autre établissement, QR inconnu, déjà reçu.

La bande en cours de la démo (EST-001-B2-01) est bloquée par le vétérinaire pour montrer le lot 17. Ces lots viennent donc de deux bandes reprises en cours de route, dans les fermes EST-002 et EST-003. `marie.nze` suit aussi EST-002, pour voir les deux états côté éleveur.

## 2. Écarts et décisions prises en construisant

1. **Noms des paramètres.** Ils commencent par `reception.` (et non `tracabilite.`). Sinon `tracabilite.adresse_publique` serait passé sous quatre yeux. Le seuil s'appelle `reception.seuil_morts_pct`. Tous les `reception.*` sont sous quatre yeux, dans le domaine sanitaire (approuvés par un vétérinaire) : ils apparaissent aussi dans « Paramètres sanitaires ».
2. **Refus au quai par l'opérateur** (lot orange, « Refuser le lot »). Les chiffres ne sont pas demandés, l'agent de la ferme est prévenu, et le lot n'est **pas** clos : il peut être scanné de nouveau. Seuls l'annulation, une réception ou le refus du vétérinaire le closent (point 6 validé).
3. **Écart reçu sans réseau sans motif** (lot inconnu du téléphone). La réception n'est pas refusée, ce qui perdrait des chiffres. Elle est gardée, les alertes partent, et le motif se complète depuis « À traiter ».
4. **Agent prévenu** par une ligne dans « Saisies à vérifier » (compteur de sa tuile). Je n'ai pas ajouté de raison d'urgence sur « Mes fermes » ; à proposer si utile.
5. **Le chargement des données fictives remplace aussi les paramètres et les listes.** Le fichier de démo contient donc ceux du lot 19 (noté dans `docs/exploitation.md`).
6. **Captures « pleine page ».** La page défile dans un bloc intérieur, si bien que les captures font la hauteur de l'écran. Elles sont prises à l'endroit utile (écart, boutons, liste des sorties).

## 3. Tests (`tests/test_lot19.py`, 18 tests)

| Exigence | Test |
|---|---|
| Un opérateur ne voit que ses lots | `test_operateur_ne_voit_que_ses_lots`, `test_compte_operateur_rattache_a_un_etablissement` |
| Contrôles, chaque cas vert / orange (pesée, vaccin avec tolérance, délai d'attente) | `test_controles_tous_verts_puis_chaque_cas` |
| Différence abattoir / marché, contrôles réglables | `test_abattoir_et_marche`, `test_parametres_de_reception_sous_quatre_yeux` |
| Case vide refusée | `test_case_vide_refusee` |
| Écart : motif obligatoire, alertes, chiffres de la ferme intacts | `test_ecart_explication_alertes_et_chiffres_de_la_ferme_intacts`, `test_ecart_sous_le_seuil_sans_alerte_veterinaire` |
| Chaque motif de refus | `test_chaque_motif_de_refus` |
| Alerte après 3 refus | `test_alerte_dge_apres_3_refus_du_meme_qr` |
| Sous réserve : décision du vétérinaire seulement | `test_sous_reserve_puis_decision_du_veterinaire_seulement`, `test_refus_par_le_veterinaire_et_refus_au_quai` |
| Réception sans réseau contrôlée à l'arrivée | `test_reception_sans_reseau_controlee_a_l_arrivee` |
| Indicateurs justes, rapport mensuel | `test_indicateurs_de_tracabilite`, `test_indicateurs_dans_le_rapport_mensuel` |
| Journal des scans | `test_journal_des_scans` |
| Affichage éleveur, étape de la page publique | `test_affichage_eleveur_et_page_publique` |
| Données fictives | `tests/test_demo_donnees.py` (comptes, réceptions, scans) |

Suite complète (SQLite, 09/11/2026) : **418 réussis, 1 ignoré** (le test réservé à PostgreSQL), 9 min 38. La migration 0021 sera passée sur PostgreSQL (base temporaire) au déploiement.

## 4. Ergonomie (`docs/ergonomie.md`)

- [x] **Un seul bouton mis en avant** : Valider la réception, ou Recevoir sous réserve (Refuser le lot en secondaire).
- [x] **3 clics au plus.** Scanner → (lecture automatique) → Valider = 2. Numéro tapé → Chercher → Valider = 3.
- [x] **Aucun bouton inutilisable** : pas de « Libérer » chez l'ADMIN ni chez la DGE, pas d'appel s'il n'y a pas de téléphone.
- [x] **Aucun mot technique.** Pas de « synchronisation » ni d'« UUID ». L'éleveur ne lit jamais « sous réserve ».
- [x] **360 px sans défilement horizontal** : 20 écrans contrôlés au navigateur, largeur 360, aucune erreur JavaScript.
- [x] **Rien d'ajouté sans demande.** Seul ajout : la liste « Sorties de cette bande », nécessaire au point J.
- **Contrastes.** Sur l'écran de l'éleveur, le texte « refusé » est écrit en bleu nuit et non en rouge vif : le rouge n'atteint pas le contraste demandé pour du texte.

## 5. Tes tests à la main (téléphone Android, Chrome)

Ces tests demandent une adresse en HTTPS, donc la démo une fois déployée : la caméra et le mode sans réseau ne marchent qu'en HTTPS.

1. **Connexion et accueil.** Connecte-toi en `abattoir.owendo`. Tu dois voir la tuile orange « Scanner un lot », « Lots attendus » avec le compteur 2, « À traiter (1) » et « Attendus cette semaine ».
2. **Scan à la caméra.** Imprime ou affiche à l'écran l'étiquette QR d'un lot attendu de l'abattoir : fiche de la bande EST-002-B1-01 → étiquettes, en ADMIN ou en agent. Dans « Scanner un lot », accepte la caméra et vise le QR. Le résultat vert doit s'ouvrir seul, avec une petite vibration.
3. **Écart.** Tape 95 vivants, 3 morts, un poids. Le tableau « Annoncé / Reçus / Morts » doit s'afficher et la raison doit devenir obligatoire. Touche « Autre » : le champ texte apparaît. Valide.
4. **Refus.** Scanne le même QR une deuxième fois : l'écran rouge doit dire « Déjà reçu le … par Abattoir d'Owendo ». Essaie « Appeler l'agent de la ferme ».
5. **Autre établissement.** Connecte-toi en `marche.montbouet` et scanne un lot de l'abattoir : refus, « destiné à Abattoir d'Owendo ».
6. **Sans réseau.**
   - Ouvre d'abord « Scanner un lot » avec du réseau, puis passe en mode avion.
   - Tape le numéro d'un lot attendu ou scanne-le. Tu dois voir « 📵 Pas de réseau », le lot reconnu et l'annoncé.
   - Saisis les chiffres et enregistre. L'accueil doit afficher « ◷ Réception enregistrée, en attente de vérification ».
   - Remets le réseau : la réception part, et le résultat apparaît dans « Mes réceptions » (ou « À traiter » si elle a été refusée).
7. **Vétérinaire.** Connecte-toi en `veto`. Dans « Signalements », l'encadré « Lots retenus à la réception » doit apparaître. Libère le lot avec un motif. Repasse en `abattoir.owendo` : « Libéré par le vétérinaire » doit apparaître dans « À traiter ».
8. **Éleveur.** Connecte-toi en `marie.nze`, puis « Ventes et sorties » sur la bande EST-002 : tu dois voir « ✓ Partis › ✓ Reçus par l'abattoir » et le nombre compté. Sur la bande EST-003 : « ◷ En attente du vétérinaire ».
9. **Page publique.** Scanne le QR d'un lot reçu et validé avec l'appareil photo normal du téléphone : l'étape « Reçus à l'abattoir » doit apparaître, sans aucun nom de personne.
10. **DGE.** Connecte-toi en `dge`. Le Tableau de bord doit contenir le bloc « Traçabilité aval », et « Journal des scans » doit s'ouvrir avec ses filtres et l'export CSV.
11. **Installation.** Installe l'application sur l'écran d'accueil depuis le compte opérateur, puis ouvre le scanner depuis l'icône.

## 6. Captures

Elles sont dans `docs/captures/lot19/`.
- **Opérateur, 360 px (01 à 12)** : accueil, scanner, lot vert, écart et motifs, « Autre », lot orange et ses boutons, refus « déjà reçu » et « QR inconnu », attendus, mes réceptions, sans réseau, refus « autre établissement ».
- **Éleveur, 360 px (13, 14)**.
- **Page publique, 360 px (15)**.
- **Ordinateur (16 à 20)** : vétérinaire avec les lots retenus, Tableau de bord de la DGE, zoom sur la traçabilité, journal des scans, accueil de l'opérateur sur ordinateur.
