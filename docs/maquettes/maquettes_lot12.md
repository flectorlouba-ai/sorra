# SORRA — Lot 12 : réponses à l'éleveur, visites de l'agent, règle des conflits, « case vide ≠ zéro »

Aperçu : `docs/maquettes/apercu_lot12.html`. On réutilise l'existant :
- les 8 tuiles, « Vaccins et soins » et « 👤 Moi » (lot 11) ;
- les déclarations et les alertes (lot 4) ;
- l'encadré Alertes de l'agent ;
- l'écran « Saisies à vérifier » et le mode sans réseau (lot 7) ;
- le journal.

Règle des clics du lot 11 : 3 clics au plus. Les choix dans un même écran ne comptent pas.

---

## A. Réponse du vétérinaire

### Côté vétérinaire (écran de l'alerte, `/sante/alertes/<n°>`)

Sous l'historique de l'alerte, une carte **« Réponse à l'éleveur »** :
- des **conseils types à cocher** (liste `conseils_veterinaire`, Configuration → Listes, ADMIN) : « Isolez les poulets malades », « Augmentez la ventilation », « Ne vendez pas avant ma visite », « Je passe vous voir », « Donnez de l'eau propre en continu », « Appelez-moi » ;
- un **message court** (300 caractères), facultatif si un conseil est coché ;
- le bouton **« Envoyer à l'éleveur »**.

Chaque réponse est :
- datée ;
- signée du vétérinaire (« Dr Nzé, vétérinaire ») ;
- inscrite au journal.

Plusieurs réponses sont possibles, et elles s'affichent dans l'ordre. Une réponse ne s'efface pas. Toutes les alertes peuvent recevoir une réponse : celles d'une déclaration de l'éleveur, et celles du feu rouge (beaucoup de morts).

### Côté éleveur (Vaccins et soins → 💬 Mes signalements)

Une carte par signalement : date, bâtiment, signes en images, et un **état simple**. Les mots « confirmée » et « infirmée » n'apparaissent jamais.

| État affiché | Quand |
|---|---|
| **Envoyé ✓** | alerte « nouvelle », sans réponse |
| **Le vétérinaire regarde** | alerte « en analyse », sans réponse |
| **💬 Réponse du vétérinaire** | au moins une réponse : le message et les conseils en gros, avec la date et le nom |
| **Terminé** | alerte close, confirmée ou infirmée ; les réponses restent visibles |

Les alertes du feu rouge qui ont reçu une réponse apparaissent aussi, comme « Beaucoup de morts le 08/11 ».

**Nouvelle réponse non lue :**
- une pastille **« 💬 »** sur la tuile « Vaccins et soins » ;
- une ligne **« 💬 Le vétérinaire vous a répondu → »** dans la ligne d'état de l'accueil. Un toucher ouvre la réponse ;
- la réponse est marquée lue quand l'éleveur l'ouvre.

### Côté agent

Sur la fiche de la ferme, une ligne par alerte : « Signalement du 08/11 · le vétérinaire a répondu le 09/11 » ou « · pas encore de réponse ». Le contenu de la déclaration et de la réponse n'apparaît pas : le cahier des charges réserve les déclarations aux vétérinaires.

La DGE voit les réponses comme elle voit déjà les alertes (lecture). L'ADMIN aussi.

---

## B. Visites de l'agent

### Côté agent (fiche de la ferme → carte « Visites »)

- **« Planifier une visite »** : date, objet en cases (Suivi · Vaccination · Contrôle · Panne · Autre), puis Enregistrer.
- Liste des visites prévues, chacune avec **« Compte rendu »**.
- **« Compte rendu de visite »** : on part d'une visite prévue, ou d'aucune (visite non planifiée). L'écran contient :
  - **constats** (texte court, 500 caractères) ;
  - **recommandations types à cocher** (liste `recommandations_visite`, Configuration → Listes) : « Nettoyez les abreuvoirs chaque jour », « Changez la litière humide », « Pesez 10 poulets chaque semaine », « Respectez le vide sanitaire », « Notez les morts chaque jour »… ;
  - une **recommandation libre** (texte court) ;
  - la **position GPS relevée automatiquement** si le téléphone l'accepte. Sinon : « position non relevée », sans blocage ;
  - une **photo facultative** ;
  - Enregistrer.
