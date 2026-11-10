"""Accueil — repris de l'accueil de PERFORM YL.1 : onglets par module, tuiles,
encadré Alertes (maquette A, docs/maquettes/maquettes_lot1.md)."""
from flask import Blueprint, render_template, url_for, session, redirect
from flask_login import login_required, current_user

from app import indicateurs
from app.models import Ferme, Profil, Livraison, Bande
from app.models.bande import StatutBande
from app.services import bandes as regles_bandes
from app.models.base import maintenant
from app.models.intrant import StatutLivraison
from app.services import intrants
from app.utils.dates import en_utc
from app.utils.permissions import filtre_perimetre

accueil_bp = Blueprint('accueil', __name__)

A, D = Profil.ADMIN, Profil.DGE

# ── Lot 15 : accueil du pilotage en tuiles par profil ───────────────────
# Une tuile : (titre, sous-titre, icône, endpoint, compteur). Une tuile n'existe que si son écran
# existe (aucune tuile morte) ; la table tuile → écran → lot est dans docs/pilotage.md.


def _n_visas(user):
    from app.services import maedr
    return maedr.n_a_viser() if user.profil == Profil.MAEDR else 0


def _n_a_verifier(user):
    from app.routes.hors_ligne import conflits_a_voir
    return conflits_a_voir(user).count()


def _n_arbitrages(user):
    from app.models.hors_ligne import ConflitHorsLigne
    from app.services import verifications
    return verifications.a_trancher(filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)).count()


def _n_a_approuver(user):
    from app.services import approbations
    return len(approbations.a_decider(user))


def _n_signalements(user):
    from app.models.sante import AlerteSanitaire, StatutAlerte
    from app.services import sante
    from app.services import receptions
    retenus = receptions.sous_reserve_visibles(user).count() if user.profil == Profil.VETO else 0   # lot 19
    return sante.alertes_visibles(user).filter(AlerteSanitaire.statut.in_(StatutAlerte.OUVERTES)).count() + retenus


def _n_alertes_confirmees(user):
    from app.models.sante import AlerteSanitaire, StatutAlerte
    from app.services import sante
    return sante.alertes_visibles(user).filter(AlerteSanitaire.statut == StatutAlerte.CONFIRMEE).count()


def _n_actions_retard(user):
    from app.services import actions
    return actions.n_en_retard(user)


def _n_fermes_rouges(user):
    from app.services import agent
    u = agent.urgences(Ferme.query.filter_by(agent_id=user.id).all())
    return sum(1 for x in u.values() if x['couleur'] == 'rouge')


def _n_tournee(user):
    from app.services import agent
    return len(agent.tournee(user))


def _n_commandes(user):
    """Agent : refus pas encore lus ; DGE et ADMIN : commandes à décider."""
    from app.models.agent import CommandeIntrant, StatutCommande as SC
    q = filtre_perimetre(CommandeIntrant.query, utilisateur=user)
    if user.profil == Profil.AGENT:
        return q.filter(CommandeIntrant.statut == SC.REFUSEE, CommandeIntrant.refus_lu_le.is_(None)).count()
    return q.filter(CommandeIntrant.statut == SC.ENVOYEE).count()


def _n_surveillance(user):
    """Sorties reçues après un blocage, à vérifier."""
    from app.services import veto
    return len(veto.sorties_a_verifier(veto.blocages_visibles(user).all()))


def _n_prevues_en_retard(user):
    """Livraisons prévues dont la date est passée (planning de la DGE)."""
    from datetime import date as _date
    from app.models.intrant import StatutLivraison
    return filtre_perimetre(Livraison.query, utilisateur=user).filter(
        Livraison.statut == StatutLivraison.PREVUE, Livraison.date_livraison < _date.today()).count()


