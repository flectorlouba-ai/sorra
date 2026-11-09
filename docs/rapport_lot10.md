# SORRA — Rapport du lot 10 : entretien des installations et protection des saisies en attente

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1.

**Tests :** **298 tests réussis** et 1 réservé à PostgreSQL, dont 22 nouveaux dans `tests/test_entretien.py`. Les tests d'ordre des tuiles (`tests/test_accueil_eleveur.py`) incluent maintenant Entretien.

**Migration :** 0012, qui crée les tables `tache_entretien`, `entretien_fait` et `panne`, ajoute la colonne `bande.ouverte_sans_desinfection`, et charge la liste de départ des 7 tâches.

**Références :** description dans `docs/maquettes/maquettes_lot10.md`, aperçu de l'étape 1 dans `docs/maquettes/apercu_lot10.html`, règles dans `docs/ergonomie.md` (section F, « Entretien des installations » et « Protection des saisies en attente »), consigne des agents dans `docs/exploitation.md`.

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

**Tuile « 🔧 Entretien » sur l'accueil.**
- Elle est placée dans l'ordre fixe, entre « J'ai acheté » et « Mes bandes ».
- Sa pastille compte les tâches à faire + les pannes en cours. Elle est rouge s'il y a une panne.
- Sous le nom : « tâches à faire », « pannes en cours » ou « tout est fait ».

**Écran Entretien** (`/entretien`), de haut en bas :
- les **pannes en cours**, en cartes roses, avec « C'est réparé » ;
- les **tâches**, une carte par tâche, avec « Fait ✓ » :
  - les bâtiments concernés sont regroupés (« B2 et B3 · chaque jour »), et un seul « Fait ✓ » coche tous les bâtiments ;
  - une tâche faite reste grisée « ✓ fait » jusqu'à la fin de sa période (jour, semaine, mois) ;
  - **retard** : « pas fait la semaine dernière » ou « pas fait le mois dernier », en tête de liste. **Jamais pour les tâches du jour** (votre précision 2). Pas de retard non plus pour une bande ou une ferme qui n'existait pas encore la période précédente ;
- le bouton **« ⚠️ Quelque chose est en panne »**.

**Quelles tâches, pour quelle ferme :**
- les tâches de bande (abreuvoirs, mangeoires, litière) concernent les bâtiments qui ont une bande en cours ;
- les tâches de ferme n'apparaissent que si la ferme a l'installation sur sa fiche : pédiluve, groupe électrogène, forage ou puits ;
- **« Nettoyer et désinfecter »** apparaît à la **clôture** d'une bande, pour le bâtiment vidé (« B1 · vide sanitaire depuis 3 jours »). Une fois faite, elle est liée à la bande clôturée.

**Nouvelle bande dans un bâtiment pas désinfecté :**
- un avertissement **non bloquant** s'affiche : « ⚠️ B1 n'a pas été marqué « nettoyé et désinfecté ». Continuer quand même ? » ;
- l'éleveur choisit « Commencer la bande » ou « Je nettoie d'abord » ;
- s'il continue, la bande est **marquée** (`ouverte_sans_desinfection`), l'action est **inscrite au journal** (« Bande ouverte sans désinfection »), et l'agent le voit sur la fiche de la ferme.

**Panne** (`/entretien/panne`) :
- 6 grandes images : Chauffage, Eau, Électricité, Ventilation, Mangeoires, Bâtiment ;
- le bâtiment, ou « Toute la ferme ». Ce choix est caché si la ferme n'a qu'un bâtiment ;
- photo facultative ;
- gros bouton rouge **« Envoyer à mon agent »**. Pas d'annulation après Envoyer (votre précision 9).

**Annuler dans les 10 secondes :**
- « **Fait ✓ — Annuler (10)** » après « Fait ✓ » : la tâche redevient à faire ;
- « **Réparé ✓ — Annuler (10)** » après « C'est réparé » (votre précision 9) : la panne redevient « Signalée », l'alerte de l'agent revient, et l'annulation est inscrite au journal.

**Côté agent :**
- **alerte** « Panne signalée : 💧 Eau · B2 » sur son accueil, avec un lien vers la fiche de la ferme ;
- **carte « Entretien »** sur la fiche de la ferme (agent, DGE, ADMIN) :
  - dernière synchronisation du téléphone de l'éleveur ;
  - pannes en cours ;
  - bandes ouvertes sans désinfection ;
  - tâches en retard ;
  - dernière désinfection de chaque bâtiment ;
