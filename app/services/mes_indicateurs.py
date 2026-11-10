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
    bandes = _bandes(user)
    en_cours = [b for b in bandes if b.statut == StatutBande.EN_COURS]
    cartes = []
    for b in en_cours:
        v = ind.calculer(b)
        cartes.append(_carte(f'Viabilité · {b.batiment.code}', _pct(v['viabilite']), f'mortalité {_pct(v["mortalite"])}'))
        cartes.append(_carte(f'Aliment consommé · {b.batiment.code}', _nombre(v['aliment_kg'], 0, ' kg'),
                             f'{_nombre(v["sacs"], 0)} sacs'))
        cartes.append(_carte(f'Indice de consommation · {b.batiment.code}',
                             'sans objet' if v['ponte'] else _nombre(v['indice_consommation'], 2)))
    fermes = _fermes(user)
    p = ind.participation(fermes)
    cartes.append(_carte("Progression vers l'objectif annuel", _pct(p['atteinte'], 0) if p['atteinte'] is not None else '—',
                         f'{_nombre(p["reelle"], 1, " t")} produites sur 12 mois'))
    from app.services import argent
    mvts = argent.mouvements([f.id for f in fermes])
    ventes = [(m['date'], m['montant']) for m in mvts if m['signe'] > 0 and m['montant']]
    return {'cartes': cartes[:8], 'courbes': [
        _courbe('Mortalité de la bande', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Poids moyen', 'g', ind.serie_poids_hebdo(bandes), 'bleu', 0),
        _courbe('Gagné', 'FCFA par semaine', ind.serie_somme_hebdo(ventes), 'vert', 0)]}


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
    return {'cartes': [
        _carte('Mortalité de mes fermes', _pct(mv['mortalite'], 2), f'{mv["bandes"]} bande(s) en cours'),
        _carte('Visites ce mois', f'{sum(1 for d in faites if d and d >= debut_mois)} / '
                                  f'{sum(1 for d in prevues if d >= debut_mois and d.month == debut_mois.month)}',
               'faites / prévues'),
        _carte('Alertes ouvertes', str(alertes), alerte=alertes > 0),
        _carte('Écarts à arbitrer', str(ecarts), alerte=ecarts > 0),
        _carte('Mes fermes', str(len(fermes)))], 'courbes': [
        _courbe('Mortalité de mes fermes', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
        _courbe('Régularité des saisies', '% des jours', ind.serie_regularite_hebdo(bandes), 'bleu', 0),
        _courbe('Visites faites', 'par semaine', ind.serie_compte_hebdo(faites, debut=min(prevues + faites) if (prevues + faites) else None), 'vert', 0)]}


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
    return {'cartes': [
        _carte('Alertes ouvertes', str(sum(1 for a in toutes if a.statut in StatutAlerte.OUVERTES))),
        _carte('Mortalité de la zone', _pct(mv['mortalite'], 2), f'{mv["bandes"]} bande(s) en cours'),
        _carte('Vaccinations en retard', str(len(en_retard)), alerte=bool(en_retard)),
        _carte('Bandes bloquées', '—' if bloquees is None else str(bloquees)),
        _carte('Délai moyen de réponse', '—' if not delais else _nombre(sum(delais) / len(delais), 0, ' h'))],
        'courbes': [
        _courbe('Alertes par semaine', 'alertes', ind.serie_compte_hebdo([a.cree_le.date() for a in toutes]), 'rouge', 0),
        _courbe('Mortalité de la zone', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'orange', 2),
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
    return {'cartes': [
        _carte('Production 12 mois', _nombre(p['reelle'], 1, ' t'), f'{_pct(p["part_nationale"], 2)} de l\'objectif national'),
        _carte('Mortalité nationale', _pct(mv['mortalite'], 2), f'viabilité {_pct(mv["viabilite"], 2)}'),
        _carte('Élevages', str(len(fermes)), f'{sum(1 for f in fermes if f.statut == "Opérationnelle")} opérationnels'),
        _carte('Provinces ≥ 80 % de la cible', f'{provinces_80} / {len(par_province)}'),
        _carte('Écarts sur intrants', '—' if ecarts is None else str(ecarts)),
        _carte('Équivalent carcasse', _nombre(p['carcasse'], 1, ' t'))], 'courbes': [
        _courbe('Production (poids vif)', 't par semaine', ind.serie_production_hebdo(bandes), 'bleu', 2),
        _courbe('Mortalité nationale', '% par semaine', ind.serie_mortalite_hebdo(bandes), 'rouge', 2),
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
    return {'cartes': [
        _carte('Comptes actifs', str(len(actifs)), f'{len(comptes) - len(actifs)} archivé(s)'),
        _carte('Répartition par profil', ' · '.join(f'{n} {k}' for k, n in sorted(profils.items(), key=lambda x: -x[1])[:3])),
        _carte('Validations en attente', str(attente), alerte=attente > 0),
        _carte('Échecs de connexion (7 jours)', str(echecs_7j), alerte=echecs_7j > 10)], 'courbes': [
        _courbe('Comptes', 'créés (cumul)', actifs_hebdo, 'bleu', 0),
        _courbe('Opérations sensibles', 'par semaine',
                ind.serie_compte_hebdo([h.date() for a, h in journal if a in sensibles], debut=depuis), 'orange', 0),
        _courbe('Échecs de connexion', 'par semaine',
                ind.serie_compte_hebdo([h.date() for a, h in journal if a == Action.ECHEC_CONNEXION], debut=depuis), 'rouge', 0)]}


PAR_PROFIL = {Profil.ELEVEUR: eleveur, Profil.AGENT: agent, Profil.VETO: veterinaire, Profil.DGE: dge,
              Profil.ADMIN: administrateur}


def pour(user):
    fonction = PAR_PROFIL.get(user.profil)
    return fonction(user) if fonction else None
