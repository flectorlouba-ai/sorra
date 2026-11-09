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

## Par la DGE (et les vétérinaires pour les visites)

| Point | Où le changer | Valeur de départ | Lot |
|---|---|---|---|
| Catégories de dépenses « J'ai payé » | Listes → `categories_depenses` | 7 catégories | 11 |
| Seuil d'affichage des totaux d'argent par province | code (`argent.SEUIL_AGREGAT`) | 3 fermes | 11 |
| **Recommandations de visite** (provisoire) | Listes → `recommandations_visite` | 6 recommandations | 12 |
| **Objets de visite** (provisoire) | Listes → `objets_visite` | Suivi, Vaccination, Contrôle, Panne, Autre | 12 |
| Délai avant qu'un doublon de sortie non tranché passe en rouge et remonte à la DGE | code (`verifications.DELAI_ROUGE_HEURES`) | 48 h | 12 |
| Seuil « à vérifier » de la dernière synchronisation du téléphone | code | 3 jours | 10 |

## Test terrain

L'écran de l'éleveur doit être **testé par 3 à 5 vrais éleveurs** avant d'être figé (`docs/ergonomie.md`, section E) : 8 tuiles, saisie du jour avec « — », « Aucun mort », « Comme hier ».
