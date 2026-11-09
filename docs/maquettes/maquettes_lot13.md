# SORRA — Lot 13 : tutoriel, « Comment faire ? », Mon compte, consentement BCEG

Aperçu : `docs/maquettes/apercu_lot13.html`. On réutilise l'existant :
- 👤 Moi et ses écrans « Bientôt » (lot 11), Mes visites (lot 12) ;
- la mascotte, les pastilles, les grosses cases ;
- l'écran « Changer mon mot de passe » (lot 0) ;
- la fiche ferme, le profil BCEG (il existe, il ne voit encore aucune ferme) ;
- le journal et le mode sans réseau.

Rien n'est refait en double.

---

## A. Tutoriel au premier lancement

- **Quand** : à la première ouverture de l'accueil par un éleveur, une seule fois **par compte**. L'information est gardée sur le serveur (`utilisateur.presentation_vue_le`), pas sur le téléphone.
- **Une seule page, 4 écrans** qui défilent sans recharger. La page est gardée par le téléphone, donc elle marche sans réseau.
- Chaque écran : la mascotte, une phrase courte, et les boutons **« Suivant »** (gros, mis en avant) et **« Passer »** (lien discret). « Passer » ou le dernier « C'est parti ! » enregistrent « vue » et ramènent à l'accueil.
- **Revoir** : 👤 Moi → « 🎬 Revoir la présentation ».

| # | Mascotte | Phrase | Illustration |
|---|---|---|---|
| 1 | content | **Chaque jour, notez vos morts et votre aliment.** | la tuile verte « Saisie du jour », puis « Envoyer ✓ », avec la mention « 2 touchers » |
| 2 | inquiet | **Un problème avec vos poulets ? Prévenez le vétérinaire.** | la tuile rose « 🩺 Poulet malade » |
| 3 | dort | **Pas de réseau ? Saisissez quand même : tout part quand le réseau revient.** | le bandeau « ◷ en attente » puis « ✓ envoyé » |
| 4 | content | **Votre agent Paul est là pour vous aider.** | bouton « 📞 Appeler Paul » |

Le prénom de l'écran 4 est celui de l'**agent réellement affecté à la ferme**. Sans agent, la phrase devient « Votre agent technique est là pour vous aider », sans bouton. Sans téléphone de l'agent, il n'y a pas de bouton 📞.

---

## B. « Comment faire ? »

**Bouton rond « ? »** en haut à droite du titre (44 px), sur les 9 écrans principaux de l'éleveur :

| Écran | Aide ouverte |
|---|---|
| Saisie du jour | Noter les morts et l'aliment |
| Sortie (Ventes et sorties) | Enregistrer une vente ou une sortie |
| Pesée | Peser mes poulets |
| Vaccin du jour | Faire un vaccin |
| Poulet malade | Prévenir le vétérinaire |
| J'ai acheté | Noter un achat |
| J'ai payé | Noter une dépense |
| Entretien | Cocher l'entretien, signaler une panne |
| Mon argent | Lire Mon argent |

