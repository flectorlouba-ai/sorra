# SORRA — Points à faire valider par les vétérinaires et la DGE

Liste unique, tenue à jour à chaque lot. Toutes ces valeurs sont **provisoires**. Elles se modifient sans développement :
- dans **Configuration → Paramètres** ;
- dans **Configuration → Listes** ;
- ou dans **Santé → Calendrier vaccinal**.

## Par les vétérinaires

| Point | Où le changer | Valeur de départ | Lot |
|---|---|---|---|
| Seuils du feu : orange et rouge (mortalité du jour) | Paramètres `bandes.seuil_orange_pct`, `bandes.seuil_rouge_pct` | 0,5 % et 1 % | 3 |
| Écart toléré à la courbe de croissance | Paramètre `bandes.ecart_courbe_pct` | 10 % | 3 |
| **Courbe de croissance attendue** (âge : poids) | Paramètre de la courbe | courbe de départ | 3 |
| **Calendrier vaccinal de départ** | Santé → Calendrier vaccinal (bouton « Valider le calendrier ») | calendrier de départ | 4 |
| Délai avant « vaccin en retard » | Paramètre `sante.retard_vaccin_jours` | 2 jours | 4 |
| Seuil de mortalité à l'arrivée des poussins | Paramètre `intrants.seuil_mortalite_arrivee_pct` | 2 % | 5 |
| Seuils des étoiles (mortalité, indice de consommation) | Paramètres | 3 %, 1,7 et 5 % | 8 |
| Texte du conseil du feu rouge | Santé → conseil | texte de départ | 8 |
| Tâches d'entretien de départ (noms, fréquences, installations) | Configuration → Tâches d'entretien | 7 tâches | 10 |
| **Conseils du vétérinaire à l'éleveur** (provisoire) | Listes → `conseils_veterinaire` | 6 conseils | 12 |
| **Maladies suspectées** du diagnostic | Listes → `maladies_suspectees` | 9 maladies + Autre | 17 |
| **Gravité des signalements** (feu rouge 3, déclaration de 10 poulets ou plus 2, sinon 1 ; +1 sans réponse depuis 24 h) | code (`veto.gravite`) | — | 17 |
| **Grille de biosécurité** (10 points) et seuils du score (rouge < 50 %, orange < 80 %) | Listes → `grille_biosecurite` ; seuils : code (`agent.couleur_score`) | 10 points | 16 |
| **Contrôles à la réception et leur caractère bloquant** (TOUS : bloquant partout ; ABATTOIR : bloquant à l'abattoir, pour information au marché, chez l'acheteur et le distributeur ; INFO ; NON) | Paramètres → `reception.controle_delai_attente`, `reception.controle_vaccins`, `reception.controle_pesee` (quatre yeux) | délai d'attente TOUS · vaccins ABATTOIR · pesée ABATTOIR | 19 |
| Contrôles de **refus** à la réception (QR inconnu, lot annulé, déjà reçu ou refusé par le vétérinaire, destiné à un autre opérateur, ventes bloquées) | code (`receptions.motif_refus`) | toujours un refus | 19 |
| **Vaccins obligatoires** à la réception : tous les vaccins actifs du calendrier dont la date (au plus tard le jour de la sortie) est passée, sauf ceux d'avant le début du suivi. **Tolérance** : un vaccin en retard de moins de N jours ne met pas le lot en réserve | Santé → Calendrier vaccinal ; tolérance : Paramètres → `reception.vaccin_tolerance_jours` (quatre yeux) | 2 jours | 19 |
| Pesée « récente » à la réception (avant la sortie) | Paramètres → `reception.pesee_max_jours` (quatre yeux) | moins de 7 jours | 19 |
| **Seuil des morts à la réception** (abattoir, marché) : au-delà, le vétérinaire de la zone est alerté quel que soit le motif. Distinct du seuil des poussins morts à l'arrivée à la ferme (`intrants.seuil_mortalite_arrivee_pct`) | Paramètres → `reception.seuil_morts_pct` (quatre yeux) | 2 % de l'annoncé | 19 |

## Par la DGE (et les vétérinaires pour les visites)

