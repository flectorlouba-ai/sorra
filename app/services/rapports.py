"""Lot D — rapports standards gardés en PDF : bilan de bande (enrichi), rapport mensuel de ferme, rapport mensuel
d'agent, rapport national / provincial (lot 18 complété). Chaque PDF est écrit dans instance/rapports/, enregistré
dans la table `rapport` et au journal. Les calculs viennent de app/indicateurs.py et des services existants."""
import os
from datetime import date, timedelta

from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, Spacer

from app import db, indicateurs as ind
from app.models import Ferme, Profil, Province, Utilisateur
from app.models.action import Action
from app.models.bande import Bande, StatutBande
from app.models.rapport import Rapport, TypeRapport
from app.services import rapports_pdf as pdf
from app.services.journal import enregistrer, Action as J
from app.utils.nombres import quantite
from app.utils.permissions import filtre_perimetre

_q = pdf._q


def _mois(mois):
    annee, m = (int(x) for x in mois.split('-'))
    du = date(annee, m, 1)
    au = (du.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return du, au


def _garder(contenu, nom, user, automatique=False, **cibles):
    from app.services.dge import dossier_rapports
    with open(os.path.join(dossier_rapports(), nom), 'wb') as f:
        f.write(contenu)
    r = Rapport(fichier=nom, genere_par=user.id if user else None, automatique=automatique,
                pages=contenu.count(b'/Type /Page') - contenu.count(b'/Type /Pages') or None, **cibles)
    db.session.add(r)
    db.session.flush()
    enregistrer(J.EXPORT, table='rapport', enregistrement_id=r.id,
                detail=f'Rapport {r.libelle_type.lower()} {r.periode} · {r.cible} généré'
                       + (' automatiquement' if automatique else f' par {user.nom_complet}'))
    return r


def lire(rapport):
    from app.services.dge import dossier_rapports
    with open(os.path.join(dossier_rapports(), rapport.fichier), 'rb') as f:
        return f.read()


# ── A. Bilan de bande ───────────────────────────────────────────────────

def contenu_bilan_bande(bande, financier=True):
    """PDF du bilan d'une bande clôturée : identité, effectifs, indicateurs, courbe, intrants par article et origine,
    vaccins et traitements, sorties et lots, économie (jamais pour le vétérinaire), visites et biosécurité."""
    from app.services import argent, intrants, sante
    from app.models.sante import Vaccination, Traitement
    from app.models.visite import Visite, StatutVisite
    b = bande.bilan or ind.bilan(bande)
    f = bande.ferme
    fin = bande.date_cloture or date.today()
    el = [Paragraph(f'Bilan de la bande {bande.numero}', pdf.TITRE),
          Paragraph(f'{f.nom} ({f.numero}) · {f.localite.nom}, {f.province.nom} · bâtiment {bande.batiment.code} · '
                    f'{bande.libelle_type}{(" · souche " + bande.souche) if bande.souche else ""} · poussins : '
                    f'{bande.origine_poussins or "origine non renseignée"} · du {bande.date_mise_en_place:%d/%m/%Y} au '
                    f'{fin:%d/%m/%Y} ({b.get("duree_jours", "—")} jours)'
                    + (' · indicateurs partiels (rattrapage)' if b.get('partiels') else ''), pdf.SOUS),
          Paragraph('Effectifs', pdf.SECTION),
          pdf._table([['Mis en place', 'Morts', 'Sortis', 'Mortalité', 'Viabilité'],
                      [quantite(b.get('mis_en_place')), quantite(b.get('morts')), quantite(b.get('sortis')),
                       _q(b.get('mortalite'), 2, ' %'), _q(b.get('viabilite'), 2, ' %')]], [3.5 * cm] * 5),
          Paragraph('Indicateurs', pdf.SECTION),
          pdf._table([['Poids moyen de sortie', 'GMQ', 'Indice de consommation', 'Poids vif produit', 'Aliment'],
                      ['sans objet' if bande.ponte else _q(b.get('poids_moyen_sortie_kg'), 3, ' kg'),
                       'sans objet' if bande.ponte else _q(b.get('gmq'), 1, ' g/j'),
                       'sans objet' if bande.ponte else _q(b.get('indice_consommation'), 2) + (' (incomplet)' if b.get('incomplet') else ''),
                       _q(b.get('poids_vif_produit_kg'), 1, ' kg'), _q(b.get('aliment_kg'), 1, ' kg')]], [3.5 * cm] * 5)]
    # Courbe de croissance vs référence (en tableau : pesées réelles et poids attendu)
    if bande.pesees and not bande.ponte:
        el += [Paragraph('Croissance : pesées et courbe de référence', pdf.SECTION),
               pdf._table([['Jour', 'Pesée (g)', 'Attendu (g)', 'Écart']] + [
                   [str(ind.age(bande, p.date)), quantite(round(p.poids_moyen_g)), quantite(round(ind.poids_attendu(ind.age(bande, p.date)))),
                    f'{round(p.poids_moyen_g - ind.poids_attendu(ind.age(bande, p.date))):+d} g'] for p in bande.pesees])]
    # Intrants consommés par article et origine (Programme d'abord, lot A2)
    stock = {s['produit'].id: s for s in intrants.stock_ferme(f)}
    conso = {}
    for s in bande.saisies:
        for a in s.aliments:
            c = conso.setdefault(a.produit_id, {'produit': a.produit, 'quantite': 0.0})
            c['quantite'] += a.sacs
    for v in Vaccination.query.filter_by(bande_id=bande.id, annule=False).filter(Vaccination.archive_le.is_(None)):
        conso.setdefault(v.produit_id, {'produit': v.produit, 'quantite': 0.0})['quantite'] += v.quantite or 0
    traitements = Traitement.query.filter_by(bande_id=bande.id).filter(Traitement.archive_le.is_(None)).all()
    for t in traitements:
        conso.setdefault(t.produit_id, {'produit': t.produit, 'quantite': 0.0})['quantite'] += t.quantite or 0
    lignes = []
    for pid, c in conso.items():
        s = stock.get(pid)
        prog, ext = intrants.imputer(s['etat'], c['quantite']) if s else (c['quantite'], 0)
        lignes.append([c['produit'].nom, quantite(c['quantite']), c['produit'].unite, quantite(prog), quantite(ext)])
    el += [Paragraph('Intrants consommés par article et origine', pdf.SECTION),
           pdf._table([['Article', 'Quantité', 'Unité', 'Programme', 'Externe']] + (lignes or [['—', '', '', '', '']]))]
    el += [Paragraph('Vaccins et traitements', pdf.SECTION),
           pdf._table([['Le', 'Quoi', 'Produit', 'Poulets']] +
                      [[v.date.strftime('%d/%m'), 'Vaccin', v.produit.nom, quantite(v.nombre_animaux)]
                       for v in Vaccination.query.filter_by(bande_id=bande.id, annule=False).filter(Vaccination.archive_le.is_(None)).order_by(Vaccination.date)] +
                      [[t.date_debut.strftime('%d/%m'), f'Traitement · {t.motif}', t.produit.nom, quantite(t.nombre_animaux)] for t in traitements]
                      or [['—', '', '', '']])]
    el += [Paragraph('Sorties et lots', pdf.SECTION),
           pdf._table([['Le', 'Motif', 'Destinataire', 'Poulets', 'Poids (kg)', 'Lot (QR)']] +
                      [[s.date.strftime('%d/%m'), s.motif, s.destinataire, quantite(s.nombre), quantite(s.poids_total_kg),
                        (s.lot.numero + (' · annulé' if s.lot.annule else '')) if getattr(s, 'lot', None) else '—']
                       for s in bande.sorties_comptees] or [['—', '', '', '', '', '']])]
    if financier:
        eco = b if 'chiffre_affaires' in b else argent.bilan_financier(bande)
        kg = b.get('poids_vif_produit_kg') or 0
        el += [Paragraph('Économie', pdf.SECTION),
               pdf._table([['Ventes', 'Dépenses', 'Marge', 'Coût au kg vif produit', "Aide de l'État"],
                           [_q(eco.get('chiffre_affaires'), 0, ' FCFA'), _q(eco.get('depenses'), 0, ' FCFA'),
                            _q(eco.get('marge'), 0, ' FCFA'), _q(eco['depenses'] / kg, 0, ' FCFA/kg') if kg and eco.get('depenses') is not None else '—',
                            _q(eco.get('aide_etat'), 0, ' FCFA')]], [3.5 * cm] * 5)]
    visites = (Visite.query.filter(Visite.ferme_id == f.id, Visite.statut == StatutVisite.FAITE,
                                   Visite.faite_le >= bande.date_mise_en_place, Visite.faite_le <= fin).order_by(Visite.faite_le).all())
    el += [Paragraph('Visites et biosécurité', pdf.SECTION),
           pdf._table([['Le', 'Agent', 'Objet', 'Biosécurité', 'Conseils']] +
                      [[v.faite_le.strftime('%d/%m'), v.agent.nom_complet, v.objet,
                        f'{v.score_biosecurite} %' if v.score_biosecurite is not None else '—', str(len(v.toutes_recommandations))]
                       for v in visites] or [['—', '', '', '', '']])]
    return pdf._document(el)


def bilan_bande(bande, user, automatique=False):
    """Génère (ou rend) le bilan gardé d'une bande clôturée."""
    existant = Rapport.query.filter_by(type=TypeRapport.BANDE, bande_id=bande.id).first()
    if existant is not None:
        return existant, False
    nom = f'bilan_{bande.numero}.pdf'
    r = _garder(contenu_bilan_bande(bande), nom, user, automatique, type=TypeRapport.BANDE,
                periode=(bande.date_cloture or date.today()).isoformat(), bande_id=bande.id, ferme_id=bande.ferme_id)
    return r, True


# ── B. Rapports mensuels : ferme, agent, national / provincial ─────────

def _actions_lignes(actions):
    return [[a.numero, a.intitule[:60], a.responsable.nom_complet, a.echeance.strftime('%d/%m'), a.libelle_etat] for a in actions] \
        or [['—', '', '', '', '']]


def contenu_ferme(ferme, mois, user):
    from app.models.visite import Visite, StatutVisite
    du, au = _mois(mois)
    bandes = Bande.query.filter(Bande.ferme_id == ferme.id, Bande.date_mise_en_place <= au,
                                db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= du)).all()
    s = ind.synthese(bandes, du, au)
    s['fermes'], s['fermes_actives'] = 1, int(ferme.statut == 'Opérationnelle')
    p = ind.production_fermes([ferme])[ferme.id]
    el = [Paragraph(f'Rapport mensuel de la ferme {ferme.numero} — {du:%m/%Y}', pdf.TITRE),
          Paragraph(f'{ferme.nom} · {ferme.localite.nom}, {ferme.province.nom} · {ferme.libelle_programme} · '
                    f'agent : {ferme.agent.nom_complet if ferme.agent else "—"} · du {du:%d/%m/%Y} au {au:%d/%m/%Y}', pdf.SOUS),
          pdf._chiffres(s),
          Paragraph('Bandes du mois', pdf.SECTION),
          pdf._table([['Bande', 'Type', 'Mise en place', 'Effectif', 'Mortalité', 'IC', 'État']] + [
              [b.numero, b.libelle_type, b.date_mise_en_place.strftime('%d/%m/%y'), quantite(ind.calculer(b)['effectif_present']),
               _q(ind.calculer(b)['mortalite'], 2, ' %'), 'sans objet' if b.ponte else _q(ind.calculer(b)['indice_consommation'], 2),
               b.libelle_statut] for b in bandes] or [['—', '', '', '', '', '', '']]),
          Paragraph('Objectif de production', pdf.SECTION),
          Paragraph(f'Produit sur 12 mois : {_q(p["reelle"], 1, " t")} de poids vif · cible : '
                    f'{_q(p["cible"], 1, " t") if p["cible"] else "— (hors programme)"} · atteinte : '
                    f'{_q(p["atteinte"], 0, " %") if p["atteinte"] is not None else "—"}', pdf.TEXTE)]
    visites = Visite.query.filter(Visite.ferme_id == ferme.id, Visite.statut == StatutVisite.FAITE,
                                  Visite.faite_le >= du, Visite.faite_le <= au).order_by(Visite.faite_le).all()
    el += [Paragraph('Visites et biosécurité', pdf.SECTION),
           pdf._table([['Le', 'Agent', 'Objet', 'Biosécurité']] +
                      [[v.faite_le.strftime('%d/%m'), v.agent.nom_complet, v.objet,
                        f'{v.score_biosecurite} %' if v.score_biosecurite is not None else '—'] for v in visites] or [['—', '', '', '']])]
    actions = Action.query.filter(Action.ferme_id == ferme.id, Action.archive_le.is_(None)).order_by(Action.echeance).all()
    el += [Paragraph("Plan d'actions de la ferme", pdf.SECTION),
           pdf._table([['N°', 'Action', 'Responsable', 'Échéance', 'État']] + _actions_lignes(actions))]
    return pdf._document(el)


