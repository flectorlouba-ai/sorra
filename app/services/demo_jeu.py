"""Lot J — jeu de données complet de la DÉMONSTRATION (données fictives), déterministe (graine fixe), daté par
rapport à « aujourd'hui ». Commande : `flask demo-jeu-complet` (refusée hors démonstration et sur une base non vide).

Deux étapes :
1. l'historique de 12 mois (150 élevages, bandes, saisies quotidiennes, pesées, vaccinations, livraisons, sorties,
   lots tracés, dépenses, œufs) est calculé en mémoire puis inséré en blocs : rapide, et les stocks, effectifs et
   totaux sont cohérents par construction (on ne consomme jamais plus que livré, on ne sort jamais plus que présent) ;
2. les situations du présent (feu rouge, doublon de sortie, ventes bloquées, visas MAEDR, validations quatre yeux,
   accords BCEG, plans d'actions…) passent par les VRAIS services de l'application, comme un utilisateur.

Le journal part d'une base neuve : ce qui passe par les services y est inscrit, chaîne d'intégrité valide.
"""
import math
import random
import struct
import uuid
import zlib
from datetime import date, datetime, time, timedelta, timezone

import sqlalchemy as sa

from app import db

GRAINE = 2026

# Élevages par province (au prorata de la maquette) — 150 au total
REPARTITION = [('EST', 48), ('WNT', 22), ('HOG', 17), ('NGO', 14), ('OGM', 12), ('MOG', 11), ('NYA', 9), ('OGL', 9),
               ('OGI', 8)]
LOCALITES = {
    'EST': ['Libreville', 'Owendo', 'Akanda', 'Ntoum', 'Kango', 'Cocobeach'],
    'WNT': ['Oyem', 'Bitam', 'Minvoul', 'Mitzic', 'Médouneu'],
    'HOG': ['Franceville', 'Moanda', 'Mounana', 'Okondja', 'Akiéni'],
    'NGO': ['Mouila', 'Ndendé', 'Lébamba', 'Fougamou', 'Mbigou'],
    'OGM': ['Port-Gentil', 'Omboué', 'Gamba'],
    'MOG': ['Lambaréné', 'Ndjolé'],
    'NYA': ['Tchibanga', 'Mayumba', 'Moulengui-Binza'],
    'OGL': ['Koulamoutou', 'Lastoursville', 'Pana'],
    'OGI': ['Makokou', 'Booué', 'Mékambo'],
}
NOMS = ['Mba', 'Obiang', 'Nzé', 'Ondo', 'Mintsa', 'Ndong', 'Ella', 'Essono', 'Mbadinga', 'Moussavou', 'Nguema', 'Okouyi',
        'Bongo', 'Mabika', 'Nziengui', 'Boussougou', 'Koumba', 'Mouketou', 'Ndjave', 'Obame', 'Eyeghe', 'Biyoghe',
        'Mengue', 'Assoumou', 'Edzang', 'Allogo', 'Nkoghe', 'Mavoungou', 'Ibinga', 'Makaya', 'Pambou', 'Lekogo',
        'Ngoma', 'Mboumba', 'Nyama', 'Oyane', 'Abessolo', 'Ekomie', 'Ndoutoume', 'Ovono']
PRENOMS = ['Jean', 'Marie', 'Paul', 'Sylvie', 'Pierre', 'Claire', 'Hervé', 'Alice', 'Marc', 'Clarisse', 'Serge',
           'Nadège', 'Rodrigue', 'Prisca', 'Ghislain', 'Laure', 'Fabrice', 'Annick', 'Patrice', 'Yolande']

# Comptes : mêmes identifiants qu'avant (liens « Comptes de démonstration » du lot L), plus `maedr`
AGENTS = [('agent.est', 'Ndong', 'Paul', ['EST']), ('agent.est2', 'Ondo', 'Sylvie', ['EST']),
          ('agent.hog', 'Okouyi', 'Marie', ['HOG', 'OGL']), ('agent.wnt', 'Ella', 'Rodrigue', ['WNT', 'OGI']),
          ('agent.ngo', 'Koumba', 'Prisca', ['NGO', 'NYA']), ('agent.mog', 'Mabika', 'Serge', ['MOG', 'OGM'])]
VETOS = [('veto', 'Moussavou', 'Dr Jean', ['EST', 'MOG', 'OGM']), ('veto.nord', 'Biyoghe', 'Dr Laure', ['WNT', 'OGI', 'HOG']),
         ('veto.sud', 'Mboumba', 'Dr Fabrice', ['NGO', 'NYA', 'OGL'])]

# Simulation d'une bande de chair
DUREE_CHAIR = 44          # dernière sortie vers 42–45 jours
VIDE = (14, 21)           # vide sanitaire entre deux bandes
POIDS_42 = 2100           # g (courbe de référence locale, posée en paramètre)
COURBE = '0:42; 7:160; 14:400; 21:780; 28:1200; 35:1650; 42:2100; 49:2500'
CALENDRIER = [(7, 'nd_hb1', 'Goutte oculaire'), (14, 'gumboro', 'Eau de boisson'), (21, 'nd_lasota', 'Eau de boisson'),
              (28, 'gumboro_rappel', 'Eau de boisson')]
PRIX_KG = {'Abattoir': 1900, 'Vente': 2300}
POSTES = ["👷 Main-d'œuvre", '⚡ Électricité', '⛽ Carburant', '🚚 Transport', '💧 Eau', '🔧 Réparation', '📦 Autre']


class RegleJeu(Exception):
    pass


# ── Outils ────────────────────────────────────────────────────────────────

class _Jeu:
    def __init__(self, aujourdhui, mot_de_passe, adresse):
        self.r = random.Random(GRAINE)
        self.auj = aujourdhui
        self.debut = aujourdhui - timedelta(days=365)
        self.mdp = mot_de_passe
        self.adresse = adresse
        self.t = {}                      # table → lignes à insérer
        self.compteurs = {}              # (type, prefixe, annee) → dernier numéro
        self.volumes = {}

    def uid(self):
        return uuid.UUID(int=self.r.getrandbits(128), version=4)

    def code(self):
        return ''.join(self.r.choice('ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789') for _ in range(22))

    @staticmethod
    def dt(jour, heure=18, minute=0):
        return datetime.combine(jour, time(heure, minute), tzinfo=timezone.utc)

    def ajouter(self, table, **ligne):
        self.t.setdefault(table, []).append(ligne)
        return ligne

    def numero(self, type_, prefixe, annee=0, largeur=6, format_=None):
        cle = (type_, prefixe, annee)
        self.compteurs[cle] = self.compteurs.get(cle, 0) + 1
        n = self.compteurs[cle]
        if format_ == 'rang':
            return n
        return f'{prefixe}-{annee}-{n:0{largeur}d}' if annee else f'{prefixe}-{n:0{largeur}d}'

    def saisie_terrain(self, jour, auteur, heure=18):
        """Colonnes communes des tables de saisie terrain."""
        return {'id': self.uid(), 'statut_synchro': 'SYNCHRONISE', 'numero_provisoire': False,
                'cree_par': auteur, 'modifie_par': auteur, 'cree_le': self.dt(jour, heure), 'modifie_le': self.dt(jour, heure)}


def _png(couleur):
    """Petite image PNG unie (photo factice de signalement), produite ici : aucun fichier externe."""
    largeur = hauteur = 64
    brut = b''.join(b'\x00' + bytes(couleur) * largeur for _ in range(hauteur))

    def bloc(nom, donnees):
        return struct.pack('>I', len(donnees)) + nom + donnees + struct.pack('>I', zlib.crc32(nom + donnees) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + bloc(b'IHDR', struct.pack('>IIBBBBB', largeur, hauteur, 8, 2, 0, 0, 0))
            + bloc(b'IDAT', zlib.compress(brut)) + bloc(b'IEND', b''))


def _point_dans(jeu, contours, code):
    """Position GPS tirée au hasard à l'intérieur de la province (contours officiels)."""
    from app.services.geo import _dans_anneau
    anneaux = contours.get(code) or []
    xs = [p[0] for a in anneaux for p in a]
    ys = [p[1] for a in anneaux for p in a]
    for _ in range(500):
        lon, lat = jeu.r.uniform(min(xs), max(xs)), jeu.r.uniform(min(ys), max(ys))
        if any(_dans_anneau(lon, lat, a) for a in anneaux):
            return round(lat, 5), round(lon, 5)
    return round(sum(ys) / len(ys), 5), round(sum(xs) / len(xs), 5)


# ── Étape 0 : contrôles ───────────────────────────────────────────────────

def verifier_base():
    from app.models import Ferme, Utilisateur
    if Ferme.query.count() or Utilisateur.query.count():
        raise RegleJeu('Refusé : la base contient déjà des élevages ou des comptes. Le jeu complet se charge dans une '
                       'base de démonstration NEUVE (base recréée, puis migrations).')


# ── Étape 1 : référentiels et comptes (ORM, peu de lignes) ───────────────

