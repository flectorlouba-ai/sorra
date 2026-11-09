# SORRA — Lot 8 : espace éleveur ludique, style « illustré doux »

> Description fournie par le propriétaire le 09/11/2026. Aucun fichier
> `maquettes_sorra_eleveur.html` n'existant, elle sert de référence visuelle.
> Aperçu indicatif construit à partir d'elle : `docs/maquettes/apercu_lot8.html`.

## Périmètre (décisions validées)

- Style « illustré doux » UNIQUEMENT pour l'espace ÉLEVEUR et la PAGE PUBLIQUE du QR code.
- Tous les autres profils gardent la charte bleu nuit actuelle (sobre). L'agent qui saisit « pour l'éleveur » reste dans la charte sobre.
- Idées ludiques retenues :
  1. le poulet qui réagit ;
  2. la bande qui grandit ;
  3. l'envoi agréable ;
  4. la série de jours ;
  6. le bilan en étoiles ;
  7. les messages vivants.
- Pas de badges, pas de classement, pas de son.

## A. Charte « illustrée douce »

Feuille dédiée (`static/css/eleveur.css`), chargée seulement pour l'éleveur et la page publique.

**Couleurs** (variables CSS) :

| Nom | Code | Usage |
|---|---|---|
| nuit | `#1b2a5e` | textes |
| bleu | `#2a7de1` | actions |
| soleil | `#f7c948` | |
| prairie | `#2fa36b` | tout va bien, bouton Envoyer |
| orange | `#f08a24` | attention |
| rouge | `#e5484d` | alerte |
| crème | `#fbf8f2` | fond de page |
| gris | `#6b7594` | textes secondaires |

**Cartes** : pas de contours épais. Cartes blanches, bordure très fine (`#edf0f6`), ombre légère (`0 2px 10px rgba(27,42,94,.08)`), coins arrondis de 16 à 18 px.

**Boutons** : plats et arrondis.
- Bouton principal plein, avec une ombre douce de sa couleur :
  - vert pour « Envoyer » ;
  - bleu pour les autres actions ;
  - rouge pour « Envoyer au vétérinaire ».
- Boutons secondaires blancs, bordure fine, texte bleu.
- Compteurs + / − ronds de 44 px : « − » gris clair, « + » bleu plein.

**Police** : une seule, ronde, Nunito (licence libre OFL), avec les fichiers en local dans `static/polices` (aucun chargement Internet) et des polices de secours sans empattement.

**En-tête** : dégradé bleu (`#2a7de1` → `#1b4fae`), logo poulet et « SORRA » en blanc, « Bonjour {Prénom} ! 👋 » en dessous.

**Émojis** autorisés comme pictogrammes simples : 📦 ⚖️ 🚚 🩺 💉 📋 🔥 💪 🎤 📞 📵 🐣.

## B. Le poulet mascotte (idée 1)

Même personnage que le logo SORRA, au trait fin, en SVG local.

| Feu | Expression |
|---|---|
| Vert | content : yeux en sourire, joues roses |
| Orange | inquiet : yeux ronds, sourcils froncés, goutte |
| Rouge | malade : yeux en croix, corps rosé, thermomètre |
| Gris | content, yeux fermés |

Il apparaît :
- dans la carte du haut de « Ma bande aujourd'hui » (environ 78 px) ;
- sur l'écran « Bien reçu ! » (environ 130 px) ;
- sur la connexion, le bilan de fin de bande et la page publique.

## C. Animations (idées 2 et 3)

Animations légères, en CSS seulement (transform, opacity).

- **« Votre bande grandit »** : barre jaune de J0 à la durée de référence, avec un petit poussin dessiné qui avance au-dessus selon l'âge. Libellés : « 🐣 Jour 0 · À mi-chemin ! · Jour 45 ».
- **Compteurs** : le chiffre grossit brièvement à chaque appui ; vibration légère si possible (`navigator.vibrate`), sans erreur sinon.
- **Après « Envoyer »** :

  | Situation | Ce qui s'affiche |
  |---|---|
  | Feu vert | écran « Bien reçu ! » pendant environ 2 s : le poulet fait 2 petits sauts, la série du jour, quelques petites étincelles colorées (pas de pluie de confettis) |
  | Feu orange ou rouge | ni saut ni étincelle, seulement « Envoyé ✓ — Votre agent est prévenu » |
  | Hors ligne | « ◷ Sera envoyé dès que le réseau revient » |

- Tout est coupé si l'appareil demande de réduire les animations (`prefers-reduced-motion`).

## D. Série de jours (idée 4)

- Pastille « 🔥 N jours » : nombre de jours consécutifs avec une saisie dans la bande en cours. Les saisies hors ligne comptent à leur date.
- Un jour manqué remet le compteur à 0, avec un message encourageant.
- Le record personnel est gardé, et « Nouveau record personnel ! » s'affiche quand il est battu.

## E. Bilan en étoiles (idée 6)

À la clôture, 1 à 3 étoiles, jamais 0. Les seuils sont dans les Paramètres, marqués « à valider par les vétérinaires ».

| Étoiles | Règle de départ | Phrase |
|---|---|---|
| 3 | mortalité ≤ 3 % ET indice de consommation ≤ 1,7 | « Votre meilleure bande ! » |
| 2 | mortalité ≤ 5 % | « Bonne bande ! » |
| 1 | sinon | « La prochaine sera meilleure » |

Les étoiles sont visibles dans l'historique des bandes.

## F. Messages vivants (idée 7)

- « Bonjour {Prénom} ! ».
- Après une pesée : « 💪 +210 g en 7 jours » (écart avec la pesée précédente).
- Jamais de message joyeux quand le feu est orange ou rouge.

