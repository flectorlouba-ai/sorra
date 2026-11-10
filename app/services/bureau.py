"""Lot R — version ordinateur : les fonctionnalités de chaque profil (boutons de gauche, 2 par ligne), leur point
d'entrée EXISTANT, leur compteur (ce qui attend une action) et leur bouton « ＋ ». Référence :
docs/maquettes/validees/maquette_sorra_bureau.html. Les règles et les droits sont ceux des écrans existants."""
from flask import request, url_for

from app.models import Profil

# (clé, icône, nom, endpoint, compteur (fonction(user) → int | None), bouton « ＋ » : (libellé, endpoint) | None,
#  autres endpoints de la même fonctionnalité — pour savoir quel bouton est actif)
FONCTIONS = {
    Profil.DGE: [
        ('accueil', '📊', 'Accueil national', 'bureau.accueil', None, ('＋ Nouvelle action', None), ()),
        ('elevages', '🗺️', 'Élevages', 'fermes.liste', '_n_fermes_rouges', ('＋ Nouvel élevage', 'fermes.nouvelle'),
         ('fermes.', 'indicateurs.niveaux', 'pilotage.carte')),
        ('livraisons', '🚚', 'Livraisons', 'dge.planning', '_n_prevues_en_retard', ('＋ Planifier une livraison', 'dge.planning'),
         ('livraisons.', 'dge.planning', 'dge.prevoir')),
        ('commandes', '🛒', 'Commandes', 'agent.commandes', '_n_commandes', None, ('agent.commandes',)),
        ('arbitrages', '⚖️', 'Arbitrages', 'hors_ligne.conflits', '_n_arbitrages', None, ('hors_ligne.',)),
        ('classement', '🏆', 'Classement', 'dge.classement', None, None, ('dge.classement',)),
        ('rapports', '📑', 'Rapports', 'pilotage.rapports', None, ('＋ Générer un rapport', 'pilotage.rapports'),
         ('pilotage.rapports', 'pilotage.tableau', 'indicateurs.mes', 'controle.', 'catalogue.', 'parametres.', 'listes.',
          'dge.agents', 'operateurs.', 'tracabilite.', 'sante.', 'veto.')),
        ('actions', '🎯', "Plans d'actions", 'bureau.plans_actions', None, ('＋ Nouvelle action', None), ()),
    ],
    Profil.VETO: [
        ('accueil', '🩺', 'Accueil sanitaire', 'bureau.accueil', None, None, ()),
        ('signalements', '📨', 'Signalements', 'sante.alertes', '_n_signalements', None, ('sante.alertes', 'sante.alerte', 'sante.declarations')),
        ('seuils', '🎚️', 'Seuils sanitaires', 'veto.parametres', None, ('＋ Proposer un seuil', 'veto.parametres'), ('veto.parametres',)),
        ('calendrier', '📅', 'Calendrier vaccinal', 'sante.vaccins', None, ('＋ Ajouter une étape', 'sante.vaccins'), ('sante.vaccins',)),
        ('diagnostics', '🔬', 'Diagnostics', 'bureau.diagnostics', None, None, ()),
        ('bloquees', '⛔', 'Ventes bloquées', 'veto.surveillance', '_n_surveillance', ('＋ Bloquer une bande', 'veto.surveillance'), ('veto.surveillance',)),
        ('tracabilite', '🔎', 'Traçabilité', 'veto.recherche', None, None, ('veto.recherche', 'tracabilite.')),
        ('validations', '👀', 'Validations sensibles', 'controle.approbations_ecran', '_n_a_approuver', None, ('controle.approbations',)),
    ],
    Profil.ADMIN: [
        ('accueil', '🛡️', 'Administration', 'bureau.accueil', None, None, ()),
        ('utilisateurs', '👥', 'Utilisateurs', 'utilisateurs.index', None, ('＋ Nouvel utilisateur', 'utilisateurs.index'), ('utilisateurs.',)),
        ('droits', '🔑', 'Profils et droits', 'bureau.droits', None, None, ()),
        ('parametres', '⚙️', 'Paramètres', 'controle.configuration', None, ('＋ Ajouter un paramètre ou une liste', 'parametres.index'),
         ('controle.configuration', 'parametres.', 'listes.', 'catalogue.', 'referentiel.', 'aides.administrer', 'entretien.taches', 'pilotage.formules')),
        ('validations', '👀', 'Validations', 'controle.approbations_ecran', '_n_a_approuver', None, ('controle.approbations',)),
        ('securite', '🔐', 'Sessions et sécurité', 'controle.sessions', None, None, ('controle.sessions', 'controle.integrite')),
        ('journal', '📜', 'Journal', 'journal.index', None, ('＋ Exporter le journal', 'journal.export'), ('journal.',)),
    ],
    Profil.AUDITEUR: [
        ('accueil', '📊', "Tableau de bord d'audit", 'bureau.accueil', None, None, ()),
        ('journal', '📜', "Journal d'audit", 'journal.index', None, ('＋ Exporter le journal', 'journal.export'), ('journal.index', 'journal.detail')),
        ('integrite', '🔗', 'Intégrité', 'controle.integrite', None, None, ('controle.integrite',)),
        ('scans', '📷', 'Journal des scans', 'journal.scans', None, ('＋ Exporter les scans', 'journal.scans_export'), ('journal.scans',)),
        ('exports', '⬇️', 'Journal des exports', 'bureau.exports', None, None, ()),
        ('recherche', '🔍', 'Recherche', 'bureau.recherche', None, None, ()),
    ],
    Profil.ELEVEUR: [
        ('accueil', '🏠', 'Mon accueil', 'bureau.accueil', None, ("＋ Saisir aujourd'hui", 'eleveur.saisie'), ()),
        ('bandes', '🐔', 'Mes bandes', 'bandes.mes_bandes', None, ('＋ Ouvrir une bande', 'bandes.ouvrir'), ('bandes.',)),
        ('saisie', '📝', 'Saisie journalière', 'eleveur.saisie', None, ("＋ Saisir aujourd'hui", 'eleveur.saisie'), ('eleveur.saisie',)),
        ('argent', '💰', 'Mon argent', 'argent.mon_argent', None, ("＋ J'ai payé", 'argent.payer'), ('argent.', 'eleveur.achat', 'eleveur.stock')),
        ('sante', '🩺', 'Santé', 'eleveur.soins', None, ('＋ Signaler un problème', 'sante.declarer'), ('eleveur.soins', 'sante.')),
        ('livraisons', '🚚', 'Livraisons', 'eleveur.produits', None, None, ('eleveur.produits', 'livraisons.')),
        ('lots', '📦', 'Mes lots', 'bureau.mes_lots', None, None, ()),
        ('bceg', '🏦', 'Consentement BCEG', 'eleveur.ma_banque', None, None, ('eleveur.ma_banque',)),
    ],
    Profil.AGENT: [
        ('accueil', '🏠', 'Mon accueil', 'bureau.accueil', None, ('＋ Nouvelle visite', None), ()),
        ('fermes', '🏘️', 'Mes fermes', 'fermes.liste', '_n_fermes_rouges', ('＋ Nouvelle ferme', 'fermes.nouvelle'), ('fermes.liste', 'fermes.fiche', 'fermes.modifier')),
        ('enrolement', '➕', 'Enrôlement', 'fermes.nouvelle', None, ('＋ Enrôler une ferme', 'fermes.nouvelle'),
         ('fermes.nouvelle', 'agent.nouvel_eleveur')),
        ('tournees', '🚗', 'Mes tournées', 'agent.tournee', '_n_tournee', None, ('agent.tournee',)),
        ('visites', '📋', 'Visites', 'bureau.visites', None, None, ('visites.',)),
        ('controle', '⚖️', 'Contrôle des saisies', 'hors_ligne.conflits', '_n_a_verifier', None, ('hors_ligne.',)),
        ('stocks', '📦', 'Stocks et livraisons', 'livraisons.liste', None, ('＋ Livraison reçue', 'livraisons.nouvelle'), ('livraisons.',)),
        ('commandes', '🛒', 'Commandes', 'agent.commandes', '_n_commandes', ('＋ Préparer une commande', 'agent.commandes'), ('agent.commandes',)),
    ],
    Profil.OPERATEUR: [
        ('accueil', '🏭', 'Accueil', 'bureau.accueil', None, None, ()),
        ('attendus', '🚚', 'Lots qui arrivent', 'operateur.attendus', None, None, ('operateur.attendus',)),
        ('receptions', '📋', 'Mes réceptions', 'operateur.receptions', None, None, ('operateur.receptions', 'operateur.reception')),
        ('scanner', '📷', 'Scanner', 'operateur.scanner', None, None, ('operateur.scanner', 'operateur.lot')),
    ],
    Profil.BCEG: [('accueil', '🏦', 'Accueil BCEG', 'bureau.accueil', None, None, ())],
    Profil.MAEDR: [('accueil', '🏛️', 'Accueil MAEDR', 'bureau.accueil', None, None, ())],
}


