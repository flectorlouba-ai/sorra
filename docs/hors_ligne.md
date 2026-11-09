# SORRA — Saisie sans réseau (lot 7)

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

**Sur le téléphone** (`static/js/hors_ligne.js`, `static/js/sw.js`) :
- Un *service worker* garde les fichiers de style et les pages déjà vues. Pour les pages, il essaie d'abord le réseau (8 s au plus).
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

### Vrai conflit (deux personnes) : la plus récente gagne, l'agent est prévenu
Il n'y a conflit que si **deux personnes différentes** (l'éleveur et l'agent) ont saisi la même chose pour la même bande et le même jour.

| Cas | Règle |
|---|---|
| **Saisie du jour** déjà faite ce jour-là par une autre personne | On compare l'heure de la saisie sur le téléphone et l'heure de la dernière modification sur le serveur. **La plus récente est gardée**, sans addition des deux. Si les deux saisies sont identiques, rien n'est changé ni signalé. |
| **Livraison déjà confirmée** par une autre personne | Même règle. Si la confirmation du téléphone est plus récente, elle remplace l'autre (quantités reçues, morts à l'arrivée). |
| Pesée, sortie, déclaration | Elles s'ajoutent : pas de conflit possible, seulement les doublons ci-dessus. |

Pour chaque vrai conflit, une ligne « **Saisies à vérifier** » est créée pour l'agent de la ferme : alerte sur son accueil, puis écran avec bouton « Vu ». Elle dit ce qui a été gardé et ce qui a été remplacé, valeurs comprises. Pour revenir à l'autre version, l'agent corrige la saisie depuis la fiche de la bande ou de la livraison (correction déjà journalisée).

### Refus
Une saisie qui ne passe plus les contrôles au moment de l'envoi (par exemple plus de poulets sortis que de poulets présents) :
- est **refusée** ;
- le refus s'affiche sur le téléphone ;
- l'agent le voit dans « Saisies à vérifier » ;
- la saisie est retirée du téléphone.

### Limites connues
- Entre deux personnes, l'heure du téléphone sert à départager. Un téléphone mal réglé peut fausser l'ordre ; l'agent voit chaque conflit.
- Pour la même personne, les saisies s'additionnent sans question. En ligne, l'écran « Déjà envoyé » propose d'ajouter ; une erreur se corrige ensuite par l'agent depuis la fiche de la bande.
- Les pages gardées montrent l'état au dernier passage avec réseau (chiffres, « À faire aujourd'hui »).

## 6. Tests

`tests/test_hors_ligne.py` (14 tests) couvre :
- doublon (même identifiant renvoyé) ;
- reprise après coupure (file renvoyée en entier) ;
- même personne : saisie en ligne puis deux saisies sans réseau, additionnées quel que soit l'ordre des heures ;
- même personne : deux saisies sans réseau, additionnées ;
- même personne : confirmation de livraison sans conflit ;
- vrai conflit (agent puis éleveur) sur la saisie du jour, dans les deux sens ;
- vrai conflit sur la confirmation de livraison ;
- deux personnes, mêmes valeurs : pas de conflit ;
- refus ;
- session perdue ;
- jour passé compté depuis le jour de la saisie ;
- déclaration avec photo ;
- absence d'effet sans en-tête ;
- fichiers de l'application installable.

Le parcours complet (saisie et pesée sans réseau, puis retour du réseau) a été vérifié dans Chromium au format téléphone.