- **Sans réseau** : le compte rendu est gardé sur le téléphone, photo et position comprises, puis envoyé au retour du réseau.
- **Accueil de l'agent** : une ligne dans l'encadré Alertes, « Visite prévue aujourd'hui : Ferme Mba ».
- Une visite prévue peut être annulée (avec un motif), mais jamais effacée.

### Côté éleveur

- **Ligne d'état de l'accueil** : « 📅 Visite de Paul jeudi 12 » (la prochaine visite prévue, aujourd'hui ou plus tard).
- **👤 Moi → 📋 Mes visites** : les visites faites, la plus récente en haut, avec les recommandations de l'agent **en gros** et la date. Les constats sont affichés en plus petit.
- Une pastille **« nouveau »** est sur « 👤 Moi » et sur « 📋 Mes visites » tant que l'éleveur n'a pas ouvert le dernier compte rendu.

C'est la fonctionnalité « Visites techniques » du cahier des charges.

---

## C. Règle des conflits (toutes les saisies terrain)

**« La plus récente gagne » est supprimée partout** (saisie du jour, confirmation de livraison). Aucune donnée n'est perdue ni écrasée.

| Cas | Règle |
|---|---|
| Même personne, même bande, même jour | Les saisies **s'additionnent** (inchangé, avec ou sans réseau). |
| **Saisie du jour**, deux personnes (éleveur et agent), valeurs différentes | **Les deux versions sont gardées.** La journée passe « à vérifier ». **Les indicateurs utilisent la version de l'éleveur** jusqu'à la décision. |
| Saisie du jour, deux personnes, mêmes valeurs | Rien à vérifier (inchangé). |
| **Sorties** du même jour par deux personnes | Ce n'est pas un conflit (deux ventes différentes), **sauf** si le nombre **et** le destinataire sont identiques : « doublon possible » (voir ci-dessous). |
| **Confirmation de livraison** par deux personnes, quantités ou morts différents | Les deux versions sont gardées, et celle de l'éleveur compte jusqu'à la décision. |
| Pesée, déclaration | Elles s'ajoutent, comme aujourd'hui. |

**Ce que voit l'éleveur** : sur la saisie du jour, ou sur la bande, « ◷ À vérifier par votre agent ». Jamais un message d'erreur.

**Ce que voient l'agent et la DGE** :
- une ligne dans l'encadré Alertes : « 3 saisies à vérifier » ;
- l'**écran « Saisies à vérifier »** (l'écran existant, complété) : les deux versions côte à côte (qui, quand, valeurs) ;
- un bouton **« Retenir cette version »** sous chaque version, avec un **motif obligatoire** ;
- la décision est inscrite au journal et les indicateurs sont recalculés. Si la bande est terminée, son bilan l'est aussi ;
- la bande porte la mention « à vérifier » tant qu'une journée n'est pas tranchée (fiche de la bande, liste des bandes).

Les anciennes lignes « Vu » (refus de saisies faites sans réseau) restent dans le même écran.

**Doublon possible de sortie** : deux sorties du même jour, même bande, par deux personnes, avec le même nombre et le même destinataire.
- **Les deux restent enregistrées.**
- Celle de l'éleveur compte. Celle de l'autre personne est **mise de côté** : elle ne compte ni dans les poulets présents, ni dans les indicateurs, ni dans « Mon argent », et son lot tracé (QR) n'est créé que si elle est retenue.
- Dans « Saisies à vérifier », trois boutons :
  - **« Ce sont deux sorties différentes »** : les deux comptent ;
  - **« Garder celle de l'éleveur »** ;
  - **« Garder celle de l'agent »**.
  
  Chaque choix demande un motif.

**`docs/hors_ligne.md`** est mis à jour (section « Règles » et tests).

---

## D. « Case vide ≠ zéro »