- **1 toucher** ouvre **l'aide de cet écran**, pas une liste. « ‹ Retour » ramène à l'écran.
- **Chaque aide** : un titre, et **3 étapes au plus**. Chaque étape a un numéro rond, une **capture simplifiée** (le vrai bouton reproduit en petit : « ✓ Aucun mort », « Envoyer ✓ »…) et une phrase très courte.
- **Liste complète** : 👤 Moi → « ❓ Comment faire ? » (l'écran « Bientôt » du lot 11 est remplacé). Elle est rangée par grandes actions :
  - **Chaque jour** : Saisie du jour, Vaccin, Entretien ;
  - **Ma bande** : Pesée, Sortie ;
  - **Santé** : Poulet malade ;
  - **Mon argent** : Achat, Dépense, Mon argent.
- **Sans réseau** : à chaque ouverture de l'accueil avec du réseau, le téléphone garde la liste et les 9 aides, comme les autres pages.
- **ADMIN** : Configuration → **« Aides »**. On modifie le titre, les 3 étapes (texte et capture, choisie dans une liste de boutons) et « actif ». Chaque modification est **inscrite au journal**. Il n'y a pas de suppression : une aide inactive n'affiche plus son « ? ».

### Textes de départ (à faire relire — `docs/a_faire_valider.md`)

| Aide | Étape 1 | Étape 2 | Étape 3 |
|---|---|---|---|
| **Saisie du jour** | Comptez les poulets morts. Touchez + ou « Aucun mort ». | Touchez le nombre de sacs donnés, ou « Comme hier ». | Touchez « Envoyer ✓ ». C'est fini. |
| **Sortie** | Touchez qui prend les poulets : abattoir, vente ou autre. | Comptez les poulets et notez le poids. | Notez l'argent reçu si vous le savez, puis « Enregistrer ». |
| **Pesée** | Prenez 10 poulets au hasard. | Pesez-les ensemble et notez le poids total. | Touchez « Enregistrer la pesée ». |
| **Vaccin** | Donnez le vaccin comme le vétérinaire l'a dit. | Touchez « ✓ C'est fait ». | Une erreur ? Touchez « Annuler » tout de suite. |
| **Poulet malade** | Touchez ce que vous voyez : toux, diarrhée… | Prenez une photo si vous pouvez. | Touchez « Envoyer au vétérinaire ». Il vous répondra. |
| **Achat** | Touchez ce que vous avez acheté. | Notez la quantité, et le prix si vous voulez. | Touchez « Enregistrer ». |
| **Dépense** | Touchez pour quoi vous avez payé. | Notez combien vous avez payé. | Touchez « Enregistrer ». |
| **Entretien** | Le travail est fait ? Touchez « Fait ✓ ». | Quelque chose est cassé ? Touchez « Quelque chose est en panne ». | Votre agent est prévenu. |
| **Mon argent** | « Gagné » : l'argent de vos ventes. | « Dépensé » : vos achats et vos dépenses. | « Reste » : ce qui vous reste. |

---

## C. Mon compte (👤 Moi → « 🔑 Mon compte »)

L'entrée « Mon compte », qui menait jusqu'ici directement au mot de passe, ouvre désormais l'écran **« Mon compte »**.

**En gros, en lecture :**
- nom ;
- téléphone ;
- ferme(s) et bâtiments (B1 · 1 200 places…) ;
- agent (avec 📞) ;
- vétérinaire de la zone : les vétérinaires de la province de la ferme, avec leur téléphone s'il est connu.

**Modifiable par l'éleveur, seulement :**
- **son téléphone** (Enregistrer, inscrit au journal) ;
- **son mot de passe**. L'écran existant affiche les règles en clair : « au moins 10 caractères », « différent de l'ancien », « tapez-le deux fois ». Le changement est inscrit au journal (déjà le cas), et ramène à « Mon compte ».

Sous le nom, les fermes et l'agent : « **Pour changer cela, appelez Paul** » (📞).

**« Me déconnecter »**, bien visible en bas (le même bouton que dans 👤 Moi) :
- le téléphone compte les saisies encore gardées sans réseau ;
- s'il en reste : « **⚠️ 3 saisies ne sont pas encore parties. Ne vous déconnectez pas avant qu'elles partent.** » Il faut un second toucher, « Me déconnecter quand même », pour sortir ;
- **elles ne sont jamais effacées** : elles restent sur le téléphone, rattachées à ce compte, et partent à la prochaine connexion (règle du lot 7, vérifiée par un test).

---

## D. Consentement BCEG

**Case « Ferme financée par la BCEG »**, sur la fiche ferme, cochée par l'agent de la ferme ou l'ADMIN. C'est inscrit au journal.

**Ferme non financée : rien ne s'affiche** chez l'éleveur. L'entrée « 🏦 Partage avec la BCEG · bientôt » du lot 11 disparaît.

**Ferme financée** : 👤 Moi → **« 🏦 Ma banque »**.
- Texte très simple :
  > **La BCEG finance votre ferme.** Si vous êtes d'accord, elle pourra voir :
  > ✓ vos ventes · ✓ vos dépenses · ✓ ce qui vous reste (la marge) · ✓ si vous notez chaque jour.
  > **Elle ne verra rien d'autre** : ni vos poulets malades, ni vos visites, ni vos messages.
  > Vous pouvez changer d'avis à tout moment.
- Deux gros boutons : **« J'accepte »** (vert) et **« Je refuse »** (blanc).
- Ensuite : « ✓ Vous avez accepté le 09/11/2026 », et « Retirer mon accord ». Le retrait demande une **confirmation** (« Oui, retirer mon accord » / « Non, garder »). Après un refus ou un retrait, « J'accepte » reste possible.
- **Pastille « nouveau »** sur 👤 Moi tant que l'éleveur d'une ferme financée n'a pas répondu.
- **Historique conservé** : chaque accord, refus ou retrait est une ligne datée, jamais modifiée, et il est inscrit au journal.

**Règle d'accès du profil BCEG (préparée maintenant, l'écran viendra plus tard)** : la BCEG ne voit **que** les fermes financées **et** avec un accord en cours, c'est-à-dire dont la dernière réponse est « accepte ».
- Sans réponse, après un refus, ou après un retrait : **aucun accès**.
- La règle est placée dans le filtre de périmètre unique (`filtre_perimetre`), donc elle vaut partout (fermes, bandes, argent…).
- Elle est testée.

---

## E. Contrôle de toute l'interface éleveur (lots 9 à 13)

Fait pendant la construction. Le rapport donnera le tableau complet (**action → clics → conforme oui/non**), avec les corrections. **Constats déjà faits :**

