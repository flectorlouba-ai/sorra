"""Lot C3 — indicateurs clés par profil (5 à 8), dont 3 avec une courbe hebdomadaire sur 52 semaines.
Les formules sont dans app/indicateurs.py ; ce module choisit ce que chaque profil voit, dans son périmètre.
Une semaine sans donnée est un trou (None), jamais zéro. Le vétérinaire ne voit aucune donnée financière."""
from datetime import date, timedelta

from app import db, indicateurs as ind
from app.models import Ferme, Profil, Utilisateur
from app.models.bande import Bande, StatutBande
from app.utils.permissions import filtre_perimetre


def _carte(nom, valeur, sous=None, alerte=False):
    return {'nom': nom, 'valeur': valeur, 'sous': sous, 'alerte': alerte}


def _courbe(nom, unite, valeurs, couleur='bleu', decimales=1):
    sem = ind.semaines()
    points = [(s[0], v) for s, v in zip(sem, valeurs)]
    connues = [v for v in valeurs if v is not None]
    return {'nom': nom, 'unite': unite, 'points': points, 'couleur': couleur, 'decimales': decimales,
            'derniere': connues[-1] if connues else None, 'min': min(connues) if connues else None,
            'max': max(connues) if connues else None}


def _pct(v, n=1):
    return '—' if v is None else f'{v:.{n}f} %'.replace('.', ',')


def _nombre(v, n=0, unite=''):
    if v is None:
        return '—'
    texte = f'{v:,.{n}f}'.replace(',', ' ').replace('.', ',')
    return f'{texte}{unite}'


def _bandes(user, depuis_jours=365):
    debut = date.today() - timedelta(days=depuis_jours)
    return (filtre_perimetre(Bande.query, utilisateur=user)
            .filter(db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= debut)).all())


def _fermes(user):
    return filtre_perimetre(Ferme.query, utilisateur=user).all()


# ── Par profil ──────────────────────────────────────────────────────────

def eleveur(user):
    """Libellés = cahier de conformité (lot K) ; les cartes sont calculées sur la bande principale (la plus récente en
    cours) ; plusieurs bandes : une carte Viabilité par bâtiment en plus (la maquette est un minimum)."""
    bandes = _bandes(user)
    en_cours = sorted([b for b in bandes if b.statut == StatutBande.EN_COURS], key=lambda b: b.date_mise_en_place, reverse=True)
    fermes = _fermes(user)
    from app.services import argent
    mvts = argent.mouvements([f.id for f in fermes])
    ventes = [(m['date'], m['montant']) for m in mvts if m['signe'] > 0 and m['montant']]
    debut_mois = date.today().replace(day=1)
    gagne_mois = sum(m for d, m in ventes if d >= debut_mois)
    cartes = []
    if en_cours:
        b = en_cours[0]
        v = ind.calculer(b)
        cartes += [_carte(f'Mortalité de la bande {b.batiment.code}', _pct(v['mortalite'], 2), f'{b.numero}'),
                   _carte('Viabilité', _pct(v['viabilite'])),
                   _carte('Poids moyen', _nombre(v['poids_moyen_g'] / 1000, 2, ' kg') if v['poids_moyen_g'] else '—',
                          f'pesée J{v["age_pesee"]}' if v.get('age_pesee') is not None else 'pas encore pesée'),
                   _carte('Aliment consommé', _nombre(v['aliment_kg'], 0, ' kg'), f'{_nombre(v["sacs"], 0)} sacs'),
                   _carte('Indice de consommation', 'sans objet' if v['ponte'] else _nombre(v['indice_consommation'], 2))]
    else:
        cartes += [_carte('Mortalité de la bande', '—', 'aucune bande en cours'), _carte('Viabilité', '—'), _carte('Poids moyen', '—'),
                   _carte('Aliment consommé', '—'), _carte('Indice de consommation', '—')]
    p = ind.participation(fermes)
    cartes += [_carte('Gagné ce mois', _nombre(gagne_mois, 0, ' FCFA')),
               _carte('Part de ma cible annuelle', _pct(p['atteinte'], 0) if p['atteinte'] is not None else '—',
                      f'{_nombre(p["reelle"], 1, " t")} produites sur 12 mois')]
    for b in en_cours[1:]:
        v = ind.calculer(b)
        cartes.append(_carte(f'Viabilité · {b.batiment.code}', _pct(v['viabilite']), f'mortalité {_pct(v["mortalite"])}'))
    return {'cartes': cartes[:8], 'courbes': [
        _courbe('Mortalité de la bande (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Poids moyen (kg)', 'kg', [(x / 1000 if x is not None else None) for x in ind.serie_poids_hebdo(bandes)], 'bleu', 2),
        _courbe('Gagné par semaine (FCFA)', 'FCFA par semaine', ind.serie_somme_hebdo(ventes), 'vert', 0)]}