def _referentiels(jeu):
    from app.models import Province, Localite, Produit, Fournisseur, Operateur, ListeDeroulante, Parametre
    from app.models.sante import CalendrierVaccinal
    from app.services import parametres
    provinces = {p.code: p for p in Province.query}
    if len(provinces) < 9:
        raise RegleJeu('Les 9 provinces doivent exister (migrations non passées ?).')
    localites = {}
    for code, noms in LOCALITES.items():
        for nom in noms:
            l = Localite.query.filter_by(province_id=provinces[code].id, nom=nom).first()
            if l is None:
                l = Localite(province_id=provinces[code].id, nom=nom, actif=True)
                db.session.add(l)
            localites.setdefault(code, []).append(l)
    f = {}
    for cle, nom, type_, tel, ville in (('smag', 'SMAG Aliments', 'Aliment', '011 70 12 34', 'Owendo'),
                                        ('siat', 'Couvoir SIAT', 'Couvoir', '011 72 45 10', 'Ntoum'),
                                        ('pharma', 'Pharmavet Libreville', 'Pharmacie vétérinaire', '011 76 33 21', 'Libreville'),
                                        ('quinc', "Quincaillerie de l'Estuaire", 'Matériel', '011 74 88 02', 'Libreville')):
        f[cle] = Fournisseur.query.filter_by(nom=nom).first() or Fournisseur(nom=nom)
        f[cle].type, f[cle].telephone, f[cle].ville, f[cle].actif = type_, tel, ville, True
        db.session.add(f[cle])
    db.session.flush()
    p = {}
    for cle, nom, type_, unite, sac, delai, ref, four, cond in (
            ('poussins', 'Poussins chair Cobb 500', 'Poussins', 'têtes', None, None, 'CBB500-J1', 'siat', 'carton de 100 poussins'),
            ('poussins_ponte', 'Poussins ponte ISA Brown', 'Poussins', 'têtes', None, None, 'ISA-J1', 'siat', 'carton de 100 poussins'),
            ('demarrage', 'Aliment démarrage 25 kg', 'Aliment', 'sacs', 25, None, 'SMAG-DEM-25', 'smag', 'sac de 25 kg'),
            ('croissance', 'Aliment croissance 50 kg', 'Aliment', 'sacs', 50, None, 'SMAG-CRO-50', 'smag', 'sac de 50 kg'),
            ('finition', 'Aliment finition 50 kg', 'Aliment', 'sacs', 50, None, 'SMAG-FIN-50', 'smag', 'sac de 50 kg'),
            ('ponte', 'Aliment ponte 50 kg', 'Aliment', 'sacs', 50, None, 'SMAG-PON-50', 'smag', 'sac de 50 kg'),
            ('nd_hb1', 'Vaccin Newcastle + Bronchite (HB1/H120)', 'Vaccin', 'doses', None, None, 'NDIB-1000', 'pharma', 'flacon de 1 000 doses'),
            ('gumboro', 'Vaccin Gumboro', 'Vaccin', 'doses', None, None, 'IBD-1000', 'pharma', 'flacon de 1 000 doses'),
            ('nd_lasota', 'Vaccin Newcastle (La Sota)', 'Vaccin', 'doses', None, None, 'ND-1000', 'pharma', 'flacon de 1 000 doses'),
            ('gumboro_rappel', 'Vaccin Gumboro (rappel)', 'Vaccin', 'doses', None, None, 'IBD-R-1000', 'pharma', 'flacon de 1 000 doses'),
            ('anticocci', 'Anticoccidien buvable', 'Médicament', 'flacons', None, 7, 'ACC-1L', 'pharma', 'flacon de 1 litre'),
            ('antibio', 'Antibiotique (oxytétracycline)', 'Médicament', 'sachets', None, 5, 'OXY-100', 'pharma', 'sachet de 100 g'),
            ('vitamines', 'Vitamines anti-stress', 'Médicament', 'sachets', None, 0, 'VIT-AS', 'pharma', 'sachet de 100 g'),
            ('abreuvoir', 'Abreuvoir 10 litres', 'Matériel', 'unités', None, None, 'ABR-10', 'quinc', "à l'unité"),
            ('copeaux', 'Copeaux de litière (sac)', 'Matériel', 'sacs', None, None, 'COP-SAC', 'quinc', 'sac de 20 kg')):
        p[cle] = Produit.query.filter_by(nom=nom).first() or Produit(nom=nom)       # les migrations en posent déjà
        p[cle].type, p[cle].unite, p[cle].poids_sac_kg, p[cle].delai_attente_jours = type_, unite, sac, delai
        p[cle].reference, p[cle].fournisseur_id, p[cle].conditionnement, p[cle].actif = ref, f[four].id, cond, True
        db.session.add(p[cle])
    db.session.flush()
    cal = {}
    for age, cle, mode in CALENDRIER:
        cal[cle] = CalendrierVaccinal.query.filter_by(age_jours=age).first() or CalendrierVaccinal(age_jours=age)
        cal[cle].produit_id, cal[cle].mode, cal[cle].actif = p[cle].id, mode, True
        db.session.add(cal[cle])
    for autre in CalendrierVaccinal.query.filter(CalendrierVaccinal.age_jours.notin_([a for a, _, _ in CALENDRIER])):
        autre.actif = False
    ops = {}
    for cle, nom, type_, code, conv, contact, tel in (
            ('owendo', "Abattoir d'Owendo", 'Abattoir', 'EST', True, 'Responsable du quai', '011 70 55 10'),
            ('montbouet', 'Marché de Mont-Bouët', 'Marché', 'EST', True, 'Responsable du quai', '011 76 20 44'),
            ('komo', 'Poulets du Komo', 'Acheteur', 'EST', True, 'M. Allogo', '077 41 22 10'),
            ('franceville', 'Marché de Franceville', 'Acheteur', 'HOG', False, 'Mme Ibinga', '066 30 12 70'),
            ('supergros', 'Super Gros Libreville', 'Distributeur', 'EST', True, 'Service achats', '011 74 10 00')):
        ops[cle] = Operateur(numero=jeu.numero('OPERATEUR', 'OPE', largeur=4), nom=nom, type=type_,
                             province_id=provinces[code].id, contact=contact, telephone=tel, convention=conv,
                             convention_date=jeu.auj - timedelta(days=jeu.r.randint(60, 300)) if conv else None, actif=True)
        db.session.add(ops[cle])
    if not ListeDeroulante.query.filter_by(categorie='types_operateurs', valeur='Marché').first():
        db.session.add(ListeDeroulante(categorie='types_operateurs', valeur='Marché', ordre=9, actif=True))
    # Courbe de poids de référence locale et adresse publique des QR (réglages de la démonstration)
    for cle, valeur in (('bandes.courbe_poids', COURBE), ('tracabilite.adresse_publique', jeu.adresse)):
        prm = Parametre.query.filter_by(cle=cle).first()
        if prm is not None and valeur:
            prm.valeur = valeur
    db.session.flush()
    parametres.oublier_cache()
    return provinces, localites, p, cal, ops


def _comptes(jeu, provinces, ops):
    from app.models import Utilisateur, Profil
    u = {}

    def compte(ident, nom, prenom, profil, prov=(), tel=None, operateur=None):
        x = Utilisateur(identifiant=ident, nom=nom, prenom=prenom, profil=profil, actif=True, doit_changer_mdp=False,
                        telephone=tel, operateur_id=operateur.id if operateur else None,
                        presentation_vue_le=jeu.dt(jeu.auj - timedelta(days=30)))
        x.set_password(jeu.mdp)
        x.provinces = [provinces[c] for c in prov]
        db.session.add(x)
        u[ident] = x
        return x
    compte('admin', 'Nguema', 'Hervé', Profil.ADMIN)
    compte('dge', 'Nzé', 'Alice', Profil.DGE)
    for ident, nom, prenom, prov in AGENTS:
        compte(ident, nom, prenom, Profil.AGENT, prov, f'+241 77 {jeu.r.randint(10, 99)} {jeu.r.randint(10, 99)} {jeu.r.randint(10, 99)}')
    for ident, nom, prenom, prov in VETOS:
        compte(ident, nom, prenom, Profil.VETO, prov, f'+241 66 {jeu.r.randint(10, 99)} {jeu.r.randint(10, 99)} {jeu.r.randint(10, 99)}')
    compte('aninf', 'ANINF', None, Profil.AUDITEUR)
    compte('auditeur', 'Mintsa', 'Claire', Profil.AUDITEUR)
    compte('bceg', 'BCEG', None, Profil.BCEG, ['EST'])
    compte('maedr', 'MAEDR', None, Profil.MAEDR)
    compte('eleveur', 'Mba', 'Jean', Profil.ELEVEUR)
    compte('marie.nze', 'Nzé', 'Marie', Profil.ELEVEUR, tel='+241 77 45 12 90')
    compte('paul.obame', 'Obame', 'Paul', Profil.ELEVEUR, tel='+241 77 30 41 52')      # compte bloqué (administration)
    compte('abattoir.owendo', 'Ondo', 'Marc', Profil.OPERATEUR, operateur=ops['owendo'])
    compte('marche.montbouet', 'Mintsa', 'Clarisse', Profil.OPERATEUR, operateur=ops['montbouet'])
    db.session.flush()
    return u


# ── Étape 2 : élevages, bâtiments (blocs) ────────────────────────────────

