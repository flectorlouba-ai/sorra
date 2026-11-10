"""Lot R — version ordinateur : les fonctionnalités de chaque profil (boutons de gauche, 2 par ligne), leur point
d'entrée EXISTANT, leur compteur (ce qui attend une action) et leur bouton « ＋ ». Référence :
docs/maquettes/validees/maquette_sorra_bureau.html. Les règles et les droits sont ceux des écrans existants."""
from flask import request, url_for

from app.models import Profil

# (clé, icône, nom, endpoint, compteur (fonction(user) → int | None), bouton « ＋ » : (libellé, endpoint) | None,
#  autres endpoints de la même fonctionnalité — pour savoir quel bouton est actif)
FONCTIONS = {
    Profil.DGE: [
        ('accueil', '📊', 'Accueil national', 'bureau.accueil', None, ('＋ Nouvelle action', 'actions.liste', '?nouvelle=1'), ()),
        ('elevages', '🗺️', 'Élevages', 'fermes.liste', '_n_fermes_rouges', ('＋ Nouvel élevage', 'fermes.nouvelle'),
         ('fermes.', 'indicateurs.niveaux', 'pilotage.carte')),
        ('livraisons', '🚚', 'Livraisons', 'dge.planning', '_n_prevues_en_retard', ('＋ Planifier une livraison', 'dge.planning', '#prevoir'),
         ('livraisons.', 'dge.planning', 'dge.prevoir')),
        ('commandes', '🛒', 'Commandes', 'agent.commandes', '_n_commandes', ('＋ Nouvelle commande', 'agent.commandes', '#commander'), ('agent.commandes',)),
        ('arbitrages', '⚖️', 'Arbitrages', 'hors_ligne.conflits', '_n_arbitrages', ('＋ Signaler un écart', 'hors_ligne.conflits', '@creation'), ('hors_ligne.',)),
        ('classement', '🏆', 'Classement', 'dge.classement', None, ('＋ Nouveau classement', 'dge.classement', '?recalcul=1'), ('dge.classement',)),
        ('rapports', '📑', 'Rapports', 'actions.rapports', None, ('＋ Générer un rapport', 'actions.rapports', '@fen-generer'),
         ('actions.rapports', 'actions.generer', 'pilotage.rapports', 'pilotage.tableau', 'indicateurs.mes', 'controle.', 'catalogue.', 'parametres.', 'listes.',
          'dge.agents', 'operateurs.', 'tracabilite.', 'sante.', 'veto.', 'imports.')),
        ('actions', '🎯', "Plans d'actions", 'actions.liste', '_n_actions_retard', ('＋ Nouvelle action', 'actions.liste', '?nouvelle=1'), ('actions.',)),
    ],
    Profil.VETO: [
        ('accueil', '🩺', 'Accueil sanitaire', 'bureau.accueil', None, ('＋ Créer une alerte', 'bureau.accueil', '@creation'), ()),
        ('signalements', '📨', 'Signalements', 'sante.alertes', '_n_signalements', ('＋ Enregistrer un signalement', 'sante.alertes', '@creation'),
         ('sante.alertes', 'sante.alerte', 'sante.declarations')),
        ('seuils', '🎚️', 'Seuils sanitaires', 'veto.parametres', None, ('＋ Proposer un seuil', 'veto.parametres', '#proposer'), ('veto.parametres',)),
        ('calendrier', '📅', 'Calendrier vaccinal', 'sante.vaccins', None, ('＋ Ajouter une étape', 'sante.vaccins', '@fen-entree'), ('sante.vaccins',)),
        ('diagnostics', '🔬', 'Diagnostics', 'bureau.diagnostics', None, ('＋ Nouveau diagnostic', 'bureau.diagnostics', '@creation'), ()),
        ('bloquees', '⛔', 'Ventes bloquées', 'veto.surveillance', '_n_surveillance', ('＋ Bloquer une bande', 'veto.surveillance', '#bloquer'), ('veto.surveillance',)),
        ('tracabilite', '🔎', 'Traçabilité', 'veto.recherche', None, ('＋ Nouvelle recherche', 'veto.recherche', '#recherche'), ('veto.recherche', 'tracabilite.')),
        ('validations', '👀', 'Validations sensibles', 'controle.approbations_ecran', '_n_a_approuver', ('＋ Proposer un changement', 'veto.parametres', '#proposer'), ('controle.approbations',)),
    ],
    Profil.ADMIN: [
        ('accueil', '🛡️', 'Administration', 'bureau.accueil', None, ('＋ Nouvelle action', 'actions.liste', '?nouvelle=1'), ()),
        ('utilisateurs', '👥', 'Utilisateurs', 'utilisateurs.index', None, ('＋ Nouvel utilisateur', 'utilisateurs.index', '@fen-user'), ('utilisateurs.',)),
        ('droits', '🔑', 'Profils et droits', 'bureau.droits', None, ('＋ Proposer un changement de droits', 'bureau.droits', '@creation'), ()),
        ('parametres', '⚙️', 'Paramètres', 'controle.configuration', None, ('＋ Ajouter un paramètre ou une liste', 'listes.index'),
         ('controle.configuration', 'parametres.', 'listes.', 'catalogue.', 'referentiel.', 'aides.administrer', 'entretien.taches', 'pilotage.formules', 'imports.', 'bureau.synchronisation')),
        ('validations', '👀', 'Validations', 'controle.approbations_ecran', '_n_a_approuver', ('＋ Proposer un changement', 'controle.configuration'), ('controle.approbations',)),
        ('securite', '🔐', 'Sessions et sécurité', 'controle.sessions', None, ("＋ Fermer les sessions d'un compte", 'controle.sessions', '@creation'), ('controle.sessions', 'controle.integrite')),
        ('journal', '📜', 'Journal', 'journal.index', None, ('＋ Exporter le journal', 'journal.export'), ('journal.',)),
    ],
    Profil.AUDITEUR: [
        ('accueil', '📊', "Tableau de bord d'audit", 'bureau.accueil', None, ('＋ Lancer une vérification', 'bureau.accueil', '@creation'), ()),
        ('journal', '📜', "Journal d'audit", 'journal.index', None, ('＋ Exporter le journal', 'journal.export'), ('journal.index', 'journal.detail')),
        ('integrite', '🔗', 'Intégrité', 'controle.integrite', None, ('＋ Lancer une vérification', 'controle.integrite', '@creation'), ('controle.integrite',)),
        ('scans', '📷', 'Journal des scans', 'journal.scans', None, ('＋ Exporter les scans', 'journal.scans_export'), ('journal.scans',)),
        ('exports', '⬇️', 'Journal des exports', 'bureau.exports', None, ('＋ Nouvel export', 'journal.export'), ()),
        ('recherche', '🔍', 'Recherche', 'bureau.recherche', None, ('＋ Nouvelle recherche', 'bureau.recherche', '#recherche'), ()),
    ],
    Profil.ELEVEUR: [
        ('accueil', '🏠', 'Mon accueil', 'bureau.accueil', None, ("＋ Saisir aujourd'hui", 'eleveur.saisie'), ()),
        ('bandes', '🐔', 'Mes bandes', 'bandes.mes_bandes', None, ('＋ Ouvrir une bande', 'bandes.ouvrir'), ('bandes.',)),
        ('saisie', '📝', 'Saisie journalière', 'eleveur.saisie', None, ("＋ Saisir aujourd'hui", 'eleveur.saisie'), ('eleveur.saisie',)),
        ('argent', '💰', 'Mon argent', 'argent.mon_argent', None, ("＋ J'ai payé / J'ai vendu", 'argent.payer'), ('argent.', 'eleveur.achat', 'eleveur.stock')),
        ('sante', '🩺', 'Santé', 'eleveur.soins', None, ('＋ Signaler un problème', 'sante.declarer'), ('eleveur.soins', 'sante.')),
        ('livraisons', '🚚', 'Livraisons', 'eleveur.produits', None, ('＋ Signaler une différence', 'eleveur.produits', '#differences'), ('eleveur.produits', 'livraisons.')),
        ('lots', '📦', 'Mes lots', 'bureau.mes_lots', None, ('＋ Déclarer une sortie', None, '/aller/sortie'), ()),
        ('bceg', '🏦', 'Consentement BCEG', 'eleveur.ma_banque', None, ('＋ Donner ou retirer mon accord', 'eleveur.ma_banque', '#accord'), ('eleveur.ma_banque',)),
    ],
    Profil.AGENT: [
        ('accueil', '🏠', 'Mon accueil', 'bureau.accueil', '_n_actions_retard', ('＋ Nouvelle visite', 'bureau.accueil', '@creation'), ('actions.',)),
        ('fermes', '🏘️', 'Mes fermes', 'fermes.liste', '_n_fermes_rouges', ('＋ Nouvelle ferme', 'fermes.nouvelle'), ('fermes.liste', 'fermes.fiche', 'fermes.modifier')),
        ('enrolement', '➕', 'Enrôlement', 'bureau.enrolement', None, ('＋ Enrôler une ferme', 'fermes.nouvelle'),
         ('fermes.nouvelle', 'agent.nouvel_eleveur')),
        ('tournees', '🚗', 'Mes tournées', 'agent.tournee', '_n_tournee', ('＋ Planifier une tournée', 'agent.tournee', '@creation'), ('agent.tournee',)),
        ('visites', '📋', 'Visites', 'bureau.visites', None, ('＋ Nouveau compte rendu', 'bureau.visites', '@creation'), ('visites.',)),
        ('controle', '⚖️', 'Contrôle des saisies', 'hors_ligne.conflits', '_n_a_verifier', ('＋ Signaler un écart', 'hors_ligne.conflits', '@creation'), ('hors_ligne.',)),
        ('stocks', '📦', 'Stocks et livraisons', 'livraisons.liste', None, ('＋ Livraison reçue', 'livraisons.nouvelle'), ('livraisons.',)),
        ('commandes', '🛒', 'Commandes', 'agent.commandes', '_n_commandes', ('＋ Préparer une commande', 'agent.commandes'), ('agent.commandes',)),
    ],
    Profil.OPERATEUR: [
        ('accueil', '🏭', 'Accueil', 'bureau.accueil', None, None, ()),
        ('attendus', '🚚', 'Lots qui arrivent', 'operateur.attendus', None, None, ('operateur.attendus',)),
        ('receptions', '📋', 'Mes réceptions', 'operateur.receptions', None, None, ('operateur.receptions', 'operateur.reception')),
        ('scanner', '📷', 'Scanner', 'operateur.scanner', None, None, ('operateur.scanner', 'operateur.lot')),
    ],
    Profil.BCEG: [('accueil', '🏦', 'Accueil BCEG', 'bureau.accueil', None, None, ()),
                  ('fermes', '🏘️', 'Fermes financées', 'maedr.bceg_fermes', None, None, ('maedr.bceg_fermes',))],
    Profil.MAEDR: [('accueil', '🏛️', 'Accueil MAEDR', 'bureau.accueil', '_n_visas', None, ()),
                   ('visas', '📑', 'Rapports à viser', 'maedr.visas', '_n_visas', None, ('maedr.',))],
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
        b = None
        if bouton:
            # (libellé, endpoint, complément) — complément : '?x=1' ou '#ancre' ajouté au lien ; '@fen-x' : ouvre la fenêtre
            # fen-x de la page quand on y est ; '@creation' : la fenêtre de création du tableau conforme (lot K)
            lib, bep, extra = (bouton + (None,))[:3]
            lien = url_for(bep) if bep else None
            ouvrir = None
            if extra and extra.startswith('@'):
                ouvrir = extra[1:]
                lien = (lien or '') + '#ouvrir'
            elif extra:
                lien = (lien or '') + extra
            b = {'libelle': lib, 'lien': lien, 'ouvrir': ouvrir, 'ici': endpoint == bep or endpoint == 'bureau.accueil' and bep == 'bureau.accueil'}
        resultat.append({'cle': cle, 'icone': icone, 'nom': nom, 'lien': url_for(ep), 'actif': actif,
                         'compteur': n or None, 'bouton': b})
    # Une seule fonctionnalité active : la plus précise (hors accueil) ; sinon l'accueil quand on y est
    actifs = [f for f in resultat if f['actif'] and f['cle'] != 'accueil']
    for f in resultat:
        f['actif'] = (f in actifs[:1]) if actifs else (f['cle'] == 'accueil' and endpoint == 'bureau.accueil')
    return resultat


def fonction_active(user):
    return next((f for f in fonctions_pour(user) if f['actif']), None)