### Saisie du jour (éleveur et agent, même formulaire)

```
 Morts aujourd'hui
 [ − ]   —   [ + ]        [ ✓ Aucun mort ]
 Sacs d'aliment · Aliment démarrage
 [ − ]   —   [ + ]        [ Pas d'aliment donné ]
 [            Envoyer ✓            ]
```

**Morts :**
- le compteur démarre à **« — »** (pas noté) ;
- la grosse case **« ✓ Aucun mort »** met 0 d'un toucher ;
- le premier « + » met 1 ;
- « − » à 0 revient à « — ».

**Aliment** : même principe. Le compteur démarre à « — ». La case **« Pas d'aliment donné »** met 0, explicitement. Le premier « + » met 1 sac.

**Envoyer** :
- il est refusé tant que les morts sont à « — », avec le message **« Touchez « Aucun mort » s'il n'y a pas eu de mort »** ;
- il est refusé aussi tant que l'aliment est à « — », avec le message **« Touchez « Pas d'aliment donné » si vous n'avez pas donné d'aliment »** (écart 1) ;
- le contrôle se fait **sur le téléphone avant l'envoi** (même sans réseau), et **sur le serveur** ;
- **« Ajouter à la saisie du jour »** suit la même règle.

**Clics** : Saisie du jour → Envoyer reste **2**. « Aucun mort », « Pas d'aliment donné » et les +/− sont des choix dans l'écran.

### Calculs et tableaux de bord

- **Un jour non saisi n'est jamais compté 0** : il est compté « non saisi ».
  - La régularité (jours saisis / jours écoulés) existe déjà.
  - Nouveau : le nombre de jours non saisis est affiché sur la fiche de la bande, dans le bilan et dans les tableaux de bord.
- **Indice de consommation** : il porte la mention **« incomplet »** s'il manque des jours de saisie dans la bande (un jour non saisi n'a pas d'aliment noté). Cette mention apparaît sur la fiche de la bande, le bilan, le rapport PDF et le tableau de bord (« IC moyen · incomplet : 4 bandes sur 12 »).
- **Mortalité cumulée** : elle reste la somme des morts notés, avec la mention « incomplet (N jours non saisis) » (écart 2).
- **Feu** : il ne lit jamais un jour non saisi comme « 0 mort ». Le feu orange « pas envoyé hier » existe déjà.
- **Courbes** : un jour non saisi est un trou, jamais un point à 0 (écart 3).
- **Saisies anciennes** (avant le lot 12) : une saisie faite avec 0 sac est considérée comme « pas d'aliment donné ». On ne peut pas distinguer, et c'était l'ancien sens.

---

## Tables et champs (migration 0014)

| Table | Champs | Rôle |
|---|---|---|
| **`reponse_veterinaire`** (nouvelle) | id, alerte_id, texte, conseils (JSON : liste de libellés), veto_id, cree_le, lue_le | réponse datée et signée ; `lue_le` sert à la pastille |
| **`visite`** (nouvelle, mixin terrain, périmètre ferme) | ferme_id, agent_id, date_prevue (facultative), objet, statut (PREVUE · FAITE · ANNULEE), faite_le, constats, recommandations (JSON), recommandation_libre, latitude, longitude, photo, motif_annulation, vue_par_eleveur_le | visites techniques |
| **`conflit_hors_ligne`** (existante : « Saisies à vérifier ») | + genre (SAISIE_JOUR · LIVRAISON · SORTIE · MESSAGE), objet_table, objet_id, bande_id, versions (JSON), statut (A_VERIFIER · TRANCHE · VU), retenue, motif, decide_par, decide_le | deux versions côte à côte et décision ; les anciennes lignes deviennent « MESSAGE » |
| **`saisie_jour`** | + a_verifier (booléen), + aliment_note (booléen) | journée en attente de décision ; aliment noté explicitement |
| **`sortie`** | + a_verifier, + mise_de_cote (booléens) | doublon possible |
| **`liste_deroulante`** | catégories `conseils_veterinaire`, `recommandations_visite`, `objets_visite` | listes configurables (ADMIN) |

