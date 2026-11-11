"""Tableaux de bord, carte des fermes : rassemble les données visibles par
l'utilisateur. Les calculs restent dans app/indicateurs.py."""
from datetime import date, timedelta

from app import db, indicateurs
from app.models import Ferme, Province, Profil, Livraison, LivraisonLigne
from app.models.bande import Bande, StatutBande
from app.models.intrant import Produit, StatutLivraison, TYPE_POUSSINS, OrigineLivraison
from app.services import geo, parametres
from app.utils.permissions import filtre_perimetre


def lire_filtres(args):
    f = {k: (args.get(k) or '').strip() for k in ('province', 'cohorte', 'statut', 'du', 'au', 'programme')}
    for cle in ('du', 'au'):
        try:
            f[cle + '_date'] = date.fromisoformat(f[cle]) if f[cle] else None
        except ValueError:
            f[cle + '_date'] = None
    return f


def fermes_filtrees(user, f):
    q = filtre_perimetre(Ferme.query, utilisateur=user)
    if f.get('province', '').isdigit():
        q = q.filter(Ferme.province_id == int(f['province']))
    if f.get('cohorte') in ('1', '2'):
        q = q.filter(Ferme.cohorte == int(f['cohorte']))
    if f.get('statut'):
        q = q.filter(Ferme.statut == f['statut'])
    if f.get('programme') == 'programme':                       # lot A3 : Programme / Hors programme / Toutes
        q = q.filter(Ferme.programme_poufa.is_(True))
    elif f.get('programme') == 'hors':
        q = q.filter(Ferme.programme_poufa.is_(False))
    return q


def production(fermes):
    """Lot A3 : production réelle 12 mois, cible et atteinte du programme, hors programme compté à part."""
    p = indicateurs.production_fermes(fermes)
    au_programme = [fe for fe in fermes if fe.programme_poufa]
    hors = [fe for fe in fermes if not fe.programme_poufa]
    reelle_prog = sum(p[fe.id]['reelle'] for fe in au_programme)
    cible = sum(p[fe.id]['cible'] or 0 for fe in au_programme)
    reelle_hors = sum(p[fe.id]['reelle'] for fe in hors)
    objectif = indicateurs.objectif_national_t()
    atteinte = indicateurs.taux_atteinte(reelle_prog, cible)
    return {'reelle_programme': reelle_prog, 'cible': cible, 'atteinte': atteinte,
            'couleur': indicateurs.couleur_atteinte(atteinte),
            'fermes_hors': len(hors), 'reelle_hors': reelle_hors,
            'reelle_totale': reelle_prog + reelle_hors, 'objectif': objectif,
            'part_nationale': (reelle_prog + reelle_hors) * 100 / objectif if objectif else None,
            'carcasse': (reelle_prog + reelle_hors) * indicateurs.rendement_carcasse()}


def bandes_filtrees(user, f):
    ids = [i for (i,) in fermes_filtrees(user, f).with_entities(Ferme.id)]
    q = filtre_perimetre(Bande.query, utilisateur=user).filter(Bande.ferme_id.in_(ids))
    if f.get('au_date'):
        q = q.filter(Bande.date_mise_en_place <= f['au_date'])
    if f.get('du_date'):
        q = q.filter(db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= f['du_date']))
    return q


def tableau(user, f):
    fermes = fermes_filtrees(user, f).all()
    bandes = bandes_filtrees(user, f).all()
    total = indicateurs.synthese(bandes, f.get('du_date'), f.get('au_date'))
    total['fermes'] = len(fermes)
    total['production'] = production(fermes)
    total['fermes_actives'] = sum(1 for fe in fermes if fe.statut == 'Opérationnelle')
    par_province = []
    for p in Province.query.order_by(Province.ordre):
        bp = [b for b in bandes if b.ferme.province_id == p.id]
        fp = [fe for fe in fermes if fe.province_id == p.id]
        if not fp:
            continue
        s = indicateurs.synthese(bp, f.get('du_date'), f.get('au_date'))
        s.update({'province': p, 'fermes': len(fp), 'fermes_actives': sum(1 for fe in fp if fe.statut == 'Opérationnelle')})
        par_province.append(s)
    trace = tracabilite(user, f, fermes, bandes)
    for s in par_province:
        s['tracabilite'] = trace['par_province'].get(s['province'].id)
    return {'total': total, 'par_province': par_province, 'arrivee': mortalite_arrivee(user, f),
            'tracabilite': trace['total']}


