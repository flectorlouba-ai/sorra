"""Lot M — BCEG (fermes financées, avec l'accord de l'éleveur) et MAEDR (vue agrégée nationale, visa de diffusion des
rapports). La BCEG voit l'économie des fermes consentantes seulement ; le MAEDR ne voit que des agrégats et vise les rapports
soumis par la DGE. Tout au journal."""
from datetime import date, timedelta

from app import db, indicateurs as ind
from app.models import Ferme, Profil, Province
from app.models.base import maintenant
from app.models.rapport import Rapport, TypeRapport
from app.services.journal import enregistrer, Action as J
from app.utils.permissions import filtre_perimetre


class RegleMaedr(Exception):
    pass


# ── BCEG ──────────────────────────────────────────────────────────────────

def fermes_bceg(user):
    """Fermes financées avec accord en cours (périmètre du profil BCEG)."""
    return filtre_perimetre(Ferme.query, utilisateur=user).order_by(Ferme.numero_metier).all()


def situation_bceg(user):
    from app.models.bande import Bande, StatutBande
    from app.services import argent, bilan, pilotage
    fermes = fermes_bceg(user)
    financees = Ferme.query.filter(Ferme.financee_bceg.is_(True)).count()
    production = ind.production_fermes(fermes)
    lignes = []
    tot_rec = tot_dep = 0
    for f in fermes:
        i = pilotage.infos_ferme(f, production)
        b = bilan.bilan([f])
        tot_rec += b['recettes']; tot_dep += b['depenses']
        bande = Bande.query.filter_by(ferme_id=f.id, statut=StatutBande.EN_COURS).order_by(Bande.date_mise_en_place.desc()).first()
        lignes.append({'ferme': f, 'infos': i, 'bande': bande, 'recettes': b['recettes'], 'depenses': b['depenses'], 'benefice': b['benefice'],
                       'marge': b['marge'], 'production': production.get(f.id)})
    return {'fermes': fermes, 'financees': financees, 'lignes': lignes, 'recettes': tot_rec, 'depenses': tot_dep, 'benefice': tot_rec - tot_dep}


# ── MAEDR ─────────────────────────────────────────────────────────────────

def agregats_maedr():
    """Par province : fermes, bandes en cours, production 12 mois, cible, atteinte, mortalité — jamais une ferme nommée."""
    from app.models.bande import Bande, StatutBande
    fermes = Ferme.query.filter(Ferme.archive_le.is_(None)).all()
    lignes = []
    for p in Province.query.order_by(Province.ordre):
        fs = [f for f in fermes if f.province_id == p.id]
        if not fs:
            continue
        ids = [f.id for f in fs]
        bandes = Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS).all()
        part = ind.participation(fs)
        mv = ind.mortalite_viabilite(bandes)
        lignes.append({'province': p, 'fermes': len(fs), 'actives': sum(1 for f in fs if f.statut == 'Opérationnelle'), 'bandes': len(bandes),
                       'production': part['reelle'], 'cible': part['cible'], 'atteinte': part['atteinte'], 'mortalite': mv['mortalite']})
    return lignes


def rapports_a_viser():
    return Rapport.query.filter(Rapport.diffusion == 'SOUMIS').order_by(Rapport.soumis_le).all()


def rapports_diffusables():
    return Rapport.query.filter(Rapport.diffusion.in_(('SOUMIS', 'VALIDE', 'REFUSE'))).order_by(Rapport.soumis_le.desc()).limit(200).all()


def soumettre(rapport, user):
    if user.profil not in (Profil.DGE, Profil.ADMIN):
        raise RegleMaedr('Seule la DGE soumet un rapport au visa du MAEDR.')
    if rapport.type not in (TypeRapport.NATIONAL, TypeRapport.PROVINCE):
        raise RegleMaedr('Seuls les rapports nationaux et provinciaux (agrégés) se soumettent au MAEDR.')
    if rapport.diffusion == 'VALIDE':
        raise RegleMaedr('Ce rapport est déjà visé.')
    rapport.diffusion, rapport.soumis_le, rapport.soumis_par = 'SOUMIS', maintenant(), user.id
    rapport.vise_le = rapport.vise_par = rapport.motif_visa = None
    enregistrer(J.MODIFICATION, table='rapport', enregistrement_id=rapport.id, detail=f'Rapport {rapport.periode} {rapport.libelle_type} soumis au visa du MAEDR ({user.nom_complet})')


def viser(rapport, user, valider, motif=None):
    if user.profil != Profil.MAEDR:
        raise RegleMaedr('Seul le MAEDR vise la diffusion.')
    if rapport.diffusion != 'SOUMIS':
        raise RegleMaedr("Ce rapport n'est pas soumis au visa.")
    if not valider and not (motif or '').strip():
        raise RegleMaedr('Indiquez le motif du refus.')
    rapport.diffusion = 'VALIDE' if valider else 'REFUSE'
    rapport.vise_le, rapport.vise_par, rapport.motif_visa = maintenant(), user.id, (motif or '').strip()[:300] or None
    enregistrer(J.APPROBATION if valider else J.REFUS, table='rapport', enregistrement_id=rapport.id,
                detail=f'Visa MAEDR : rapport {rapport.periode} {rapport.libelle_type} {"validé pour diffusion" if valider else "refusé"} ({user.nom_complet})' + (f' — {motif}' if motif else ''))


def n_a_viser():
    return Rapport.query.filter(Rapport.diffusion == 'SOUMIS').count()