- bouton **« Cocher ou réparer pour l'éleveur »** : le même écran, dans la charte de l'agent. Chaque coche faite par l'agent est inscrite au journal (« pour l'éleveur »).

**Liste des tâches (ADMIN)** : Configuration → « Tâches d'entretien ».
- On ajoute, modifie ou désactive une tâche ; on ne la supprime jamais.
- Pour chaque tâche : nom, icône, fréquence, portée (bâtiments avec bande, toute la ferme, bâtiment en vide sanitaire), installation requise.
- La liste de départ est marquée **« à valider par les vétérinaires »**.

**Sans réseau** : « Fait ✓ », « Envoyer » (avec la photo) et « C'est réparé » sont gardés sur le téléphone, puis envoyés au retour du réseau, sans doublon. Après un envoi différé, pas de bandeau « Annuler ».

**Protection des saisies en attente :**
- sur l'accueil, si des saisies attendent le réseau depuis plus de 24 h, un bandeau orange s'affiche : « ◷ N saisies attendent le réseau. Ne videz pas les données de l'application. » ;
- sur la fiche de la ferme : « Dernière synchronisation du téléphone de l'éleveur : il y a X jours ». C'est la dernière saisie reçue de l'éleveur ; les simples connexions ne comptent pas. La mention « à vérifier » s'ajoute à partir de 3 jours ;
- consigne pour les agents dans `docs/exploitation.md` : ne jamais vider les données de l'application sans avoir vérifié qu'aucune saisie n'est « ◷ en attente ».

**Corrigé au passage :**
- **Écran « Nouveaux poussins »** : la carte de la livraison s'affichait en boîtes imbriquées (défaut des lots 8 et 9, visible quand des poussins attendent). C'est maintenant une seule carte.

## Tableau des clics, vérifié par un test (`test_nombre_de_touches`)

