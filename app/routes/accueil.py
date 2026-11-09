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

# Une tuile : (titre, sous-titre, icône, endpoint ou None si pas encore livrée,
#              profils qui l'ouvrent). La première tuile de chaque onglet est orange.
MODULES = [
    {'code': 'config', 'titre': 'Configuration', 'icone': 'gear', 'option': False, 'tuiles': [
        ('Journal des opérations', 'Qui a fait quoi, et quand', 'journal-text', 'journal.index',
         {A, Profil.AUDITEUR}),
        ('Utilisateurs', 'Comptes et droits', 'people-fill', 'utilisateurs.index', {A}),
        ('Provinces et localités', 'Référentiel géographique', 'map', 'referentiel.index', {A}),
        ('Listes', 'Valeurs des listes', 'list-ul', 'listes.index', {A}),
        ('Paramètres', 'Seuils et durées', 'sliders', 'parametres.index', {A}),
        ('Catalogue des intrants', 'Produits, unités, sacs', 'box-seam', 'catalogue.index', {A}),
        ('Formules des indicateurs', 'Mortalité, GMQ, IC…', 'calculator', 'pilotage.formules', {A}),
        ("Tâches d'entretien", 'Abreuvoirs, litière, désinfection…', 'tools', 'entretien.taches', {A}),
        ('Aides', '« Comment faire ? » de l\'éleveur', 'question-circle', 'aides.administrer', {A}),
    ]},
    {'code': 'fermes', 'titre': 'Fermes et élevage', 'icone': 'egg', 'option': False, 'tuiles': [
        ('Fermes', 'Fiches, bâtiments, GPS', 'house-door', 'fermes.liste',
         {A, D, Profil.AGENT, Profil.VETO}),
        ('Bandes', 'Du poussin à la sortie', 'collection', 'bandes.liste',
         {A, D, Profil.AGENT, Profil.VETO}),
        ('Intrants', 'Poussins, aliment, vaccins', 'box-seam', 'livraisons.liste',
         {A, D, Profil.AGENT}),
        ("Indicateurs d'élevage", 'Mortalité, croissance, aliment', 'graph-up', 'pilotage.tableau',
         {A, D, Profil.AGENT, Profil.VETO}),
    ]},
    {'code': 'sante', 'titre': 'Santé animale', 'icone': 'heart-pulse', 'option': False, 'tuiles': [
        ('Alertes sanitaires', 'Mortalité anormale', 'exclamation-triangle', 'sante.alertes',
         {A, D, Profil.VETO}),
        ('Déclarations', 'Signes et photos', 'camera', 'sante.declarations', {A, Profil.VETO}),
        ('Vaccins et traitements', 'Calendrier vaccinal', 'capsule', 'sante.vaccins',
         {A, Profil.VETO, Profil.AGENT}),
        ('Biosécurité', 'Contrôles des fermes', 'shield-check', None, None),
    ]},
    {'code': 'tracabilite', 'titre': 'Traçabilité', 'icone': 'qr-code', 'option': False, 'tuiles': [
        ('Indicateurs de traçabilité', 'Lots tracés, QR', 'graph-up', None, None),
        ('Lots et QR codes', 'De la ferme au consommateur', 'qr-code-scan', 'tracabilite.lots',
         {A, D, Profil.AGENT, Profil.VETO}),
        ('Opérateurs', 'Abattoirs, acheteurs', 'truck', 'operateurs.liste', {A, D, Profil.AGENT}),
        ('Recherche amont / aval', 'Origine d\'un lot', 'search', None, None),
    ]},
    {'code': 'economie', 'titre': 'Économie', 'icone': 'cash-coin', 'option': False, 'tuiles': [
        ('Rentabilité', 'Marge par ferme', 'graph-up-arrow', None, None),
        ('Ventes', 'Quantités et prix', 'cart', None, None),
        ('Charges', 'Par poste', 'receipt', None, None),
        ('Coût de production', 'Par kg vif', 'calculator', None, None),
    ]},
    {'code': 'pilotage', 'titre': 'Pilotage', 'icone': 'speedometer2', 'option': False, 'tuiles': [
        ('Tableau de bord national', 'Provinces et programme', 'bar-chart-line', 'pilotage.tableau', {A, D}),
        ('Carte des fermes', 'Couleur selon l\'état', 'geo-alt', 'pilotage.carte', {A, D}),
        ('Rapports', 'Hebdomadaires et mensuels', 'file-earmark-text', 'pilotage.rapports', {A, D}),
        ('Classement des fermes', 'Bonnes pratiques', 'trophy', None, None),
    ]},
    {'code': 'maintenance', 'titre': 'Maintenance', 'icone': 'tools', 'option': True, 'tuiles': [
        ('Indicateurs de maintenance', '', 'graph-up', None, None),
        ('Suivi des pannes', '', 'wrench', None, None),
        ('Maintenance préventive', 'Pendant le vide sanitaire', 'calendar-check', None, None),
        ('Stock de pièces', '', 'boxes', None, None),
    ]},
    {'code': 'qhse', 'titre': 'QHSE', 'icone': 'shield-check', 'option': True, 'tuiles': [
        ('Indicateurs QHSE', '', 'graph-up', None, None),
        ('Audits', '', 'clipboard-check', None, None),
        ('Non-conformités', '', 'x-octagon', None, None),
        ('Sécurité et environnement', '', 'tree', None, None),
    ]},
    {'code': 'comptabilite', 'titre': 'Comptabilité', 'icone': 'calculator', 'option': True,
     'tuiles': [
        ('Tableau financier', '', 'graph-up', None, None),
        ('Trésorerie', 'Caisse, banque, Mobile Money', 'wallet2', None, None),
        ('Écritures', 'SYSCOHADA', 'journal-bookmark', None, None),
        ('Fiscalité et prêt BCEG', '', 'bank', None, None),
    ]},
]

