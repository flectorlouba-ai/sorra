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
| **Liste des réglages sensibles** soumis aux quatre yeux | code (`approbations.SENSIBLES`) | seuils sanitaires, délais, formules, calendrier vaccinal, profils | 15 |
| Seuil « à vérifier » de la dernière synchronisation du téléphone | code | 3 jours | 10 |

## Textes à faire relire (éleveurs, agents, DGE)

| Point | Où le changer | Lot |
|---|---|---|
| **Message du blocage à l'éleveur** : « ⛔ Le vétérinaire a bloqué les ventes de cette bande » + « 📞 Appeler le vétérinaire » | `templates/eleveur/_accueil.html`, `templates/bandes/sortie.html` | 17 |
| **Les 4 phrases du tutoriel** : « Chaque jour, notez vos morts et votre aliment. » · « Un problème avec vos poulets ? Prévenez le vétérinaire. » · « Pas de réseau ? Saisissez quand même : tout part quand le réseau revient. » · « Votre agent Paul est là pour vous aider. » | `templates/eleveur/presentation.html` | 13 |
| **Les 9 aides « Comment faire ? »** (titres et 3 étapes chacune) | Configuration → Aides (ADMIN) | 13 |
| **Le texte de « Ma banque »** (ce que la BCEG verra et ne verra pas) — à faire valider aussi par la BCEG | `templates/eleveur/ma_banque.html` | 13 |

## Test terrain

L'écran de l'éleveur doit être **testé par 3 à 5 vrais éleveurs** avant d'être figé (`docs/ergonomie.md`, section E) : 8 tuiles, saisie du jour avec « — », « Aucun mort », « Comme hier ».
