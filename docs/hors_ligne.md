# SORRA — Saisie sans réseau (lot 7, règle des conflits revue au lot 12)

## 1. Ce que voit l'éleveur

- Il saisit comme d'habitude. Quand le réseau manque, il touche « Envoyer » et l'écran revient à l'accueil avec un bandeau orange :
  **« ◷ 1 saisie gardée sur le téléphone — Envoi dès le retour du réseau »**, suivi de la liste des saisies en attente (◷).
- Au retour du réseau, l'envoi part tout seul. Le bandeau devient vert : **« ✓ Envoyé : 2 saisies gardées sur le téléphone »**.
- Si une saisie est refusée, par exemple 5 000 poulets sortis pour 997 présents, le bandeau le dit et son agent est prévenu.
- Il n'a rien à apprendre : pas de bouton « synchroniser » ni de mot technique.

## 2. Quand ça marche

| Situation | Saisie sans réseau |
|---|---|
| Site en **HTTPS** (nom de domaine), ou ouvert sur l'ordinateur lui-même (`localhost`) | **Oui** |
| Site en HTTP par adresse IP (cas actuel du VPS : `http://187.124.217.218:5021`) | **Non** : le navigateur l'interdit. Le site marche exactement comme avant, sans rien garder sur le téléphone. |

**→ Le passage en HTTPS avec un nom de domaine est nécessaire avant le pilote** : sans lui, pas de saisie sans réseau sur les téléphones.

Le téléphone garde les pages que l'éleveur a ouvertes avec du réseau. À chaque ouverture de l'accueil, il garde aussi les pages Pesée, Sortie, Poulet malade et Reçu moins. **Il faut donc avoir ouvert l'application une fois avec du réseau.**

## 3. Saisies possibles sans réseau

| Saisie | Écran | Libellé dans le bandeau |
|---|---|---|
| Saisie du jour (morts, sacs) | « Ma bande aujourd'hui » | Saisie du jour · bâtiment B1 |
| Pesée | Peser | Pesée · bâtiment B1 |
| Sortie | Sortie | Sortie · bâtiment B1 |
| Confirmation de livraison | carte « Livraison à confirmer » (Tout reçu), écran « J'ai reçu moins » | Livraison du 08/11 · tout reçu |
| Déclaration sanitaire, avec photos | Poulet malade | Poulet malade · bâtiment B1 |

Les photos sont gardées sur le téléphone, déjà réduites (1 600 px), puis envoyées avec la déclaration. Le message vocal aussi.

## 4. Comment c'est fait

**Sur le téléphone** (`static/js/hors_ligne.js` ; service worker : gabarit `templates/sw.js`, servi par `/sw.js`) :
- Un *service worker* garde les fichiers de style et les pages déjà vues.
  - Pages, CSS et JS : **réseau d'abord** (8 s au plus), la copie gardée seulement sans réseau.
  - Polices et images : cache d'abord.
- **Mises à jour automatiques** (correctif du 09/11, `docs/rapport_correctif_cache.md`) :
  - les caches portent la version de l'application (empreinte des fichiers statiques et gabarits, `app/utils/statiques.py`) ;
  - chaque fichier statique est appelé avec son empreinte (`?v=…`) ;
  - le nouveau service worker prend la main tout de suite et supprime les anciens caches ;
  - la page se recharge une fois, proprement.
- Un formulaire marqué `data-hors-ligne="libellé"` est intercepté à l'envoi :
  - le téléphone vérifie d'abord que le serveur répond (`/hors-ligne/ping`, 5 s au plus) ;
  - s'il répond, le formulaire part normalement ;
  - sinon, la saisie est rangée dans le téléphone (IndexedDB) avec :
    - un **identifiant unique (UUID)** tiré sur l'appareil ;
    - l'**heure de la saisie** ;
    - le libellé ;
    - tous les champs, photos comprises.
