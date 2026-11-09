# SORRA — règles d'ergonomie

> **À relire et à appliquer au début de CHAQUE lot.** Tout écran nouveau ou modifié est
> vérifié contre ce document avant d'être livré. Le rapport de chaque lot indique
> comment ces règles ont été respectées.

## A. Principe

Les **éleveurs sont les premiers utilisateurs**.

L'innovation (calculs, alertes, synchronisation, journal) travaille en coulisses. L'éleveur ne voit qu'un écran simple :
- utilisable **d'une main**, sur un **téléphone Android d'entrée de gamme** ;
- aussi naturel que WhatsApp.

**La saisie quotidienne prend moins de 30 secondes.**

## B. Écran d'accueil de l'éleveur : « Ma bande aujourd'hui »

| Zone | Contenu |
|---|---|
| En haut | Un **feu tricolore** (vert / orange / rouge) et **une phrase simple**, par exemple « Jour 23 · Vos poulets grossissent bien ». |
| Au centre | De **gros compteurs avec + et −** : *Morts aujourd'hui*, *Sacs d'aliment*, *Pesée le jour prévu*. |
| En bas | **Un seul gros bouton « Envoyer »**. |

## C. Les 7 fonctions retenues

Le lot de réalisation est indiqué entre parenthèses.

1. **Saisie de l'aliment en sacs** : le système convertit en kg avec le poids du sac. Ce poids est propre à chaque produit du catalogue des intrants (25 kg, 50 kg…), et non un paramètre unique (décision du lot 2). *(lot Bandes)*
2. **« À faire aujourd'hui »** : vaccins, pesées, fin de bande, calculés automatiquement et affichés à l'éleveur. *(lots Bandes et Sanitaire)*
3. **Déclaration sanitaire par photo** et par **pictogrammes** des signes observés, sans texte à écrire. *(lot Sanitaire)*
4. **Coches comme WhatsApp** à côté de chaque saisie : ⏳ en attente de réseau, ✓ envoyé. *(lot Hors ligne)*
5. **Message vocal** de l'éleveur à son agent technique. *(lot Sanitaire)*
6. **Comparaison qui encourage**, par exemple « Votre mortalité est meilleure que la moyenne de la province ». *(lot Tableaux de bord)*
7. **Saisie par l'agent technique pour le compte d'un éleveur**, signalée clairement dans le journal. *(lot Bandes)*

**Reporté, à ne pas coder** : connexion des éleveurs par numéro de téléphone et code PIN.

## D. Règles générales (validées)

- **Une seule action principale par écran** : un seul bouton mis en avant.
- **Trois clics maximum** pour toute action courante.
- **Chacun ne voit que ce qu'il a le droit de faire** : pas de bouton grisé, pas de tuile inutile.
- **Mots simples, aucun terme technique** à l'écran (pas d'UUID, de synchro, d'enregistrement…).
- **Les fonctions techniques restent invisibles** (journal, numérotation, hors ligne) : l'utilisateur n'en voit que le résultat.
- **Rien d'ajouté sans demande** : une option utile se propose dans le rapport du lot, elle ne se code pas d'office.

## E. Validation terrain

Avant de figer le lot Bandes, l'écran éleveur sera **testé par 3 à 5 vrais éleveurs**. Leurs retours priment sur les choix faits au bureau.

## Liste de contrôle d'un écran (à cocher dans chaque rapport de lot)

- [ ] Un seul bouton mis en avant ?
- [ ] L'action courante se fait en 3 clics au plus ?
- [ ] Aucun bouton ni tuile que l'utilisateur ne peut pas utiliser ?
- [ ] Aucun mot technique visible ?
- [ ] Utilisable d'une main sur un écran de 360 px de large, sans défilement horizontal de la page ?
- [ ] Écran éleveur : saisie du jour en moins de 30 secondes ?
- [ ] Rien d'ajouté qui n'ait été demandé ?
