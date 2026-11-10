"""Lot F — œufs d'une bande de ponte : ramassage dans la saisie du jour, stock en plateaux, taux de ponte, chute de ponte,
ventes (recettes de Mon argent), réforme. Case vide ≠ zéro : une saisie de ponte sans œufs notés est refusée."""
from datetime import date, timedelta

from app import db, indicateurs as ind
from app.models.bande import Bande, StatutBande
from app.models.oeufs import VenteOeufs
from app.services import parametres
from app.services.numerotation import generer_numero


class RegleOeufs(Exception):
    pass


def par_plateau():
    return max(1, int(parametres.obtenir('ponte.oeufs_par_plateau', 30)))


def plateaux(n):
    """(plateaux, reste) pour n œufs."""
    p = par_plateau()
    return (n // p, n % p) if n and n > 0 else (0, 0)


def ramasses(bande, jusqu_a=None):
    return sum((s.oeufs_ramasses or 0) - (s.oeufs_casses or 0) for s in bande.saisies if jusqu_a is None or s.date <= jusqu_a)


def vendus(bande, jusqu_a=None):
    q = VenteOeufs.query.filter_by(bande_id=bande.id).filter(VenteOeufs.archive_le.is_(None))
    if jusqu_a is not None:
        q = q.filter(VenteOeufs.date <= jusqu_a)
    return sum(v.oeufs for v in q)


def stock(bande):
    """Œufs en stock (ramassés − cassés − vendus), jamais négatif."""
    return max(0, ramasses(bande) - vendus(bande))


def taux_du_jour(bande, jour=None):
    jour = jour or date.today()
    s = ind.saisie_du(bande, jour)
    if s is None or s.oeufs_ramasses is None:
        return None
    present = ind.calculer(bande, jour)['effectif_present'] or 0
    return round(100 * s.oeufs_ramasses / present, 1) if present else None


def taux_moyen(bande, fin, jours=7):
    """Taux de ponte moyen sur `jours` jours finissant à `fin` ; None si aucune saisie d'œufs."""
    valeurs = []
    for i in range(jours):
        t = taux_du_jour(bande, fin - timedelta(days=i))
        if t is not None:
            valeurs.append(t)
    return round(sum(valeurs) / len(valeurs), 1) if valeurs else None


def chute(bande, jour=None):
    """Baisse (%) entre les 7 jours précédents et les 7 derniers, si elle dépasse le seuil ; sinon None."""
    jour = jour or date.today()
    recent, avant = taux_moyen(bande, jour), taux_moyen(bande, jour - timedelta(days=7))
    if recent is None or not avant:
        return None
    baisse = round(100 * (avant - recent) / avant)
    return baisse if baisse >= int(parametres.obtenir('ponte.chute_pct', 15)) else None


def situation(bande):
    p, r = plateaux(stock(bande))
    return {'stock': stock(bande), 'plateaux': p, 'reste': r, 'taux': taux_du_jour(bande), 'taux_7j': taux_moyen(bande, date.today()),
            'chute': chute(bande), 'ventes': VenteOeufs.query.filter_by(bande_id=bande.id).filter(VenteOeufs.archive_le.is_(None)).order_by(VenteOeufs.date.desc()).limit(30).all()}


def bandes_de_ponte(fermes):
    ids = [f.id for f in fermes]
    return (Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS, Bande.type_production == 'PONTE')
            .order_by(Bande.date_mise_en_place.desc()).all()) if ids else []


def vendre(bande, jour, plateaux_vendus, oeufs_unite, montant, acheteur, user):
    if not bande.ponte:
        raise RegleOeufs("Cette bande n'est pas une bande de ponte.")
    n = (plateaux_vendus or 0) * par_plateau() + (oeufs_unite or 0)
    if n <= 0:
        raise RegleOeufs("Indiquez le nombre de plateaux ou d'œufs vendus.")
    if n > stock(bande):
        raise RegleOeufs(f'Il n\'y a que {stock(bande)} œufs en stock.')
    if jour is None or jour > date.today():
        raise RegleOeufs('La date de la vente est aujourd\'hui ou avant.')
    from app.models import Profil
    v = VenteOeufs(numero_metier=generer_numero('VENTE_OEUFS', 'OEU', annuel=True), bande_id=bande.id, date=jour, oeufs=n,
                   montant_fcfa=int(montant) if montant else None, acheteur=(acheteur or '').strip()[:150] or None,
                   saisi_par_agent=user.profil == Profil.AGENT, cree_par=user.id)
    db.session.add(v)
    db.session.flush()
    from app.services.journal import enregistrer, Action
    enregistrer(Action.CREATION, table='vente_oeufs', enregistrement_id=v.id,
                detail=f'Vente d\'œufs {v.numero} · {bande.numero} · {n} œufs · {montant or "—"} FCFA ({user.nom_complet})')
    return v