TUILES = {
    'mes_fermes':      ('Mes fermes', "Triées par urgence", 'house-door', 'fermes.liste', _n_fermes_rouges),
    'tournee':         ('Tournée du jour', 'Visites et fermes en rouge', 'signpost-split', 'agent.tournee', _n_tournee),
    'commandes':       ("Commandes d'intrants", 'Envoyée, validée, livrée', 'cart-check', 'agent.commandes', _n_commandes),
    'fermes':          ('Fermes', 'Fiches, bâtiments, GPS', 'house-door', 'fermes.liste', None),
    'a_verifier':      ('Saisies à vérifier', 'Deux versions à trancher', 'check2-square', 'hors_ligne.conflits', _n_a_verifier),
    'arbitrages':      ('Arbitrages', 'Saisies et livraisons à trancher', 'check2-square', 'hors_ligne.conflits', _n_arbitrages),
    'livraisons':      ('Livraisons et stock', 'Réceptions, écarts', 'box-seam', 'livraisons.liste', None),
    'livraisons_etat': ("Livraisons de l'État", 'Planning : prévue, livrée, confirmée', 'box-seam', 'dge.planning', _n_prevues_en_retard),
    'classement':      ('Classement', 'Fermes, score pondéré', 'trophy', 'dge.classement', None),
    'agents':          ('Agents', 'Affectation et charge', 'person-badge', 'dge.agents', None),
    'bandes':          ('Bandes', 'Du poussin à la sortie', 'collection', 'bandes.liste', None),
    'indicateurs':     ("Indicateurs d'élevage", 'Mortalité et viabilité par niveau, objectif', 'graph-up', 'indicateurs.niveaux', None),
    'mes_indicateurs': ('Mes indicateurs', 'Chiffres clés et courbes sur 52 semaines', 'graph-up-arrow', 'indicateurs.mes', None),   # lot C
    'tableau':         ('Tableau de bord', 'Provinces et programme', 'bar-chart-line', 'pilotage.tableau', None),
    'carte':           ('Carte', "Couleur selon l'état", 'geo-alt', 'pilotage.carte', None),
    'rapports':        ('Rapports', 'Hebdomadaires et mensuels', 'file-earmark-text', 'pilotage.rapports', None),
    'signalements':    ('Signalements', 'Alertes à qualifier', 'exclamation-triangle', 'sante.alertes', _n_signalements),
    'alertes_sanitaires': ('Alertes sanitaires', 'Alertes confirmées', 'exclamation-triangle', 'sante.alertes', _n_alertes_confirmees),
    'declarations':    ('Déclarations', 'Signes et photos', 'camera', 'sante.declarations', None),
    'vaccins':         ('Vaccins et calendrier', 'Calendrier vaccinal, délais', 'capsule', 'sante.vaccins', None),
    'lots':            ('Lots et QR codes', 'De la ferme au consommateur', 'qr-code-scan', 'tracabilite.lots', None),
    'operateurs':      ('Opérateurs', 'Abattoirs, acheteurs', 'truck', 'operateurs.liste', None),
    'utilisateurs':    ('Utilisateurs', 'Comptes et droits', 'people-fill', 'utilisateurs.index', None),
    'configuration':   ('Configuration', 'Listes, paramètres, catalogue…', 'gear', 'controle.configuration', None),
    'catalogue':       ('Catalogue des intrants', 'Articles et fournisseurs', 'box-seam', 'catalogue.index', None),   # lot A2
    'a_approuver':     ('Paramètres à approuver', 'Quatre yeux', 'check2-circle', 'controle.approbations_ecran', _n_a_approuver),
    'sessions':        ('Sessions', 'Appareils connectés', 'pc-display', 'controle.sessions', None),
    'journal':         ('Journal', 'Qui a fait quoi, et quand', 'journal-text', 'journal.index', None),
    'integrite':       ('Intégrité', 'Journal chaîné', 'shield-check', 'controle.integrite', None),
    'surveillance':    ('Surveillance', 'Sorties bloquées', 'sign-stop', 'veto.surveillance', _n_surveillance),
    'parametres_sanitaires': ('Paramètres sanitaires', 'Seuils, quatre yeux', 'sliders', 'veto.parametres', None),
    'recherche_lots':  ('Recherche de lots', 'Amont et aval', 'diagram-3', 'veto.recherche', None),
}

