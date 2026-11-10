# Lot R — Nouvelle version ordinateur, tous profils (maquette ; référence `validees/maquette_sorra_bureau.html`)

## Principe
- Sur **ordinateur**, tous les profils partagent le même gabarit (`_base.html` en style bureau) : zone titre en haut
  (logo, titre de la fonctionnalité ouverte, personne + profil, ❓ Aide, ⏻), trait bleu, **sans bande kente** ; à gauche,
  les **boutons des fonctionnalités 2 par ligne** (dégradés YL.1, actif en orange, pastille rouge), puis le périmètre ;
  à droite, barre (filtres, recherche, « ＋ … »), graphiques et tableaux.
- Le **téléphone** de l'éleveur, de l'agent et de l'opérateur ne change pas (style terrain). Bascule automatique
  ≥ 900 px (une fois, mémorisée dans la session) et lien « Version terrain / Version ordinateur » dans Moi.
- **Routes, services, règles et droits existants réutilisés** : ce lot change l'organisation et la présentation.

## Registre des fonctionnalités (`app/services/bureau.py`)
Un dictionnaire par profil : (clé, icône, nom, point d'entrée existant, compteur, bouton « ＋ »). Les anciennes tuiles
(`accueil.TUILES`) fournissent les compteurs. Le bouton actif = la fonctionnalité dont le point d'entrée appartient au
même groupe d'adresses que la page ouverte.

## Tableau de bord (`/bureau`, nouvel accueil de tous les profils bureau)
Cartes d'indicateurs (lot C, `mes_indicateurs`) → carte du Gabon (lot E, `pilotage.carte` zoomée sur le périmètre) +
« ⚠️ Fermes en alerte » (raisons selon le profil) → 3 courbes hebdomadaires (lot C) → tableau de synthèse
(fermes du périmètre). Les anciennes adresses d'accueil en tuiles redirigent vers `/bureau`.

## Tableaux
`static/js/tableaux.js` sur chaque tableau de bureau : tri par clic sur l'en-tête, pagination au-delà de 50 lignes,
« 🖨️ Imprimer » (aperçu A4 paysage avec en-tête SORRA, titre, filtres, date, nom ; `window.print`) et « ⬇️ Excel »
(.xlsx des lignes affichées, toutes colonnes, construit par le serveur à partir des lignes envoyées — déjà filtrées par
le périmètre — et journalisé). L'impression est journalisée par un appel au serveur.

## Fenêtres
`.modal-box` : titre et pied fixes, corps qui défile, 2 colonnes (`form-grid`) sur ordinateur, 1 sous 700 px, jamais
plus haute que l'écran (`max-height: calc(100vh - 32px)`).

## Écarts et choix
- Tableaux « plus fournis » : Élevages reçoit les colonnes de la maquette ; les autres tableaux gardent leurs colonnes
  existantes (chaque colonne sans donnée réelle est notée dans `decisions_autonomes.md`).
- BCEG, MAEDR : gabarit + accueil simple (contenu au lot M).
- « Enrôlement » (agent) : renvoie à « Nouvelle ferme » existante ; « Profils et droits » (admin) : matrice des droits
  en lecture (générée depuis les routes) ; « Diagnostics » (vétérinaire) : alertes avec diagnostic ; « Seuils
  sanitaires » : paramètres sanitaires existants ; « Validations sensibles » : approbations existantes.
