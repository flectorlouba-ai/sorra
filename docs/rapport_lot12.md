# SORRA — Rapport du lot 12 : réponses à l'éleveur, visites de l'agent, règle des conflits, « case vide ≠ zéro »

**État :** terminé, commit dédié. **Aucun déploiement** : le VPS reste au lot 1.

**Tests :** **335 tests réussis** et 1 réservé à PostgreSQL. Nouveaux tests :
- `tests/test_verifications.py` (10) : conflits, doublon de sortie, 48 h, livraison visible de la DGE ;
- `tests/test_case_vide.py` (6) : « — », « Aucun mort », « Comme hier », jours non saisis ;
- `tests/test_reponses_visites.py` (6) : réponse du vétérinaire, visites.

Les tests de l'ancienne règle « la plus récente gagne » sont remplacés. Les saisies des anciens tests précisent désormais l'aliment.

**Migration :** 0014.
- Tables `reponse_veterinaire` et `visite`.
- `conflit_hors_ligne` complétée : genre, versions, décision et motif.
- `saisie_jour.a_verifier`, `sortie.a_verifier` et `sortie.mise_de_cote`.
- Trois listes de départ **provisoires**.

**Références :**
- description et aperçu de l'étape 1 : `docs/maquettes/maquettes_lot12.md`, `docs/maquettes/apercu_lot12.html` ;
- règles : `docs/ergonomie.md` (section « Réponses, visites, conflits, case vide ») et `docs/hors_ligne.md` (section 5, règle des conflits réécrite) ;
- **nouvelle liste unique `docs/a_faire_valider.md`**.

**Bibliothèques :** aucune nouvelle.

## Ce qui a été fait

### A. Réponse du vétérinaire

