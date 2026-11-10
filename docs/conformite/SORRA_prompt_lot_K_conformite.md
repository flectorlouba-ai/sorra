# SORRA — Lot K : conformité totale aux maquettes (à coller dans Claude Code)

Avant de coller :
1. Dézippe `SORRA_lot_K_conformite.zip` à la racine du dépôt :
   - `maquettes/*` → `docs/maquettes/validees/` (remplace les fichiers existants ; le dossier `ref/` contient l'image de chaque écran) ;
   - `SORRA_cahier_conformite_maquettes.xlsx` et `.docx` → `docs/conformite/`.
2. Colle le texte ci-dessous dans la session en cours. Il s'ajoute à la file : termine d'abord le lot en cours.

```
SORRA — LOT K : CONFORMITÉ TOTALE AUX MAQUETTES (tous les écrans, bureau ET terrain)

PRIORITÉ : juste après le lot en cours (et après le lot L s'il n'est pas fait).
À partir de maintenant, ce lot est aussi le CRITÈRE D'ACCEPTATION de tous les lots
restants (R, T, G…) : un écran n'est terminé que s'il est conforme au cahier.

OBJECTIF
Chaque écran de SORRA reproduit sa maquette validée :
- le CONTENU : indicateurs, courbes, carte, colonnes des tableaux (mêmes libellés,
  même ordre), filtres, boutons, textes ;
- les FORMULAIRES : bouton de création au libellé exact, fenêtre qui tient à
  l'écran, champs = colonnes du tableau ;
- les MODIFICATIONS : clic sur une ligne = formulaire prérempli, avec les actions
  de la colonne « Au clic sur une ligne » du cahier, selon les droits.
« S'en inspirer » ne suffit plus : la maquette fait foi.

RÉFÉRENCES (lis-les avant de commencer)
- docs/conformite/SORRA_cahier_conformite_maquettes.xlsx — LA grille :
  · « Règles communes » : s'applique à tous les écrans ;
  · « Bureau - écrans » : 45 écrans (DGE 8, Vétérinaire 8, Admin 7, Éleveur 8,
    Agent 8, Auditeur 6) : bouton de création, pastille, indicateurs, courbes,
    carte, titre et colonnes du tableau, action au clic, image de référence ;
  · « Bureau - colonnes et champs » : 352 colonnes, chacune = un champ du
    formulaire, typée « Saisi », « Calculé (lecture seule) » ou « Automatique » ;
  · « Terrain - écrans » : 87 écrans (téléphone éleveur, agent, opérateur, GPS,
    notifications, actions, fiche papier, Mon argent, fenêtres de la maquette
    des formulaires) avec le contenu texte à reproduire et la priorité ;
  · « Contrôle » : la grille à remplir (132 lignes).
- docs/maquettes/validees/*.html (à ouvrir avec Playwright) et
  docs/maquettes/validees/ref/*.png (image de chaque écran).
- Le .docx est la même chose en lecture (une fiche par écran).

RÈGLES
1. La maquette fait foi pour la présentation, les libellés, les colonnes, les
   champs et les actions. Si deux maquettes se contredisent, la plus récente
   l'emporte (colonne « Priorité » : le plus grand chiffre gagne ;
   maquette_sorra_bureau.html est la référence de toute la version ordinateur).
2. La maquette est un MINIMUM : ne retire JAMAIS une fonction déjà en service qui
   n'y figure pas. Elle reste, à l'endroit le plus logique, présentée dans le
   même style.
3. Champs « Calculé (lecture seule) » et « Automatique » : affichés dans le
   formulaire, jamais saisissables. Seuls les champs « Saisi » se modifient.
   Si le classement d'une colonne te paraît faux, corrige-le et note-le.
4. Une colonne dont la donnée n'existe pas encore : ajoute le champ au modèle
   par une NOUVELLE migration (ne jamais modifier une migration existante) ou
   calcule-la. Si c'est impossible dans ce lot : « Écart justifié » dans la
   grille, avec la raison et le lot qui la fera. Jamais de chiffre inventé ;
   une valeur absente s'affiche « — ».
5. Les données des maquettes sont fictives : on reproduit la structure et les
   libellés, pas les valeurs. MAIS complète le jeu de DÉMONSTRATION pour que
   chaque tableau montre des lignes comparables à la maquette (données fictives,
   bandeau démo inchangé) : le jury doit voir des écrans pleins.
6. Archiver, jamais supprimer. Droits : matrice existante, quatre yeux pour les
   paramètres sensibles, le vétérinaire ne voit jamais de donnée financière ; un
   profil sans le droit voit le formulaire en lecture seule.
7. Terrain : on PEUT modifier les écrans du téléphone pour les rendre conformes,
   en gardant le hors ligne, la file de synchronisation, « case vide ≠ zéro »,
   les 3 clics et tous les tests existants. Incrémente la version du service
   worker à chaque livraison terrain.
8. Vrai logo SORRA partout (icône poule sur fond bleu nuit), pas d'émoji en logo.
9. Règles communes de docs/regles_lots.md toujours en vigueur (pas de CDN,
   secrets hors git, ne rien toucher hors de SORRA sur le serveur, etc.).

DÉROULÉ
Étape 1 — Correspondance (sans changer l'application)
- docs/conformite/correspondance.csv : pour chaque ligne de « Bureau - écrans »
  et de « Terrain - écrans » : route Flask, gabarit, état actuel (Existe /
  Partiel / Absent).
- Capture de l'application dans l'état actuel, même cadrage que la référence
  (bureau 1440×900, téléphone 390×844), avec les comptes de démo :
  docs/conformite/avant/.
Étape 2 — Construction, par sous-lots, chacun : tests verts → merge main → push
→ déploiement sur la démo (règle permanente) :
  K1 bureau DGE + Vétérinaire
  K2 bureau Administrateur + Auditeur
  K3 bureau Éleveur + Agent
  K4 téléphone Éleveur (dont Mon argent, entretien, plusieurs bandes, fiche papier)
  K5 téléphone Agent + Opérateur + GPS + notifications + actions de l'agent
Étape 3 — Tests automatiques : tests/test_conformite.py, piloté par le fichier
  xlsx (lu avec openpyxl dans le test) :
  - pour chaque écran de bureau : connexion avec le profil, la page répond, le
    titre, le libellé exact du bouton de création, CHAQUE en-tête de colonne dans
    l'ordre, les boutons « Excel » et « Imprimer », la carte sur les accueils ;
  - pour chaque formulaire : les champs attendus ; les champs calculés et
    automatiques en lecture seule ; « Archiver » présent seulement si le profil
    a le droit ;
  - pour le terrain : les boutons et libellés principaux de chaque écran.
  Un écart justifié est déclaré dans une liste d'exceptions du test, avec sa
  raison : le test échoue sur tout écart non déclaré.
Étape 4 — Preuve visuelle
- docs/conformite/apres/ : capture de chaque écran de l'application.
- docs/conformite/rapport_conformite.html : pour chaque écran, la maquette à
  gauche, l'application à droite, l'état et la justification.
- docs/conformite/controle_rempli.xlsx : l'onglet « Contrôle » rempli
  (Conforme / Écart justifié / Non conforme, justification, chemin de la capture).

FIN DE LOT
docs/rapport_lotK.md, court : nombre d'écrans Conformes / Écarts justifiés /
Non conformes par sous-lot, liste des écarts avec leur raison, migrations
ajoutées, nombre de tests, « Déployé sur la démo : oui / non », version, et ce
que je dois regarder en priorité dans rapport_conformite.html.
Objectif : 0 « Non conforme » à la fin du lot.
```