def tracabilite(user, f, fermes, bandes):
    """Lot 19 (fonction 66) : traçabilité aval du périmètre et de la période (sorties à leur date, réceptions et
    scans à leur jour). Les refus d'un QR inconnu n'ont pas de province : comptés au total national seulement."""
    from app.models.tracabilite import Reception, Scan, LotTrace, ResultatScan
    from app.utils.dates import en_utc
    du, au = f.get('du_date'), f.get('au_date')

    def dans(jour):
        return (du is None or jour >= du) and (au is None or jour <= au)
    ids = {fe.id for fe in fermes}
    province_de = {fe.id: fe.province_id for fe in fermes}
    sorties = [s for b in bandes for s in b.sorties if dans(s.date)]
    receptions = [r for r in Reception.query.filter(Reception.ferme_id.in_(ids)) if dans(en_utc(r.recu_le).astimezone().date())] \
        if ids else []
    scans = [(sc, lot_ferme) for sc, lot_ferme in
             db.session.query(Scan, LotTrace.ferme_id).outerjoin(LotTrace, Scan.lot_id == LotTrace.id)
             .filter(Scan.resultat == ResultatScan.ROUGE)
             if dans(en_utc(sc.horodatage).astimezone().date()) and (lot_ferme in ids or (lot_ferme is None and user.est_national))]
    seuil = float(parametres.obtenir('reception.seuil_morts_pct', 2))
    total = indicateurs.tracabilite(sorties, receptions, len(scans), seuil)
    par_province = {}
    for pid in set(province_de.values()):
        fp = {i for i, p in province_de.items() if p == pid}
        par_province[pid] = indicateurs.tracabilite(
            [s for s in sorties if s.bande.ferme_id in fp], [r for r in receptions if r.ferme_id in fp],
            sum(1 for _, lf in scans if lf in fp), seuil)
    return {'total': total, 'par_province': par_province}


def mortalite_arrivee(user, f):
    """Taux de poussins morts à l'arrivée, par livraison et par fournisseur."""
    seuil = float(parametres.obtenir('intrants.seuil_mortalite_arrivee_pct', 2))
    ids = [i for (i,) in fermes_filtrees(user, f).with_entities(Ferme.id)]
    q = (LivraisonLigne.query.join(Livraison).join(Produit, LivraisonLigne.produit_id == Produit.id)
         .filter(Livraison.ferme_id.in_(ids), Livraison.statut.in_(StatutLivraison.CONFIRMEES),
                 Produit.type == TYPE_POUSSINS, Livraison.origine == OrigineLivraison.ETAT))
    if f.get('du_date'):
        q = q.filter(Livraison.date_livraison >= f['du_date'])
    if f.get('au_date'):
        q = q.filter(Livraison.date_livraison <= f['au_date'])
    lignes, fournisseurs = [], {}
    for l in q.order_by(Livraison.date_livraison.desc()).all():
        taux = indicateurs.mortalite_arrivee(l)
        lignes.append({'ligne': l, 'taux': taux, 'alerte': taux is not None and taux > seuil})
        fo = fournisseurs.setdefault(l.livraison.fournisseur or '—', {'fournisseur': l.livraison.fournisseur or '—',
                                                                      'recus': 0, 'morts': 0, 'livraisons': 0})
        fo['recus'] += l.quantite_recue or 0
        fo['morts'] += l.morts_arrivee or 0
        fo['livraisons'] += 1
    for fo in fournisseurs.values():
        fo['taux'] = fo['morts'] / fo['recus'] * 100 if fo['recus'] else None
    return {'seuil': seuil, 'lignes': lignes, 'fournisseurs': sorted(fournisseurs.values(), key=lambda x: -(x['taux'] or 0))}


def alertes_arrivee_recentes(user, jours=30):
    """Livraisons de poussins des 30 derniers jours au-delà du seuil (alerte DGE)."""
    f = {'du_date': date.today() - timedelta(days=jours)}
    return [x for x in mortalite_arrivee(user, f)['lignes'] if x['alerte']]


# ── Carte des fermes ────────────────────────────────────────────────────

def feu_de_la_ferme(ferme, bandes=None, valeurs=None):
    """Le feu le plus grave des bandes en cours de la ferme ; gris sans bande. `bandes` / `valeurs` : déjà calculées
    par l'appelant (infos_ferme), pour ne pas tout recalculer."""
    ordre = {'rouge': 3, 'orange': 2, 'vert': 1, 'gris': 0}
    pire = 'gris'
    if bandes is None:
        bandes = Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).all()
    for k, b in enumerate(bandes):
        c = indicateurs.feu(b, valeurs=valeurs[k] if valeurs else None)[0]
        if ordre[c] > ordre[pire]:
            pire = c
    return pire


INDICATEURS_CARTE = {'feu': 'Alertes (feu des bandes)', 'mortalite': 'Mortalité', 'regularite': 'Régularité des saisies',
                     'atteinte': 'Atteinte de la cible'}


def bandes_en_cours_par_ferme(fermes):
    """{ferme_id: [bandes en cours]} en une lecture (bandes légères, lot J) — pour infos_ferme sur beaucoup de fermes."""
    from app.services import bandes_legeres
    ids = [f.id for f in fermes]
    par_ferme = {i: [] for i in ids}
    if ids:
        for b in bandes_legeres.charger(Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS)
                                        .order_by(Bande.date_mise_en_place)):
            par_ferme[b.ferme_id].append(b)
    return par_ferme


