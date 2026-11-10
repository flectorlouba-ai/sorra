from app.models.base import SaisieTerrainMixin, HorodatageMixin, StatutSynchro  # noqa: F401
from app.models.utilisateur import (Utilisateur, UtilisateurFerme, Profil,  # noqa: F401
                                    PROFILS_NATIONAUX, utilisateur_province)
from app.models.referentiel import Province, Localite  # noqa: F401
from app.models.liste_deroulante import ListeDeroulante  # noqa: F401
from app.models.parametre import Parametre, TypeParametre  # noqa: F401
from app.models.compteur import Compteur  # noqa: F401
from app.models.journal import JournalAudit  # noqa: F401
from app.models.ferme import (Ferme, Batiment, FermeStatutHistorique,  # noqa: F401
                              FermeInfrastructure, SourcePosition)
from app.models.operateur import Operateur  # noqa: F401
from app.models.intrant import (Produit, Livraison, LivraisonLigne, Fournisseur,  # noqa: F401
                                StatutLivraison, OrigineLivraison)
from app.models.bande import (Bande, BandePoussins, SaisieJour, SaisieAliment,  # noqa: F401
                              Pesee, Sortie, StatutBande, MotifSortie)
from app.models.sante import (Declaration, DeclarationPhoto, AlerteSanitaire,  # noqa: F401
                              AlerteHistorique, CalendrierVaccinal, Vaccination, Traitement,
                              StatutAlerte, OrigineAlerte)
from app.models.tracabilite import LotTrace, Reception, Scan  # noqa: F401
from app.models.hors_ligne import EnvoiHorsLigne, ConflitHorsLigne  # noqa: F401
from app.models.entretien import TacheEntretien, EntretienFait, Panne  # noqa: F401
from app.models.argent import Depense  # noqa: F401
from app.models.visite import Visite  # noqa: F401
from app.models.aide import Aide  # noqa: F401
from app.models.bceg import ConsentementBceg, DecisionBceg  # noqa: F401
from app.models.securite import JournalChaine, Proposition, SessionUtilisateur  # noqa: F401
from app.models.agent import CommandeIntrant, InventaireStock  # noqa: F401
from app.models.veto import Diagnostic, BlocageSorties  # noqa: F401
from app.models.dge import RapportMensuel  # noqa: F401

from app.models.position import PositionFerme  # noqa: F401,E402  (lot E)
from app.models.rapport import Rapport, TypeRapport  # noqa: F401,E402  (lot D)
from app.models.action import Action, OrigineAction, Priorite  # noqa: F401,E402  (lot D)
from app.models.notification import AbonnementPush, PreferenceNotification, Notification, TypeNotification  # noqa: F401,E402  (lot T)

# Lot A : saisies archivées masquées partout (voir app/models/base.py)
from app.models.base import masquer_archivees as _masquer  # noqa: E402
from app.models.entretien import EntretienFait as _EF, Panne as _P  # noqa: E402
_masquer(SaisieJour, Pesee, Vaccination, Traitement, Depense, _EF, _P, Visite,
         # Fiches qui ne s'archivent que si rien ne les utilise (achat sans poussins en bande, bande vide, ferme vide)
         Livraison, Bande, Ferme, Action)