1. **Sans réseau** : le téléphone ne garde pas encore les pages des lots 10 à 12 (`/ma-bande`, `/vaccins-et-soins`, `/mes-produits`, `/mon-argent`, `/j-ai-paye`, `/entretien`, `/entretien/panne`, `/moi`, `/mes-visites`, `/sante/mes-declarations`). Seules celles des lots 7 à 9 l'étaient. **À corriger** : la liste des pages gardées sera complétée.
2. **Contrastes** (rapport de contraste, norme WCAG AA : 4,5 pour le texte courant, 3 pour le gros texte gras) :

   | Couleurs | Rapport | Verdict |
   |---|---|---|
   | gris secondaire sur crème | 4,31 | **à corriger** (texte courant) |
   | orange sur orange pâle (« pas fait la semaine dernière ») | 2,26 | **à corriger** |
   | blanc sur pastille orange | 2,51 | **à corriger** |
   | orange « Dépensé » sur blanc | 2,51 | **à corriger** |
   | blanc sur bouton vert (gros, gras) | 3,20 | conforme (gros texte) |
   | blanc sur bleu | 4,10 | conforme (gros texte) |
   | bleu nuit sur crème | 12,9 | conforme |

   Correction prévue : un **orange foncé** pour les textes et les pastilles, et un gris un peu plus foncé. Ce sont les couleurs de la charte, assombries ; l'apparence reste la même.
3. **Tailles** : certaines petites mentions sont à 0,62–0,75 rem (pastille « nouveau », dates). Correction prévue : **0,75 rem au moins** partout, et des boutons et cases d'au moins **44 px** de haut (à vérifier écran par écran).

---

## Tables et champs (migration 0015)

| Table | Champs | Rôle |
|---|---|---|
| `utilisateur` | + `presentation_vue_le` | tutoriel vu une fois par compte |
| `ferme` | + `financee_bceg` (booléen) | ferme financée par la BCEG |
| **`consentement_bceg`** (nouvelle) | id, ferme_id, utilisateur_id, decision (ACCEPTE · REFUSE · RETIRE), cree_le | historique daté, jamais modifié |
| **`aide`** (nouvelle) | id, cle (unique : saisie, sortie, pesee, vaccin, malade, achat, depense, entretien, argent), groupe, titre, etapes (JSON : 3 × {texte, capture}), actif, ordre | aides « Comment faire ? », modifiables par l'ADMIN, journalisées |

---

## Chemins de clics

| Action | Clics |
|---|---|
| Écran (ex. Saisie du jour) → « ? » | 1 (l'aide de cet écran) |
| 👤 Moi → Comment faire ? → une aide | 3 |
| 👤 Moi → Revoir la présentation | 2 |
| 👤 Moi → Mon compte → Enregistrer mon téléphone | 3 |
| 👤 Moi → Ma banque → J'accepte | 3 |
| 👤 Moi → Ma banque → Retirer mon accord → Oui, retirer | 4 : **au-delà de 3, voulu** (confirmation demandée) |
| 👤 Moi → Se déconnecter | 2 (3 s'il reste des saisies : second toucher voulu) |

---

## Écarts et choix à valider

1. **Le tutoriel ne s'affiche qu'aux éleveurs.** Il s'affiche aussi aux éleveurs déjà inscrits, une fois, au prochain lancement.
2. **Écran 4 sans agent ou sans téléphone** : la phrase est adaptée, sans bouton 📞.
3. **Les captures des aides sont des boutons reproduits en HTML** (les vrais libellés, en petit), pas des images. Elles restent nettes, légères, lisibles sans réseau, et l'ADMIN les choisit dans une liste.
4. **Le « ? » n'est montré qu'à l'éleveur** (charte illustrée), pas à l'agent qui saisit pour lui.
5. **Vétérinaire de la zone** : tous les vétérinaires de la province de la ferme (nom et téléphone).
6. **Mot de passe** : on réutilise l'écran existant, avec les règles affichées en clair. Pour l'éleveur, il ramène à « Mon compte ».
7. **Déconnexion avec saisies en attente** : un avertissement et un second toucher. On ne bloque pas : un téléphone partagé doit pouvoir se déconnecter. Les saisies restent sur le téléphone.
8. **Ferme financée, plusieurs éleveurs rattachés** : la réponse de l'un vaut pour la ferme, et la dernière réponse compte. Elle est signée dans l'historique.
9. **Case « financée par la BCEG »** : agent de la ferme et ADMIN. La DGE la voit sans la modifier.
10. **Un « Retirer mon accord » suivi d'un nouveau « J'accepte » est possible**, et chaque étape reste dans l'historique.
11. **Retrait à 4 clics** : c'est la seule action au-delà de 3, à cause de la confirmation que vous demandez.
12. **Contrôle E** : les corrections de couleurs et de tailles restent dans la charte (mêmes teintes, plus foncées). Je les liste dans le rapport.
