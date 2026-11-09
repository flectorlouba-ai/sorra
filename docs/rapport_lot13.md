# SORRA — Rapport du lot 13 : tutoriel, « Comment faire ? », Mon compte, consentement BCEG

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1.

**Tests :** **347 tests réussis** et 1 réservé à PostgreSQL, dont 12 nouveaux dans `tests/test_lot13.py`. L'un d'eux vérifie que **toutes les pages de l'éleveur** sont dans la liste que le téléphone garde pour le mode sans réseau.

**Migration :** 0015.
- Tables `aide` (9 aides de départ) et `consentement_bceg` (historique).
- `utilisateur.presentation_vue_le`, `ferme.financee_bceg`, `ferme.responsable_id`.

**Références :**
- description et aperçu de l'étape 1 : `docs/maquettes/maquettes_lot13.md`, `docs/maquettes/apercu_lot13.html` ;
- règles : `docs/ergonomie.md` (tutoriel, aides, Mon compte, Ma banque, contrôle de l'interface, exception des 4 touchers) ;
- textes à relire : `docs/a_faire_valider.md`.

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

### A. Tutoriel

- Il s'affiche au premier lancement, **une fois par compte** : c'est gardé sur le serveur, donc un autre téléphone ne le remontre pas.
- 4 écrans dans une seule page, avec la mascotte, une phrase chacun, « Suivant » et « Passer ». La page est gardée par le téléphone, donc elle s'ouvre sans réseau.
- Le prénom de l'écran 4 est celui de l'**agent affecté à la ferme**. Sans agent : « Votre agent technique… ». Sans téléphone d'agent : pas de bouton 📞.
- On le revoit depuis 👤 Moi → « 🎬 Revoir la présentation ».

### B. « Comment faire ? »

- **« ? »** (44 px) en haut des 9 écrans principaux. 1 toucher ouvre **l'aide de cet écran** : 3 étapes au plus, chacune avec le **vrai bouton reproduit en petit**. « ‹ Retour » ramène à l'écran d'où l'on vient.
- **Liste complète** dans 👤 Moi → « ❓ Comment faire ? », par grandes actions : Chaque jour, Ma bande, Santé, Mon argent.
- **Sans réseau** : les 9 aides et la liste font partie des pages gardées (vérifié au navigateur : l'aide s'ouvre sans réseau).
- **ADMIN** : Configuration → **Aides**. On modifie le titre, les 3 étapes et leur capture (choisie dans une liste), et « active ». Il n'y a pas de suppression. Chaque modification est inscrite au journal.
- Le « ? » n'apparaît que chez l'éleveur (écart 4).

### C. Mon compte

- Affiché en gros : nom, téléphone, ferme(s) et bâtiments, agent avec 📞, vétérinaires de la zone.
- **Vétérinaires (votre précision sur l'écart 5)** : au-delà de 3 dans la province, d'abord celui ou ceux qui ont répondu aux signalements de l'éleveur, puis « Voir les autres ».
- **L'éleveur modifie seulement son téléphone** (journal automatique) **et son mot de passe**.
  - L'écran du mot de passe affiche maintenant les règles en clair : « au moins 10 caractères ; différent de l'ancien ; tapez le nouveau deux fois, pareil ».
  - Le changement est inscrit au journal et ramène à « Mon compte ».
  - Pour le reste : « Pour changer cela, appelez Paul ».
- **« Me déconnecter »** (dans Mon compte et dans 👤 Moi) : s'il reste des saisies gardées sans réseau, « ⚠️ 1 saisie n'est pas encore partie. Ne vous déconnectez pas avant qu'elle parte. Elle partira quand vous vous reconnecterez. », puis il faut un second toucher.
- **Elles ne sont jamais effacées, et gardent leur auteur** (votre précision sur l'écart 7). Vérifié au navigateur :
  - une autre personne se connecte sur le même téléphone : les saisies de l'éleveur **restent en attente sans partir** ;
  - l'éleveur se reconnecte : elles partent, à son nom.

### D. Consentement BCEG

- **Fiche ferme → carte « Banque (BCEG) »** (agent de la ferme et ADMIN ; la DGE en lecture) :
  - la case « Ferme financée par la BCEG » ;
  - le **responsable de la ferme** : nouveau champ, choisi parmi les éleveurs rattachés ;
  - l'historique daté du consentement.
- **Seul le responsable** (votre précision sur l'écart 8) voit 👤 Moi → « 🏦 Ma banque » et répond. Les autres éleveurs de la ferme ne voient pas la rubrique. Ferme non financée : rien ne s'affiche.
- **Ma banque** : ce que la BCEG verra (ventes, dépenses, ce qui reste, régularité des saisies) et ne verra pas. « J'accepte » ou « Je refuse ».
  - Après un accord : « ✓ Vous avez accepté le … » et « **Retirer mon accord** », avec confirmation : 4 touchers, exception notée dans `docs/ergonomie.md`.
  - Après un refus ou un retrait, on peut de nouveau accepter.
- **Changement de responsable** : l'accord en cours tombe (ligne « Accord tombé »), et le nouveau responsable a une pastille sur 👤 Moi jusqu'à sa réponse.
- **Historique** : chaque accord, refus, retrait ou chute est une ligne datée, jamais modifiée, et inscrite au journal (« Consentement BCEG »).
- **Règle d'accès du profil BCEG**, dans le filtre de périmètre unique : seulement les fermes **financées** dont la **dernière réponse est un accord**. Sans réponse, après un refus, un retrait, un changement de responsable, ou si la ferme n'est plus financée : **aucun accès**. Elle est testée cas par cas. L'écran BCEG viendra dans la phase pilotage.

### E. Contrôle de toute l'interface de l'éleveur (lots 9 à 13)

**Corrigé :**
1. **Pages sans réseau** : les pages des lots 10 à 12 n'étaient pas gardées par le téléphone.
   - Désormais **une seule liste** côté serveur (`PAGES_ELEVEUR`, servie par `/hors-ligne/pages`, 47 pages pour la ferme de démonstration, dont les pages de chaque bande et les 9 aides) est gardée à chaque ouverture de l'accueil avec du réseau.
   - Un test parcourt **toutes** les pages de l'application que l'éleveur peut ouvrir, et échoue si l'une manque à la liste.
2. **Pages obtenues par redirection** (« Peser », « Ventes et sorties » → la bande la plus utile) : le service worker les gardait d'une façon que le navigateur refuse d'afficher sans réseau. Elles sont maintenant gardées « propres » (vérifié : « Peser » s'ouvre sans réseau).
3. **Contrastes** (rapports mesurés) :

   | Avant | Rapport | Après | Rapport |
   |---|---|---|---|
   | gris secondaire #6b7594 sur crème | 4,31 | #5c6683 | 5,38 |
   | orange en texte (« pas fait la semaine dernière », « Dépensé ») | 2,26–2,51 | orange foncé #a8520f | 4,9–5,4 |
   | blanc sur pastille orange | 2,51 | **bleu nuit** sur pastille orange | 5,43 |
   | vert foncé sur vert pâle | 3,89 | #17734a | 5,24 |
   | bleu en texte (liens) sur blanc | 4,10 | bleu foncé de la charte | 7,56 |

   **L'orange reste reconnaissable** à côté du rouge (votre précision sur l'écart 12) :
   - les pastilles orange gardent leur fond orange vif avec un texte bleu nuit ;
   - les pastilles rouges gardent leur fond rouge avec un texte blanc ;
   - la teinte du fond ne change pas, seul le texte change.
4. **Tailles** : un contrôle automatique au navigateur parcourt les 47 pages de l'éleveur (textes de moins de 12 px, boutons de moins de 44 px, largeur au-delà de 360 px). Il a trouvé :
   - le bouton « ✓ C'est fait » de l'accueil (40 px) ;
   - des textes de 9 à 11,7 px : badges de livraison, axes et légende de la courbe, mention « livré : … », « Jour 15 · Bâtiment B2 », message « Aucun poussin en attente », écran du mot de passe ;
   - le bouton « Enregistrer » du mot de passe (33 px).

   Tout est corrigé. Au dernier passage, **aucune page** n'a de défaut.

**Tableau de contrôle (action → clics → conforme) :**

| Action de l'éleveur | Clics | Conforme |
|---|---|---|
| Saisie du jour → Envoyer (Aucun mort, Comme hier : choix) | 2 | oui |
| Ventes et sorties → Enregistrer | 2 | oui |
| Vaccins et soins → ✓ C'est fait | 2 (1 depuis le raccourci) | oui |
| Poulet malade → Envoyer au vétérinaire | 2 | oui |
| Mes produits → Tout reçu | 2 | oui |
| Ma bande → Nouvelle bande → Commencer | 3 | oui |
| Ma bande → Peser → Enregistrer | 3 | oui |
| Mes produits → J'ai acheté → Enregistrer | 3 | oui |
| Mon argent → J'ai payé → Enregistrer | 3 | oui |
| Mon argent → compléter une vente → Enregistrer | 3 | oui |
| Vaccins et soins → Traitement → Enregistrer | 3 | oui |
| Vaccins et soins → Mes signalements | 2 | oui |
| Accueil → « 💬 Le vétérinaire vous a répondu » | 1 | oui |
| Entretien → Fait ✓ | 2 | oui |
| Entretien → Quelque chose est en panne → Envoyer | 3 | oui |
| Entretien → C'est réparé | 2 | oui |
| 👤 Moi → Mes visites | 2 | oui |
| 👤 Moi → Mon compte → Enregistrer mon téléphone | 3 | oui |
| 👤 Moi → Mon compte → Changer mon mot de passe → Enregistrer | 4 | **non** (voir ci-dessous) |
| 👤 Moi → Ma banque → J'accepte | 3 | oui |
| 👤 Moi → Ma banque → Retirer mon accord → Oui, retirer | 4 | exception validée |
| 👤 Moi → Comment faire ? → une aide | 3 | oui |
| N'importe quel écran → « ? » | 1 | oui |
| 👤 Moi → Se déconnecter | 2 (3 avec saisies en attente) | oui (second toucher voulu) |
| 📞 Appeler l'agent | 1 | oui |
| Annuler (10) après une saisie | 1 | oui |

**Un écart restant, à trancher par vous** : changer son mot de passe depuis « Moi » fait 4 clics (Moi → Mon compte → Changer mon mot de passe → Enregistrer). C'est une action rare. Deux choix :
- l'ajouter à l'exception « action rare et sensible » ;
- ou mettre le formulaire du mot de passe directement dans « Mon compte » (3 clics).

Je ne l'ai pas changé sans votre accord.

**Autres constats :** aucun mot technique visible sur les 47 pages. Toutes tiennent à 360 px. Aucune erreur JavaScript.

## Captures (`docs/captures/lot13/`, 360 px sauf mention)

| Fichier | Écran |
|---|---|
| `01` à `04_presentation_*.png` | les 4 écrans du tutoriel |
| `05_accueil.png` | l'accueil après « C'est parti ! » |
| `06_saisie_bouton_aide.png`, `07_aide_saisie.png` | le « ? » et l'aide de la saisie du jour |
| `08_comment_faire.png` | la liste par grandes actions |
| `09_moi.png`, `10_mon_compte.png`, `11_mot_de_passe.png` | Moi, Mon compte, mot de passe avec ses règles |
| `12_ma_banque.png`, `13_ma_banque_acceptee.png`, `14_retirer_confirmation.png` | consentement BCEG |
| `15_deconnexion_avertissement.png` | déconnexion avec une saisie en attente |
| `16_mon_compte_ordinateur.png`, `17_aide_ordinateur.png` | ordinateur |
| `18_agent_bceg_fiche.png` | agent : carte « Banque (BCEG) » de la fiche ferme |
| `19_admin_aides.png` | ADMIN : modification d'une aide |

## Décisions

Écarts 1 à 12 appliqués, avec vos précisions :
- **5** : les vétérinaires qui ont répondu d'abord ;
- **7** : l'auteur est gardé, avec le message « partiront quand vous vous reconnecterez » et un test ;
- **8** : un responsable unique, un accord qui tombe au changement, et des tests ;
- **11** : l'exception est notée ;
- **12** : l'orange reste reconnaissable.

## Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** : Suivant, Enregistrer mon téléphone, J'accepte, Oui, retirer.
- [x] **3 clics au plus**, sauf le retrait du consentement (exception validée) et le mot de passe (à trancher, voir ci-dessus).
- [x] **Rien d'inutile** : « Ma banque » seulement pour le responsable d'une ferme financée ; « ? » seulement chez l'éleveur.
- [x] **Aucun mot technique**.
- [x] **360 px**, boutons ≥ 44 px, textes ≥ 12 px, contrastes AA : contrôle automatique sur les 47 pages.
- [x] **Saisie du jour en moins de 30 s** : inchangée.
- [x] **Rien d'ajouté sans demande**.

## Tests que vous ferez

Base de démonstration : `http://127.0.0.1:5020`, mot de passe `Demo-yl2-2026`.

1. **Tutoriel** :
   - connectez-vous en `eleveur` : les 4 écrans s'affichent. Essayez « Suivant », puis « Passer » ;
   - reconnectez-vous : il ne revient pas ;
   - 👤 Moi → « Revoir la présentation ».
2. **« ? »** : sur la saisie du jour, touchez « ? ». L'aide de la saisie s'ouvre ; « ‹ Retour » revient. Essayez aussi sur Mon argent et sur l'entretien.
3. **Sans réseau** (F12 → Réseau → Hors connexion, après une ouverture de l'accueil avec du réseau) : ouvrez un « ? », puis 👤 Moi → Comment faire ?, puis Ma bande et Peser. Tout s'affiche.
4. **Mon compte** :
   - changez votre téléphone ;
   - le nom n'est pas modifiable, et « Pour changer cela, appelez Paul » s'affiche ;
   - changez le mot de passe : les règles sont affichées, puis vous revenez sur Mon compte.
5. **Déconnexion avec saisie en attente** :
   - sans réseau, faites une dépense ;
   - remettez le réseau, puis allez vite sur 👤 Moi → Se déconnecter : l'avertissement apparaît ;
   - « Me déconnecter quand même », puis reconnectez-vous : la dépense part.
6. **Admin** (`admin`) : Configuration → Aides. Modifiez une étape de la saisie du jour, puis vérifiez la ligne au journal et le texte chez l'éleveur.
7. **BCEG** :
   - en `agent.est`, sur la fiche EST-001, carte « Banque (BCEG) » : cochez « financée » et choisissez le responsable ;
   - côté éleveur : pastille « nouveau » sur Moi, puis 🏦 Ma banque → J'accepte, puis « Retirer mon accord » → « Oui, retirer » ;
   - l'historique s'affiche sur la fiche.
8. **Changement de responsable** : choisissez un autre éleveur comme responsable. L'accord tombe (ligne « Accord tombé »), et l'ancien responsable ne voit plus « Ma banque ».
9. **Ferme non financée** : décochez la case. « Ma banque » disparaît chez l'éleveur.
10. **Couleurs** : sur l'accueil et sur Entretien, les pastilles orange (texte foncé) restent bien distinctes des rouges.

## Points à valider

- **Textes du tutoriel, des 9 aides et de « Ma banque »** : à faire relire (`docs/a_faire_valider.md`). Le texte de « Ma banque » est aussi à faire valider par la BCEG.
- **Mot de passe à 4 clics** : l'ajouter à l'exception, ou le mettre dans Mon compte (voir la partie E).
- **Le test terrain** avec 3 à 5 éleveurs, avant de figer l'interface de l'éleveur (c'était le dernier gros lot de cette interface).
