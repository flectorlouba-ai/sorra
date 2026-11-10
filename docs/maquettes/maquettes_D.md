# Lot D — Bilan de bande, rapports standards, plans d'actions (maquette, mode autonome)

## A. Bilan de bande (PDF)
- Reprend et enrichit `rapports_pdf.rapport_fin_bande` (existant) : identité (ferme, bâtiment, bande, chair / ponte,
  souche, dates), effectifs (mis en place, morts, sortis, viabilité), indicateurs (mortalité, IC, GMQ, poids de sortie,
  courbe de croissance dessinée vs référence), intrants consommés par article et origine (Programme / Externe),
  vaccins et traitements, sorties et lots (numéro, QR en texte), économie (ventes, dépenses, marge, coût au kg : jamais
  pour le vétérinaire), visites et biosécurité.
- Généré **à la clôture** (fichier gardé dans `instance/rapports/bandes/`) et à la demande pour une bande clôturée.
- Téléphone éleveur : « Ma bande » → « 📄 Bilan de la bande » (bandes clôturées, dans Mes bandes).
  Ordinateur : Mes bandes / Élevages → fiche de la bande → bouton « 📄 Bilan (PDF) ».

## B. Rapports standards (PDF)
- **Ferme (mensuel)** : bandes du mois, indicateurs, visites, biosécurité, actions de la ferme.
- **Agent (mensuel)** : ses fermes, alertes, visites faites / prévues, régularité, écarts, ses actions.
- **National et provincial** : existant (lot 18), complété : production vs 100 000 t, atteinte par province et cohorte,
  traçabilité, classement, actions.
- Table `rapport` (remplace `rapport_mensuel` sans la supprimer) : type (NATIONAL, PROVINCE, FERME, AGENT, BANDE),
  période, cible (province / ferme / agent / bande), fichier, généré le, par, nombre de pages.
- Génération automatique le 1ᵉʳ du mois par la commande `rapports-mensuels` existante (étendue), et à la demande.
- Liste dans « Rapports » (DGE) et sur l'accueil ordinateur de l'agent ; téléchargement ; journal.

## C. Plans d'actions
- Table `action` : numéro (ACT-2026-000001), intitulé, origine (ALERTE, VISITE, RAPPORT, ARBITRAGE, MANUEL) + lien
  (table, id), périmètre (ferme / province / national), responsable, créée par, échéance, priorité (HAUTE, MOYENNE,
  BASSE), avancement %, état calculé (à faire, en cours, faite, en retard), commentaire et photo de clôture ; archivage.
- DGE : fonctionnalité « Plans d'actions » (tableau, « ＋ Nouvelle action » en fenêtre, affectation, suivi).
  Agent : « 🎯 Mes actions » sur son accueil ordinateur, création de ses propres actions.
- « Créer une action » depuis une alerte sanitaire, une visite, un arbitrage, un rapport (bouton).
- Action en retard : sur le tableau de bord de son responsable, pastille sur le bouton.
- Journal : création, modification, clôture (automatique + détail).

## Écarts et choix
- La photo de clôture est stockée comme les photos existantes (`sante._enregistrer`).
- Le rapport provincial = le rapport national filtré sur la province (même modèle).
