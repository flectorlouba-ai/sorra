# SORRA — Lot 17 : écrans du vétérinaire (mode autonome)

Lot construit en mode autonome. Les choix faits seul sont dans `docs/decisions_autonomes.md` (17-x).
Charte YL.1. Chaque écran est à 2 clics de l'accueil et vérifié à 360 px. L'interface de l'éleveur ne change que pour le blocage (C).

## A. Signalements, triés par gravité (tuile « Signalements »)

- **Gravité**, de 1 à 4 points :
  - 3 pour une mortalité anormale (feu rouge) ; sinon 2 pour une déclaration de 10 poulets ou plus, 1 au-dessous ;
  - **+1** si personne n'a répondu depuis plus de 24 h.
- Chaque ligne montre une pastille : « grave » (4), « à voir vite » (3), « à voir » (2 ou moins).
- Tri : gravité décroissante, puis le plus ancien d'abord (il attend depuis plus longtemps).
- Filtres existants gardés (statut).
- La tuile compte les signalements ouverts (existant).

## B. Diagnostics (fiche du signalement)

- Carte **« Diagnostic »** sur la fiche du signalement. Réservée au vétérinaire, qui l'écrit et la modifie ; l'ADMIN la lit.
  - **Maladie suspectée** : liste `maladies_suspectees` (provisoire), ou « Autre ».
  - **Prélèvement envoyé au laboratoire** : oui ou non.
  - **Observations** : texte libre.
- **L'agent ne voit jamais le contenu.** Sa fiche ferme dit seulement « diagnostic posé le … ». La DGE ne le voit pas non plus.
- Chaque diagnostic est daté et inscrit au journal (automatique). Un nouveau diagnostic s'ajoute aux précédents : historique.

## C. Surveillance et blocage des sorties

- **Écran « Surveillance »** (nouvelle tuile du vétérinaire) :
  - les bandes **bloquées** (motif, depuis quand, par qui) ;
  - les **sorties reçues après le blocage**, à vérifier ;
  - un formulaire **« Bloquer les sorties »** : bande en cours de sa province, motif obligatoire.
- Le blocage se pose aussi depuis la fiche du signalement (« ⛔ Bloquer les sorties de cette bande »).
- **Effets du blocage** :
  - le serveur **refuse** toute sortie de la bande : « ⛔ Le vétérinaire a bloqué les ventes de cette bande » ;
  - **pas de lot, pas de QR** ;
  - l'éleveur voit le message en rouge sur son accueil et à la place du formulaire Sortie, avec **📞 le vétérinaire**. La page gardée sur le téléphone montre le même message, donc **aucune sortie n'est possible sans réseau** après le blocage.
- **Sortie faite sans réseau AVANT de savoir, reçue APRÈS le blocage** : elle n'est **pas perdue**. Elle est enregistrée **mise de côté, à vérifier**, sans lot ni QR, et elle apparaît dans « Surveillance ». Le vétérinaire la marque « Vérifiée » (avec une note).
- **Levée** : seulement par **un vétérinaire** (pas l'agent, pas la DGE, pas l'ADMIN), avec un motif obligatoire. Blocage et levée sont inscrits au journal.

## D. Paramètres sanitaires (quatre yeux)

- **Écran « Paramètres sanitaires »** (tuile du vétérinaire) : les seuils sanitaires (`sante.*`, `bandes.seuil_*`, écart à la courbe, courbe de poids).
- « Proposer » avec un motif. Un **autre** vétérinaire, la DGE ou l'ADMIN approuve (mécanisme du lot 15).
- Le calendrier vaccinal passe déjà par les quatre yeux (lot 15).

## E. Recherche de lots, amont et aval (tuile « Recherche de lots »)

- **On cherche** un numéro de lot (QR), de bande, de livraison, ou le nom d'un fournisseur de poussins.
- **Amont** : ferme, bande, livraisons de poussins (fournisseur, date), aliments reçus, vaccins et traitements de la bande.
- **Aval** : sorties de la bande (date, nombre, destinataire), avec leurs lots et le nombre de lectures du QR.
- Pour un fournisseur ou une livraison : **toutes les bandes** qui ont reçu ces poussins, puis leur aval.
- **Export CSV** du résultat.
- **Chaque recherche est inscrite au journal** (« Recherche de lots » : ce qui a été cherché), et chaque export aussi.
- Ouverte au vétérinaire (sa province), à la DGE et à l'ADMIN (national).
