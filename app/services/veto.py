"""Lot 17 — le vétérinaire : gravité des signalements, diagnostics (contenu réservé), blocage des
sorties d'une bande, sorties reçues après un blocage, recherche de lots amont et aval."""
from datetime import timedelta

from app import db
from app.models import Profil
from app.models.base import maintenant
from app.utils.dates import en_utc
from app.models.veto import Diagnostic, BlocageSorties

MESSAGE_BLOCAGE = '⛔ Le vétérinaire a bloqué les ventes de cette bande'


class RegleVeto(Exception):
    pass


def _veto(user):
    if user.profil != Profil.VETO:
        raise RegleVeto('Réservé aux vétérinaires.')


# ── A. Gravité ──────────────────────────────────────────────────────────

def gravite(a):
    """1 à 4 : mortalité anormale 3, déclaration de 10 poulets ou plus 2, sinon 1 ; +1 sans réponse depuis 24 h."""
    from app.models.sante import OrigineAlerte, StatutAlerte
    if a.origine == OrigineAlerte.FEU_ROUGE:
        g = 3
    else:
        g = 2 if a.declaration is not None and (a.declaration.nombre_animaux or 0) >= 10 else 1
    if a.statut in StatutAlerte.OUVERTES and not a.reponses and maintenant() - en_utc(a.cree_le) > timedelta(hours=24):
        g += 1
    return g


def libelle_gravite(g):
    return 'grave' if g >= 4 else 'à voir vite' if g == 3 else 'à voir'


def trier_par_gravite(alertes):
    return sorted(alertes, key=lambda a: (-gravite(a), en_utc(a.cree_le)))


# ── B. Diagnostics ──────────────────────────────────────────────────────

def maladies():
    from app.models.liste_deroulante import ld_choices
    return [v for v, _ in ld_choices('maladies_suspectees')]


def peut_lire_diagnostic(user):
    return user.profil in (Profil.VETO, Profil.ADMIN)


def diagnostiquer(alerte, maladie, prelevement, observations, user):
    _veto(user)
    maladie = (maladie or '').strip()
    if not maladie:
        raise RegleVeto('Choisissez la maladie suspectée (ou « Autre »).')
    d = Diagnostic(alerte_id=alerte.id, maladie=maladie[:150], prelevement=bool(prelevement),
                   observations=(observations or '').strip()[:1000] or None, veto_id=user.id)
    db.session.add(d)
    db.session.flush()
    return d


# ── C. Blocage des sorties ──────────────────────────────────────────────

def blocage_actif(bande):
    if bande is None or bande.id is None:
        return None
    return BlocageSorties.query.filter_by(bande_id=bande.id, leve_le=None).first()


def bloquer(bande, motif, user, alerte=None):
    from app.models.bande import StatutBande
    _veto(user)
    if bande.statut != StatutBande.EN_COURS:
        raise RegleVeto('Seule une bande en cours peut être bloquée.')
    if blocage_actif(bande):
        raise RegleVeto('Les sorties de cette bande sont déjà bloquées.')
    if not (motif or '').strip():
        raise RegleVeto('Indiquez le motif du blocage.')
    b = BlocageSorties(bande_id=bande.id, ferme_id=bande.ferme_id, alerte_id=alerte.id if alerte else None,
                       motif=motif.strip()[:300], pose_par=user.id)
    db.session.add(b)
    db.session.flush()
    return b


def lever(blocage, motif, user):
    _veto(user)                                   # seul un vétérinaire lève un blocage
    if not blocage.actif:
        raise RegleVeto('Ce blocage est déjà levé.')
    if not (motif or '').strip():
        raise RegleVeto('Indiquez le motif de la levée.')
    blocage.leve_le, blocage.leve_par, blocage.motif_levee = maintenant(), user.id, motif.strip()[:300]


def sortie_bloquee(sortie, blocage):
    """Sortie faite sans réseau avant de savoir, reçue après le blocage : gardée, mise de côté, à vérifier,
    sans lot ni QR."""
    sortie.blocage_id, sortie.a_verifier, sortie.mise_de_cote = blocage.id, True, True


def sorties_a_verifier(blocages):
    from app.models.bande import Sortie
    ids = [b.id for b in blocages]
    return (Sortie.query.filter(Sortie.blocage_id.in_(ids), Sortie.a_verifier.is_(True))
            .order_by(Sortie.cree_le).all()) if ids else []


def verifier_sortie(sortie, compter, user):
    """« Les poulets sont bien sortis » (comptée, toujours sans QR) ou « pas sortis » (reste de côté)."""
    _veto(user)
    if not sortie.a_verifier or sortie.blocage_id is None:
        raise RegleVeto('Cette sortie est déjà vérifiée.')
    sortie.a_verifier = False
    sortie.mise_de_cote = not compter


def blocages_visibles(user):
    from app.utils.permissions import filtre_perimetre
    return filtre_perimetre(BlocageSorties.query, utilisateur=user)


# ── D. Paramètres sanitaires ────────────────────────────────────────────

def parametres_sanitaires():
    from app.models import Parametre
    from app.services.approbations import SANITAIRES
    return [p for p in Parametre.query.order_by(Parametre.cle) if p.cle.startswith(SANITAIRES)]


# ── E. Recherche de lots, amont et aval ─────────────────────────────────