def agent(user):
    bandes = _bandes(user)
    fermes = _fermes(user)
    from app.services import sante
    from app.models.sante import AlerteSanitaire, StatutAlerte
    from app.models.hors_ligne import ConflitHorsLigne, StatutVerification
    from app.models.visite import Visite, StatutVisite
    ids = [f.id for f in fermes]
    alertes = sante.alertes_visibles(user).filter(AlerteSanitaire.statut.in_(StatutAlerte.OUVERTES)).count()
    ecarts = (ConflitHorsLigne.query.filter(ConflitHorsLigne.ferme_id.in_(ids),
                                            ConflitHorsLigne.statut == StatutVerification.A_VERIFIER).count()
              if ids else 0)
    visites = Visite.query.filter(Visite.ferme_id.in_(ids)).all() if ids else []
    faites = [v.faite_le for v in visites if v.statut == StatutVisite.FAITE]
    prevues = [v.date_prevue for v in visites if v.date_prevue]
    mv = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS])
    debut_mois = date.today().replace(day=1)
    regularite = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS]).get('regularite')
    from app.services import actions as services_actions
    retard = services_actions.n_en_retard(user)
    serie_reg = ind.serie_regularite_hebdo(bandes)
    reg = next((x for x in reversed(serie_reg) if x is not None), None) if serie_reg else None
    return {'cartes': [
        _carte('Mortalité de mes fermes', _pct(mv['mortalite'], 2), f'{mv["bandes"]} bande(s) en cours'),
        _carte('Régularité des saisies', _pct(reg, 0) if reg is not None else '—', 'semaine en cours'),
        _carte('Visites faites / prévues', f'{sum(1 for d in faites if d and d >= debut_mois)} / '
                                           f'{sum(1 for d in prevues if d >= debut_mois and d.month == debut_mois.month)}', 'ce mois'),
        _carte('Alertes ouvertes', str(alertes), alerte=alertes > 0),
        _carte('Écarts à arbitrer', str(ecarts), alerte=ecarts > 0),
        _carte('Mes actions en retard', str(retard), alerte=retard > 0),
        _carte('Mes fermes', str(len(fermes)))], 'courbes': [
        _courbe('Mortalité de mes fermes (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Régularité des saisies (%)', '% des jours', serie_reg, 'bleu', 0),
        _courbe('Visites par semaine', 'visites', ind.serie_compte_hebdo(faites, debut=min(prevues + faites) if (prevues + faites) else None), 'vert', 0)]}


