# Lot G — Mon argent sur 12 mois, mini bilan, fiscalité estimée, rappels

Le cœur du lot a été livré au sous-lot K4 (écran de la maquette `maquette_mon_argent.html`) ; ce lot termine les rappels.

- **12 mois** : sélecteur Ce mois / Cette bande / 12 mois ; Gagné · Dépensé · Bénéfice ; graphique mois par mois (SVG,
  barres gagné / dépensé, ligne du bénéfice).
- **📄 Mon bilan (PDF)** : 2 pages A4 paysage au modèle `SORRA_Mon_bilan_2026_exemple.pdf` (identité, 4 chiffres, graphique,
  « ce qu'il faut retenir », fiscalité ; page 2 : détail par mois et par poste) ; écran « Mon bilan » (⬇️ Enregistrer, ⤴ Partager,
  « À montrer à la banque, au comptable ou à la DGE ») ; export journalisé.
- **🏛️ Ma fiscalité** : chiffre d'affaires de l'année, régime estimé (ISL < `fiscalite.seuil_isl_fcfa` = 30 M ; régime simplifié
  < `fiscalite.seuil_rsi_fcfa` = 60 M ; réel au-delà), jauge et « proche du seuil » dès 80 %, mention « Estimation indicative,
  seuils réglables, à valider avec la DGI. SORRA ne remplace pas un comptable. » Seuils = paramètres sensibles (quatre yeux).
- **📅 Rappels** : déclaration annuelle (date `fiscalite.rappel_declaration`, 30/04 par défaut) rappelée 30 jours avant, et seuil
  approché ; affichés dans Ma fiscalité et envoyés en notification (type « 🏛️ Rappels fiscaux », une fois par an, désactivable
  dans 🔔 Mes notifications).
- **Qui voit** : l'éleveur ; l'agent, la DGE, l'administrateur pour une ferme du périmètre ; la BCEG avec l'accord de l'éleveur ;
  jamais le vétérinaire (403).
- Migration 0030 (K4). Tests : `test_conformite.test_mon_argent_douze_mois_bilan_fiscalite`, `test_lotT.test_rappels_fiscaux_lot_g`.

## À tester
- **Téléphone, `eleveur`** : Mon argent → « 12 mois » → graphique, « 📄 Télécharger mon bilan (PDF) » → Enregistrer / Partager ;
  carte « 🏛️ Ma fiscalité » → régime, jauge, rappels. Moi → 🔔 Mes notifications : « Rappels fiscaux ».
- **Ordinateur, `admin`** : Paramètres → `fiscalite.seuil_isl_fcfa` → modification = proposition quatre yeux.
- **Ordinateur, `veto`** : `/mon-argent/bilan.pdf?ferme=EST-001` → refusé.
- Limite : le jeu de démo n'a presque pas de ventes (bilan presque vide) — à enrichir.

Déployé sur la démo : **oui** — version 2026-11-10-f6056e5.