- Au retour du réseau (événement `online`, ouverture d'une page, puis toutes les 30 s), le téléphone :
  1. demande un jeton de formulaire frais (`/hors-ligne/jeton`) ;
  2. rejoue chaque saisie, dans l'ordre, sur **la même adresse que le formulaire d'origine**, avec les en-têtes `X-Hors-Ligne-Id`, `X-Hors-Ligne-Horodatage`, `X-Hors-Ligne-Libelle` et `X-Appareil`.
- Une saisie n'est effacée du téléphone qu'après une réponse « ok », « déjà reçu », « conflit » ou « refusé ». Après une coupure ou un délai dépassé, elle reste et repart plus tard.
- Quand on se connecte, les pages gardées sont effacées. Les saisies en attente restent : elles portent l'identifiant de leur auteur et ne partent qu'avec sa session.

**Sur le serveur** (`app/services/hors_ligne.py`) :
- Les écrans existants font tout le travail : contrôles, journal, alertes sanitaires, lots tracés, stocks. Il n'existe pas de second chemin de saisie.
- L'identifiant reçu est noté dans la table `envoi_hors_ligne`, **dans la même transaction que la saisie**. Une saisie refusée n'est pas notée.
- La table garde aussi l'objet créé (`objet_table`, `objet_id`). Les lignes créées portent `appareil_id`.
- Réponse en JSON, au lieu de la page :

  | `etat` | Sens |
  |---|---|
  | `ok` | saisie enregistrée |
  | `deja` | identifiant déjà reçu |
  | `conflit` | une autre version existait déjà |
  | `refuse` | la saisie ne passe pas les contrôles (message) |
  | `connexion` | session expirée : la saisie reste sur le téléphone |
- **« Aujourd'hui » d'une saisie rejouée = le jour où elle a été faite sur le téléphone.** Une saisie faite lundi sans réseau et envoyée jeudi reste donc celle de lundi, sans tomber sous la limite des 3 jours passés de l'éleveur.
- Une heure de téléphone dans le futur est ramenée à l'heure du serveur.

## 5. Règles

### Doublons
Un même identifiant n'est **jamais compté deux fois** : réponse perdue, double envoi, envoi coupé puis repris. Le second envoi reçoit `deja`, et rien n'est rejoué.

L'identifiant est noté dans la même transaction que la saisie, donc il n'existe pas de cas « saisie enregistrée mais identifiant oublié ». Deux envois simultanés du même identifiant : le second bute sur la clé unique et reçoit `deja`.

### Même personne : les saisies s'additionnent
Plusieurs saisies du jour de la **même personne**, pour la même bande et le même jour, **s'additionnent exactement comme en ligne** (morts et sacs). C'est le cas avec ou sans réseau, depuis le même téléphone ou non, et quel que soit l'ordre d'arrivée. Exemple : 2 morts le matin sans réseau, puis 1 mort le soir sans réseau, donnent 3 morts.

Ce n'est pas un conflit : rien n'est signalé à l'agent.

« La même personne » est celle qui a écrit la saisie existante en dernier. Si l'agent l'a corrigée entre-temps, c'est lui.

Une confirmation de livraison déjà faite par la même personne ne s'additionne pas : sa confirmation la plus récente compte, sans signalement.

### Deux personnes : les deux versions sont gardées (lot 12)

**« La plus récente gagne » est supprimée partout.** Aucune donnée n'est perdue ni écrasée. La même règle vaut avec ou sans réseau.

| Cas | Règle |
|---|---|
| **Saisie du jour** déjà faite ce jour-là par une autre personne (éleveur et agent), avec d'autres valeurs (morts ou aliment) | Les **deux versions sont gardées**. La journée passe « à vérifier ». **La version de l'éleveur compte** pour les indicateurs jusqu'à la décision, qu'elle soit arrivée en premier ou en second. Mêmes valeurs : rien à vérifier. |
| En ligne, l'agent saisit après l'éleveur | L'écran « Déjà envoyé » propose : **« Ajouter »** (des morts de plus dans la journée : cela s'additionne) ou **« Mes chiffres sont différents »** (deux versions, à vérifier). |
| **Confirmation de livraison** déjà faite par une autre personne, avec d'autres quantités ou morts | Les deux versions sont gardées, celle de l'éleveur compte. L'écart est visible de l'agent **et de la DGE**. |
| **Sorties** du même jour par deux personnes | Ce n'est pas un conflit (deux ventes), **sauf** si le nombre **et** le destinataire sont identiques : **« doublon possible »**. Celle de l'éleveur compte. Celle de l'autre personne est **mise de côté** : elle n'entre ni dans les poulets présents, ni dans les indicateurs, ni dans « Mon argent », et son lot QR n'est créé (ou réactivé) que si elle est retenue. **Non tranché sous 48 h** : l'alerte passe en rouge chez l'agent et remonte à la DGE. |
| Pesée, déclaration | Elles s'ajoutent : pas de conflit possible, seulement les doublons ci-dessus. |