| Point | Où le changer | Valeur de départ | Lot |
|---|---|---|---|
| Catégories de dépenses « J'ai payé » | Listes → `categories_depenses` | 7 catégories | 11 |
| Seuil d'affichage des totaux d'argent par province | code (`argent.SEUIL_AGREGAT`) | 3 fermes | 11 |
| **Recommandations de visite** (provisoire) | Listes → `recommandations_visite` | 6 recommandations | 12 |
| **Objets de visite** (provisoire) | Listes → `objets_visite` | Suivi, Vaccination, Contrôle, Panne, Autre | 12 |
| Délai avant qu'un doublon de sortie non tranché passe en rouge et remonte à la DGE | Paramètres → `verifications.delai_rouge_heures` (quatre yeux) | 48 h | 12, 15 |
| **Durée d'inactivité avant déconnexion** (pilotage seulement ; éleveur et agent jamais) | Paramètres → `securite.duree_session_minutes` | 30 min (était 60) | 15 |
| **Profils à double authentification obligatoire** | Paramètres → `securite.profils_2fa` | ADMIN, DGE, MAEDR, BCEG, AUDITEUR | 15 |
| **Seuil d'écart de stock** (livré − utilisé − compté) | Paramètres → `intrants.seuil_ecart_stock_pct` (quatre yeux) | 10 % du livré | 16 |
| **Poids de l'urgence** des fermes de l'agent | code (`agent.ROUGE`, `agent.ORANGE`) | rouge 10, orange 3 | 16 |
| **Pondérations du classement** (mortalité, IC, GMQ, régularité) | Paramètres → `classement.poids_*` (quatre yeux) | 35 / 25 / 20 / 20 | 18 |
| **Barème des notes du classement** (mortalité 0 % → 100, 10 % → 0 ; IC 1,4 → 100, 2,6 → 0 ; GMQ 30 → 0, 70 g/j → 100) et seuil « bande incomplète » (80 % des jours saisis) | Paramètres → `classement.*` (quatre yeux) | voir ci-contre | 18 |
| **Charge d'un agent** (orange au-delà de 15 fermes, rouge au-delà de 25) | code (`dge.CHARGE_ORANGE`, `CHARGE_ROUGE`) | 15 / 25 | 18 |
| **Destinataires du rapport mensuel** et interrupteur d'envoi | Paramètres → `rapports.email_destinataires`, `rapports.email_actif` | aucun · coupé | 18 |
| **Liste des réglages sensibles** soumis aux quatre yeux | code (`approbations.SENSIBLES`) | seuils sanitaires, délais, formules, calendrier vaccinal, profils ; réglages `reception.*` depuis le lot 19 | 15, 19 |
| **Motifs d'écart à la réception** (touchés au quai ; seul « Autre » demande un texte). Tout écart de nombre, ou des morts au-delà du seuil, demande un motif | Listes → `motifs_ecart_quai` | Erreur de comptage · Morts au transport · Poulets échappés · Autre | 19 |
| **Refus répétés du même QR** qui alertent la DGE (tous opérateurs confondus) | Paramètres → `reception.refus_alerte_nombre`, `reception.refus_alerte_heures` (quatre yeux) | 3 refus en 24 h | 19 |
| Type d'opérateur « Marché » (le type « Abattoir » seul applique tous les contrôles) | Listes → `types_operateurs` | ajouté au lot 19 | 19 |
| Seuil « à vérifier » de la dernière synchronisation du téléphone | code | 3 jours | 10 |

## Textes à faire relire (éleveurs, agents, DGE)

| Point | Où le changer | Lot |
|---|---|---|
| **Message du blocage à l'éleveur** : « ⛔ Le vétérinaire a bloqué les ventes de cette bande » + « 📞 Appeler le vétérinaire » | `templates/eleveur/_accueil.html`, `templates/bandes/sortie.html` | 17 |
| **Les 4 phrases du tutoriel** : « Chaque jour, notez vos morts et votre aliment. » · « Un problème avec vos poulets ? Prévenez le vétérinaire. » · « Pas de réseau ? Saisissez quand même : tout part quand le réseau revient. » · « Votre agent Paul est là pour vous aider. » | `templates/eleveur/presentation.html` | 13 |
| **Les 9 aides « Comment faire ? »** (titres et 3 étapes chacune) | Configuration → Aides (ADMIN) | 13 |
| **Messages de l'éleveur sur ses sorties** : « ✓ Partis › ✓ Reçus par l'abattoir — L'abattoir a compté N vivants et M morts au transport », « ◷ En attente du vétérinaire », « ✗ Le vétérinaire n'a pas accepté ces poulets — appelez votre agent » | `services/receptions.etat_pour_eleveur` | 19 |
| **Messages de refus au quai** (QR inconnu, lot annulé, déjà reçu, destiné à un autre opérateur, ventes bloquées) | `services/receptions.motif_refus` | 19 |
| **Le texte de « Ma banque »** (ce que la BCEG verra et ne verra pas) — à faire valider aussi par la BCEG | `templates/eleveur/ma_banque.html` | 13 |

## Test terrain

L'écran de l'éleveur doit être **testé par 3 à 5 vrais éleveurs** avant d'être figé (`docs/ergonomie.md`, section E) : 8 tuiles, saisie du jour avec « — », « Aucun mort », « Comme hier ».