def _fermes(jeu, provinces, localites, u):
    from app.services import geo
    contours = geo.contours()
    agents_par_prov = {}
    for ident, _, _, prov in AGENTS:
        for c in prov:
            agents_par_prov.setdefault(c, []).append(u[ident])
    fermes = []
    noms_pris = set()
    n_total = sum(n for _, n in REPARTITION)
    # 8 « en préparation », 3 hors programme : répartis sur des rangs fixes (jamais EST-001 à EST-011)
    en_preparation = {('WNT', 21), ('HOG', 16), ('NGO', 13), ('OGI', 8), ('EST', 45), ('EST', 47), ('NYA', 9), ('OGL', 8)}
    hors_programme = {('EST', 40), ('WNT', 18), ('OGM', 11)}
    for code, n in REPARTITION:
        for rang in range(1, n + 1):
            numero = jeu.numero('FERME', code, largeur=3)
            libres = [x for x in NOMS if (code, x) not in noms_pris] or NOMS     # un nom par ferme tant qu'il en reste
            nom = jeu.r.choice(libres)
            noms_pris.add((code, nom))
            prenom = jeu.r.choice(PRENOMS)
            designation = jeu.r.choice(['Ferme', 'Élevage', 'Ferme avicole', 'GIE'])
            if numero == 'EST-001':
                nom, prenom, designation = 'Mba', 'Jean', 'Ferme'
            elif numero == 'EST-002':
                nom, prenom, designation = 'Obiang', 'Marie', 'Ferme'
            elif numero == 'EST-003':
                nom, prenom, designation = 'Nzé', 'Marie', 'Ferme'
            tel = f'07{jeu.r.randint(1000000, 9999999)}'
            agents = agents_par_prov[code]
            agent = agents[0] if code != 'EST' else agents[(rang - 1) % 2]
            if numero in ('EST-001', 'EST-002', 'EST-003'):
                agent = u['agent.est']
            lat, lon = _point_dans(jeu, contours, code)
            statut = 'En préparation' if (code, rang) in en_preparation else 'Opérationnelle'
            capacite = jeu.r.randrange(800, 3001, 100)
            nb_bat = 1 if capacite < 1200 else jeu.r.choice([1, 2, 2, 3]) if capacite < 2400 else jeu.r.choice([2, 3])
            if numero == 'EST-001':
                capacite, nb_bat = 1800, 2
            fe = {'id': jeu.uid(), 'numero_metier': numero, 'nom': f'{designation} {nom}', 'exploitant_nom': f'{prenom} {nom}',
                  'exploitant_telephone': tel, 'telephone_normalise': tel.lstrip('0'), 'province_id': provinces[code].id,
                  'localite_id': jeu.r.choice(localites[code]).id, 'cohorte': 1 if rang <= n * 0.6 else 2,
                  'statut': statut, 'agent_id': agent.id, 'latitude': lat, 'longitude': lon, 'gps_precision_m': jeu.r.randint(4, 15),
                  'gps_date': jeu.dt(jeu.debut + timedelta(days=jeu.r.randint(0, 40)), 10), 'gps_source': 'GPS',
                  'financee_bceg': False, 'programme_poufa': (code, rang) not in hors_programme, 'bandes_par_an': 6,
                  'position_a_verifier': False, 'numero_provisoire': False, 'statut_synchro': 'SYNCHRONISE',
                  'cree_le': jeu.dt(jeu.debut - timedelta(days=jeu.r.randint(10, 60)), 9),
                  'modifie_le': jeu.dt(jeu.debut, 9), 'cree_par': agent.id, 'modifie_par': agent.id}
            jeu.ajouter('ferme', **fe)
            jeu.ajouter('ferme_statut_historique', ferme_id=fe['id'], statut='En préparation', date=fe['cree_le'], utilisateur_id=agent.id)
            if statut != 'En préparation':
                jeu.ajouter('ferme_statut_historique', ferme_id=fe['id'], statut=statut,
                            date=fe['cree_le'] + timedelta(days=8), utilisateur_id=agent.id)
            jeu.ajouter('position_ferme', ferme_id=fe['id'], latitude=lat, longitude=lon, precision_m=fe['gps_precision_m'],
                        releve_le=fe['gps_date'], auteur_id=agent.id, appareil='Téléphone de l\'agent', hors_ligne=False,
                        origine='GPS', a_verifier=False, en_vigueur=True)
            for infra in jeu.r.sample(["Magasin d'aliment", 'Forage ou puits', 'Raccordement électrique (SEEG)', 'Groupe électrogène',
                                       'Pédiluve', 'Clôture', 'Fosse à cadavres ou incinérateur'], jeu.r.randint(2, 5)):
                jeu.ajouter('ferme_infrastructure', ferme_id=fe['id'], infrastructure=infra)
            parts = [capacite // nb_bat] * nb_bat
            parts[0] += capacite - sum(parts)
            fe['_batiments'] = []
            for i, cap in enumerate(parts, start=1):
                b = jeu.ajouter('batiment', ferme_id=fe['id'], rang=i, code=f'B{i}', nom=None, capacite=int(round(cap, -1)), actif=True)
                fe['_batiments'].append(b)
            jeu.compteurs[('BATIMENT', numero, 0)] = nb_bat
            fe['_agent'], fe['_code'] = agent, code
            fermes.append(fe)
    assert len(fermes) == n_total
    return fermes


# ── Étape 3 : 12 mois d'élevage (calcul en mémoire) ──────────────────────

def _ration_g(age):
    return min(170, 12 + 3.5 * age)


def _aliment_du_jour(age):
    return 'demarrage' if age <= 10 else 'croissance' if age <= 24 else 'finition'


def _poids_g(age, facteur):
    pts = [(int(a), int(p)) for a, p in (x.split(':') for x in COURBE.replace(' ', '').split(';'))]
    for (a0, p0), (a1, p1) in zip(pts, pts[1:]):
        if a0 <= age <= a1:
            return (p0 + (p1 - p0) * (age - a0) / (a1 - a0)) * facteur
    return pts[-1][1] * facteur


def _cycles(jeu, en_cours_force):
    """Dates de mise en place d'un bâtiment sur 12 mois, en remontant depuis aujourd'hui.
    Renvoie [(debut, en_cours)]. Avec `en_cours_force`, la dernière bande est en cours aujourd'hui."""
    cycles = []
    if en_cours_force or jeu.r.random() < 0.75:
        debut = jeu.auj - timedelta(days=jeu.r.randint(3, 41))
        cycles.append((debut, True))
    else:
        fin = jeu.auj - timedelta(days=jeu.r.randint(1, 12))
        debut = fin - timedelta(days=DUREE_CHAIR)
        cycles.append((debut, False))
    while True:
        debut = cycles[-1][0] - timedelta(days=DUREE_CHAIR + jeu.r.randint(*VIDE))
        if debut < jeu.debut - timedelta(days=10):
            break
        cycles.append((debut, False))
    return list(reversed(cycles))


def _bandes(jeu, fermes, p, cal, ops, u):
    """Bandes, saisies, aliments, pesées, vaccinations, traitements, livraisons, sorties, lots — pour chaque bâtiment."""
    ponte_fermes = {'EST-020', 'WNT-004', 'HOG-010', 'NGO-008', 'OGM-005'}
    p_aliments = {k: p[k] for k in ('demarrage', 'croissance', 'finition', 'ponte')}
    ecarts_livraison = 0
    for fe in fermes:
        if fe['statut'] != 'Opérationnelle':
            continue
        fe['_bandes'] = []
        eleveur = u['eleveur'] if fe['numero_metier'] == 'EST-001' else u['marie.nze'] if fe['numero_metier'] in ('EST-002', 'EST-003') else None
        auteur = (eleveur or fe['_agent']).id
        for b_i, bat in enumerate(fe['_batiments']):
            if fe['numero_metier'] in ponte_fermes and b_i == 0:
                _bande_ponte(jeu, fe, bat, p, u, auteur)
                continue
            for debut, en_cours in _cycles(jeu, en_cours_force=(b_i == 0)):
                ecarts_livraison += _bande_chair(jeu, fe, bat, debut, en_cours, p, p_aliments, cal, ops, u, auteur, eleveur,
                                                 ecart=(not en_cours and ecarts_livraison < 6 and jeu.r.random() < 0.02))
    return ponte_fermes


def _livraison(jeu, fe, jour, fournisseur, lignes, auteur, statut='RECUE', confirme=True, origine='ETAT', prix=None):
    annee = jour.year
    liv = {'ferme_id': fe['id'], 'date_livraison': jour, 'fournisseur': fournisseur, 'statut': statut, 'origine': origine,
           'confirmee_le': jeu.dt(jour, 17) if confirme else None, 'confirmee_par': auteur if confirme else None,
           'confirmee_par_agent': confirme and auteur == fe['_agent'].id, 'prix_paye_fcfa': prix,
           'numero_metier': jeu.numero('LIVRAISON' if origine == 'ETAT' else 'ACHAT', 'LIV' if origine == 'ETAT' else 'ACH', annee),
           **jeu.saisie_terrain(jour, auteur, 9)}
    jeu.ajouter('livraison', **liv)
    sorties = []
    for produit, livre, recu, morts, valeur, motif in lignes:
        ligne_id = len(jeu.t.get('livraison_ligne', [])) + 1
        jeu.ajouter('livraison_ligne', id=ligne_id, livraison_id=liv['id'], produit_id=produit.id, quantite_livree=livre,
                    subventionne=origine == 'ETAT', part_subventionnee=50 if origine == 'ETAT' else None,
                    valeur_unitaire=valeur, quantite_recue=recu if confirme else None, motif_ecart=motif, morts_arrivee=morts)
        sorties.append(ligne_id)
    return liv, sorties


def _bande_chair(jeu, fe, bat, debut, en_cours, p, p_aliments, cal, ops, u, auteur, eleveur, ecart=False):
    """Une bande de chair complète ; renvoie 1 si sa livraison a un écart."""
    r = jeu.r
    numero_bande_prefixe = f"{fe['numero_metier']}-{bat['code']}"
    rang = jeu.numero('BANDE', numero_bande_prefixe, format_='rang')
    numero = f'{numero_bande_prefixe}-{rang:02d}'
    effectif = int(round(bat['capacite'] * r.uniform(0.85, 1.0), -1))
    mortalite_cible = r.uniform(1.8, 4.0)
    if fe['numero_metier'] in ('EST-007',) and en_cours:
        mortalite_cible = 6.5
    ic = r.uniform(1.6, 1.9)
    facteur_poids = r.uniform(0.96, 1.04)
    bande_id = jeu.uid()
    fin_prevue = debut + timedelta(days=45)
    souche = r.choice(['Cobb 500', 'Cobb 500', 'Ross 308', 'Arbor Acres'])
    age_fin = DUREE_CHAIR if not en_cours else (jeu.auj - debut).days
    # Livraison de l'État : poussins, aliments (besoin + marge), vaccins
    morts_arrivee = r.randint(0, int(effectif * 0.01))
    besoin = {'demarrage': 0.0, 'croissance': 0.0, 'finition': 0.0}
    present_estime = effectif
    for age in range(0, DUREE_CHAIR + 1):
        besoin[_aliment_du_jour(age)] += present_estime * _ration_g(age) * ic / 1.75 / 1000 / p_aliments[_aliment_du_jour(age)].poids_sac_kg
    manque_poussins = 300 if fe['numero_metier'] == 'NGO-003' and en_cours and bat['code'] == 'B1' else 0
    lignes = [(p['poussins'], effectif + morts_arrivee + manque_poussins, effectif + morts_arrivee, morts_arrivee, 450,
               'Manquant' if manque_poussins else None)]
    for k in ('demarrage', 'croissance', 'finition'):
        livre = math.ceil(besoin[k] * 1.08) + 3
        recu = livre - (4 if ecart and k == 'croissance' else 0)
        lignes.append((p[k], livre, recu, None, 14000 if k == 'demarrage' else 24000 if k == 'croissance' else 23000,
                       'Manquant' if recu < livre else None))
    for _, cle, _ in CALENDRIER:
        lignes.append((p[cle], effectif, effectif, None, 15, None))
    statut_liv = 'RECUE_ECART' if (ecart or manque_poussins) else 'RECUE'
    jeu.aide = getattr(jeu, 'aide', {})
    jeu.aide[bande_id] = round(sum(recu * valeur * 50 / 100 for _, _, recu, _, valeur, _ in lignes))
    liv, lignes_ids = _livraison(jeu, fe, debut - timedelta(days=1), 'Couvoir SIAT', lignes, auteur, statut_liv)
    jeu.ajouter('bande', id=bande_id, numero_metier=numero, ferme_id=fe['id'], batiment_id=bat['_id'], rang=rang,
                date_mise_en_place=debut, effectif_initial=effectif, poids_initial_g=42, rattrapage=False, morts_avant_suivi=0,
                date_fin_prevue=fin_prevue, statut='EN_COURS' if en_cours else 'CLOTUREE',
                date_cloture=None if en_cours else debut + timedelta(days=age_fin), cloturee_par=None if en_cours else auteur,
                type_production='CHAIR', souche=souche, ouverte_sans_desinfection=False, numero_provisoire=False,
                statut_synchro='SYNCHRONISE', cree_par=auteur, modifie_par=auteur, cree_le=jeu.dt(debut, 10), modifie_le=jeu.dt(debut, 10))
    jeu.ajouter('bande_poussins', bande_id=bande_id, livraison_ligne_id=lignes_ids[0], quantite=effectif)
    # Jours : mortalité, aliment, pesées, vaccins, sorties
    present = effectif
    total_morts_cible = effectif * mortalite_cible / 100
    poids_jours = [3.0 if a < 7 else 1.0 for a in range(DUREE_CHAIR + 1)]
    somme = sum(poids_jours)
    sorties_prevues = sorted({40, r.choice([42, 43]), 44}) if r.random() < 0.7 else [42, 44]
    oublis = set(r.sample(range(1, DUREE_CHAIR), r.randint(0, 2)))
    jours_vaccin = {cle: age_v + r.choice([0, 0, 1]) for age_v, cle, _ in CALENDRIER}
    dus = [cle for age_v, cle, _ in CALENDRIER if age_v <= (jeu.auj - debut).days - 3]
    vaccin_saute = dus[-1] if (en_cours and dus and r.random() < 0.06) else None
    traitement = r.random() < 0.15
    dernier_jour = min(age_fin, (jeu.auj - debut).days)
    sans_saisie_recente = en_cours and r.random() < 0.06            # « ferme sans saisie » depuis quelques jours
    for age in range(0, dernier_jour + 1):
        jour = debut + timedelta(days=age)
        if jour > jeu.auj:
            break
        if en_cours and jour == jeu.auj and r.random() < 0.35:       # saisie du jour pas encore envoyée
            continue
        if sans_saisie_recente and (jeu.auj - jour).days < 4:
            continue
        if age in oublis and not en_cours:
            continue                                                    # jour non saisi : case vide, jamais zéro
        morts = int(total_morts_cible * poids_jours[age] / somme + r.random())
        if fe['numero_metier'] == 'EST-007' and en_cours and (jeu.auj - jour).days <= 1:
            morts = max(morts, int(present * 0.025))                    # feu rouge : 2,5 % de morts en un jour
        morts = min(morts, present)
        present -= morts
        produit = p_aliments[_aliment_du_jour(age)]
        sacs = round(present * _ration_g(age) * ic / 1.75 / 1000 / produit.poids_sac_kg, 1)
        sj = jeu.saisie_terrain(jour, auteur, 18)
        jeu.ajouter('saisie_jour', bande_id=bande_id, date=jour, morts=morts, oeufs_ramasses=None, oeufs_casses=None,
                    saisi_par_agent=eleveur is None, a_verifier=False, **sj)
        if sacs > 0:
            jeu.ajouter('saisie_aliment', saisie_id=sj['id'], produit_id=produit.id, sacs=sacs, kg=round(sacs * produit.poids_sac_kg, 2))
        if age > 0 and age % 7 == 0:
            moyen = round(_poids_g(age, facteur_poids) * r.uniform(0.97, 1.03))
            jeu.ajouter('pesee', bande_id=bande_id, date=jour, nombre_pesees=10, poids_total_kg=round(moyen * 10 / 1000, 3),
                        poids_moyen_g=moyen, poids_attendu_g=round(_poids_g(age, 1.0)), saisi_par_agent=eleveur is None,
                        **jeu.saisie_terrain(jour, auteur, 8))
        for age_v, cle, mode in CALENDRIER:
            if age == jours_vaccin[cle] and cle != vaccin_saute:
                jeu.ajouter('vaccination', bande_id=bande_id, calendrier_id=cal[cle].id, date=jour, produit_id=p[cle].id,
                            mode=mode, nombre_animaux=present, quantite=present, saisi_par_agent=True, annule=False,
                            **jeu.saisie_terrain(jour, fe['_agent'].id, 9))
        if traitement and age == 20:
            fin_t = jour + timedelta(days=4)
            jeu.ajouter('traitement', bande_id=bande_id, date_debut=jour, date_fin=fin_t, produit_id=p['anticocci'].id,
                        motif='Coccidiose (diarrhée sanglante)', nombre_animaux=present, quantite=2, saisi_par_agent=True,
                        **jeu.saisie_terrain(jour, fe['_agent'].id, 10))
        if age in sorties_prevues and present > 0:
            nombre = present if age == sorties_prevues[-1] else int(present * r.uniform(0.3, 0.5))
            if nombre <= 0:
                continue
            _sortie(jeu, fe, bande_id, numero, jour, nombre, _poids_g(age, facteur_poids), ops, auteur, eleveur)
            present -= nombre
    jeu.ajouter('_bande_resume', id=bande_id, numero=numero, ferme=fe, en_cours=en_cours, debut=debut, present=present,
                effectif=effectif, bat=bat, livraison=liv)
    return 1 if ecart else 0


def _sortie(jeu, fe, bande_id, numero_bande, jour, nombre, poids_g, ops, auteur, eleveur):
    r = jeu.r
    code = fe['_code']
    if code in ('EST', 'MOG', 'OGM') and r.random() < 0.6:
        motif, operateur, libre = 'Abattoir', ops['owendo'], None
    elif code == 'EST':
        motif, operateur, libre = 'Vente', r.choice([ops['montbouet'], ops['komo'], ops['supergros']]), None
    elif code == 'HOG':
        motif, operateur, libre = 'Vente', ops['franceville'], None
    else:
        motif, operateur, libre = 'Vente', None, r.choice(['Marché central', 'Revendeuse du quartier', 'Restaurant Le Baobab', 'Particuliers'])
    poids_kg = round(nombre * poids_g / 1000, 1)
    s = {'bande_id': bande_id, 'date': jour, 'motif': motif, 'operateur_id': operateur.id if operateur else None,
         'destinataire_libre': libre, 'nombre': nombre, 'poids_total_kg': poids_kg, 'saisi_par_agent': eleveur is None,
         'montant_fcfa': int(round(poids_kg * PRIX_KG[motif] * r.uniform(0.95, 1.05), -2)), 'a_verifier': False,
         'mise_de_cote': False, **jeu.saisie_terrain(jour, auteur, 11)}
    s = jeu.ajouter('sortie', **s)
    rang = jeu.numero('LOT', numero_bande, format_='rang')
    lot = {'id': len(jeu.t.get('lot_trace', [])) + 1, 'numero': f'{numero_bande}-S{rang}', 'code': jeu.code(),
           'sortie_id': s['id'], 'ferme_id': fe['id'], 'cree_par': auteur, 'annule': False,
           'cree_le': jeu.dt(jour, 11), 'modifie_le': jeu.dt(jour, 11)}
    jeu.ajouter('lot_trace', **lot)
    s['_lot'], s['_operateur'], s['_ferme'] = lot, operateur, fe
    return s


def _bande_ponte(jeu, fe, bat, p, u, auteur):
    """Bande de ponte : ~260 jours, ponte à partir de 20 semaines, ventes d'œufs en plateaux ; EST-020 : chute de ponte."""
    r = jeu.r
    prefixe = f"{fe['numero_metier']}-{bat['code']}"
    rang = jeu.numero('BANDE', prefixe, format_='rang')
    debut = jeu.auj - timedelta(days=r.randint(240, 280))
    effectif = int(round(bat['capacite'] * 0.9, -1))
    bande_id = jeu.uid()
    morts_arrivee = r.randint(0, 8)
    liv, ids = _livraison(jeu, fe, debut - timedelta(days=1), 'Couvoir SIAT',
                          [(p['poussins_ponte'], effectif + morts_arrivee, effectif + morts_arrivee, morts_arrivee, 900, None)], auteur)
    jeu.ajouter('bande', id=bande_id, numero_metier=f'{prefixe}-{rang:02d}', ferme_id=fe['id'], batiment_id=bat['_id'], rang=rang,
                date_mise_en_place=debut, effectif_initial=effectif, poids_initial_g=40, rattrapage=False, morts_avant_suivi=0,
                date_fin_prevue=debut + timedelta(days=560), statut='EN_COURS', type_production='PONTE', souche='ISA Brown',
                ouverte_sans_desinfection=False, numero_provisoire=False, statut_synchro='SYNCHRONISE', cree_par=auteur,
                modifie_par=auteur, cree_le=jeu.dt(debut, 10), modifie_le=jeu.dt(debut, 10))
    jeu.ajouter('bande_poussins', bande_id=bande_id, livraison_ligne_id=ids[0], quantite=effectif)
    present, stock, livre, consomme = effectif, 0, 0.0, 0.0
    chute = fe['numero_metier'] == 'EST-020'
    for age in range(0, (jeu.auj - debut).days + 1):
        jour = debut + timedelta(days=age)
        if jour == jeu.auj and r.random() < 0.3:
            continue
        morts = 1 if r.random() < present * 0.00015 else 0
        present -= morts
        sacs = round(present * min(115, 15 + age * 1.2) / 1000 / 50, 1)
        if consomme + sacs > livre:                                    # livraison d'aliment ponte, 30 jours d'avance
            q = math.ceil(present * 115 * 30 / 1000 / 50 * 1.1)
            _livraison(jeu, fe, jour - timedelta(days=1), 'SMAG Aliments', [(p['ponte'], q, q, None, 22000, None)], auteur)
            livre += q
        consomme += sacs
        oeufs = None
        casses = None
        if age >= 140:
            taux = min(0.88, 0.25 + (age - 140) * 0.02) * r.uniform(0.96, 1.02)
            if chute and (jeu.auj - jour).days <= 2:
                taux *= 0.68
            oeufs = int(present * taux)
            casses = int(oeufs * r.uniform(0.005, 0.02))
            stock += oeufs - casses
        sj = jeu.saisie_terrain(jour, auteur, 18)
        jeu.ajouter('saisie_jour', bande_id=bande_id, date=jour, morts=morts, oeufs_ramasses=oeufs, oeufs_casses=casses,
                    saisi_par_agent=False, a_verifier=False, **sj)
        jeu.ajouter('saisie_aliment', saisie_id=sj['id'], produit_id=p['ponte'].id, sacs=sacs, kg=round(sacs * 50, 2))
        if age >= 145 and age % 4 == 0 and stock >= 300:
            plateaux = int(stock * 0.85) // 30
            n = plateaux * 30
            stock -= n
            jeu.ajouter('vente_oeufs', bande_id=bande_id, date=jour, oeufs=n, montant_fcfa=plateaux * 2700,
                        acheteur=r.choice(['Marché de Mont-Bouët', 'Boulangerie du quartier', 'Super Gros Libreville', 'Revendeuses']),
                        saisi_par_agent=False, numero_metier=jeu.numero('VENTE_OEUFS', 'OEU', jour.year), **{k: v for k, v in jeu.saisie_terrain(jour, auteur, 12).items()})
        if age > 0 and age % 28 == 0 and age <= 140:
            moyen = round(min(1900, 40 + age * 12) * r.uniform(0.97, 1.03))
            jeu.ajouter('pesee', bande_id=bande_id, date=jour, nombre_pesees=10, poids_total_kg=round(moyen / 100, 3),
                        poids_moyen_g=moyen, poids_attendu_g=None, saisi_par_agent=False, **jeu.saisie_terrain(jour, auteur, 8))
    jeu.ajouter('_bande_resume', id=bande_id, numero=f'{prefixe}-{rang:02d}', ferme=fe, en_cours=True, debut=debut,
                present=present, effectif=effectif, bat=bat, livraison=liv, ponte=True)


# ── Étape 4 : réceptions, scans, argent, visites (blocs) ─────────────────

def _receptions(jeu, u, ops):
    """Réceptions à l'abattoir d'Owendo et au marché de Mont-Bouët des 45 derniers jours ; un écart de nombre ;
    un lot gardé à part ; trois scans refusés du même QR (HOG-006)."""
    r = jeu.r
    ok = [{'cle': c, 'libelle': l, 'ok': True, 'bloquant': True, 'detail': None} for c, l in (
        ('qr', 'QR connu et jamais reçu'), ('destinataire', 'Destiné à votre établissement'),
        ('vaccins', 'Vaccins obligatoires faits'), ('delai_attente', "Aucun traitement en délai d'attente"),
        ('blocage', 'Bande non bloquée par le vétérinaire'), ('pesee', 'Pesée récente'))]
    candidates = [s for s in jeu.t['sortie'] if s.get('_operateur') in (ops['owendo'], ops['montbouet'])
                  and (jeu.auj - s['date']).days <= 45]
    ecart_fait = reserve_fait = False
    for i, s in enumerate(sorted(candidates, key=lambda x: x['date'])):
        if (jeu.auj - s['date']).days == 0 and i % 2:
            continue                                                    # attendu aujourd'hui, pas encore reçu
        operateur = s['_operateur']
        user = u['abattoir.owendo'] if operateur is ops['owendo'] else u['marche.montbouet']
        vivants, morts, etat, motif_ecart, explication, controles = s['nombre'], 0, 'VALIDEE', None, None, ok
        if not ecart_fait and s['nombre'] > 200:
            morts = 4
            vivants = s['nombre'] - int(s['nombre'] * 0.04)
            motif_ecart, explication, ecart_fait = 'Morts au transport', 'Camion arrivé avec 2 h de retard (chaleur).', True
        elif not reserve_fait and operateur is ops['owendo'] and i > 3:
            etat, reserve_fait = 'SOUS_RESERVE', True
            controles = [dict(c) for c in ok]
            controles[2].update(ok=False, detail='Pas fait : Vaccin Gumboro (rappel)')
        jeu.ajouter('reception', lot_id=s['_lot']['id'], ferme_id=s['_ferme']['id'], operateur_id=operateur.id,
                    recu_le=jeu.dt(s['date'], 14), lot_saisi=s['_lot']['numero'], annonce=s['nombre'],
                    annonce_kg=s['poids_total_kg'], vivants=vivants, morts=morts,
                    poids_kg=round(float(s['poids_total_kg']) * vivants / s['nombre'] * r.uniform(0.98, 1.0), 1), etat=etat,
                    controles=controles, motif_ecart=motif_ecart, explication=explication, hors_ligne=False,
                    vu_le=jeu.dt(s['date'], 16), numero_metier=None, **jeu.saisie_terrain(s['date'], user.id, 14))
        jeu.ajouter('scan', horodatage=jeu.dt(s['date'], 13, 55), utilisateur_id=user.id, operateur_id=operateur.id,
                    lot_id=s['_lot']['id'], empreinte=_empreinte(s['_lot']['code']), saisie=None, source='CAMERA',
                    resultat='ORANGE' if etat == 'SOUS_RESERVE' else 'VERT', motif=None)
    # HOG-006 : son dernier lot vendu au marché de Franceville, scanné 3 fois à Owendo en moins de 24 h → refusé
    lots_hog = [s for s in jeu.t['sortie'] if s['_ferme']['numero_metier'] == 'HOG-006']
    if lots_hog:
        s = lots_hog[-1]
        for k in range(3):
            jeu.ajouter('scan', horodatage=jeu.dt(jeu.auj - timedelta(days=1), 9 + k * 2), utilisateur_id=u['abattoir.owendo'].id,
                        operateur_id=ops['owendo'].id, lot_id=s['_lot']['id'], empreinte=_empreinte(s['_lot']['code']), saisie=None,
                        source='CAMERA', resultat='ROUGE',
                        motif=f"Ce lot est destiné à {s['_operateur'].nom if s['_operateur'] else s['destinataire_libre']}, pas à vous.")


def _empreinte(code):
    import hashlib
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def _argent(jeu, fermes, u):
    """Dépenses mensuelles par poste ; achats personnels ; chiffre d'affaires de l'éleveur réglé près du 1er seuil
    fiscal (ISL)."""
    r = jeu.r
    for fe in fermes:
        if fe['statut'] != 'Opérationnelle':
            continue
        cap = sum(b['capacite'] for b in fe['_batiments'])
        auteur = (u['eleveur'] if fe['numero_metier'] == 'EST-001' else fe['_agent']).id
        m = jeu.debut.replace(day=1)
        while m <= jeu.auj:
            for poste, base in ((POSTES[0], 60 * cap), (POSTES[1], 15 * cap), (POSTES[2], 8 * cap), (POSTES[3], 10 * cap), (POSTES[4], 4 * cap)):
                jour = min(m + timedelta(days=r.randint(1, 27)), jeu.auj)
                if jour < jeu.debut:
                    continue
                jeu.ajouter('depense', ferme_id=fe['id'], batiment_id=None, categorie=poste,
                            montant_fcfa=int(round(base * r.uniform(0.8, 1.2), -2)), date=jour, saisi_par_agent=auteur != (u['eleveur'].id),
                            annule=False, numero_metier=jeu.numero('DEPENSE', 'DEP', jour.year), **jeu.saisie_terrain(jour, auteur, 19))
            if r.random() < 0.25:
                jour = min(m + timedelta(days=r.randint(1, 27)), jeu.auj)
                jeu.ajouter('depense', ferme_id=fe['id'], batiment_id=None, categorie=r.choice(POSTES[5:]),
                            montant_fcfa=int(round(r.uniform(15000, 120000), -2)), date=jour, saisi_par_agent=False, annule=False,
                            numero_metier=jeu.numero('DEPENSE', 'DEP', jour.year), **jeu.saisie_terrain(jour, auteur, 19))
            m = (m + timedelta(days=32)).replace(day=1)
    # Achats personnels (copeaux, abreuvoirs, vitamines) : quelques-uns par élevage
    return


def _achats(jeu, fermes, p, u):
    r = jeu.r
    for fe in fermes:
        if fe['statut'] != 'Opérationnelle':
            continue
        auteur = (u['eleveur'] if fe['numero_metier'] == 'EST-001' else fe['_agent']).id
        for _ in range(r.randint(1, 4)):
            jour = jeu.debut + timedelta(days=r.randint(5, 360))
            produit, q, pu = r.choice([(p['copeaux'], r.randint(5, 20), 2500), (p['abreuvoir'], r.randint(2, 6), 6500),
                                        (p['vitamines'], r.randint(1, 4), 3000)])
            _livraison(jeu, fe, min(jour, jeu.auj), r.choice(['Quincaillerie de Nzeng-Ayong', 'Marché de Mont-Bouët', 'Pharmavet Libreville']),
                       [(produit, q, q, None, None, None)], auteur, origine='ACHAT', prix=q * pu)


def _reglage_chiffre_eleveur(jeu):
    """Le chiffre d'affaires de l'année civile de l'éleveur (EST-001) approche le 1er seuil fiscal (92 % de 30 M FCFA)."""
    from app.services import bilan
    seuil = bilan.seuils()['isl']
    ids = {b['id'] for b in jeu.t['_bande_resume'] if b['ferme']['numero_metier'] == 'EST-001'}
    annee = [s for s in jeu.t['sortie'] if s['bande_id'] in ids and s['date'].year == jeu.auj.year]
    total = sum(s['montant_fcfa'] or 0 for s in annee)
    if total:
        f = seuil * 0.92 / total
        for s in (x for x in jeu.t['sortie'] if x['bande_id'] in ids):
            s['montant_fcfa'] = int(round(s['montant_fcfa'] * f, -2))


def _visites(jeu, fermes, u):
    """Visites faites (3 derniers mois), tournées prévues (7 prochains jours), biosécurité notée."""
    from app.models.liste_deroulante import ListeDeroulante
    r = jeu.r
    grille = [l.valeur for l in ListeDeroulante.query.filter_by(categorie='grille_biosecurite').order_by(ListeDeroulante.ordre)]
    recos = [l.valeur for l in ListeDeroulante.query.filter_by(categorie='recommandations_visite')]
    for fe in fermes:
        agent = fe['_agent']
        for k in range(r.randint(1, 3)):
            jour = jeu.auj - timedelta(days=r.randint(3, 90))
            jeu.ajouter('visite', ferme_id=fe['id'], agent_id=agent.id, date_prevue=jour, objet=r.choice(['Suivi', 'Vaccination', 'Contrôle']),
                        statut='FAITE', faite_le=jour, constats=r.choice(['Litière un peu humide près des abreuvoirs.', 'Bande homogène, bon appétit.',
                                                                          'Quelques poulets abattus dans le coin nord.', 'Registre bien tenu.']),
                        recommandations=r.sample(recos, 2) if recos else [], latitude=fe['latitude'], longitude=fe['longitude'],
                        precision_m=8, distance_m=r.randint(5, 60), vue_par_eleveur_le=jeu.dt(jour + timedelta(days=1), 8),
                        **jeu.saisie_terrain(jour, agent.id, 11))
        if r.random() < 0.15:
            jour = jeu.auj + timedelta(days=r.randint(1, 7))
            jeu.ajouter('visite', ferme_id=fe['id'], agent_id=agent.id, date_prevue=jour, objet='Suivi', statut='PREVUE',
                        recommandations=[], **jeu.saisie_terrain(jeu.auj, agent.id, 8))
        if grille and r.random() < 0.45:
            jour = jeu.auj - timedelta(days=r.randint(5, 120))
            reponses = {pt: ('oui' if r.random() < 0.78 else 'non') for pt in grille}
            oui = sum(1 for v in reponses.values() if v == 'oui')
            mesures = [{'point': pt, 'mesure': 'À corriger avant la prochaine bande'} for pt, v in reponses.items() if v == 'non']
            jeu.ajouter('visite', ferme_id=fe['id'], agent_id=agent.id, date_prevue=jour, objet='Biosécurité', statut='FAITE', faite_le=jour,
                        recommandations=[], biosecurite=reponses, score_biosecurite=round(oui * 100 / len(grille)),
                        mesures_correctives=mesures, **jeu.saisie_terrain(jour, agent.id, 15))


# ── Insertion ─────────────────────────────────────────────────────────────

ORDRE = ['ferme', 'ferme_statut_historique', 'position_ferme', 'ferme_infrastructure', 'batiment', 'livraison', 'livraison_ligne',
         'bande', 'bande_poussins', 'saisie_jour', 'saisie_aliment', 'pesee', 'vaccination', 'traitement', 'sortie', 'lot_trace',
         'reception', 'scan', 'vente_oeufs', 'depense', 'visite']


def _inserer(jeu, tables):
    conn = db.session.connection()
    for nom in ORDRE:
        lignes = jeu.t.get(nom, [])
        if not lignes:
            continue
        t = tables[nom]
        propres = [{k: v for k, v in l.items() if not k.startswith('_') and k in t.c} for l in lignes]
        groupes = {}                                             # une insertion par jeu de colonnes identique
        for l in propres:
            groupes.setdefault(tuple(sorted(l)), []).append(l)
        for g in groupes.values():
            for i in range(0, len(g), 2000):
                conn.execute(t.insert(), g[i:i + 2000])
        if nom == 'batiment':                                    # identifiants des bâtiments pour les bandes
            ids = {(r.ferme_id, r.code): r.id for r in conn.execute(sa.select(t.c.id, t.c.ferme_id, t.c.code))}
            for b in lignes:
                b['_id'] = ids[(b['ferme_id'], b['code'])]
        jeu.volumes[nom] = len(lignes)


def _compteurs(jeu):
    from app.models.compteur import Compteur
    for (type_, prefixe, annee), n in jeu.compteurs.items():
        c = Compteur.query.filter_by(type=type_, prefixe=prefixe, annee=annee).first()
        if c is None:
            db.session.add(Compteur(type=type_, prefixe=prefixe, annee=annee, dernier_numero=n))
        else:
            c.dernier_numero = max(c.dernier_numero, n)
    db.session.flush()


def _sequences():
    conn = db.session.connection()
    if conn.dialect.name != 'postgresql':
        return
    for t in db.metadata.sorted_tables:
        for c in t.primary_key.columns:
            if isinstance(c.type, sa.Integer) and c.autoincrement is not False:
                conn.execute(sa.text(f"SELECT setval(pg_get_serial_sequence('{t.name}', '{c.name}'), "
                                     f"COALESCE((SELECT max({c.name}) FROM {t.name}), 0) + 1, false)"))


# ── Étape 5 : le présent, par les services ───────────────────────────────

def _present(jeu, u, p, ops):
    from app.models import Ferme, Profil
    from app.models.bande import Bande, Sortie
    from app.models.intrant import Livraison
    from app.models.agent import CommandeIntrant
    from app.models.hors_ligne import ConflitHorsLigne
    from app.models.sante import Declaration, DeclarationPhoto, AlerteSanitaire
    from app.models.bceg import ConsentementBceg
    from app.models.notification import Notification, TypeNotification
    from app.models.securite import SessionUtilisateur
    from app.models.base import maintenant
    from app import indicateurs
    from app.services import sante, veto, actions, approbations, maedr, rapports, verifications
    from app.models.rapport import TypeRapport
    r = jeu.r

    def ferme(numero):
        return Ferme.query.filter_by(numero_metier=numero).one()

    def bande_en_cours(numero):
        return (Bande.query.filter_by(ferme_id=ferme(numero).id, statut='EN_COURS')
                .filter(Bande.type_production == 'CHAIR').order_by(Bande.date_mise_en_place.desc()).first())

    # Éleveurs rattachés à leurs fermes
    from app.models.utilisateur import UtilisateurFerme
    for ident, numeros in (('eleveur', ['EST-001']), ('marie.nze', ['EST-003', 'EST-002']), ('paul.obame', ['EST-014'])):
        for n in numeros:
            db.session.add(UtilisateurFerme(utilisateur_id=u[ident].id, ferme_id=ferme(n).id))
    db.session.flush()
    for x in u.values():
        db.session.expire(x)

    # Bilans figés des bandes clôturées (étoiles, marge, aide de l'État)
    # Pendant le chargement seulement : mouvements d'argent lus une fois par ferme, aide de l'État lue sur la livraison
    # de la bande (le générateur la connaît) — sinon chaque bilan relit et répartit toutes les livraisons de la ferme
    from app.services import argent
    from sqlalchemy.orm import selectinload
    from app.models.bande import SaisieJour
    toutes = (Bande.query.options(selectinload(Bande.saisies_toutes).selectinload(SaisieJour.aliments),
                                  selectinload(Bande.sorties_toutes), selectinload(Bande.pesees_toutes)).all())
    par_ferme = {}
    for b in toutes:
        par_ferme.setdefault(b.ferme_id, []).append(b)
    lire_mvts, lire_aide, lire_bandes, memo = argent.mouvements, argent.aide_etat, argent.bandes_du_jour, {}
    argent.mouvements = lambda ids: memo[tuple(ids)] if tuple(ids) in memo else memo.setdefault(tuple(ids), lire_mvts(ids))
    argent.aide_etat = lambda bande: jeu.aide.get(bande.id)
    argent.bandes_du_jour = lambda ferme_id, jour, bandes=None: [b for b in par_ferme.get(ferme_id, []) if b.date_mise_en_place <= jour
                                                    and (b.date_cloture is None or jour <= b.date_cloture)]
    try:
        with db.session.no_autoflush:
            for b in toutes:
                if b.statut == 'CLOTUREE':
                    b.bilan = indicateurs.bilan(b)
    finally:
        argent.mouvements, argent.aide_etat, argent.bandes_du_jour = lire_mvts, lire_aide, lire_bandes
    db.session.flush()
    _etape('bilans des bandes clôturées')

    # Sanitaire : feu rouge EST-007 → alerte ; signalements avec photos ; diagnostics ; ventes bloquées
    b7 = bande_en_cours('EST-007')
    if b7 is not None:
        sante.alerte_si_feu_rouge(b7)
    signes_possibles = [['Diarrhée', 'Abattement'], ['Toux / respiration difficile'], ['Mortalité soudaine', 'Ne mange plus'],
                        ['Plumes ébouriffées', 'Diarrhée'], ['Boiterie'], ['Gonflement de la tête', 'Toux / respiration difficile']]
    from pathlib import Path
    dossier = Path(sante.dossier())
    couleurs = [(180, 140, 90), (120, 160, 90), (200, 190, 170), (150, 110, 80)]
    signalements = []
    for k, numero in enumerate(['EST-012', 'EST-019', 'WNT-006', 'HOG-003', 'NGO-005', 'OGM-002', 'MOG-004', 'EST-026']):
        b = bande_en_cours(numero)
        if b is None:
            continue
        jour = jeu.auj - timedelta(days=k % 6)
        d = Declaration(ferme_id=b.ferme_id, bande_id=b.id, signes=signes_possibles[k % len(signes_possibles)],
                        nombre_animaux=r.randint(5, 60), saisi_par_agent=k % 2 == 0, numero_metier=None,
                        cree_le=jeu.dt(jour, 9 + k))
        db.session.add(d)
        db.session.flush()
        for c in range(1 + k % 2):
            nom = f'demo_{d.id.hex[:12]}_{c}.png'
            (dossier / nom).write_bytes(_png(couleurs[(k + c) % len(couleurs)]))
            db.session.add(DeclarationPhoto(declaration_id=d.id, fichier=nom, type_mime='image/png'))
        a = sante._nouvelle_alerte(b.ferme, b, 'DECLARATION', declaration=d)
        signalements.append((a, b))
    db.session.flush()
    vetos = {v: u[v] for v in ('veto', 'veto.nord', 'veto.sud')}

    def veto_de(b):
        code = b.ferme.province.code
        return next(v for ident, _, _, prov in VETOS for v in [vetos[ident]] if code in prov)
    for k, (a, b) in enumerate(signalements):
        v = veto_de(b)
        if k in (0, 1, 2, 4):
            sante.changer_statut(a, 'EN_ANALYSE', 'Prise en charge, visite prévue.', v)
            sante.repondre(a, 'Isolez les poulets malades et gardez la litière sèche.', ['Isolez les poulets malades', 'Augmentez la ventilation'], v)
        if k in (0, 4):
            veto.diagnostiquer(a, 'Coccidiose' if k == 0 else 'Newcastle', 'Fientes, 2 cadavres', 'Lésions compatibles.', v)
            sante.changer_statut(a, 'CONFIRMEE', 'Diagnostic posé.', v)
        if k == 4:                                                  # NGO-005 : ventes bloquées
            veto.bloquer(b, 'Suspicion de Newcastle confirmée : sorties bloquées jusqu\'à la levée.', v, alerte=a)
        if k == 2:
            sante.changer_statut(a, 'INFIRMEE', 'Pas de maladie contagieuse : stress de chaleur.', v)
            sante.changer_statut(a, 'CLOSE', 'Plus de signes après la ventilation.', v)
    db.session.flush()

    # Intrants : livraisons à confirmer (4), prévues par la DGE (5), commandes (à valider, validées, refusée)
    from app.models.intrant import LivraisonLigne
    for numero in ['EST-004', 'WNT-002', 'HOG-001', 'NYA-003']:
        f = ferme(numero)
        liv = Livraison(ferme_id=f.id, date_livraison=jeu.auj - timedelta(days=1), fournisseur='SMAG Aliments', statut='A_CONFIRMER',
                        origine='ETAT', numero_metier=_num(jeu, 'LIVRAISON', 'LIV', jeu.auj.year))
        db.session.add(liv)
        db.session.flush()
        db.session.add(LivraisonLigne(livraison_id=liv.id, produit_id=p['croissance'].id, quantite_livree=20, subventionne=True,
                                      part_subventionnee=50, valeur_unitaire=24000))
    for k, numero in enumerate(['EST-005', 'EST-009', 'WNT-007', 'HOG-004', 'OGM-003']):
        f = ferme(numero)
        liv = Livraison(ferme_id=f.id, date_livraison=jeu.auj + timedelta(days=2 + k * 2), fournisseur='Couvoir SIAT', statut='PREVUE',
                        origine='ETAT', numero_metier=_num(jeu, 'LIVRAISON', 'LIV', jeu.auj.year))
        db.session.add(liv)
        db.session.flush()
        db.session.add(LivraisonLigne(livraison_id=liv.id, produit_id=p['poussins'].id, quantite_livree=1000, subventionne=True,
                                      part_subventionnee=50, valeur_unitaire=450))
    for k, (numero, produit, q, statut) in enumerate([('EST-006', 'croissance', 30, 'ENVOYEE'), ('EST-013', 'finition', 25, 'ENVOYEE'),
                                                       ('WNT-003', 'demarrage', 40, 'ENVOYEE'), ('HOG-002', 'gumboro', 1500, 'ENVOYEE'),
                                                       ('NGO-002', 'croissance', 20, 'ENVOYEE'), ('MOG-002', 'finition', 30, 'VALIDEE'),
                                                       ('OGM-004', 'demarrage', 25, 'VALIDEE'), ('EST-015', 'croissance', 60, 'REFUSEE')]):
        f = ferme(numero)
        agent = f.agent
        c = CommandeIntrant(ferme_id=f.id, produit_id=p[produit].id, quantite=q, motif='Stock bas pour la fin de bande',
                            statut=statut, demandee_par=agent.id, cree_le=jeu.dt(jeu.auj - timedelta(days=k % 4 + 1), 10))
        if statut != 'ENVOYEE':
            c.decidee_par, c.decidee_le = u['dge'].id, jeu.dt(jeu.auj - timedelta(days=1), 15)
            if statut == 'REFUSEE':
                c.motif_refus = 'Quantité trop élevée pour la taille du bâtiment.'
        db.session.add(c)

    # Comptages de stock par les agents (dont un écart)
    from app.models.agent import InventaireStock
    from app.services import intrants
    for k, numero in enumerate(['EST-001', 'EST-004', 'EST-009', 'WNT-001', 'HOG-005', 'NGO-001']):
        f = ferme(numero)
        for s in intrants.stock_ferme(f)[:2]:
            compte = s['stock'] - (8 if k == 2 else 0)
            livre = s['etat'] + s['achat']
            db.session.add(InventaireStock(ferme_id=f.id, produit_id=s['produit'].id, jour=jeu.auj - timedelta(days=k),
                                           livre=livre, utilise=livre - s['stock'], compte=max(0, compte),
                                           agent_id=f.agent_id, externe=False))
    db.session.flush()

    # Arbitrages : doublon de sortie sur EST-011 (en attente depuis 49 h) ; deux journées saisies deux fois
    b11 = bande_en_cours('EST-011')
    if b11 is not None:
        present = indicateurs.calculer(b11)['effectif_present']
        if present > 60:
            jour = jeu.auj - timedelta(days=2)
            a1, a2 = u['agent.est'], u['agent.est2']
            s1 = Sortie(bande_id=b11.id, date=jour, motif='Vente', operateur_id=ops['montbouet'].id, nombre=50, poids_total_kg=95,
                        montant_fcfa=218500, cree_par=a1.id, modifie_par=a1.id, cree_le=maintenant() - timedelta(hours=50))
            s2 = Sortie(bande_id=b11.id, date=jour, motif='Vente', operateur_id=ops['montbouet'].id, nombre=50, poids_total_kg=95,
                        montant_fcfa=218500, cree_par=a2.id, modifie_par=a2.id, cree_le=maintenant() - timedelta(hours=49))
            db.session.add_all([s1, s2])
            db.session.flush()
            verifications.doublon_sortie(s2, a2)
            db.session.flush()
            c = ConflitHorsLigne.query.filter_by(objet_table='sortie').order_by(ConflitHorsLigne.id.desc()).first()
            if c is not None:
                c.cree_le = maintenant() - timedelta(hours=49)
    from app.models.bande import SaisieJour
    for numero in ['EST-008', 'WNT-005']:
        b = bande_en_cours(numero)
        s = SaisieJour.query.filter_by(bande_id=b.id).order_by(SaisieJour.date.desc()).first() if b else None
        if s is not None:
            verifications.deux_versions_saisie(b, s, s.morts + 3, {}, b.ferme.agent, saisi_le=maintenant() - timedelta(hours=20))
    db.session.flush()

    # Plans d'actions : DGE → agents, agents pour leurs fermes (dont en retard, dont faites)
    for k, (createur, responsable, numero, intitule, delta, faite) in enumerate([
            ('dge', 'agent.est', 'EST-007', 'Visite sanitaire après le feu rouge', 2, False),
            ('dge', 'agent.ngo', 'NGO-003', 'Régulariser les 300 poussins manquants avec le couvoir', -5, False),
            ('dge', 'agent.hog', 'HOG-006', 'Expliquer les 3 scans refusés à Owendo', -2, False),
            ('dge', 'agent.wnt', None, 'Former les éleveurs de Woleu-Ntem à la pesée hebdomadaire', 20, False),
            ('dge', 'agent.mog', None, 'Relancer les fermes sans saisie depuis 3 jours', -1, False),
            ('dge', 'agent.est2', 'EST-011', 'Trancher le doublon de sortie', 1, False),
            ('agent.est', 'agent.est', 'EST-001', 'Refaire le pédiluve', -3, False),
            ('agent.est', 'agent.est', 'EST-005', 'Contrôler le stock de croissance', 4, False),
            ('agent.est', 'agent.est', 'EST-009', 'Recompter le stock (écart de 8 sacs)', 3, False),
            ('agent.hog', 'agent.hog', 'HOG-002', 'Vacciner le rappel Gumboro', -8, True),
            ('dge', 'agent.est', None, 'Préparer le bilan trimestriel Estuaire', -12, True)]):
        a = actions.creer(u[createur], intitule, jeu.auj + timedelta(days=delta), responsable=u[responsable],
                          ferme=ferme(numero) if numero else None,
                          province=None if numero else Ferme.query.filter_by(agent_id=u[responsable].id).first().province)
        if faite:
            a.avancement, a.faite_le = 100, jeu.auj + timedelta(days=delta - 1)
    db.session.flush()

    # BCEG : 6 élevages financés (responsable = éleveur rattaché), 4 accords dont 1 retiré ensuite
    bceg_fermes = ['EST-001', 'EST-003', 'EST-002', 'EST-014', 'EST-016', 'EST-018']
    for numero in bceg_fermes:
        f = ferme(numero)
        f.financee_bceg = True
        resp = next((x for x in ('eleveur', 'marie.nze', 'paul.obame') if f.id in u[x].ferme_ids), None)
        f.responsable_id = u[resp].id if resp else None
    db.session.flush()
    for numero, resp in (('EST-001', 'eleveur'), ('EST-003', 'marie.nze'), ('EST-002', 'marie.nze'), ('EST-014', 'paul.obame')):
        db.session.add(ConsentementBceg(ferme_id=ferme(numero).id, utilisateur_id=u[resp].id, decision='ACCEPTE',
                                        cree_le=jeu.dt(jeu.auj - timedelta(days=60), 10)))
    db.session.add(ConsentementBceg(ferme_id=ferme('EST-002').id, utilisateur_id=u['marie.nze'].id, decision='RETIRE',
                                    cree_le=jeu.dt(jeu.auj - timedelta(days=10), 10)))

    # Rapports mensuels (3 derniers mois) ; 1 soumis au visa du MAEDR, 2 visés (diffusés)
    mois = []
    m = jeu.auj.replace(day=1)
    for _ in range(3):
        m = (m - timedelta(days=1)).replace(day=1)
        mois.append(m.strftime('%Y-%m'))
    produits = []
    for periode in reversed(mois):
        try:
            rap, _ = rapports.generer(TypeRapport.NATIONAL, periode, u['dge'], automatique=True)
            produits.append(rap)
        except Exception as e:                                      # un PDF ne doit pas arrêter le jeu de données
            print(f'  rapport {periode} non produit : {e}')
    for rap in produits[:2]:
        maedr.soumettre(rap, u['dge'])
        maedr.viser(rap, u['maedr'], True)
    if len(produits) >= 3:
        maedr.soumettre(produits[2], u['dge'])
    db.session.flush()

    # Administration : 2 validations quatre yeux en attente, sessions, un compte bloqué, notifications de chaque type
    approbations.proposer('PARAMETRE', 'bandes.seuil_rouge_pct', 'Seuil du feu rouge (% de morts en un jour)', '1', '0.8',
                          {'valeur': '0.8', 'type': 'DECIMAL'}, 'Plus de prudence pendant la saison des pluies.', u['dge'])
    approbations.proposer('PARAMETRE', 'fiscalite.seuil_isl_fcfa', "Seuil de l'impôt synthétique (FCFA)", '30000000', '35000000',
                          {'valeur': '35000000', 'type': 'ENTIER'}, 'Nouvelle loi de finances (à confirmer avec la DGI).', u['admin'])
    for ident, minutes in (('dge', 4), ('admin', 12), ('agent.est', 2), ('veto', 30)):
        db.session.add(SessionUtilisateur(id=str(jeu.uid()), utilisateur_id=u[ident].id, appareil='Chrome sur Windows' if ident != 'agent.est' else 'Téléphone Android',
                                          adresse_ip=f'41.158.{r.randint(1, 250)}.{r.randint(1, 250)}',
                                          ouverte_le=maintenant() - timedelta(minutes=minutes + 40), derniere_activite=maintenant() - timedelta(minutes=minutes)))
    u['paul.obame'].echecs_connexion = 5
    u['paul.obame'].bloque_jusqu_a = maintenant() + timedelta(hours=2)
    destinataires = {'SAISIE_OUBLIEE': 'eleveur', 'PESEE_RETARD': 'eleveur', 'VACCIN_DEMAIN': 'eleveur', 'REPONSE_VETO': 'marie.nze',
                     'LIVRAISON_A_CONFIRMER': 'agent.est', 'VENTES_BLOQUEES': 'agent.ngo', 'RAPPEL_FISCAL': 'eleveur',
                     'FEU_ROUGE': 'veto', 'FERME_SANS_SAISIE': 'agent.est', 'DEUX_VERSIONS': 'agent.est',
                     'ACTION_RETARD': 'agent.hog', 'VISITE_DEMAIN': 'eleveur', 'LOT_EN_ROUTE': 'abattoir.owendo',
                     'LOT_DECIDE': 'agent.est', 'SIGNALEMENT': 'veto', 'ALERTE_SANITAIRE': 'dge', 'PARAMETRE_A_APPROUVER': 'admin'}
    for k, (type_, ident) in enumerate(destinataires.items()):
        if not hasattr(TypeNotification, type_):
            continue
        quand = maintenant() - timedelta(hours=k * 3 + 1)
        db.session.add(Notification(utilisateur_id=u[ident].id, type=type_, cle=f'demo-{type_.lower()}',
                                    titre=type_.replace('_', ' ').capitalize()[:80], texte=_texte_notification(type_)[:200],
                                    lien='/', cree_le=quand, envoyee_le=quand, resultat='sans_abonnement'))
    db.session.flush()


def _texte_notification(type_):
    return {
        'SAISIE_OUBLIEE': "Vous n'avez pas envoyé hier : notez les morts et l'aliment de la bande.",
        'PESEE_RETARD': 'La pesée de la semaine est en retard : pesez 10 poulets.',
        'VACCIN_DEMAIN': 'Demain : vaccin Gumboro (eau de boisson) pour la bande B1.',
        'REPONSE_VETO': 'Le vétérinaire a répondu à votre signalement.',
        'LIVRAISON_A_CONFIRMER': 'Une livraison attend la confirmation de réception.',
        'VENTES_BLOQUEES': 'Les sorties de la bande NGO-005 sont bloquées par le vétérinaire.',
        'RAPPEL_FISCAL': "Votre chiffre d'affaires approche le seuil de l'impôt synthétique.",
        'FEU_ROUGE': 'Feu rouge sur EST-007 : 2,5 % de morts en un jour.',
        'FERME_SANS_SAISIE': 'Des fermes n’ont rien envoyé depuis 3 jours.',
        'DEUX_VERSIONS': 'Deux versions d’une même journée sont à trancher.',
        'ACTION_RETARD': 'Une action de votre plan est en retard.',
        'VISITE_DEMAIN': 'Votre agent passe demain.',
        'LOT_EN_ROUTE': 'Un lot est en route vers votre quai.',
        'LOT_DECIDE': 'Le lot gardé à part a été décidé.',
        'SIGNALEMENT': 'Nouveau signalement d’un éleveur.',
        'ALERTE_SANITAIRE': 'Nouvelle alerte sanitaire dans votre périmètre.',
        'PARAMETRE_A_APPROUVER': 'Une modification de réglage attend votre validation.',
    }.get(type_, 'Notification de démonstration.')


def _num(jeu, type_, prefixe, annee):
    from app.services.numerotation import generer_numero
    n = jeu.compteurs.get((type_, prefixe, annee), 0) + 1
    jeu.compteurs[(type_, prefixe, annee)] = n
    from app.models.compteur import Compteur
    c = Compteur.query.filter_by(type=type_, prefixe=prefixe, annee=annee).first()
    if c is not None:
        c.dernier_numero = n
    return f'{prefixe}-{annee}-{n:06d}'


# ── Point d'entrée ────────────────────────────────────────────────────────

def _etape(nom, _t=[None]):
    import sys
    import time as _time
    maintenant_ = _time.perf_counter()
    if _t[0] is not None:
        print(f'  … {nom} ({maintenant_ - _t[0]:.1f} s)', file=sys.stderr, flush=True)
    _t[0] = maintenant_


def generer(mot_de_passe, adresse=None, aujourdhui=None):
    """Remplit une base de démonstration NEUVE. Renvoie les volumes créés."""
    verifier_base()
    _etape('début')
    jeu = _Jeu(aujourdhui or date.today(), mot_de_passe, adresse)
    tables = {t.name: t for t in db.metadata.sorted_tables}
    provinces, localites, p, cal, ops = _referentiels(jeu)
    u = _comptes(jeu, provinces, ops)
    _etape('u = _comptes(jeu, provinces, o')
    fermes = _fermes(jeu, provinces, localites, u)
    # Les bâtiments sont insérés d'abord : les bandes ont besoin de leurs identifiants
    _inserer_partiel(jeu, tables, ['ferme', 'ferme_statut_historique', 'position_ferme', 'ferme_infrastructure', 'batiment'])
    _bandes(jeu, fermes, p, cal, ops, u)
    _etape('_bandes(jeu, fermes, p, cal, o')
    _receptions(jeu, u, ops)
    _reglage_chiffre_eleveur(jeu)
    _argent(jeu, fermes, u)
    _achats(jeu, fermes, p, u)
    _visites(jeu, fermes, u)
    _etape('_visites(jeu, fermes, u)')
    _inserer_partiel(jeu, tables, [n for n in ORDRE if n not in ('ferme', 'ferme_statut_historique', 'position_ferme',
                                                                  'ferme_infrastructure', 'batiment')])
    _compteurs(jeu)
    _sequences()
    _etape('_sequences()')
    db.session.expire_all()
    _present(jeu, u, p, ops)
    _etape('_present(jeu, u, p, ops)')
    _compteurs(jeu)
    db.session.flush()
    v = dict(jeu.volumes)
    v['utilisateur'] = len(u)
    v['bande_chair'] = sum(1 for b in jeu.t.get('_bande_resume', []) if not b.get('ponte'))
    v['bande_ponte'] = sum(1 for b in jeu.t.get('_bande_resume', []) if b.get('ponte'))
    return v


def _inserer_partiel(jeu, tables, noms):
    global ORDRE
    complet = ORDRE
    try:
        ORDRE = [n for n in complet if n in noms]
        _inserer(jeu, tables)
    finally:
        ORDRE = complet