**L'éleveur** voit « ◷ À vérifier par votre agent » sur la saisie ou la sortie concernée (saisie du jour, Mes bandes, Mon argent). Jamais un message d'erreur.

**L'agent** (et la DGE, l'ADMIN) ouvre **« Saisies à vérifier »** (`/hors-ligne/a-verifier`), depuis l'encadré Alertes :
- les deux versions côte à côte : qui, quand, valeurs, laquelle compte en attendant ;
- **« Retenir cette version »**, ou pour une sortie : « Ce sont deux sorties différentes », « Garder celle de l'éleveur » ou « Garder celle de l'autre personne » ;
- **motif obligatoire** ;
- la décision est inscrite au journal (« Saisie à vérifier tranchée »). Les indicateurs se recalculent, et le bilan aussi si la bande est terminée.

L'éleveur ne tranche jamais.

Table : `conflit_hors_ligne`, complétée (genre, versions en JSON, statut, décision, motif). Les refus d'envoi restent des lignes « Vu ». Service : `app/services/verifications.py`.

### Refus
Une saisie qui ne passe plus les contrôles au moment de l'envoi (par exemple plus de poulets sortis que de poulets présents) :
- est **refusée** ;
- le refus s'affiche sur le téléphone ;
- l'agent le voit dans « Saisies à vérifier » ;
- la saisie est retirée du téléphone.

### Limites connues
- Entre deux personnes, l'heure du téléphone ne départage plus rien : les deux versions sont gardées, c'est l'agent qui tranche.
- Pour la même personne, les saisies s'additionnent sans question. En ligne, l'écran « Déjà envoyé » propose d'ajouter ; une erreur se corrige ensuite par l'agent depuis la fiche de la bande.
- Les pages gardées montrent l'état au dernier passage avec réseau (chiffres, « À faire aujourd'hui »).

### L'agent sans réseau (relecture des lots 15-18, remplace la règle du lot 16)

**Avant la relecture**, les saisies de l'agent demandaient le réseau de deux façons :
- **pas de formulaire « hors ligne » du tout** : vaccin et traitement pour l'éleveur, biosécurité, nouvel éleveur, et aussi nouvelle bande, clôture, rattrapage, corrections, planifier ou annuler une visite, comptage du stock, commande, livraison, ferme (création, modification, bâtiments, GPS), BCEG ;
- **formulaire « hors ligne », mais page jamais gardée sur le téléphone de l'agent**, donc inutilisable sans réseau sauf si elle avait été ouverte juste avant : saisie du jour, pesée, sortie, poulet malade, J'ai payé, entretien, réception de livraison, compte rendu de visite. Seules la tournée et les fiches des fermes étaient gardées (lot 16).