def contenu_agent(agent, mois, user):
    from app.models.visite import Visite, StatutVisite
    from app.models.hors_ligne import ConflitHorsLigne, StatutVerification
    from app.models.sante import AlerteSanitaire, StatutAlerte
    du, au = _mois(mois)
    fermes = Ferme.query.filter_by(agent_id=agent.id).order_by(Ferme.numero_metier).all()
    ids = [f.id for f in fermes]
    bandes = Bande.query.filter(Bande.ferme_id.in_(ids), Bande.date_mise_en_place <= au,
                                db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= du)).all() if ids else []
    s = ind.synthese(bandes, du, au)
    s['fermes'], s['fermes_actives'] = len(fermes), sum(1 for x in fermes if x.statut == 'Opérationnelle')
    visites = Visite.query.filter(Visite.ferme_id.in_(ids)).all() if ids else []
    faites = [v for v in visites if v.statut == StatutVisite.FAITE and v.faite_le and du <= v.faite_le <= au]
    prevues = [v for v in visites if v.date_prevue and du <= v.date_prevue <= au]
    alertes = AlerteSanitaire.query.filter(AlerteSanitaire.ferme_id.in_(ids), AlerteSanitaire.cree_le >= du).count() if ids else 0
    ecarts = ConflitHorsLigne.query.filter(ConflitHorsLigne.ferme_id.in_(ids), ConflitHorsLigne.statut == StatutVerification.A_VERIFIER).count() if ids else 0
    el = [Paragraph(f"Rapport mensuel de l'agent {agent.nom_complet} — {du:%m/%Y}", pdf.TITRE),
          Paragraph(f'{", ".join(p.nom for p in agent.provinces) or "—"} · {len(fermes)} ferme(s) · du {du:%d/%m/%Y} au {au:%d/%m/%Y}', pdf.SOUS),
          pdf._chiffres(s),
          Paragraph('Suivi du mois', pdf.SECTION),
          pdf._table([['Visites faites', 'Visites prévues', 'Alertes', 'Écarts à arbitrer', 'Régularité des saisies'],
                      [str(len(faites)), str(len(prevues)), str(alertes), str(ecarts), _q(s['regularite'], 0, ' %')]], [3.5 * cm] * 5),
          Paragraph('Ses fermes', pdf.SECTION),
          pdf._table([['N°', 'Ferme', 'Bandes en cours', 'Mortalité', 'Dernière saisie']] + [
              [f.numero, f.nom[:30], str(sum(1 for b in bandes if b.ferme_id == f.id and b.statut == StatutBande.EN_COURS)),
               _q(ind.mortalite_viabilite([b for b in bandes if b.ferme_id == f.id])['mortalite'], 2, ' %'),
               max((x.date for b in bandes if b.ferme_id == f.id for x in b.saisies), default=None).strftime('%d/%m') if any(x for b in bandes if b.ferme_id == f.id for x in b.saisies) else '—']
              for f in fermes] or [['—', '', '', '', '']])]
    actions = Action.query.filter(Action.responsable_id == agent.id, Action.archive_le.is_(None)).order_by(Action.echeance).all()
    el += [Paragraph('Ses actions', pdf.SECTION), pdf._table([['N°', 'Action', 'Responsable', 'Échéance', 'État']] + _actions_lignes(actions))]
    return pdf._document(el)


