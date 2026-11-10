# Lot T — Ajouts terrain (maquette ; référence `validees/maquettes_sorra_terrain_ajouts.html`)

Rien de ce qui existe ne change : on ajoute.

## A. Notifications (cahier § 7.6)
- **Web Push** de l'application installée, `pywebpush` (bibliothèque Python), clés VAPID dans le `.env` du serveur
  (`SORRA_VAPID_PRIVEE`, `SORRA_VAPID_PUBLIQUE`, `SORRA_VAPID_CONTACT`) — jamais dans git. Sans clés : les écrans
  existent, les envois sont ignorés et le journal le dit.
- Tables : `abonnement_push` (utilisateur, appareil, endpoint, clés p256dh / auth, créé le, dernier envoi, actif) ;
  `preference_notification` (utilisateur, type, actif, heure du rappel) ; `notification` (destinataire, type, titre,
  texte court sans donnée personnelle, lien, créée le, envoyée le, résultat) — c'est le journal des envois.
- **Demande d'autorisation au bon moment** : après la première saisie réussie (bandeau « Gardé ✓ » / « Enregistré ✓ »),
  une carte « 🔔 Être prévenu quand il faut saisir ? » → bouton ; jamais au premier lancement.
- **👤 Moi → « 🔔 Mes notifications »** : interrupteurs par type ; heure du rappel (17 h / 18 h / 19 h) ; les alertes
  sanitaires ne se coupent pas.
- Qui reçoit quoi : éleveur (saisie oubliée à l'heure choisie, pesée en retard, vaccin demain, réponse du vétérinaire,
  livraison à confirmer, ventes bloquées) ; agent (feu rouge, ferme sans saisie depuis 2 jours, deux versions à
  trancher, action en retard, visite demain) ; opérateur (lot en route, lot libéré ou refusé) ; vétérinaire et DGE
  (nouveau signalement, alerte sanitaire, écart à 48 h, paramètre à approuver).
- Envoi : commande `notifications-envoyer` (cron toutes les 15 min) qui calcule les événements du moment et envoie ce
  qui n'a pas déjà été envoyé (clé d'unicité type + objet + jour) ; envoi immédiat pour les alertes sanitaires (à la
  création d'une alerte). Un toucher ouvre le bon écran (après connexion) : le lien est dans la notification.
- Le service worker reçoit `push` et `notificationclick`.

## B. Actions de l'agent (téléphone)
- Accueil : ligne d'état « 🎯 N action(s) en retard » et encadré « 🎯 Mes actions » sous les tuiles (les 8 tuiles ne
  changent pas).
- Écran `/terrain/actions` : les plus urgentes en haut, phrases (« ⏰ en retard de 2 jours », « pour demain »),
  demandeur, ferme ; « ＋ Nouvelle action » (feuille).
- Toucher une action = feuille : Pas commencé / En cours / ✓ Fait, « Ce que j'ai fait », 📷 photo, Enregistrer ;
  hors ligne (file d'attente).

## C. Fiche papier de la semaine (pilote)
- « Ma bande » (éleveur) et fiche ferme (agent) : « 🖨️ Imprimer la fiche de la semaine » → PDF A4 : en-tête SORRA
  (ferme, éleveur, bande, bâtiment, semaine, âge, effectif au début), QR de la bande (vers la fiche), tableau 7 jours
  (jour, âge, morts, aliment, sacs, pesée, sorties, observations, « Saisi ✓ »), vaccins prévus déjà écrits, total,
  signatures, rappel « écrire 0 s'il n'y a eu aucun mort ». Bande de ponte : colonne « œufs ramassés » (lot F).