- **Vétérinaire** : sur l'écran de l'alerte, une carte « Réponse à l'éleveur » avec des conseils types à cocher (liste configurable, provisoire), un message court, puis « Envoyer à l'éleveur ». Chaque réponse est datée, signée et inscrite au journal (« Réponse du vétérinaire à l'éleveur »). Plusieurs réponses sont possibles, et aucune ne s'efface. Les alertes du feu rouge peuvent aussi recevoir une réponse (écart 10).
- **Éleveur** : Vaccins et soins → 💬 **Mes signalements**.
  - Quatre états simples : **Envoyé ✓** · **Le vétérinaire regarde** · **💬 Réponse du vétérinaire** · **Terminé**. Jamais « confirmée » ni « infirmée ».
  - Les conseils et le message sont affichés en gros, avec le nom du vétérinaire et la date.
  - Une réponse non lue met la pastille 💬 sur la tuile et la ligne « 💬 Le vétérinaire vous a répondu → » sur l'accueil (1 toucher). Les deux disparaissent une fois la réponse lue.
- **Agent** (fiche de la ferme) : « Signalement du 08/11 · le vétérinaire a répondu le 09/11 », ou « pas encore de réponse ». Il ne voit jamais le contenu de la réponse, ni les signes, ni les photos (écart 11).

### B. Visites de l'agent

- **Agent** (fiche de la ferme → carte « Visites ») :
  - « Planifier une visite » : date, objet en cases ;
  - « Compte rendu », d'une visite prévue ou non planifiée (écart 12) : constats, recommandations à cocher, recommandation libre, **position GPS relevée toute seule** si le téléphone l'accepte (« position non relevée » sinon, sans blocage), photo facultative ;
  - **sans réseau aussi**, photo et position comprises ;
  - une visite prévue peut être annulée, avec un motif inscrit au journal ;
  - l'encadré Alertes affiche « Visite prévue aujourd'hui : Ferme Mba » ou « Visite en retard (prévue le …) ».
- **Éleveur** :
  - « 📅 Visite de Paul jeudi 12 » dans la ligne d'état. Une visite passée et non faite n'est plus montrée (écart 13) ;
  - **👤 Moi → 📋 Mes visites** : les recommandations en gros, les constats plus petits ;
  - une pastille **« nouveau »** sur 👤 Moi et sur « Mes visites » tant que le dernier compte rendu n'est pas ouvert. Elle est placée en coin, pour ne pas élargir l'en-tête à 360 px.

### C. Règle des conflits

« La plus récente gagne » est **supprimée partout** : la saisie du jour et la confirmation de livraison. Aucune donnée n'est perdue ni écrasée.
- **Même personne** : les saisies s'additionnent (inchangé).
- **Deux personnes, saisie du jour différente** (morts ou aliment, écart 4) : les **deux versions sont gardées** et la journée passe « à vérifier ».
  - La version de l'éleveur compte, qu'elle arrive en premier ou en second (écart 6).
  - En ligne, l'écran « Déjà envoyé » de l'agent propose « Ajouter » ou « Mes chiffres sont différents » (écart 5).
- **Confirmation de livraison** : la même règle. L'écart est visible de l'agent **et de la DGE** (votre précision sur l'écart 7) : ligne dans l'encadré Alertes de la DGE, et accès à « Saisies à vérifier ».
- **Sorties** : un « doublon possible » seulement si le **nombre et le destinataire** sont identiques.
  - La sortie de l'autre personne est **mise de côté** : elle ne compte nulle part, et son lot QR n'est créé ou réactivé que si elle est retenue.
  - **Garde-fou à 48 h** (votre précision sur l'écart 8) : l'alerte de l'agent passe en rouge (« dont 1 doublon de sortie depuis plus de 48 h »), et la DGE reçoit « 1 doublon de sortie non tranché depuis plus de 48 h ».
- **L'éleveur** voit seulement « ◷ À vérifier par votre agent », sur la saisie du jour, sur Mes bandes et dans Mon argent. Jamais un message d'erreur.
- **« Saisies à vérifier »** (agent, DGE, ADMIN ; jamais l'éleveur, écart 9) :
  - les deux versions côte à côte, celle qui compte en vert ;
  - « Retenir cette version », ou les trois choix d'une sortie ;
  - **motif obligatoire**, inscrit au journal (« Saisie à vérifier tranchée ») ;
  - **recalcul** des indicateurs, et du bilan si la bande est terminée.

### D. « Case vide ≠ zéro »

- Les morts et l'aliment **démarrent à « — »**.
- Grosses cases **« ✓ Aucun mort »**, **« Pas d'aliment donné »** et **« Comme hier (N sacs) »** (votre précision sur l'écart 1) :
  - un toucher choisit aussi l'aliment d'hier ;
  - la valeur reste explicite, jamais pré-remplie ;
  - le bouton n'apparaît que si la veille a été saisie avec de l'aliment.
- Le premier « + » met 1, et « − » à 0 revient à « — ».
- **« Envoyer » est refusé tant qu'une case est à « — »** : « Touchez « Aucun mort » s'il n'y a pas eu de mort » ou « Touchez « Pas d'aliment donné »… ». Le refus se fait :
  - sur le téléphone avant tout envoi, **même sans réseau** ;
  - et sur le serveur.
- La saisie du jour reste à **2 clics**.
- **Calculs** : un jour non saisi n'est jamais compté zéro. La fiche de la bande, le bilan, le rapport PDF et le tableau de bord affichent **« incomplet : N jours non saisis »** sur la mortalité et sur l'indice de consommation (écart 2). Le tableau de bord a une nouvelle case, « Jours non saisis ».

### Corrigé au passage

Un état « envoi sans réseau » pouvait rester attaché à la requête suivante dans les tests, faute de remise à zéro. Ce n'était pas visible en production, où chaque requête repart à zéro. Il est maintenant remis à zéro au début de chaque requête.

## Tableau des clics

| Qui | Action | Clics |
|---|---|---|
| Éleveur | Saisie du jour → Envoyer (« Aucun mort », « Comme hier » : choix dans l'écran) | 2 |
| Éleveur | Accueil → « 💬 Le vétérinaire vous a répondu » | 1 |
| Éleveur | Vaccins et soins → Mes signalements | 2 |
| Éleveur | 👤 Moi → Mes visites | 2 |
| Vétérinaire | Alertes → alerte → Envoyer à l'éleveur | 3 |
| Agent | fiche ferme → Planifier une visite → Enregistrer | 2 |
| Agent | fiche ferme → Compte rendu → Enregistrer | 2 |
| Agent | Alertes → Saisies à vérifier → Retenir cette version | 2 |

## Captures (`docs/captures/lot12/`, 360 px sauf mention)

| Fichier | Écran |
|---|---|
| `01_accueil.png` | ligne « 💬 Le vétérinaire vous a répondu », « 📅 Visite de Paul jeudi 12 », pastilles 💬 et « nouveau » |
| `02_saisie_tiret.png`, `03_saisie_refus.png` | morts et aliment à « — », refus à l'envoi |
| `04_saisie_aucun_mort_comme_hier.png` | « Aucun mort » et « Comme hier (2 sacs) » choisis ; « ◷ À vérifier par votre agent » |
| `05_mes_signalements.png` | états simples, réponse en gros |
| `06_accueil_apres_lecture.png`, `07_moi_nouveau.png`, `08_mes_visites.png` | après lecture ; Moi ; Mes visites |
| `09_a_verifier_eleveur.png` | « ◷ À vérifier par votre agent » |
| `10_agent_alertes.png`, `11_saisies_a_verifier.png` | agent, ordinateur : deux versions côte à côte, doublon de sortie |
| `12_agent_visites_fiche.png`, `13_compte_rendu.png`, `14_compte_rendu_360.png` | visites (ordinateur et 360 px) |
| `15_veto_reponse.png` | vétérinaire : réponse à l'éleveur |
| `16_accueil_ordinateur.png` | éleveur sur ordinateur |

**Vérification au navigateur** (Chromium, 360 px et 1 366 px) :
- toutes les pages font 360 px de large ;
- parcours rejoué : refus du « — », Aucun mort, Comme hier, Envoyer, Mes signalements, Mes visites, Saisies à vérifier, compte rendu, réponse du vétérinaire ;
- aucune erreur JavaScript.

## Décisions

Les écarts 1 à 15 sont appliqués, avec vos précisions :
- **1** : le bouton « Comme hier » est ajouté ;
- **7** : les écarts de livraison sont visibles de la DGE ;
- **8** : le garde-fou de 48 h est en place ;
- **15** : les trois listes sont provisoires et notées dans `docs/a_faire_valider.md`.

## Liste de contrôle d'ergonomie

- [x] **Un seul bouton mis en avant** par écran : Envoyer, Envoyer à l'éleveur, Enregistrer, Retenir cette version.
- [x] **3 clics au plus** (tableau ci-dessus) ; la saisie du jour reste à 2.
- [x] **Rien d'inutile** : « Comme hier » seulement si la veille est saisie ; l'agent ne voit pas le contenu médical.
- [x] **Aucun mot technique** : « Le vétérinaire regarde », « Terminé », « ◷ À vérifier par votre agent », « incomplet ».
- [x] **360 px sans défilement horizontal** (la pastille « nouveau » est placée en coin pour cela).
- [x] **Saisie du jour en moins de 30 s** : Aucun mort, Comme hier, puis Envoyer.
- [x] **Rien d'ajouté sans demande**, en dehors des écarts validés.

## Tests que vous ferez

Base de démonstration : `http://127.0.0.1:5020`, mot de passe `Demo-yl2-2026`.

1. **Éleveur, saisie du jour** :
   - touchez Envoyer sans rien : le message « Touchez « Aucun mort »… » apparaît ;
   - touchez « ✓ Aucun mort », puis « Comme hier » (ou « Pas d'aliment donné »), puis Envoyer.
2. **Sans réseau** (F12 → Réseau → Hors connexion) : faites le même essai. Le « — » est refusé sur le téléphone, rien n'est gardé.
3. **Vétérinaire** (`veto`) : ouvrez une alerte, cochez deux conseils, écrivez un message, puis « Envoyer à l'éleveur ».
4. **Éleveur** :
   - la ligne « 💬 Le vétérinaire vous a répondu » et la pastille 💬 apparaissent ; touchez la ligne et lisez la réponse ;
   - revenez à l'accueil : la ligne et la pastille ont disparu.
5. **Agent** (`agent.est`) : sur la fiche EST-001, la ligne « le vétérinaire a répondu le … » s'affiche, sans le contenu.
6. **Agent** :
   - planifiez une visite pour jeudi ;
   - côté éleveur, « 📅 Visite de Paul jeudi … » s'affiche ;
   - côté agent, ouvrez « Compte rendu », cochez deux recommandations, ajoutez une photo, puis Enregistrez ;
   - côté éleveur : pastille « nouveau » sur 👤 Moi, puis Mes visites.
7. **Conflit** :
   - l'éleveur envoie 4 morts ;
   - l'agent saisit 6 morts pour le même jour, puis choisit « Mes chiffres sont différents » ;
   - l'éleveur voit « ◷ À vérifier par votre agent » ;
   - l'agent ouvre Alertes → Saisies à vérifier, choisit une version et donne un motif : les chiffres changent.
8. **Doublon** : l'éleveur, puis l'agent, enregistrent la même vente (même nombre, même acheteur). Celle de l'agent est mise de côté. Essayez « Ce sont deux sorties différentes ».
9. **DGE** (`dge`) : un écart de livraison (confirmation différente faite sans réseau) apparaît dans son encadré Alertes et dans « Saisies à vérifier ».
10. **Tableau de bord** : la case « Jours non saisis ». Sur une bande avec des jours oubliés : « incomplet » sur la mortalité et sur l'indice de consommation.

## Points à valider

Tous regroupés dans **`docs/a_faire_valider.md`** :
- les trois listes provisoires de ce lot (conseils, recommandations, objets de visite) ;
- les seuils, la courbe et le calendrier vaccinal déjà notés ;
- le délai de 48 h ;
- le test terrain avec 3 à 5 éleveurs.