def infos_ferme(ferme, production=None, bandes=None):
    """Lot E : ce que montre l'infobulle d'une ferme sur la carte, et sa couleur pour chaque indicateur.
    `bandes` : ses bandes en cours déjà chargées (bandes_en_cours_par_ferme), sinon lues ici."""
    if bandes is None:
        bandes = Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).all()
    valeurs = [indicateurs.calculer(b) for b in bandes]
    effectif = sum(v['effectif_present'] for v in valeurs)
    mis, morts = sum(v['mis_en_place'] for v in valeurs), sum(v['morts_cumules'] for v in valeurs)
    mortalite = morts * 100 / mis if mis else None
    jours = sum(v['jours_ecoules'] for v in valeurs)
    regularite = sum(v['jours_saisis'] for v in valeurs) * 100 / jours if jours else None
    derniere = max((s.date for b in bandes for s in b.saisies), default=None)
    pr = (production or {}).get(ferme.id) or {}
    feu = feu_de_la_ferme(ferme, bandes, valeurs)
    couleurs = {
        'feu': feu,
        'mortalite': 'gris' if mortalite is None else 'vert' if mortalite < 3 else 'orange' if mortalite <= 5 else 'rouge',
        'regularite': 'gris' if regularite is None else 'vert' if regularite >= 90 else 'orange' if regularite >= 70 else 'rouge',
        'atteinte': pr.get('couleur') or 'gris'}
    return {'effectif': effectif, 'mortalite': mortalite, 'regularite': regularite, 'derniere_saisie': derniere,
            'atteinte': pr.get('atteinte'), 'alerte': feu == 'rouge', 'couleurs': couleurs}


def carte(user, province_id=None, largeur=640, hauteur=560, marge=12, programme=None, indicateur='feu',
          details=False):
    contours = geo.contours()
    provinces = {p.code: p for p in Province.query}
    codes = [p.code for p in provinces.values() if province_id is None or p.id == province_id]
    fermes = filtre_perimetre(Ferme.query, utilisateur=user)
    if province_id:
        fermes = fermes.filter(Ferme.province_id == province_id)
    if programme in ('programme', 'hors'):                          # lot A3
        fermes = fermes.filter(Ferme.programme_poufa.is_(programme == 'programme'))
    toutes = fermes.all()
    fermes = [fe for fe in toutes if fe.a_une_position]
    a_localiser = [fe for fe in toutes if not fe.a_une_position]
    a_verifier = [fe for fe in toutes if fe.position_a_verifier]
    xs = [pt[0] for c in codes for a in contours.get(c, []) for pt in a]
    ys = [pt[1] for c in codes for a in contours.get(c, []) for pt in a]
    if not xs:
        return None
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    echelle = min((largeur - 2 * marge) / (x1 - x0), (hauteur - 2 * marge) / (y1 - y0))
    dx = (largeur - (x1 - x0) * echelle) / 2
    dy = (hauteur - (y1 - y0) * echelle) / 2

    def proj(x, y):
        return round(dx + (x - x0) * echelle, 1), round(dy + (y1 - y) * echelle, 1)

    formes = []
    for c in codes:
        chemins = ['M' + ' L'.join(f'{a},{b}' for a, b in (proj(x, y) for x, y in anneau)) + ' Z'
                   for anneau in contours.get(c, [])]
        formes.append({'province': provinces[c], 'chemins': chemins})
    points = []
    production = indicateurs.production_fermes(fermes) if details else None
    en_cours = bandes_en_cours_par_ferme(fermes) if details else {}
    from app.services import positions
    for fe in fermes:
        x, y = proj(fe.longitude, fe.latitude)
        if -20 <= x <= largeur + 20 and -20 <= y <= hauteur + 20:
            point = {'ferme': fe, 'x': x, 'y': y}
            if details:                                     # lot E : infobulle et indicateur au choix
                point['infos'] = infos_ferme(fe, production, en_cours.get(fe.id))
                point['feu'] = point['infos']['couleurs'].get(indicateur, point['infos']['couleurs']['feu'])
                point['approximative'] = positions.approximative(fe)
            else:
                point['feu'] = feu_de_la_ferme(fe)
            points.append(point)
    # Le plus grave dessiné en dernier : il reste visible quand deux fermes se superposent
    points.sort(key=lambda p: ('gris', 'vert', 'orange', 'rouge').index(p['feu']))
    # Lot V : cadre réellement occupé par les contours (viewBox sans marge vide autour du pays)
    cadre = (round(dx - marge, 1), round(dy - marge, 1), round((x1 - x0) * echelle + 2 * marge, 1), round((y1 - y0) * echelle + 2 * marge, 1))
    return {'largeur': largeur, 'hauteur': hauteur, 'formes': formes, 'points': points, 'cadre': cadre,
            'a_localiser': a_localiser, 'a_verifier': a_verifier}
