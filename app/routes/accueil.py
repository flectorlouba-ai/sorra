"""Accueil — repris de l'accueil de PERFORM YL.1 : onglets par module, tuiles,
encadré Alertes (maquette A, docs/maquettes/maquettes_lot1.md)."""
from flask import Blueprint, render_template, url_for
from flask_login import login_required, current_user

from app.models import Ferme, Profil
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
    ]},
    {'code': 'fermes', 'titre': 'Fermes et élevage', 'icone': 'egg', 'option': False, 'tuiles': [
        ('Indicateurs d\'élevage', 'Mortalité, croissance, aliment', 'graph-up', None, None),
        ('Fermes', 'Fiches, bâtiments, GPS', 'house-door', 'fermes.liste',
         {A, D, Profil.AGENT, Profil.VETO}),
        ('Bandes', 'Du poussin à la sortie', 'collection', None, None),
        ('Intrants', 'Poussins, aliment, vaccins', 'box-seam', None, None),
    ]},
    {'code': 'sante', 'titre': 'Santé animale', 'icone': 'heart-pulse', 'option': False, 'tuiles': [
        ('Alertes sanitaires', 'Mortalité anormale', 'exclamation-triangle', None, None),
        ('Déclarations', 'Signes et photos', 'camera', None, None),
        ('Vaccins et traitements', 'Calendrier vaccinal', 'capsule', None, None),
        ('Biosécurité', 'Contrôles des fermes', 'shield-check', None, None),
    ]},
    {'code': 'tracabilite', 'titre': 'Traçabilité', 'icone': 'qr-code', 'option': False, 'tuiles': [
        ('Indicateurs de traçabilité', 'Lots tracés, QR', 'graph-up', None, None),
        ('Lots et QR codes', 'De la ferme au consommateur', 'qr-code-scan', None, None),
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
        ('Tableau de bord national', 'Provinces et programme', 'bar-chart-line', None, None),
        ('Carte des fermes', 'Couleur selon l\'état', 'geo-alt', None, None),
        ('Rapports', 'Hebdomadaires et mensuels', 'file-earmark-text', None, None),
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
    Profil.AGENT:    ['fermes', 'tracabilite'],
    Profil.VETO:     ['sante', 'fermes'],
    Profil.AUDITEUR: ['config'],
}
SEULEMENT_DISPONIBLES = {
    Profil.AUDITEUR: {'config'},   # Configuration avec le Journal seul
    Profil.VETO: {'fermes'},       # Fermes et élevage avec la tuile Fermes seule
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


@accueil_bp.route('/')
@login_required
def index():
    if current_user.profil == Profil.ELEVEUR:
        fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
        return render_template('accueil.html', eleveur=True, fermes=fermes, onglets=[])
    return render_template('accueil.html', eleveur=False, onglets=onglets_pour(current_user))