def contenu_national(mois, user, province=None):
    """Rapport national (ou provincial) : lot 18 complété par la production vs objectif, l'atteinte par province et
    cohorte, la traçabilité (déjà présente) et les actions."""
    from app.routes.pilotage import contenu_mensuel, _alertes_confirmees
    from app.services import pilotage
    du, au = _mois(mois)
    f = {'du_date': du, 'au_date': au, 'province': str(province.id) if province else ''}
    donnees = pilotage.tableau(user, f)
    titre = f'Rapport mensuel {"de la province " + province.nom if province else "national"} — {du:%m/%Y}'
    fermes = pilotage.fermes_filtrees(user, f).all()
    prod = donnees['total']['production']
    el = [Paragraph('Production et objectif', pdf.SECTION),
          pdf._table([['Produit 12 mois (poids vif)', 'Objectif national', 'Part', 'Cible du programme', 'Atteinte', 'Équivalent carcasse'],
                      [_q(prod['reelle_totale'], 1, ' t'), _q(prod['objectif'], 0, ' t'), _q(prod['part_nationale'], 2, ' %'),
                       _q(prod['cible'], 1, ' t'), _q(prod['atteinte'], 0, ' %') if prod['atteinte'] is not None else '—', _q(prod['carcasse'], 1, ' t')]],
                     [3 * cm] * 6)]
    lignes = []
    for p in Province.query.order_by(Province.ordre):
        fp = [x for x in fermes if x.province_id == p.id]
        if not fp:
            continue
        part = ind.participation(fp)
        lignes.append([p.nom, str(len(fp)), _q(part['reelle'], 1), _q(part['cible'], 1) if part['cible'] else '—',
                       _q(part['atteinte'], 0, ' %') if part['atteinte'] is not None else '—'])
    for c, nom in (('1', 'Cohorte 1'), ('2', 'Cohorte 2'), (None, 'Programme, sans cohorte'), ('hors', 'Hors programme')):
        fc = [x for x in fermes if (not x.programme_poufa if c == 'hors' else x.programme_poufa and str(x.cohorte or '') == (c or ''))]
        if fc:
            part = ind.participation(fc)
            lignes.append([nom, str(len(fc)), _q(part['reelle'], 1), _q(part['cible'], 1) if part['cible'] else '—',
                           _q(part['atteinte'], 0, ' %') if part['atteinte'] is not None else '—'])
    el += [Paragraph('Atteinte par province et par cohorte', pdf.SECTION),
           pdf._table([['Niveau', 'Fermes', 'Produit (t)', 'Cible (t)', 'Atteinte']] + (lignes or [['—', '', '', '', '']]))]
    actions = Action.query.filter(Action.archive_le.is_(None)).order_by(Action.echeance).limit(40).all()
    if province:
        actions = [a for a in actions if a.province_id == province.id]
    el += [Paragraph("Plans d'actions", pdf.SECTION), pdf._table([['N°', 'Action', 'Responsable', 'Échéance', 'État']] + _actions_lignes(actions))]
    return pdf.rapport_periode(titre, f'Du {du:%d/%m/%Y} au {au:%d/%m/%Y}', donnees,
                               _alertes_confirmees(province.id if province else None), complements=el)