# Tuiles visées d'abord (dans l'ordre demandé), puis les écrans existants qui restent utiles.
TUILES_PROFIL = {
    Profil.AGENT:    ['mes_fermes', 'tournee', 'a_verifier', 'livraisons', 'commandes', 'bandes', 'indicateurs', 'vaccins', 'lots', 'operateurs',
                      'catalogue'],
    Profil.VETO:     ['signalements', 'surveillance', 'recherche_lots', 'parametres_sanitaires', 'vaccins', 'a_approuver', 'fermes', 'bandes', 'declarations', 'indicateurs', 'lots', 'mes_indicateurs'],
    Profil.DGE:      ['tableau', 'carte', 'livraisons_etat', 'arbitrages', 'rapports', 'a_approuver', 'commandes', 'fermes', 'bandes',
                      'alertes_sanitaires', 'lots', 'operateurs', 'recherche_lots', 'classement', 'agents', 'catalogue',
                      'mes_indicateurs', 'indicateurs'],   # lot C
    Profil.ADMIN:    ['utilisateurs', 'configuration', 'a_approuver', 'sessions', 'journal', 'integrite', 'arbitrages',
                      'tableau', 'fermes', 'bandes', 'livraisons_etat', 'signalements', 'declarations', 'vaccins', 'lots',
                      'operateurs', 'carte', 'rapports', 'commandes', 'surveillance', 'recherche_lots', 'classement', 'agents',
                      'mes_indicateurs'],   # lot C
    Profil.AUDITEUR: ['journal', 'integrite'],
}

# Écran « Configuration » (ADMIN) : les réglages, regroupés
TUILES_CONFIGURATION = [
    ('Provinces et localités', 'Référentiel géographique', 'map', 'referentiel.index'),
    ('Listes', 'Valeurs des listes', 'list-ul', 'listes.index'),
    ('Paramètres', 'Seuils et durées', 'sliders', 'parametres.index'),
    ('Catalogue des intrants', 'Articles, conditionnements', 'box-seam', 'catalogue.index'),
    ('Fournisseurs', 'Aliment, couvoir, pharmacie, matériel', 'truck', 'catalogue.fournisseurs'),
    ('Formules des indicateurs', 'Mortalité, GMQ, IC…', 'calculator', 'pilotage.formules'),
    ("Tâches d'entretien", 'Abreuvoirs, litière, désinfection…', 'tools', 'entretien.taches'),
    ('Aides', "« Comment faire ? » de l'éleveur", 'question-circle', 'aides.administrer'),
    ('Imports Excel / CSV', 'Reprise de l’existant, lots annulables', 'upload', 'imports.index'),
]
COULEURS = ['mc-navy', 'mc-blue', 'mc-steel', 'mc-cobalt']


def tuiles_pour(user):
    """Tuiles de l'accueil du pilotage, avec leur compteur (alertes, à vérifier, à approuver)."""
    resultat = []
    for i, cle in enumerate(TUILES_PROFIL.get(user.profil, [])):
        titre, sous, icone, endpoint, compteur = TUILES[cle]
        resultat.append({'cle': cle, 'titre': titre, 'sous_titre': sous, 'icone': icone, 'lien': url_for(endpoint),
                         'couleur': 'mc-amber' if i == 0 else COULEURS[(i - 1) % len(COULEURS)],
                         'compteur': compteur(user) if compteur else None})
    return resultat


def onglets_pour(user):
    """Compatibilité : un seul panneau de tuiles (les onglets « Bientôt » ont disparu au lot 15)."""
    tuiles = tuiles_pour(user)
    return [{'code': 'accueil', 'titre': 'Accueil', 'icone': 'grid', 'option': False, 'tuiles': tuiles}] if tuiles else []


