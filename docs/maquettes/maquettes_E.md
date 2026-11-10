# Lot E — Carte, GPS et tournées (maquette, mode autonome)

Le temps de la nuit ne permet pas tout le lot : il est livré en **deux parties**. Cette nuit, **E-a** (positions
fiables sur le terrain, contrôle des visites, carte de pilotage enrichie). **E-b** reste à faire (voir en bas).

## Table
- **position_ferme** (nouvelle, aucune position n'est jamais écrasée) : ferme, latitude, longitude, précision (m),
  relevée le, auteur, appareil, hors ligne oui / non, origine (GPS · MANUELLE · REPRISE), motif, province trouvée,
  distance à la province (km), à vérifier oui / non. La position « en vigueur » reste recopiée sur la ferme
  (latitude, longitude, précision, date, source) : rien ne change pour les écrans existants.
- **ferme** : `position_a_verifier` (oui / non).
- **visite** : `precision_m`, `distance_m` (recalculée par le serveur), `motif_distance`.
- Reprise : chaque ferme qui a déjà une position reçoit une ligne d'historique d'origine « REPRISE » (approximative si
  elle venait de la saisie à la main).
- Paramètres : précision exigée 30 m, distance de visite 1 km, correction à la main au-delà de 1 km → quatre yeux,
  tolérance de province 5 km.

## Écrans terrain (agent)
- **E1** Fiche de la ferme sans position : encadré orange « 📍 Position pas encore relevée — placez-vous dehors,
  devant le bâtiment principal » + gros bouton « Relever la position ici ».
- **E2** Écran « Relever la position » (feuille) : précision en clair (« ± 85 m » puis « ± 7 m ✓ ») et barre ;
  « Garder cette position » actif seulement sous ± 30 m. Sans réseau, l'envoi est gardé sur le téléphone.
- **E3** Contrôle de province (tolérance 5 km) : vert si cohérent ; sinon « ⚠️ Cette position est dans le
  Haut-Ogooué — la ferme est notée dans l'Estuaire (12 km) » + « Relever à nouveau » / « Garder quand même » (motif
  en pastilles) → la ferme passe « position à vérifier » chez la DGE. L'agent ne change jamais la province.
- **E4 (partie a)** Correction à la main : coordonnées tapées + motif en pastilles ; marquée « corrigée à la main » ;
  ancienne position gardée ; au-delà de 1 km → quatre yeux (DGE / ADMIN). La punaise à glisser sur la carte est en E-b.
- **E5** Historique des positions (fiche de la ferme, bureau) avec l'origine.
- **E6** Visite : « 📍 Vous êtes à 120 m de la ferme ✓ » ; au-delà de 1 km « Vous êtes à 4,2 km » + motif en
  pastilles (le compte rendu part quand même) ; « Position non relevée » si refusée. Distance recalculée par le serveur.
- **E7** Ma tournée : distances, ordre proposé par proximité (voisin le plus proche en partant de l'agent),
  « 🧭 Y aller », « Itinéraire complet » (lien vers l'application de cartes du téléphone), « 📍 à relever sur place ».
- **E9** Éleveur, Mon compte : « 📍 Position relevée ✓ le … » ou « Votre agent relèvera la position à sa prochaine visite ».

## Écrans de pilotage (bureau)
- **E10 (partie a)** Carte : couleur des fermes selon un indicateur au choix (alertes, mortalité, régularité,
  atteinte de la cible), filtre programme, zoom par province (existant), infobulle au survol (mortalité, effectif,
  atteinte, dernière saisie, alerte), clic → fiche, encadrés « À localiser (n) » et « Position à vérifier (n) »,
  positions approximatives ou corrigées en pointillé.
- **E11** DGE, tuile Agents : contrôle des visites (distance à la ferme, précision, explication), filtres « position
  éloignée » / « sans position », taux de visites confirmées par agent.
- **E12** Page publique du QR : zone d'origine (localité, département, province), jamais le point exact.

## E-b, à faire
- E4 : punaise à glisser sur la petite carte.
- E8 : nouvelle ferme sans réseau (numéro provisoire P-xxxx, rattachement, doublon à moins de 200 m).
- E10 : villes principales, boutons + / −, résumé de la province au survol, biosécurité comme indicateur.
