# Lot T — Ajouts terrain : notifications, actions de l'agent, fiche papier

Rien de l'existant ne change sur le téléphone : on ajoute.

- **A. Notifications Web Push** (`pywebpush`, clés VAPID dans le `.env` du serveur, jamais dans git). Tables
  `abonnement_push`, `preference_notification`, `notification` (journal des envois, texte court sans donnée
  personnelle). Carte « 🔔 Être prévenu quand il faut saisir ? » après une saisie réussie ; **👤 Moi → « 🔔 Mes
  notifications »** (interrupteurs par type, heure du rappel 17 / 18 / 19 h, alertes sanitaires non désactivables) ;
  bouton 🔔 dans la zone titre en version ordinateur. Qui reçoit quoi par profil (éleveur, agent, opérateur,
  vétérinaire, DGE) ; commande `flask notifications-envoyer` (cron toutes les 15 min) ; envoi immédiat à la création
  d'une alerte sanitaire ; service worker `push` / `notificationclick` (un toucher ouvre le bon écran). Remplace les
  rappels du lot 14.
- **B. Actions de l'agent sur le téléphone** : ligne d'état « 🎯 N action(s) en retard », encadré « 🎯 Mes actions »
  sous les tuiles (inchangées), écran `/terrain/actions` (les plus urgentes en haut, phrases, demandeur, ferme),
  feuille Pas commencé / En cours / ✓ Fait + « Ce que j'ai fait » + 📷 photo, « ＋ Nouvelle action » ; hors ligne.
- **C. Fiche papier de la semaine** (pilote) : « 🖨️ Imprimer la fiche de la semaine » sur Ma bande (éleveur) et sur la
  fiche ferme (agent) → PDF A4 avec QR, tableau des 7 jours, vaccins prévus, signatures ; impression journalisée.
- Migration 0029 (+ paramètres `notifications.rappel_saisie_heure`, `notifications.ferme_sans_saisie_jours`) ;
  `requirements.txt` : `pywebpush==2.5.0` ; tests `tests/test_lotT.py` (9) ; captures `docs/captures/lotT/`.

## À faire par le propriétaire (serveur de démo)
1. Générer les clés une fois : `venv/bin/python deploiement/outils/cles_vapid.py` affiche les trois lignes à coller
   dans `/var/www/performyl2-demo/.env` (`SORRA_VAPID_PRIVEE`, `SORRA_VAPID_PUBLIQUE`, `SORRA_VAPID_CONTACT`), puis
   `systemctl restart performyl2-demo`. Sans ces clés, les écrans existent mais rien n'est envoyé.
2. Cron (utilisateur du service) : `*/15 * * * * cd /var/www/performyl2-demo && venv/bin/flask notifications-envoyer`.

## À tester
- **Téléphone (iPhone, application installée sur l'écran d'accueil), `eleveur`** : faire la saisie du jour → carte
  « 🔔 Être prévenu ? » → Oui → autoriser. Moi → « 🔔 Mes notifications » : couper « Pesée en retard », choisir 19 h,
  Enregistrer ; « Ventes bloquées » reste grisé. Ma bande → « 🖨️ Imprimer la fiche de la semaine » → PDF.
- **Téléphone, `agent.est`** : accueil → « 🎯 Mes actions » (créer d'abord une action pour cet agent depuis
  l'ordinateur `dge`, échéance passée) → ligne « 🎯 1 action en retard » → toucher → En cours, « Ce que j'ai fait »,
  photo → Enregistrer ; « ＋ Nouvelle action ». Mode avion : la feuille s'enregistre et part au retour du réseau.
  Mes fermes → une ferme → « 🖨️ Imprimer la fiche de la semaine ».
- **Ordinateur, `veto` / `dge`** : 🔔 dans la zone titre → Mes notifications (style bureau), alertes grisées.
- **Serveur** : `flask notifications-envoyer` affiche « n créée(s), m envoyée(s) » (et « clés VAPID absentes » sans clés).

Déployé sur la démo : voir `docs/rapport_suite.md`.