def perimetre(user):
    if user.est_national:
        return 'National'
    if user.profil == Profil.AGENT:
        n = Ferme.query.filter_by(agent_id=user.id).count()
        return f'{n} ferme{"s" if n > 1 else ""} suivie{"s" if n > 1 else ""}'
    if user.profil == Profil.ELEVEUR:                           # lot R : sa ou ses fermes
        return ', '.join(uf.numero_ferme for uf in user.fermes) or '—'
    if user.profil == Profil.OPERATEUR:
        return user.operateur.nom if user.operateur else '—'
    noms = [p.nom for p in user.provinces]
    return ', '.join(noms) if noms else '—'


def _alertes(user):
    resultat = []
    if user.profil in (Profil.ADMIN, Profil.DGE, Profil.AGENT):
        resultat += [{**a, 'lien': url_for('livraisons.liste', alerte=a['filtre'])}
                     for a in intrants.alertes(filtre_perimetre(Livraison.query))]
    if user.profil in (Profil.DGE, Profil.AGENT, Profil.VETO):
        # Feu orange ou rouge : agent référent, DGE, vétérinaires de la province (pas l'ADMIN)
        for b in filtre_perimetre(Bande.query.filter_by(statut=StatutBande.EN_COURS)).order_by(Bande.numero_metier):
            v = indicateurs.calculer(b)
            couleur, raison = indicateurs.feu(b, valeurs=v)
            if couleur in ('orange', 'rouge'):
                resultat.append({'texte': f'{b.numero} · {indicateurs.phrase(b, couleur, raison, v)}',
                                 'lien': url_for('bandes.fiche', numero=b.numero), 'nombre': 1,
                                 'niveau': 'urgence' if couleur == 'rouge' else 'warning',
                                 'meta': f'{b.ferme.nom} · bande'})
    # Santé animale : alertes à qualifier (VETO), confirmées (DGE), vaccins en retard (agent, VETO)
    from app.services import sante
    from app.models.sante import AlerteSanitaire, StatutAlerte
    if user.profil in (Profil.VETO, Profil.DGE):
        statuts = StatutAlerte.OUVERTES if user.profil == Profil.VETO else (StatutAlerte.CONFIRMEE,)
        for a in (sante.alertes_visibles(user).filter(AlerteSanitaire.statut.in_(statuts))
                  .order_by(AlerteSanitaire.cree_le.desc())):
            resultat.append({'texte': f'{a.numero} · {a.libelle_origine} · {a.libelle_statut}',
                             'lien': url_for('sante.alerte', numero=a.numero), 'nombre': 1,
                             'niveau': 'urgence', 'meta': f'{a.ferme.nom} · alerte sanitaire'})
    if user.profil == Profil.DGE:
        from app.services import pilotage
        n = len(pilotage.alertes_arrivee_recentes(user))
        if n:
            resultat.append({'texte': f'{n} livraison{"s" if n > 1 else ""} de poussins au-delà du seuil de '
                                      f'mortalité à l\'arrivée', 'lien': url_for('pilotage.tableau') + '#arrivee',
                             'nombre': n, 'niveau': 'warning', 'meta': 'Poussins · 30 derniers jours'})
    if user.profil in (Profil.AGENT, Profil.ADMIN):
        from app.models.entretien import Panne, StatutPanne
        for p in (filtre_perimetre(Panne.query.filter_by(statut=StatutPanne.SIGNALEE, archive_le=None))
                  .order_by(Panne.signalee_le.desc())):
            resultat.append({'texte': f'Panne signalée : {p.icone} {p.libelle} · {p.ou}',
                             'lien': url_for('fermes.fiche', numero=p.ferme.numero) + '#entretien', 'nombre': 1,
                             'niveau': 'urgence', 'meta': f'{p.ferme.nom} · entretien'})
    if user.profil == Profil.AGENT:
        # Lot 12 : saisies à vérifier (deux versions, doublons, refus) ; doublon de sortie > 48 h en rouge
        from app.routes.hors_ligne import conflits_a_voir
        from app.services import verifications
        a_voir = conflits_a_voir(user).all()
        n = len(a_voir)
        if n:
            s = 's' if n > 1 else ''
            rouges = [c for c in a_voir if verifications.en_retard(c)]
            resultat.append({'texte': f'{n} saisie{s} à vérifier' + (f' dont {len(rouges)} doublon{"s" if len(rouges) > 1 else ""} '
                                                                     f'de sortie depuis plus de 48 h' if rouges else ''),
                             'lien': url_for('hors_ligne.conflits'), 'nombre': n,
                             'niveau': 'urgence' if rouges else 'warning', 'meta': 'Deux versions à trancher'})
    if user.profil in (Profil.DGE, Profil.ADMIN):
        # Lot 12 : écarts de livraison de l'État et doublons de sortie non tranchés sous 48 h
        from app.models.hors_ligne import ConflitHorsLigne, GenreVerification as G
        from app.services import verifications
        ouvertes = verifications.a_trancher(filtre_perimetre(ConflitHorsLigne.query, utilisateur=user)).all()
        livraisons = [c for c in ouvertes if c.genre == G.LIVRAISON]
        rouges = [c for c in ouvertes if verifications.en_retard(c)]
        if livraisons:
            n = len(livraisons)
            resultat.append({'texte': f'{n} écart{"s" if n > 1 else ""} de confirmation de livraison de l\'État à vérifier',
                             'lien': url_for('hors_ligne.conflits'), 'nombre': n, 'niveau': 'warning',
                             'meta': 'Saisies à vérifier · livraisons'})
        if rouges:
            n = len(rouges)
            resultat.append({'texte': f'{n} doublon{"s" if n > 1 else ""} de sortie non tranché{"s" if n > 1 else ""} '
                                      f'depuis plus de 48 h', 'lien': url_for('hors_ligne.conflits'), 'nombre': n,
                             'niveau': 'urgence', 'meta': 'Saisies à vérifier · sorties'})
    if user.profil == Profil.AGENT:
        from app.services import visites
        from datetime import date as _date
        for v in visites.du_jour_pour_agent(user):
            en_retard = v.date_prevue < _date.today()
            resultat.append({'texte': f'Visite {"en retard (prévue le " + v.date_prevue.strftime("%d/%m") + ")" if en_retard else "prévue aujourd’hui"} : {v.ferme.nom}',
                             'lien': url_for('fermes.fiche', numero=v.ferme.numero) + '#visites', 'nombre': 1,
                             'niveau': 'warning', 'meta': f'{v.objet} · visites'})
    if user.profil in (Profil.VETO, Profil.AGENT):
        for b, retards in sante.vaccins_en_retard(filtre_perimetre(Bande.query)):
            resultat.append({'texte': f'{b.numero} · vaccin en retard : {retards[0]["calendrier"].produit.nom}',
                             'lien': url_for('bandes.fiche', numero=b.numero), 'nombre': len(retards),
                             'niveau': 'warning', 'meta': f'{b.ferme.nom} · vaccins'})
    return resultat