def veterinaire(user):
    """Aucune donnée financière (règle du cahier)."""
    bandes = _bandes(user)
    from app.services import sante, veto
    from app.models.sante import AlerteSanitaire, StatutAlerte
    alertes_q = sante.alertes_visibles(user)
    toutes = alertes_q.all()
    delais = []
    for a in toutes:
        if a.reponses:
            delais.append((a.reponses[0].cree_le - a.cree_le).total_seconds() / 3600)
    bloquees = veto.blocages_visibles(user).filter_by(leve_le=None).count()
    en_retard = vaccins_en_retard(bandes)
    mv = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS])
    semaine = date.today() - timedelta(days=7)
    return {'cartes': [
        _carte('Alertes cette semaine', str(sum(1 for a in toutes if a.cree_le.date() >= semaine)),
               f'{sum(1 for a in toutes if a.statut in StatutAlerte.OUVERTES)} ouverte(s) en tout'),
        _carte('Mortalité de la zone', _pct(mv['mortalite'], 2), f'{mv["bandes"]} bande(s) en cours'),
        _carte('Vaccinations en retard', str(len(en_retard)), alerte=bool(en_retard)),
        _carte('Bandes bloquées', '—' if bloquees is None else str(bloquees)),
        _carte('Délai moyen de réponse', '—' if not delais else _nombre(sum(delais) / len(delais), 0, ' h'))],
        'courbes': [
        _courbe('Alertes par semaine', 'alertes', ind.serie_compte_hebdo([a.cree_le.date() for a in toutes]), 'rouge', 0),
        _courbe('Mortalité de la zone (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'orange', 2),
        _courbe('Vaccinations en retard', 'par semaine',
                ind.serie_compte_hebdo([d for _, d in en_retard],
                                       debut=min((b.date_mise_en_place for b in bandes), default=None)), 'rouge', 0)]}


def vaccins_en_retard(bandes):
    """[(bande, date prévue)] des étapes du calendrier non faites après la tolérance (lot 4)."""
    from app.services import sante
    resultat = []
    for b in bandes:
        if b.statut != StatutBande.EN_COURS:
            continue
        for v in sante.vaccins_de_la_bande(b):
            if v.get('etat') == 'retard':
                resultat.append((b, v.get('prevu')))
    return resultat


def dge(user):
    bandes = _bandes(user)
    fermes = _fermes(user)
    p = ind.participation(fermes)
    mv = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS])
    from app.models import Province
    provinces_80 = 0
    par_province = {}
    for f in fermes:
        par_province.setdefault(f.province_id, []).append(f)
    for pid, fs in par_province.items():
        a = ind.participation(fs)['atteinte']
        provinces_80 += 1 if a is not None and a >= 80 else 0
    from app.services import pilotage
    ecarts = len([1 for x in pilotage.ecarts_intrants(user)]) if hasattr(pilotage, 'ecarts_intrants') else None
    from app.models.tracabilite import LotTrace
    from app.models.bande import Sortie
    ids = [b.id for b in bandes]
    sorties = Sortie.query.filter(Sortie.bande_id.in_(ids)).count() if ids else 0
    lots = (db.session.query(LotTrace).join(Sortie, LotTrace.sortie_id == Sortie.id)
            .filter(Sortie.bande_id.in_(ids), LotTrace.annule.is_(False)).count()) if ids else 0
    # Libellés = cahier de conformité (lot K) ; la maquette est un minimum : l'équivalent carcasse reste en 7ᵉ
    return {'cartes': [
        _carte('Production / objectif', f'{_nombre(p["reelle"], 1, " t")} / {_nombre(p["cible"], 1, " t")}',
               f'{_pct(p["atteinte"], 0)} de l’objectif · {_pct(p["part_nationale"], 2)} du national'),
        _carte('Mortalité nationale', _pct(mv['mortalite'], 2), f'viabilité {_pct(mv["viabilite"], 2)}'),
        _carte('Élevages actifs', f'{sum(1 for f in fermes if f.statut == "Opérationnelle")} / {len(fermes)}', 'opérationnels / enrôlés'),
        _carte('Provinces ≥ 80 %', f'{provinces_80} / {len(par_province)}', 'de la cible'),
        _carte('Écarts sur intrants', '—' if ecarts is None else str(ecarts)),
        _carte('Traçabilité', _pct(100 * lots / sorties, 0) if sorties else '—', f'{lots} lot(s) avec QR sur {sorties} sortie(s)'),
        _carte('Équivalent carcasse', _nombre(p['carcasse'], 1, ' t'))], 'courbes': [
        _courbe('Production hebdomadaire (t)', 't par semaine', ind.serie_production_hebdo(bandes), 'bleu', 2),
        _courbe('Mortalité nationale (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Élevages actifs', 'avec au moins une saisie', ind.serie_fermes_actives_hebdo(bandes), 'vert', 0)]}