## G. Les 14 écrans de l'éleveur

Les écrans existants sont adaptés, pas dupliqués.

1. **Connexion**
   - fond en dégradé bleu, poulet, « SORRA », sous-titre ;
   - champs Identifiant et Mot de passe (avec l'œil) ;
   - bouton vert « Se connecter » ;
   - « Mot de passe oublié ? Appelez votre agent. »
2. **Livraison à confirmer** (en haut de l'accueil)
   - date et fournisseur, quantités en gros ;
   - compteur « Poussins morts à l'arrivée » ;
   - bouton vert « ✓ Tout reçu », bouton secondaire « J'ai reçu moins » ;
   - bandeau sombre « ✓ Reçue — merci ! · Annuler (10) ».
3. **J'ai reçu moins**
   - compteurs préremplis par produit (« livrés : 40 ») ;
   - raison en grosses cases (Manquant / Abîmé / Autre) ;
   - bouton bleu « Envoyer ».
4. **Ouvrir une bande**
   - « 🐣 Nouveaux poussins » ;
   - carte « 997 poussins — 1 000 reçus − 3 morts à l'arrivée » ;
   - bâtiments en grosses cases (les indisponibles grisés) ;
   - poids moyen facultatif ;
   - bouton vert « Commencer la bande » ;
   - « Fin prévue le … ».
5. **Ma bande aujourd'hui**
   - carte poulet avec « Jour 23 · B1 », la phrase et les poulets présents ;
   - carte « Votre bande grandit » avec la série 🔥 ;
   - encadré jaune pâle « 📋 À faire aujourd'hui » ;
   - compteurs Morts et Sacs d'aliment (nom de l'aliment, poids du sac) ;
   - gros bouton vert « Envoyer ✓ » ;
   - boutons secondaires « ⚖️ Peser » et « 🚚 Sortie ».
6. **Bien reçu !**
   - grand poulet, « Bien reçu ! », « 🔥 24 jours d'affilée » ;
   - pastille « Nouveau record personnel ! » si c'est le cas ;
   - les 2 dernières saisies avec ✓.
7. **Pesée**
   - compteur « Poulets pesés » ;
   - « Poids total sur la balance » en gros ;
   - carte « Poids moyen 980 g — Dans la courbe ✓ · 💪 +210 g en 7 jours » ;
   - bouton bleu.
8. **Sortie**
   - « Pour qui ? » en grosses cases (Abattoir / Vente / Autre) ;
   - destinataire, compteur du nombre, poids total ;
   - bouton bleu ;
   - « Il restera N poulets dans la bande ».
9. **Poulet malade**
   - 1 à 3 photos (case « + ») ;
   - « Qu'avez-vous vu ? » en grille de pictogrammes à toucher (sélection en rouge) ;
   - compteur « Poulets touchés » ;
   - bouton secondaire « 🎤 Ajouter un message vocal » ;
   - bouton rouge « Envoyer au vétérinaire ».
10. **Quand ça ne va pas** (feu rouge)
    - carte rosée avec le poulet malade ;
    - « Beaucoup de morts aujourd'hui » et « Votre agent et le vétérinaire sont prévenus » ;
    - bouton rouge « 🩺 Signaler un poulet malade » et bouton « 📞 Appeler mon agent » ;
    - encadré « 📋 Conseil ». Le texte du conseil est un PARAMÈTRE modifiable (ADMIN, VETO), marqué « à faire valider par les services vétérinaires ». Texte de départ : « Isolez les poulets malades et ne vendez pas avant l'avis du vétérinaire. »
11. **Vaccin du jour**
    - vaccin en gros, mode et nombre de poulets ;
    - compteur des flacons ;
    - bouton vert « ✓ C'est fait » ;
    - bouton secondaire « Pas encore fait » : le vaccin reste dans « À faire ». Passé la date prévue + 2 jours, il devient « en retard » et l'agent est prévenu ;
    - « Stock à la ferme : N flacons ».
12. **Bande terminée**
    - poulet content, étoiles, phrase ;
    - 4 chiffres : mortalité, poids moyen, poulets vendus, série record ;
    - « Voir mes bandes passées ».
13. **Pas de réseau**
    - bandeau orange pâle « 📵 Pas de réseau — vos saisies sont gardées sur le téléphone » ;
    - liste des saisies avec « ◷ en attente » / « ✓ envoyé ».
14. **Page publique du QR code**
    - bandeau vert avec le poulet, « Produit au Gabon », « Consommons gabonais » ;
    - carte « Élevé par · Ferme · Localité · Province · Sorti de la ferme le … · Lot … » ;
    - « Ce QR code n'est pas un certificat sanitaire » ;
    - petit « SORRA » ;
    - aucun nom de personne ni téléphone.

## H. Règles techniques

- Aucune bibliothèque d'animation ; l'ensemble reste fluide sur un Android d'entrée de gamme.
- Tout fonctionne hors ligne : polices, SVG et CSS sont mis en cache par le service worker.
- `docs/ergonomie.md` reçoit une section « Charte illustrée douce (espace éleveur) ».

## Tests demandés

Tests automatiques :
- étoiles ;
- série et record ;
- expression du poulet selon le feu ;
- pas d'étincelles en orange ou en rouge ;
- « Pas encore fait » et retard du vaccin ;
- texte du conseil paramétrable ;
- feuille de style chargée seulement pour l'éleveur et la page publique.

Vérification au navigateur en 360 px et sur ordinateur. Liste des tests à faire par le propriétaire. Commit dédié. Pas de déploiement : on déploiera tout ensemble avec le nom de domaine.