def _espace_eleveur(fermes):
    """Pour chaque ferme : poussins en attente, puis un bloc par bâtiment actif.
    Plusieurs bâtiments : une pastille par bâtiment, les bandes à saisir d'abord, et
    « À faire aujourd'hui » commun à la ferme (chaque ligne dit son bâtiment)."""
    from app.routes.bandes import contexte_bloc
    from app.services import ludique, parametres
    bandes_eleveur = filtre_perimetre(Bande.query).all()   # record personnel : toutes ses bandes
    conseil = parametres.obtenir('sante.conseil_feu_rouge')
    espace = []
    for f in fermes:
        blocs = []
        for b in f.batiments:
            if not b.actif:
                continue
            etat = regles_bandes.etat_batiment(b)
            cible = f'bat-{f.numero}-{b.code}'
            if etat['etat'] == 'bande':
                c = contexte_bloc(etat['bande'])
                oeufs = None
                if etat['bande'].ponte:                                  # lot F : taux de ponte et stock d'œufs
                    from app.services import oeufs as services_oeufs
                    so = services_oeufs.situation(etat['bande'])
                    oeufs = {'taux': so['taux'], 'plateaux': so['plateaux'], 'chute': so['chute']}
                blocs.append({'type': 'bande', 'cible': cible, 'code': b.code, 'oeufs': oeufs,
                              'a_saisir': c['deja'] is None and not c['cloture_proposee'],
                              'serie': ludique.etat_serie(etat['bande'], bandes_eleveur),
                              'progression': ludique.progression(etat['bande'], c['v']['age']), **c})
            else:
                derniere = etat.get('derniere')
                blocs.append({'type': 'vide', 'cible': cible, 'code': b.code, 'couleur': 'gris', 'a_saisir': False,
                              'batiment': b, **etat,
                              'etoiles': ludique.etoiles_du_bilan(derniere.bilan) if derniere else None})
        # Bandes à saisir d'abord, puis les bandes déjà saisies, puis les bâtiments vides
        blocs.sort(key=lambda x: (0 if x['a_saisir'] else 1 if x['type'] == 'bande' else 2, x['code']))
        a_faire = [{**t, 'batiment': x['code'], 'cible': x['cible']}
                   for x in blocs if x['type'] == 'bande' and not x['cloture_proposee'] for t in x['a_faire']]
        attente = regles_bandes.poussins_en_attente(f)
        espace.append({'ferme': f, 'blocs': blocs, 'a_faire': a_faire, 'plusieurs': len(blocs) > 1,
                       'conseil': conseil,
                       'attente': sum(d for _, d in attente) if regles_bandes.batiments_libres(f) else 0})
    return espace