def administrateur(user):
    from app.models import JournalAudit
    from app.models.securite import Proposition
    from app.services.journal import Action
    depuis = date.today() - timedelta(weeks=52)
    journal = (JournalAudit.query.filter(JournalAudit.horodatage >= depuis).with_entities(
        JournalAudit.action, JournalAudit.horodatage).all())
    sensibles = (Action.PROPOSITION, Action.APPROBATION, Action.REFUS, Action.CORRECTION, Action.ARCHIVAGE,
                 Action.RESTAURATION, Action.BLOCAGE, Action.DEBLOCAGE, Action.CHANGEMENT_MDP)
    comptes = Utilisateur.query.all()
    actifs = [u for u in comptes if u.actif]
    attente = Proposition.query.filter_by(statut='EN_ATTENTE').count()
    echecs_7j = sum(1 for a, h in journal if a == Action.ECHEC_CONNEXION and h.date() >= date.today() - timedelta(days=7))
    profils = {}
    for u in actifs:
        profils[u.profil.libelle] = profils.get(u.profil.libelle, 0) + 1
    cree = [u.cree_le.date() for u in comptes if getattr(u, 'cree_le', None)]
    sem = ind.semaines()
    actifs_hebdo = [sum(1 for d in cree if d <= s[1]) or None for s in sem]
    from app.services import securite
    sessions = securite.ouvertes().count()
    # Libellés = cahier de conformité (lot K)
    return {'cartes': [
        _carte('Comptes actifs', str(len(actifs)), f'{len(comptes) - len(actifs)} désactivé(s)'),
        _carte('Profils', str(len(profils)), ' · '.join(f'{n} {k.split(" (")[0]}' for k, n in sorted(profils.items(), key=lambda x: -x[1])[:3])),
        _carte('Validations en attente', str(attente), alerte=attente > 0),
        _carte('Opérations sensibles', str(sum(1 for a, h in journal if a in sensibles and h.date() >= date.today() - timedelta(days=7))), '7 derniers jours'),
        _carte('Sessions ouvertes', str(sessions)),
        _carte('Échecs de connexion (7 jours)', str(echecs_7j), alerte=echecs_7j > 10)], 'courbes': [
        _courbe('Connexions par semaine', 'connexions', ind.serie_compte_hebdo([h.date() for a, h in journal if a == Action.CONNEXION], debut=depuis), 'bleu', 0),
        _courbe('Échecs de connexion', 'par semaine',
                ind.serie_compte_hebdo([h.date() for a, h in journal if a == Action.ECHEC_CONNEXION], debut=depuis), 'rouge', 0),
        _courbe('Opérations sensibles', 'par semaine',
                ind.serie_compte_hebdo([h.date() for a, h in journal if a in sensibles], debut=depuis), 'orange', 0)]}


def auditeur(user):
    """Lot K : tableau de bord d'audit — intégrité, entrées, exports, scans refusés (aucune donnée financière)."""
    from app.models import JournalAudit
    from app.models.tracabilite import Scan, ResultatScan
    from app.services.journal import Action, verifier_chaine
    depuis = date.today() - timedelta(weeks=52)
    journal = JournalAudit.query.filter(JournalAudit.horodatage >= depuis).with_entities(JournalAudit.action, JournalAudit.horodatage).all()
    try:
        intact, n, _ = verifier_chaine()
    except Exception:
        intact, n = None, len(journal)
    exports = [h.date() for a, h in journal if a == Action.EXPORT]
    refuses = [s.horodatage.date() for s in Scan.query.filter(Scan.resultat == ResultatScan.ROUGE, Scan.horodatage >= depuis)]
    return {'cartes': [
        _carte('Intégrité du journal', '—' if intact is None else ('✓ chaîne intacte' if intact else '⚠️ chaîne rompue'), alerte=intact is False),
        _carte('Entrées journalisées', _nombre(n, 0), '52 dernières semaines : ' + _nombre(len(journal), 0)),
        _carte('Exports', str(len(exports)), '52 semaines'),
        _carte('Scans refusés', str(len(refuses)), '52 semaines', alerte=bool(refuses))], 'courbes': [
        _courbe('Entrées par semaine', 'entrées', ind.serie_compte_hebdo([h.date() for a, h in journal], debut=depuis), 'bleu', 0),
        _courbe('Exports par semaine', 'exports', ind.serie_compte_hebdo(exports, debut=depuis), 'vert', 0),
        _courbe('Scans refusés', 'par semaine', ind.serie_compte_hebdo(refuses, debut=depuis), 'rouge', 0)]}