| Action | Clics |
|---|---|
| Entretien → Fait ✓ | 2 |
| Entretien → Quelque chose est en panne → Envoyer | 3 (+ le choix de l'image) |
| Entretien → C'est réparé | 2 |

## Captures (`docs/captures/lot10/`, 360 px sauf mention)

| Fichier | Écran |
|---|---|
| `01_accueil.png` | accueil avec la tuile Entretien (pastille 6) |
| `02_entretien.png` | écran Entretien : retards de la semaine et du mois en tête, aucun retard pour les tâches du jour |
| `03_fait_annuler.png` | « Fait ✓ — Laver les abreuvoirs · Annuler (10) » |
| `04_panne.png`, `05_panne_choisie.png` | écran Panne, puis Eau + B2 choisis |
| `06_panne_envoyee.png` | carte rose de la panne, « C'est réparé » |
| `07_accueil_panne.png` | tuile Entretien, pastille rouge « pannes en cours » |
| `08_agent_accueil_alerte.png` | alerte « Panne signalée » sur l'accueil de l'agent (ordinateur) |
| `09_agent_fiche_entretien.png` | carte Entretien de la fiche ferme (ordinateur) |
| `09b_agent_entretien.png` | l'agent coche ou répare pour l'éleveur (ordinateur) |
| `10_repare_annuler.png` | « Réparé ✓ — Eau · B2 · Annuler (10) » |
| `11_entretien_ordinateur.png` | écran Entretien de l'éleveur sur ordinateur |
| `12_admin_taches.png`, `13_admin_taches_360.png` | liste des tâches (ADMIN) |
| `14_avertissement_desinfection.png` | avertissement à l'ouverture d'une bande dans B1 pas désinfecté |

**Vérification au navigateur** (Chromium, 360 px et 1 366 px) :
- toutes les pages font 360 px de large ;
- parcours complet rejoué : Fait et Annuler, panne Envoyer, alerte et fiche de l'agent, Réparé et Annuler, avertissement puis « Commencer la bande » ;
- aucune erreur JavaScript.

## Décisions (écarts 1 à 12, tous validés)

Les 12 écarts de l'étape 1 sont appliqués tels que décrits dans `docs/maquettes/maquettes_lot10.md`, avec vos deux précisions :
- **Écart 2** : aucun retard pour les tâches du jour ; le retard ne s'affiche que pour la semaine et le mois.
- **Écart 9** : « Réparé ✓ — Annuler (10) » ajouté ; toujours pas d'annulation après « Envoyer » une panne.

**Choix faits pendant la construction :**
- **Retard** : il ne s'affiche que si la tâche existait déjà la période précédente (bande commencée avant le début de la semaine, ferme créée avant le début du mois). Une bande qui commence ne part donc pas « en retard ».
- **Désinfection** : le « Fait ✓ » est lié à la bande clôturée. Une nouvelle clôture du même bâtiment redemande donc la désinfection.
- **Date de dernière synchronisation** : c'est la dernière saisie de l'éleveur inscrite au journal. Les connexions, déconnexions et exports ne comptent pas.
- **L'agent** utilise le même écran Entretien, dans sa charte bleu nuit.

## Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** : « Fait ✓ » par tâche, « C'est réparé » par panne, « Envoyer à mon agent » sur l'écran Panne.
- [x] **3 clics au plus** (tableau ci-dessus, vérifié par un test).
- [x] **Aucun bouton inutile** : pas de tâche de bande sans bande, pas de tâche d'installation absente, pas de choix du bâtiment s'il n'y en a qu'un.
- [x] **Aucun mot technique visible** : « vide sanitaire depuis 3 jours », « pas fait la semaine dernière ».
- [x] **360 px sans défilement horizontal**.
- [x] **Saisie du jour en moins de 30 s** : inchangée.
- [x] **Rien d'ajouté sans demande**, en dehors des écarts validés.

## Tests que vous ferez

Base de démonstration : `eleveur` / `Demo-yl2-2026`, sur `http://127.0.0.1:5020`.

1. **Accueil** : la tuile « 🔧 Entretien » est entre « J'ai acheté » et « Mes bandes », avec sa pastille.
2. **Entretien → Fait ✓** sur « Laver les abreuvoirs » :
   - le bandeau « Fait ✓ — Annuler (10) » apparaît, et la tâche est grisée « ✓ fait » ;
   - essayez « Annuler » une fois ;
   - demain matin, la tâche est de nouveau à faire, sans mention « pas fait hier ».
3. **Quelque chose est en panne** : touchez « Eau », puis un bâtiment, ajoutez une photo, puis « Envoyer à mon agent ». La carte rose apparaît, et la pastille de la tuile devient rouge.
4. **Agent** (`agent.est`) :
   - l'alerte « Panne signalée » est sur l'accueil ;
   - sur la fiche de la ferme EST-001, la carte « Entretien » montre la panne, la photo et la dernière synchronisation.
5. **C'est réparé** (éleveur) : le bandeau « Réparé ✓ — Annuler (10) » apparaît. Touchez « Annuler » : la panne revient, et l'alerte de l'agent aussi. Réparez de nouveau sans annuler : l'alerte disparaît.
6. **Fin de bande** : clôturez une bande. « Nettoyer et désinfecter » apparaît pour ce bâtiment.
7. **Nouvelle bande** dans ce bâtiment, sans avoir coché la désinfection :
   - l'avertissement apparaît ;
   - « Commencer la bande » ouvre quand même la bande ;
   - l'agent voit « ouverte sans désinfection » sur la fiche, et le journal (admin) a la ligne « Bande ouverte sans désinfection ».
8. **Admin** : Configuration → « Tâches d'entretien ». Ajoutez une tâche, puis désactivez-la : elle disparaît de l'écran de l'éleveur.
9. **Installations** : sur la fiche de la ferme, ajoutez « Pédiluve ». « Changer l'eau du pédiluve » apparaît chez l'éleveur.
10. **Sans réseau** (F12 → Réseau → Hors connexion) :
    - faites « Fait ✓ » puis une panne : « ◷ en attente » s'affiche ;
    - au retour du réseau, « ✓ envoyé » s'affiche ;
    - le bandeau orange « Ne videz pas les données de l'application » ne s'affiche qu'au-delà de 24 h d'attente : pas facile à tester à la main.

## Points à valider

- **La liste des tâches de départ**, par les vétérinaires : noms, fréquences, et installations requises.
- **Le seuil « à vérifier »** de la dernière synchronisation (3 jours).
- **Le test terrain** avec 3 à 5 éleveurs.