def _bandeau_annulation(user):
    """Livraison confirmée « Tout reçu » à l'instant : bandeau « Reçue ✓ — Annuler »."""
    numero = session.get('confirmation_recente')
    liv = Livraison.query.filter_by(numero_metier=numero).first() if numero else None
    if liv is None or not intrants.annulation_possible(liv, user):
        session.pop('confirmation_recente', None)
        return None
    ecoule = (maintenant() - en_utc(liv.confirmee_le)).total_seconds()
    return {'livraison': liv, 'secondes': max(1, round(intrants.DELAI_ANNULATION_SECONDES - ecoule))}


@accueil_bp.route('/')
@login_required
def index():
    from app.utils import terrain
    profil = terrain.profil_terrain(current_user)               # None : version ordinateur (lot R)
    if profil == 'eleveur':
        if current_user.presentation_vue_le is None:          # lot 13 : une fois par compte
            return redirect(url_for('eleveur.presentation'))
        from app.routes.eleveur import accueil as accueil_eleveur, bandeau_vaccin
        from app.services import veto
        return render_template('accueil.html', eleveur=True, onglets=[], e=accueil_eleveur(current_user),
                               bandeau_vaccin=bandeau_vaccin(current_user),
                               blocages=veto.blocages_visibles(current_user).filter_by(leve_le=None).all())
    if profil in ('agent', 'operateur'):                      # lot 19 ter : espace terrain, téléphone d'abord
        if current_user.presentation_vue_le is None:          # présentation au premier lancement, une fois par compte
            return redirect(url_for('terrain.presentation'))
        from app.routes import terrain as ecrans
        if profil == 'agent':
            return render_template('terrain/agent/accueil.html', a=ecrans.accueil_agent(current_user))
        return render_template('terrain/operateur/accueil.html', o=ecrans.accueil_operateur(current_user))
    from app.routes.bureau import tableau_de_bord                # lot R : tableau de bord de la version ordinateur
    return render_template('bureau/accueil.html', d=tableau_de_bord(current_user), alertes=_alertes(current_user),
                           financier=current_user.profil != Profil.VETO)