def bceg(user):
    """Lot M : la banque voit les fermes financées qui ont donné leur accord — effectifs, mortalité, recettes, bénéfice."""
    from app.services import maedr
    s = maedr.situation_bceg(user)
    bandes = _bandes(user)
    from app.services import argent
    mvts = argent.mouvements([f.id for f in s['fermes']]) if s['fermes'] else []
    ventes = [(m['date'], m['montant']) for m in mvts if m['signe'] > 0 and m['montant']]
    mv = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS])
    return {'cartes': [
        _carte('Fermes financées', str(s['financees'])),
        _carte('Avec accord de l’éleveur', str(len(s['fermes'])), 'les seules visibles ici'),
        _carte('Bandes en cours', str(mv['bandes'])),
        _carte('Mortalité', _pct(mv['mortalite'], 2)),
        _carte('Recettes 12 mois', _nombre(s['recettes'], 0, ' FCFA')),
        _carte('Bénéfice 12 mois', _nombre(s['benefice'], 0, ' FCFA'), alerte=s['benefice'] < 0)], 'courbes': [
        _courbe('Mortalité des fermes financées (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Recettes par semaine (FCFA)', 'FCFA', ind.serie_somme_hebdo(ventes), 'vert', 0),
        _courbe('Production hebdomadaire (t)', 't par semaine', ind.serie_production_hebdo(bandes), 'bleu', 2)]}


def maedr_(user):
    """Lot M : le ministère ne voit que des agrégats nationaux et les rapports à viser."""
    from app.services import maedr
    from app.models.bande import Bande
    lignes = maedr.agregats_maedr()
    bandes = Bande.query.filter(db.or_(Bande.date_cloture.is_(None), Bande.date_cloture >= date.today() - timedelta(days=365))).all()
    mv = ind.mortalite_viabilite([b for b in bandes if b.statut == StatutBande.EN_COURS])
    prod = sum(l['production'] or 0 for l in lignes)
    cible = sum(l['cible'] or 0 for l in lignes)
    return {'cartes': [
        _carte('Production nationale 12 mois', _nombre(prod, 1, ' t'), f'cible {_nombre(cible, 1, " t")}'),
        _carte('Atteinte de la cible', _pct(100 * prod / cible, 0) if cible else '—'),
        _carte('Provinces couvertes', str(len(lignes))),
        _carte('Élevages', str(sum(l['fermes'] for l in lignes)), f'{sum(l["actives"] for l in lignes)} opérationnels'),
        _carte('Mortalité nationale', _pct(mv['mortalite'], 2)),
        _carte('Rapports à viser', str(maedr.n_a_viser()), alerte=maedr.n_a_viser() > 0)], 'courbes': [
        _courbe('Production hebdomadaire (t)', 't par semaine', ind.serie_production_hebdo(bandes), 'bleu', 2),
        _courbe('Mortalité nationale (%)', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Élevages actifs', 'avec au moins une saisie', ind.serie_fermes_actives_hebdo(bandes), 'vert', 0)]}


PAR_PROFIL = {Profil.ELEVEUR: eleveur, Profil.AGENT: agent, Profil.VETO: veterinaire, Profil.DGE: dge,
              Profil.ADMIN: administrateur, Profil.AUDITEUR: auditeur, Profil.BCEG: bceg, Profil.MAEDR: maedr_}


def pour(user):
    fonction = PAR_PROFIL.get(user.profil)
    return fonction(user) if fonction else None