# Onglets visibles par profil, et tuiles réduites à celles qu'il peut ouvrir.
# ADMIN et DGE : tous les onglets ; la DGE n'a pas les écrans réservés à l'ADMIN
# (Configuration), cet onglet lui est donc masqué (« pas de tuile inutile »).
ONGLETS = {
    Profil.ADMIN:    [m['code'] for m in MODULES],
    Profil.DGE:      [m['code'] for m in MODULES if m['code'] != 'config'],
    Profil.AGENT:    ['fermes', 'sante', 'tracabilite'],
    Profil.VETO:     ['sante', 'fermes', 'tracabilite'],
    Profil.AUDITEUR: ['config'],
}
SEULEMENT_DISPONIBLES = {
    Profil.AUDITEUR: {'config'},   # Configuration avec le Journal seul
    Profil.VETO: {'fermes', 'tracabilite'},   # Fermes et Bandes en lecture ; Lots et QR codes
}
COULEURS = ['mc-navy', 'mc-blue', 'mc-steel', 'mc-cobalt']


def _phrase(titre, sous_titre, option):
    if option:
        return f'« {titre} » est proposé en option' + (f' : {sous_titre[0].lower()}{sous_titre[1:]}.'
                                                        if sous_titre else '.')
    return f'« {titre} » arrive bientôt' + (f' : {sous_titre[0].lower()}{sous_titre[1:]}.'
                                             if sous_titre else '.')


def onglets_pour(user):
    resultat = []
    filtrer = SEULEMENT_DISPONIBLES.get(user.profil, set())
    for m in MODULES:
        if m['code'] not in ONGLETS.get(user.profil, []):
            continue
        tuiles = []
        for i, (titre, sous, icone, endpoint, profils) in enumerate(m['tuiles']):
            disponible = endpoint is not None and user.profil in profils
            if endpoint is not None and not disponible:
                continue   # écran livré mais pas pour ce profil : pas de tuile inutile
            if m['code'] in filtrer and not disponible:
                continue
            tuiles.append({
                'titre': titre, 'sous_titre': sous, 'icone': icone,
                'lien': url_for(endpoint) if disponible else None,
                'couleur': 'mc-amber' if i == 0 else COULEURS[(i - 1) % len(COULEURS)],
                'etiquette': None if disponible else ('Option' if m['option'] else 'Bientôt'),
                'phrase': None if disponible else _phrase(titre, sous, m['option']),
            })
        if tuiles:
            resultat.append({**m, 'tuiles': tuiles})
    return resultat


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
        for p in (filtre_perimetre(Panne.query.filter_by(statut=StatutPanne.SIGNALEE))
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
                blocs.append({'type': 'bande', 'cible': cible, 'code': b.code,
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
    if current_user.profil == Profil.ELEVEUR:
        if current_user.presentation_vue_le is None:          # lot 13 : une fois par compte
            return redirect(url_for('eleveur.presentation'))
        from app.routes.eleveur import accueil as accueil_eleveur, bandeau_vaccin
        return render_template('accueil.html', eleveur=True, onglets=[], e=accueil_eleveur(current_user),
                               bandeau_vaccin=bandeau_vaccin(current_user))
    return render_template('accueil.html', eleveur=False, onglets=onglets_pour(current_user),
                           alertes=_alertes(current_user))