def fonctions_pour(user):
    """Les boutons du profil, avec leur lien, leur compteur et s'ils sont actifs pour la page ouverte."""
    from app.routes import accueil as compteurs
    endpoint = request.endpoint or ''
    if endpoint == 'accueil.index':
        endpoint = 'bureau.accueil'
    resultat = []
    for cle, icone, nom, ep, compteur, bouton, autres in FONCTIONS.get(user.profil, []):
        actif = endpoint == ep or any(endpoint == a or (a.endswith('.') and endpoint.startswith(a)) for a in autres)
        n = getattr(compteurs, compteur)(user) if compteur else None
        resultat.append({'cle': cle, 'icone': icone, 'nom': nom, 'lien': url_for(ep), 'actif': actif,
                         'compteur': n or None,
                         'bouton': {'libelle': bouton[0], 'lien': url_for(bouton[1]) if bouton[1] else None} if bouton else None})
    # Une seule fonctionnalité active : la plus précise (hors accueil) ; sinon l'accueil quand on y est
    actifs = [f for f in resultat if f['actif'] and f['cle'] != 'accueil']
    for f in resultat:
        f['actif'] = (f in actifs[:1]) if actifs else (f['cle'] == 'accueil' and endpoint == 'bureau.accueil')
    return resultat


def fonction_active(user):
    return next((f for f in fonctions_pour(user) if f['actif']), None)