**Versions** : `[{auteur_id, auteur, profil, saisi_le, valeurs: {morts, aliments: {produit: sacs}}}]`. La version de l'éleveur est dans `saisie_jour`. Celle de l'agent est gardée dans `versions`, et n'est jamais perdue.

---

## Chemins de clics

| Qui | Action | Clics |
|---|---|---|
| Éleveur | Accueil → « 💬 Le vétérinaire vous a répondu » | 1 |
| Éleveur | Vaccins et soins → Mes signalements | 2 |
| Éleveur | 👤 Moi → Mes visites | 2 |
| Éleveur | Saisie du jour → Envoyer | 2 (inchangé) |
| Vétérinaire | Alertes → alerte → Envoyer à l'éleveur | 3 |
| Agent | fiche ferme → Planifier une visite → Enregistrer | 2 |
| Agent | fiche ferme → Compte rendu → Enregistrer | 2 |
| Agent | encadré Alertes → Saisies à vérifier → Retenir cette version | 2 |

---

## Écarts et choix à valider

1. **L'aliment est obligatoire comme les morts** à l'envoi (« — » refusé). Vous dites « Pas d'aliment donné possible mais explicite ». Je le comprends comme : on ne peut pas envoyer avec l'aliment à « — ». Sinon un jour pourrait avoir des morts sans aliment noté. S'il n'y a aucun aliment en stock, seule la case « Pas d'aliment donné » s'affiche.
2. **La mortalité cumulée porte aussi « incomplet »** quand des jours manquent, pas seulement l'indice de consommation. Le chiffre ne change pas, il est simplement signalé.
3. **Courbes et séries par jour** : un jour non saisi est un trou.
4. **Conflit de saisie du jour** : il porte sur les morts **et** sur l'aliment. Les deux versions sont gardées entières. Une saisie est « à vérifier » si l'un des deux diffère.
5. **Agent en ligne, après l'éleveur, même jour** : l'écran « Déjà envoyé » existe déjà. Il propose désormais deux choix :
   - **« Ajouter »** : des morts de plus dans la journée. Cela s'additionne, comme aujourd'hui ;
   - **« Mes chiffres sont différents »** : les deux versions sont gardées, et la journée passe « à vérifier ».
   
   Sans réseau, c'est automatiquement « deux versions ».
6. **Agent avant l'éleveur** : la version de l'éleveur, arrivée en second, devient celle qui compte ; celle de l'agent est gardée à côté.
7. **Confirmation de livraison** : même règle (deux versions, celle de l'éleveur compte). Elle remplace « la plus récente gagne ».
8. **Doublon de sortie** : la sortie de l'autre personne est **mise de côté** (non comptée, sans lot QR) jusqu'à la décision. « Ce sont deux sorties différentes » la remet en compte. C'est la seule façon de suivre « les indicateurs utilisent la version de l'éleveur » sans compter deux fois les mêmes poulets.
9. **Qui tranche** : l'agent de la ferme, la DGE et l'ADMIN. L'éleveur ne tranche jamais.
10. **La réponse du vétérinaire est possible aussi sur les alertes du feu rouge.** Elles apparaissent alors dans « Mes signalements » de l'éleveur.
11. **L'agent ne voit que « a répondu le … »**, sans le contenu, ni les signes, ni les photos.
12. **Visite non planifiée** : un compte rendu est possible sans visite prévue. On ne peut pas éditer un compte rendu une fois envoyé ; seule une correction de l'ADMIN avec motif est possible (déjà prévue dans le journal).
13. **Ligne d'état** : on affiche la prochaine visite prévue, quelle que soit sa date (« Visite de Paul jeudi 12 », « Visite de Paul le 03/12 »). Une visite passée et non faite n'est plus affichée à l'éleveur. Elle reste « en retard » chez l'agent.
14. **Pastille « nouveau » sur 👤 Moi** : petite pastille ronde « nouveau », comme les pastilles des tuiles.
15. **Les listes de départ** (conseils, recommandations, objets) sont **à valider** par les vétérinaires et par la DGE.