def _aval(bande):
    from app.services import tracabilite
    lignes = []
    for s in sorted(bande.sorties, key=lambda s: (s.date, s.cree_le)):
        lot = s.lot
        lignes.append({'date': s.date, 'nombre': s.nombre, 'destinataire': s.destinataire, 'poids_kg': s.poids_total_kg,
                       'lot': lot.numero if lot else None, 'lot_annule': bool(lot and lot.annule),
                       'lectures': tracabilite.lectures(lot).count() if lot else 0,
                       'mise_de_cote': s.mise_de_cote})
    return lignes


def _amont(bande):
    from app.models.bande import BandePoussins
    from app.models.intrant import Livraison, LivraisonLigne, StatutLivraison
    poussins = []
    for bp in BandePoussins.query.filter_by(bande_id=bande.id):
        l = db.session.get(LivraisonLigne, bp.livraison_ligne_id)
        if l is not None:
            poussins.append({'livraison': l.livraison.numero, 'date': l.livraison.date_livraison,
                             'fournisseur': l.livraison.fournisseur or '—', 'produit': l.produit.nom,
                             'quantite': bp.quantite})
    debut = bande.date_mise_en_place
    aliments = [{'livraison': l.livraison.numero, 'date': l.livraison.date_livraison, 'produit': l.produit.nom,
                 'quantite': l.quantite_recue}
                for l in LivraisonLigne.query.join(Livraison)
                .filter(Livraison.ferme_id == bande.ferme_id, Livraison.statut.in_(StatutLivraison.CONFIRMEES),
                        Livraison.date_livraison >= debut - timedelta(days=7))
                if l.produit.type != 'Poussins']
    from app.models.sante import Vaccination, Traitement
    soins = ([{'date': v.date, 'quoi': f'Vaccin {v.produit.nom} ({v.mode})'}
              for v in Vaccination.query.filter_by(bande_id=bande.id, annule=False)]
             + [{'date': t.date_debut, 'quoi': f'Traitement {t.produit.nom} : {t.motif}'}
                for t in Traitement.query.filter_by(bande_id=bande.id)])
    return {'poussins': poussins, 'aliments': aliments, 'soins': sorted(soins, key=lambda x: x['date'])}


def _fiche(bande):
    return {'bande': bande, 'ferme': bande.ferme, 'amont': _amont(bande), 'aval': _aval(bande),
            'blocage': blocage_actif(bande)}


def rechercher(texte, user):
    """Lot QR, bande, livraison ou fournisseur de poussins → fiches amont/aval des bandes concernées
    (périmètre de l'utilisateur). Inscrit au journal par l'appelant."""
    from app.models import Bande, Livraison
    from app.models.bande import BandePoussins
    from app.models.intrant import LivraisonLigne
    from app.models.tracabilite import LotTrace
    from app.utils.permissions import filtre_perimetre
    texte = (texte or '').strip()
    if len(texte) < 3:
        raise RegleVeto('Tapez au moins 3 caractères (numéro de lot, de bande, de livraison, ou fournisseur).')
    bandes_visibles = filtre_perimetre(Bande.query, utilisateur=user)
    trouve, quoi = [], None
    lot = LotTrace.query.filter((LotTrace.numero == texte) | (LotTrace.code == texte)).first()
    if lot is not None:
        quoi, trouve = f'Lot {lot.numero}', [lot.sortie.bande]
    elif (b := Bande.query.filter_by(numero_metier=texte).first()) is not None:
        quoi, trouve = f'Bande {b.numero}', [b]
    else:
        livs = Livraison.query.filter(Livraison.numero_metier == texte).all()
        if livs:
            quoi = f'Livraison {texte}'
        else:
            livs = Livraison.query.filter(Livraison.fournisseur.ilike(f'%{texte}%')).all()
            quoi = f'Fournisseur « {texte} »' if livs else None
        ids = [l.id for liv in livs for l in liv.lignes if l.produit.type == 'Poussins']
        if ids:
            trouve = (Bande.query.join(BandePoussins, BandePoussins.bande_id == Bande.id)
                      .filter(BandePoussins.livraison_ligne_id.in_(ids)).all())
        if livs and not trouve:
            quoi = (quoi or texte) + ' (aucune bande de poussins)'
    visibles = {b.id for b in bandes_visibles.filter(Bande.id.in_([b.id for b in trouve]))} if trouve else set()
    fiches = [_fiche(b) for b in dict.fromkeys(trouve) if b.id in visibles]
    return {'quoi': quoi, 'fiches': fiches, 'hors_perimetre': len(set(b.id for b in trouve) - visibles)}


def lignes_csv(resultat):
    """Une ligne par élément amont ou aval, pour l'export."""
    lignes = [['Bande', 'Ferme', 'Sens', 'Date', 'Quoi', 'Quantité', 'Lot', 'Lectures QR']]
    for f in resultat['fiches']:
        b, fe = f['bande'].numero, f'{f["ferme"].numero} {f["ferme"].nom}'
        for p in f['amont']['poussins']:
            lignes.append([b, fe, 'amont', p['date'].isoformat(), f'Poussins {p["produit"]} · {p["fournisseur"]} · {p["livraison"]}',
                           p['quantite'], '', ''])
        for a in f['amont']['aliments']:
            lignes.append([b, fe, 'amont', a['date'].isoformat(), f'{a["produit"]} · {a["livraison"]}', a['quantite'], '', ''])
        for s in f['amont']['soins']:
            lignes.append([b, fe, 'amont', s['date'].isoformat(), s['quoi'], '', '', ''])
        for s in f['aval']:
            lignes.append([b, fe, 'aval', s['date'].isoformat(), f'Sortie vers {s["destinataire"]}', s['nombre'],
                           s['lot'] or '', s['lectures']])
    return lignes
