"""Lot E (partie a) — positions des fermes : relevé GPS sur place, contrôle de province, correction à la main
(quatre yeux au-delà d'une distance), historique sans rien écraser, distance d'une visite à la ferme.
Voir docs/maquettes/maquettes_E.md."""
import math

from app import db
from app.models.base import maintenant
from app.models.position import PositionFerme, OriginePosition as O
from app.services import geo, parametres


class RegleGps(Exception):
    pass


def precision_max_m():
    return int(parametres.obtenir('gps.precision_max_m', 30))


def distance_visite_m():
    return float(str(parametres.obtenir('gps.distance_visite_km', 1)).replace(',', '.')) * 1000


def seuil_quatre_yeux_m():
    return float(str(parametres.obtenir('gps.correction_quatre_yeux_km', 1)).replace(',', '.')) * 1000


def distance_m(lat1, lon1, lat2, lon2):
    """Distance à vol d'oiseau en mètres (formule de haversine) — la même que sur le téléphone."""
    r = math.radians
    dla, dlo = r(lat2 - lat1), r(lon2 - lon1)
    a = math.sin(dla / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(dlo / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def texte_distance(m):
    return f'{round(m)} m' if m < 1000 else f'{m / 1000:.1f} km'.replace('.', ',')


def _lire_coordonnees(lat, lon):
    try:
        lat, lon = float(str(lat).replace(',', '.')), float(str(lon).replace(',', '.'))
    except (TypeError, ValueError):
        raise RegleGps('Position illisible : écrivez la latitude et la longitude en chiffres.')
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise RegleGps('Position impossible : vérifiez la latitude et la longitude.')
    return lat, lon


def controle_province(ferme, lat, lon):
    """{'ok', 'distance_km', 'province_trouvee'} (tolérance de 5 km, contours existants), ou None hors contours."""
    return geo.verifier(lat, lon, ferme.province.code)


def _mettre_en_vigueur(ferme, pos):
    for ancienne in PositionFerme.query.filter_by(ferme_id=ferme.id, en_vigueur=True):
        ancienne.en_vigueur = False
    pos.en_vigueur = True
    ferme.latitude, ferme.longitude = pos.latitude, pos.longitude
    ferme.gps_precision_m, ferme.gps_date = pos.precision_m, pos.releve_le
    from app.models.ferme import SourcePosition
    ferme.gps_source = SourcePosition.GPS if pos.origine == O.GPS else SourcePosition.MANUELLE
    ferme.position_a_verifier = pos.a_verifier


def relever(ferme, lat, lon, precision, user, appareil=None, hors_ligne=False, garder_quand_meme=False, motif=None,
            releve_le=None):
    """Relevé GPS sur place. Refusé au-delà de la précision exigée ; hors de la province (au-delà de 5 km) : refusé,
    sauf « Garder quand même » avec un motif → la ferme passe « position à vérifier » chez la DGE.
    L'agent ne change jamais la province."""
    lat, lon = _lire_coordonnees(lat, lon)
    try:
        precision = int(round(float(precision)))
    except (TypeError, ValueError):
        raise RegleGps('Précision inconnue : relevez à nouveau.')
    if precision > precision_max_m():
        raise RegleGps(f'Position trop imprécise (± {precision} m) : il faut ± {precision_max_m()} m au plus.')
    c = controle_province(ferme, lat, lon)
    hors = c is not None and not c['ok']
    motif = (motif or '').strip()[:300] or None
    if hors and not garder_quand_meme:
        raise RegleGps(message_province(ferme, c))
    if hors and not motif:
        raise RegleGps('Indiquez pourquoi vous gardez cette position.')
    pos = PositionFerme(ferme_id=ferme.id, latitude=lat, longitude=lon, precision_m=precision,
                        releve_le=releve_le or maintenant(), auteur_id=user.id, appareil=(appareil or '')[:64] or None,
                        hors_ligne=bool(hors_ligne), origine=O.GPS, motif=motif,
                        province_trouvee=c['province_trouvee'] if c else None,
                        distance_province_km=c['distance_km'] if c else None, a_verifier=hors)
    db.session.add(pos)
    db.session.flush()
    _mettre_en_vigueur(ferme, pos)
    return pos


def message_province(ferme, c):
    from app.models import Province
    trouvee = Province.query.filter_by(code=c['province_trouvee']).first() if c.get('province_trouvee') else None
    ou = f'dans la province {trouvee.nom}' if trouvee else 'hors du Gabon'
    return (f'⚠️ Cette position est {ou} — la ferme est notée dans la province {ferme.province.nom} '
            f'({c["distance_km"]} km).')


def corriger_a_la_main(ferme, lat, lon, motif, user):
    """Correction à la main (coordonnées tapées) : motif obligatoire, ancienne position gardée ; au-delà du seuil,
    proposition aux quatre yeux (une autre personne, DGE ou ADMIN, l'applique). Rend ('appliquee' | 'proposee', objet)."""
    lat, lon = _lire_coordonnees(lat, lon)
    motif = (motif or '').strip()[:300]
    if not motif:
        raise RegleGps('Indiquez le motif de la correction.')
    ecart = distance_m(ferme.latitude, ferme.longitude, lat, lon) if ferme.a_une_position else None
    if ecart is not None and ecart > seuil_quatre_yeux_m():
        from app.services import approbations
        p = approbations.proposer('POSITION', f'position.{ferme.id}', f'Position de la ferme {ferme.numero}',
                                  f'{ferme.latitude:.5f}, {ferme.longitude:.5f}', f'{lat:.5f}, {lon:.5f}',
                                  {'ferme_id': str(ferme.id), 'latitude': lat, 'longitude': lon,
                                   'auteur_id': str(user.id)},
                                  f'{motif} (déplacement de {texte_distance(ecart)})', user)
        return 'proposee', p
    return 'appliquee', appliquer_correction(ferme, lat, lon, motif, user)


def appliquer_correction(ferme, lat, lon, motif, user):
    c = controle_province(ferme, lat, lon)
    pos = PositionFerme(ferme_id=ferme.id, latitude=lat, longitude=lon, precision_m=None, releve_le=maintenant(),
                        auteur_id=user.id if user else None, origine=O.MANUELLE, motif=motif,
                        province_trouvee=c['province_trouvee'] if c else None,
                        distance_province_km=c['distance_km'] if c else None, a_verifier=bool(c and not c['ok']))
    db.session.add(pos)
    db.session.flush()
    _mettre_en_vigueur(ferme, pos)
    return pos


def historique(ferme):
    return PositionFerme.query.filter_by(ferme_id=ferme.id).order_by(PositionFerme.releve_le.desc(),
                                                                     PositionFerme.id.desc()).all()


def approximative(ferme):
    """Position en pointillé sur la carte : reprise des fiches ou corrigée à la main."""
    pos = PositionFerme.query.filter_by(ferme_id=ferme.id, en_vigueur=True).first()
    return pos is not None and pos.origine in (O.REPRISE, O.MANUELLE)


# ── Visites ─────────────────────────────────────────────────────────────

def distance_visite(visite):
    """Distance (m) entre le point de la visite et la ferme, recalculée par le serveur ; None sans l'un des deux."""
    f = visite.ferme
    if visite.latitude is None or visite.longitude is None or not f.a_une_position:
        return None
    return round(distance_m(visite.latitude, visite.longitude, f.latitude, f.longitude))


def etat_visite(visite):
    """'confirmee' (à moins de la distance), 'eloignee', 'sans_position'."""
    if visite.distance_m is None:
        return 'sans_position'
    return 'confirmee' if visite.distance_m <= distance_visite_m() else 'eloignee'