def generer(type_, periode, user, automatique=False, ferme=None, agent=None, province=None):
    """Génère et garde un rapport mensuel ; jamais deux fois le même."""
    cibles = {'type': type_, 'periode': periode, 'ferme_id': ferme.id if ferme else None,
              'agent_id': agent.id if agent else None, 'province_id': province.id if province else None}
    existant = Rapport.query.filter_by(**cibles).first()
    if existant is not None:
        return existant, False
    if type_ == TypeRapport.FERME:
        contenu, nom = contenu_ferme(ferme, periode, user), f'rapport_ferme_{ferme.numero}_{periode.replace("-", "")}.pdf'
    elif type_ == TypeRapport.AGENT:
        contenu, nom = contenu_agent(agent, periode, user), f'rapport_agent_{agent.identifiant}_{periode.replace("-", "")}.pdf'
    elif type_ == TypeRapport.PROVINCE:
        contenu, nom = contenu_national(periode, user, province), f'rapport_{province.code.lower()}_{periode.replace("-", "")}.pdf'
    else:
        contenu, nom = contenu_national(periode, user), f'rapport_national_{periode.replace("-", "")}.pdf'
    return _garder(contenu, nom, user, automatique, **cibles), True


def generer_mensuels(mois, user, automatique=True):
    """Le 1er du mois : national, chaque province avec des fermes, chaque ferme opérationnelle, chaque agent."""
    nouveaux = []
    for type_, kw in [(TypeRapport.NATIONAL, {})] + \
            [(TypeRapport.PROVINCE, {'province': p}) for p in Province.query if Ferme.query.filter_by(province_id=p.id).count()] + \
            [(TypeRapport.FERME, {'ferme': f}) for f in Ferme.query.filter(Ferme.statut == 'Opérationnelle')] + \
            [(TypeRapport.AGENT, {'agent': a}) for a in Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True)]:
        r, nouveau = generer(type_, mois, user, automatique, **kw)
        if nouveau:
            nouveaux.append(r)
    return nouveaux


def visibles(user):
    """Les rapports du périmètre : la DGE et l'ADMIN tout, l'agent ses fermes et les siens, l'éleveur ses bilans de bande."""
    q = Rapport.query
    if user.profil in (Profil.DGE, Profil.ADMIN, Profil.AUDITEUR):
        return q
    ids = [f.id for f in filtre_perimetre(Ferme.query, utilisateur=user)]
    cond = [Rapport.ferme_id.in_(ids)] if ids else []
    if user.profil == Profil.AGENT:
        cond.append(Rapport.agent_id == user.id)
    if user.profil == Profil.VETO:
        cond.append(Rapport.type.in_((TypeRapport.NATIONAL, TypeRapport.PROVINCE)))
    return q.filter(db.or_(*cond)) if cond else q.filter(db.false())
