# Lot R — nouvelle version ordinateur, tous profils

- **Gabarit unique** (`_base.html`, branche ordinateur) : zone titre (logo, fonctionnalité ouverte, personne + profil,
  ❓ Aide, ⏻), trait bleu, sans bande kente ; à gauche les **fonctionnalités 2 par ligne** (actif en orange, pastille
  rouge), puis le périmètre ; à droite barre (sous-titre, « ＋ … »), tableaux et graphiques.
- **Tableau de bord** de chaque profil à `/` : indicateurs (lot C), carte du périmètre (bulle au survol, halo ⚠️),
  « ⚠️ Fermes en alerte » (raisons selon le profil) + « 🔔 Alertes » (lot 15), 3 courbes 52 semaines, synthèse.
- **Tableaux** : tri par en-tête, pagination au-delà de 50 lignes, « 🖨️ Imprimer » (A4 paysage, en-tête SORRA) et
  « ⬇️ Excel » (lignes affichées, toutes colonnes), tous deux journalisés. Élevages : colonnes de la maquette.
- **Fenêtres** : jamais plus hautes que l'écran, titre et pied fixes, 2 colonnes puis 1 sous 700 px.
- **Responsive** : aucun débordement de 360 à 1 920 px (test navigateur) ; menu en haut et défilant sous 900 px.
- **Bascule** : ≥ 900 px → version ordinateur (une fois) ; « Version terrain » (📱) dans la zone titre, « Version
  ordinateur » dans Moi. Le téléphone de l'éleveur, de l'agent et de l'opérateur ne change pas (test navigateur).
- BCEG et MAEDR : gabarit + accueil simple (contenu au lot M). Anciennes adresses redirigées.
- Tests : `tests/test_lotR.py` (11), `tests/test_lotR_navigateur.py` (6, Playwright) ; captures `docs/captures/lotR/`
  (chaque profil à 1440, 1024 et 360 px, fenêtre à 1024 × 560, téléphones inchangés).

## À tester
- **Ordinateur, `dge`, `veto`, `admin`, `aninf`** : l'accueil (boutons à gauche, carte, alertes, courbes), chaque bouton,
  « 🖨️ Imprimer » et « ⬇️ Excel » sur Élevages ; réduire la fenêtre sous 900 px : le menu passe en haut.
- **Ordinateur, `eleveur` et `agent.est`** : la version ordinateur s'ouvre d'elle-même ; 📱 ramène au terrain.
- **Téléphone, `eleveur`, `agent.est`, `abattoir.owendo`** : rien n'a changé.

Déployé sur la démo : voir `docs/rapport_suite.md`.