**Maintenant** :
- À chaque ouverture de l'accueil avec du réseau, le téléphone de l'agent garde, **une page à la fois**, toutes ses pages de saisie : tournée, fiches, compte rendu (non planifié et chaque visite prévue), biosécurité, nouvel éleveur, J'ai payé, entretien et panne, et pour chaque bande en cours : saisie du jour, jour oublié, pesée, sortie, poulet malade, vaccin, traitement ; plus la réception des livraisons à confirmer. La liste est unique (`routes/hors_ligne.pages_agent`), testée page par page.
- Ces saisies se font **sans réseau** et partent au retour du réseau (bandeau ◷ / ✓ comme chez l'éleveur), avec leur identifiant unique : jamais deux fois.
- **Règles** :
  - saisie pour l'éleveur : règle du lot 12. Même personne, les saisies s'additionnent ; deux personnes, deux versions gardées, celle de l'éleveur compte, à trancher ;
  - **compte rendu** : la date est celle du téléphone. Si la visite a reçu entre-temps un autre compte rendu, ou a été annulée, le compte rendu est **gardé comme une deuxième visite** et l'agent est prévenu ;
  - **biosécurité** : date du téléphone ; une grille incomplète est refusée à l'envoi et signalée ;
  - **nouvel éleveur** : identifiant et mot de passe provisoire sont **préparés et affichés sur le téléphone** avant l'envoi, à noter tout de suite. Identifiant déjà pris : un chiffre est ajouté, l'agent est prévenu, le mot de passe noté reste valable. Même téléphone déjà inscrit sur la ferme : refusé et signalé. **Le mot de passe provisoire est effacé du téléphone dès que l'inscription est envoyée** (le serveur a répondu : reçue, déjà reçue ou refusée) ; il n'y reste que si elle n'est pas arrivée (réseau coupé, reconnexion demandée). Test : `tests/test_effacement_mot_de_passe.py`, qui exécute le vrai script du téléphone dans Node (ignoré si Node manque).
- **Restent en ligne** (des décisions, ou des écrans de bureau) : trancher une saisie, valider ou refuser, commander, compter le stock, planifier ou annuler une visite, créer ou modifier une ferme, les livraisons de l'État, la BCEG.
- Vérifié au navigateur, réseau coupé : un nouvel éleveur et une biosécurité saisis sans réseau sont gardés (◷), puis envoyés au retour du réseau. Le compte se connecte avec le mot de passe noté. Captures : `docs/captures/agent_hors_ligne/`.

### Blocage des ventes par le vétérinaire (lot 17)
- Dès que la page de l'éleveur est relue avec du réseau, l'écran Sortie gardé sur le téléphone montre « ⛔ Le vétérinaire a bloqué les ventes de cette bande » **sans formulaire** : aucune sortie ne peut être saisie, même sans réseau. Vérifié au navigateur (`docs/captures/lot17/360_eleveur_sortie_bloquee_sans_reseau.png`).
- En ligne, le serveur **refuse** la sortie (pas de lot, pas de QR).
- Une sortie saisie sans réseau **avant** que le téléphone ne connaisse le blocage, et reçue **après**, n'est pas perdue : elle est enregistrée **mise de côté, à vérifier**, sans lot ni QR. Elle apparaît dans « Surveillance » chez le vétérinaire, qui dit si les poulets sont bien sortis (comptée, toujours sans QR) ou non.

### Réception par l'opérateur, abattoir ou marché (lot 19)
- Le téléphone de l'opérateur garde son accueil, le scanner, « Lots attendus » et « Mes réceptions » (`routes/hors_ligne.PAGES_OPERATEUR`). La page du scanner contient les lots attendus de l'opérateur : sans réseau, un QR lu (ou un numéro tapé) est reconnu sur le téléphone, qui affiche l'annoncé et l'écart dès que les chiffres sont tapés.
- La caméra lit le QR sans réseau. La réception (3 chiffres, raison de l'écart si elle est connue) part dans la file d'attente habituelle (identifiant unique, aucun doublon). L'accueil affiche « ◷ Réception enregistrée, en attente de vérification ».
- **Le serveur fait tous les contrôles à l'arrivée**, comme pour un scan en ligne, et inscrit le scan au journal (« Sans réseau »). Si un contrôle de refus échoue (QR inconnu, lot annulé, déjà reçu, autre destinataire, ventes bloquées), la réception est gardée **refusée** avec le motif ; si un contrôle bloquant manque, elle est **sous réserve**. L'opérateur le voit dans « À traiter ». Rien n'est perdu.
- Un écart sans raison (lot inconnu du téléphone) n'est pas refusé : la réception est gardée, les alertes partent, et l'opérateur complète la raison depuis « À traiter ».
- En ligne, un réseau qui tombe entre le scan et « Valider la réception » ne perd rien : le formulaire du résultat est aussi gardé sur le téléphone.

### Espace terrain de l'agent et de l'opérateur (lot 19 ter)
- **Toutes les pages terrain** de l'agent et de l'opérateur sont dans la liste unique (`routes/hors_ligne.pages_a_garder`) :
  - accueil, tournée, mes fermes, fiche de chaque ferme ;
  - saisir pour (par ferme), stock (par ferme), à vérifier, nouvel éleveur ;
  - Moi, présentation, aides « Comment faire ? » de leur profil ;
  - les écrans de saisie de l'éleveur déjà gardés depuis le lot 16.

  Un test parcourt toutes les adresses de l'application et vérifie qu'aucune page terrain ne manque (`tests/test_lot19ter.py`).
- **Pas gardées, et c'est voulu** (`EN_LIGNE_SEULEMENT`, `VERSION_BUREAU_AGENT`) :
  - la sécurité du compte, en ligne par nature ;
  - la création d'une ferme : **avec du réseau seulement**, et le téléphone le dit (« 📶 Avec du réseau seulement ») ;
  - les écrans de la « Version bureau » de l'agent.
- **Prévu au lot 19 bis (GPS)** : créer une **nouvelle ferme sans réseau** (gardée sur le téléphone, numéro attribué à l'arrivée). Aujourd'hui, sans réseau, l'agent inscrit un éleveur seulement sur une ferme déjà enregistrée.
- L'accueil de l'agent et de l'opérateur affiche « 📶 Tout est envoyé ✓ » ou « ◷ N saisies en attente » : c'est le nombre lu sur le téléphone (`window.sorraEnAttente`).

### Fiches : modifier et archiver sans réseau (lot A1)
- La fiche préremplie de chaque ligne est **déjà dans la page** (`<template>`) : elle s'ouvre sans réseau.
- « Enregistrer la modification », « 🗄️ Archiver » et « ↩️ Restaurer » partent par **une seule adresse** (`/fiches/<genre>/<id>`, `action` = modifier | archiver | restaurer) : sans réseau, l'envoi est **gardé sur le téléphone** comme les autres saisies, puis envoyé avec son identifiant unique (jamais en double). Le téléphone revient ensuite à la liste.
- À l'envoi après coup, les mêmes règles s'appliquent : bande terminée entre-temps → refus (« 🔒 ») signalé à l'agent ; lot reçu entre-temps → l'archivage de la sortie est refusé.
- `js/fenetre.js` est gardé dès l'installation.

### Position de la ferme et visites (lot E, partie a)
- La page « Relever la position » de chaque ferme de l'agent est gardée sur le téléphone ; le relevé part dans la file d'attente avec son heure et l'appareil.
- Envoyé sans réseau et hors de la province : la position est gardée et marquée « à vérifier » chez la DGE.
- La distance d'une visite à la ferme est calculée sur le téléphone, puis recalculée par le serveur à l'arrivée.

### Session (lot 15)
- L'éleveur et l'agent ne sont **jamais déconnectés par inactivité** : des jours sans réseau ne doivent pas faire perdre la session.
- Si l'ADMIN ferme la session (téléphone perdu), l'envoi suivant reçoit la réponse « connexion ». Les saisies restent sur le téléphone et partent après la reconnexion, au nom de leur auteur (lot 13).

## 6. Tests

- `tests/test_hors_ligne.py` (12 tests) couvre :
  - doublon (même identifiant renvoyé) ;
  - reprise après coupure ;
  - même personne : les saisies s'additionnent ;
  - deux personnes, mêmes valeurs : pas de conflit ;
  - confirmation de livraison par la même personne ;
  - refus, session perdue, jour passé ;
  - déclaration avec photo ;
  - absence d'effet sans en-tête ;
  - application installable.
- `tests/test_verifications.py` (lot 12) couvre :
  - deux versions de la saisie du jour, dans les deux sens, en ligne et sans réseau ;
  - décision avec motif, journal et recalcul ;
  - doublon possible de sortie (mise de côté, décisions, rouge à 48 h, DGE) ;
  - écart de confirmation de livraison visible de la DGE.
- `tests/test_lot19.py::test_reception_sans_reseau_controlee_a_l_arrivee` (lot 19) couvre la réception faite sans réseau : validée, refusée d'elle-même (autre destinataire), sous réserve d'elle-même (pesée manquante), raison de l'écart complétée ensuite, pages de l'opérateur gardées.

Le parcours complet (saisie et pesée sans réseau, puis retour du réseau) a été vérifié dans Chromium au format téléphone.
