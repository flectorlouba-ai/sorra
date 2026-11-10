# Lot E-b — Fin du lot E (maquette, référence : `validees/maquettes_sorra_gps_terrain.html`, onglets 1 et 3)

## Nouvelle ferme sans réseau (agent, terrain)
- « Nouvel éleveur » → **« 🆕 Nouvelle ferme »** ouvre un écran gardé sur le téléphone (`/terrain/nouvelle-ferme`) :
  3 étapes (la personne, la ferme, le compte). La ferme : nom, village ou lieu-dit (liste des localités de la province,
  ou un nouveau nom), bâtiments (compteur) et places, bandes par an, position relevée automatiquement (± 30 m).
- Sans réseau : « 📶 Pas de réseau : la ferme sera envoyée plus tard ». Le téléphone donne un **numéro provisoire
  P-xxxx** et l'identifiant de la ferme. L'écran « Ferme P-0412 · ◷ En attente d'envoi » montre le compte de l'éleveur
  à noter et permet de **saisir pour l'éleveur** : compte rendu de visite, dépense (« J'ai payé »).
- Au retour du réseau, les envois partent **dans l'ordre** : la ferme d'abord (le serveur donne le vrai numéro, garde
  `P-0412` comme numéro de terrain), puis les saisies adressées à `P-0412`, que le serveur **rattache** à la vraie ferme.
- **Doublon sur le téléphone** : il connaît les fermes de l'agent (avec leur position) ; à moins de 200 m (paramètre) :
  « 🤔 Une ferme existe déjà tout près : EST-009, à 80 m. Est-ce la même ? » — Oui → ajouter l'éleveur à cette ferme ;
  Non → motif en pastilles (Voisin · Autre bâtiment · Autre exploitant · Autre).
- **Doublon sur le serveur** : il revérifie sur **toutes** les fermes ; doublon trouvé à l'arrivée → message dans
  « À vérifier » (« P-0415 (EST-014) ressemble à EST-021, à 60 m »).
- Avec du réseau, le même écran crée la ferme tout de suite et montre le compte à noter (écran existant).

## Correction de position : la punaise
- Dans « ✏️ Corriger à la main » : petite carte de la province (contours SVG existants, aucun fond en ligne), une
  **punaise à glisser** du doigt ; les coordonnées se remplissent et « Déplacée de 310 m » s'affiche. La saisie des
  coordonnées reste possible. Mêmes règles qu'en E-a (motif, quatre yeux au-delà de 1 km).

## Tables
- `ferme.numero_terrain` (P-xxxx, unique, facultatif) ; paramètre `gps.doublon_m` (200) ; liste « Raisons : ce n'est pas
  la même ferme ».

## Hors lot
- Villes et boutons + / − de la carte : refaits au lot R.
