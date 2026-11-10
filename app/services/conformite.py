"""Lot K — tableaux conformes au cahier (docs/conformite) : un fournisseur de lignes par écran de bureau, la fiche
ouverte au clic (valeurs des champs, droits, action) et les gestes de la fiche (modifier / archiver / décision),
qui s'appuient TOUJOURS sur les règles existantes des services. Les champs du cahier mal classés sont corrigés ici
(`CORRECTIONS`) et notés dans docs/decisions_autonomes.md. Une valeur absente s'affiche « — », jamais un chiffre
inventé."""
from datetime import date, datetime, timedelta

from flask import url_for

from app import db, indicateurs as ind
from app.models import Ferme, Profil, Province, Utilisateur
from app.models.base import maintenant
from app.services import cahier_bureau
from app.utils.nombres import quantite
from app.utils.permissions import filtre_perimetre


class RegleConformite(Exception):
    pass


# Colonnes dont le type du cahier est corrigé (profil, n) → {colonne: type}. S = saisi, C = calculé, A = automatique.
CORRECTIONS = {
    ('DGE', 1): {'Province': 'A'},
    ('DGE', 2): {'Capacité': 'C', 'Bande en cours': 'C', 'Alerte': 'C'},
    ('DGE', 3): {'Reçu': 'C', 'État': 'A'},
    ('DGE', 4): {'Agent': 'A', 'Capacité': 'C', 'État': 'A'},
    ('DGE', 5): {'Agent': 'A', 'Priorité': 'C'},
    ('DGE', 6): {'Ferme': 'A', 'Province': 'A', 'Bandes': 'C'},
    ('DGE', 7): {'Validé MAEDR': 'A'},
    ('DGE', 8): {'Origine': 'A', 'État': 'C'},
    ('VETO', 1): {'Réponse': 'C', 'État': 'A'},
    ('VETO', 2): {'Photos': 'A', 'Déclaré par': 'A', 'État': 'A'},
    ('VETO', 3): {'Paramètre': 'A', 'Valeur en vigueur': 'A', 'Unité': 'A', 'Appliqué à': 'A', 'Proposé par': 'A'},
    ('VETO', 4): {'Ferme': 'A', 'Bande': 'A', 'Date prévue': 'C', 'État': 'C'},
    ('VETO', 5): {'Délai avant vente': 'C', 'Suivi': 'A'},
    ('VETO', 6): {'Bande / lot': 'A', 'Ferme': 'A', 'Décision': 'A', 'État': 'A'},
    ('VETO', 7): {'Point de départ': 'S', 'Type': 'A', 'Amont (origine)': 'A', 'Aval (bandes / lots)': 'A', 'Par': 'A'},
    ('VETO', 8): {'Paramètre': 'A', 'Avant': 'A', 'Après': 'A', 'Proposé par': 'A', 'Motif': 'A'},
}


def spec(profil, n):
    """Le cahier, avec les types corrigés."""
    s = dict(cahier_bureau.ecran(profil, n))
    corr = CORRECTIONS.get((profil if isinstance(profil, str) else profil.value, n), {})
    s['champs'] = [(c, corr.get(c, t), ex) for c, t, ex in s['champs']]
    return s


class Tableau:
    """Ce que la macro `tableau` attend."""

    def __init__(self, lignes, provinces=None, archives=None, creation=None, creation_caches=None, noms=None,
                 choix=None, peut_modifier=False, peut_archiver=False, colonnes_en_plus=(), vide=None):
        self.lignes = lignes
        self.provinces = provinces or sorted({l['province'] for l in lignes if l.get('province')})
        self.archives = archives
        self.creation = creation
        self.creation_caches = creation_caches or {}
        self.noms = noms or {}
        self.choix = choix or {}
        self.peut_modifier = peut_modifier
        self.peut_archiver = peut_archiver
        self.colonnes_en_plus = list(colonnes_en_plus)
        self.vide = vide


def ligne(cellules, ident, valeurs=None, action=None, droits=(), pied=None, titre=None, jour=None, province=None,
          lien=None, archivee=False):
    fiche = {'valeurs': valeurs if valeurs is not None else {k: _texte(v) for k, v in cellules.items()},
             'action': action, 'droits': list(droits), 'pied': pied, 'titre': titre}
    if valeurs is None and lien and not droits:
        fiche = {}                                                    # lecture : le clic ouvre le lien
    return {'cellules': cellules, 'id': ident, 'fiche': fiche, 'date': jour.isoformat() if jour else None,
            'province': province, 'lien': lien, 'archivee': archivee}


# ── Petits formats ──────────────────────────────────────────────────────

def _texte(v):
    from markupsafe import Markup
    if v is None:
        return ''
    if isinstance(v, Markup):
        import re
        return re.sub(r'<[^>]+>', '', str(v)).strip()
    return str(v)


def _d(v, fmt='%d/%m/%Y'):
    return v.strftime(fmt) if v else '—'


def _n(v, dec=0, suffixe=''):
    if v is None:
        return '—'
    return quantite(round(v, dec) if dec else int(round(v))) + suffixe


def _pct(v, dec=1):
    return '—' if v is None else f'{quantite(round(v, dec))} %'


def _date_de(v):
    if isinstance(v, datetime):
        return v.date()
    return v


def _heures_depuis(dt):
    if not dt:
        return 0
    now = maintenant()
    if dt.tzinfo is None:
        now = now.replace(tzinfo=None)
    return (now - dt).total_seconds() / 3600


def pied(o):
    """« Créé par X · le J/M/A · n modification(s) · inscrit au journal »."""
    parts = []
    auteur = getattr(o, 'auteur', None) or getattr(o, 'createur', None) or getattr(o, 'demandeur', None)
    if auteur is None and getattr(o, 'cree_par', None):
        auteur = db.session.get(Utilisateur, o.cree_par)
    if auteur is not None:
        parts.append(f'créé par {auteur.nom_complet}')
    cree = getattr(o, 'cree_le', None) or getattr(o, 'propose_le', None) or getattr(o, 'genere_le', None)
    if cree:
        parts.append(f'le {_d(_date_de(cree))}')
    try:
        from app.models import JournalAudit
        from app.services.journal import Action as J
        table = getattr(o, '__tablename__', None)
        if table and getattr(o, 'id', None) is not None:
            n = JournalAudit.query.filter_by(table_nom=table, enregistrement_id=str(o.id)).filter(
                JournalAudit.action.in_((J.MODIFICATION, J.CORRECTION))).count()
            parts.append(f'{n} modification{"s" if n != 1 else ""}')
    except Exception:
        pass
    parts.append('inscrit au journal')
    return ' · '.join(parts)


def _badge(etat, couleur='neutre'):
    from markupsafe import Markup, escape
    return Markup(f'<span class="badge badge-{couleur}">{escape(etat)}</span>')


def _lien(url, texte):
    from markupsafe import Markup, escape
    return Markup(f'<a href="{escape(url)}">{escape(texte)}</a>')


def _province_de(user, fermes):
    if user.est_national:
        return 'national'
    ids = {f.province_id for f in fermes} | set(user.province_ids)
    return ', '.join(p.nom for p in Province.query.filter(Province.id.in_(ids)).order_by(Province.ordre)) if ids else '—'


# ══════════════════════════════════════════════════════════════════════
# DGE
# ══════════════════════════════════════════════════════════════════════

def dge_accueil(user):
    """Situation par province : chiffres des indicateurs existants, agrégés par province. Clic : lecture seule."""
    from app.services import pilotage, dge as regles_dge
    from app.models.bande import Bande, StatutBande
    from app.models.tracabilite import LotTrace
    fermes = filtre_perimetre(Ferme.query, utilisateur=user).all()
    production = ind.production_fermes(fermes)
    arbitrages = {}
    try:
        for x in regles_dge.arbitrages_par_province(user):
            arbitrages[x['province'].id if hasattr(x.get('province'), 'id') else x.get('province_id')] = x.get('n', x.get('nombre', 0))
    except Exception:
        arbitrages = {}
    lignes = []
    for p in Province.query.order_by(Province.ordre):
        fs = [f for f in fermes if f.province_id == p.id]
        if not fs:
            continue
        ids = [f.id for f in fs]
        bandes = Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS).all()
        actives = sum(1 for f in fs if f.statut == 'Opérationnelle')
        part = ind.participation(fs)
        mv = ind.mortalite_viabilite(bandes)
        sorties = sum(len(b.sorties) for b in Bande.query.filter(Bande.ferme_id.in_(ids)))
        try:
            from app.models.bande import Sortie
            lots = (db.session.query(LotTrace).join(Sortie, LotTrace.sortie_id == Sortie.id).join(Bande, Sortie.bande_id == Bande.id)
                    .filter(Bande.ferme_id.in_(ids), LotTrace.annule.is_(False)).count())
        except Exception:
            lots = None
        qr = _pct(100 * lots / sorties, 0) if sorties and lots is not None else '—'
        cell = {'Province': p.nom, 'Fermes actives': f'{actives} / {len(fs)}', 'Bandes en cours': str(len(bandes)),
                'Production 12 mois': _n(part['reelle'], 1, ' t'), 'Objectif': _n(part['cible'], 1, ' t'),
                'Atteinte': _pct(part['atteinte'], 0), 'Mortalité': _pct(mv['mortalite'], 2),
                'Écarts intrants': str(arbitrages.get(p.id, 0)), 'Lots avec QR': qr}
        lignes.append(ligne(cell, p.id, province=p.nom, lien=url_for('fermes.liste', province=p.id),
                            pied=f'Situation calculée le {_d(date.today())} · lecture seule'))
    return Tableau(lignes, vide='Aucune ferme dans le périmètre.')


def dge_elevages(user, fermes=None, details=None, production=None):
    from app.services import pilotage, fermes as regles_fermes
    fermes = fermes if fermes is not None else filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    production = production if production is not None else ind.production_fermes(fermes)
    details = details if details is not None else {f.id: pilotage.infos_ferme(f, production) for f in fermes}
    from app.models.bande import Bande, StatutBande
    lignes = []
    for f in fermes:
        i = details[f.id]
        bande = Bande.query.filter_by(ferme_id=f.id, statut=StatutBande.EN_COURS).order_by(Bande.date_mise_en_place.desc()).first()
        pr = production.get(f.id) or {}
        cell = {'N°': _lien(url_for('fermes.fiche', numero=f.numero), f.numero), 'Élevage': f.nom, 'Province': f.province.nom,
                'Programme': f.libelle_programme, 'Agent': f.agent.nom_complet if f.agent else '—', 'Capacité': _n(f.capacite),
                'Bande en cours': bande.numero if bande else '—', 'Effectif': _n(i['effectif']),
                'Mortalité': _pct(i['mortalite'], 2), 'Atteinte': _pct(pr.get('atteinte'), 0),
                'Dernière saisie': _d(i['derniere_saisie'], '%d/%m'), 'Alerte': '⚠️' if i['alerte'] else '—'}
        peut = regles_fermes.peut_modifier(user, f)
        agents = [a.nom_complet for a in Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True)]
        lignes.append(ligne(cell, str(f.id), valeurs={**{k: _texte(v) for k, v in cell.items()}, 'N°': f.numero,
                                                       'Programme': 'POUFA' if f.programme_poufa else 'HORS',
                                                       'Agent': str(f.agent_id) if f.agent_id else '', 'Province': str(f.province_id)},
                            action=url_for('bureau.fiche_conforme', cle='DGE-2', ident=str(f.id)),
                            droits=['modifier', 'archiver'] if peut else [], pied=pied(f), titre=f'{f.numero} · {f.nom}',
                            jour=_date_de(f.cree_le), province=f.province.nom, archivee=f.archive_le is not None))
    agents = Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True).order_by(Utilisateur.nom).all()
    choix = {'Programme': [('POUFA', '🏛️ Programme POUFA'), ('HORS', 'Hors programme')],
             'Agent': [(str(a.id), a.nom_complet) for a in agents],
             'Province': [(str(p.id), p.nom) for p in Province.query.order_by(Province.ordre)]}
    return Tableau(lignes, choix=choix, peut_modifier=True,
                   peut_archiver=user.profil in (Profil.DGE, Profil.ADMIN), vide='Aucune ferme dans le périmètre.')


def dge_livraisons(user):
    from app.models.intrant import Livraison, OrigineLivraison, StatutLivraison as S
    livs = (filtre_perimetre(Livraison.query).filter(Livraison.origine == OrigineLivraison.ETAT)
            .order_by(Livraison.date_livraison.desc()).limit(400).all())
    lignes = []
    for liv in livs:
        for l in liv.lignes:
            ecart = None if l.quantite_recue is None else l.quantite_recue - l.quantite_livree
            cell = {'N°': _lien(url_for('livraisons.fiche', numero=liv.numero), liv.numero) if liv.numero else '—',
                    'Ferme': f'{liv.ferme.numero} · {liv.ferme.nom}', 'Province': liv.ferme.province.nom, 'Article': l.produit.nom,
                    'Prévu': _n(l.quantite_livree, 1), 'Reçu': _n(l.quantite_recue, 1), 'Écart': _n(ecart, 1) if ecart else ('0' if ecart == 0 else '—'),
                    'Date prévue': _d(liv.date_livraison), 'Confirmée le': _d(_date_de(liv.confirmee_le)),
                    'État': _badge(liv.libelle_statut, {'A_CONFIRMER': 'warn', 'PREVUE': 'neutre', 'RECUE': 'ok', 'RECUE_ECART': 'warn', 'ANNULEE': 'off'}.get(liv.statut, 'neutre'))}
            droits = []
            if liv.statut in (S.PREVUE, S.A_CONFIRMER) and user.profil in (Profil.DGE, Profil.ADMIN):
                droits = ['modifier', 'archiver']
            lignes.append(ligne(cell, f'{liv.id}:{l.id}', valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Date prévue': liv.date_livraison.isoformat()},
                                action=url_for('bureau.fiche_conforme', cle='DGE-3', ident=f'{liv.id}:{l.id}'), droits=droits,
                                pied=pied(liv), titre=f'Livraison {liv.numero or ""} · {l.produit.nom}', jour=liv.date_livraison,
                                province=liv.ferme.province.nom, archivee=liv.statut == S.ANNULEE))
    return Tableau(lignes, peut_modifier=True, peut_archiver=True,
                   noms={'Date prévue': 'date_prevue', 'Prévu': 'quantite', 'État': 'etat'},
                   vide="Aucune livraison de l'État.")


def dge_commandes(user):
    """Une ligne par commande d'une ferme (les articles d'une même demande regroupés)."""
    from app.models.agent import CommandeIntrant, StatutCommande as SC
    from app.services import agent as regles_agent
    q = filtre_perimetre(CommandeIntrant.query).order_by(CommandeIntrant.cree_le.desc()).limit(400).all()
    groupes = {}
    for c in q:
        cle = (c.ferme_id, c.demandee_par, _date_de(c.cree_le), c.statut)
        groupes.setdefault(cle, []).append(c)
    lignes = []
    for (fid, _, jour, statut), cs in groupes.items():
        f = cs[0].ferme
        def q_type(mot):
            tot = sum(c.quantite for c in cs if mot in c.produit.nom.lower() or mot in c.produit.type.lower())
            return _n(tot, 0) if tot else '—'
        ident = ','.join(str(c.id) for c in cs)
        cell = {'N°': f'C-{cs[0].id}', 'Ferme': f'{f.numero} · {f.nom}', 'Agent': cs[0].demandeur.nom_complet,
                'Bande': '—', 'Poussins': q_type('poussin'), 'Aliment démarrage': q_type('démarrage'),
                'Aliment croissance': q_type('croissance'), 'Vaccins': q_type('vaccin'), 'Mise en place': '—',
                'Capacité': _n(f.capacite), 'État': _badge(cs[0].libelle_statut, {'ENVOYEE': 'neutre', 'VALIDEE': 'ok', 'REFUSEE': 'danger', 'LIVREE': 'ok'}.get(statut, 'neutre'))}
        droits = ['modifier'] if statut == SC.ENVOYEE and regles_agent.peut_decider_commande(user) else []
        lignes.append(ligne(cell, ident, valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Motif': cs[0].motif or ''},
                            action=url_for('bureau.fiche_conforme', cle='DGE-4', ident=ident), droits=droits, pied=pied(cs[0]),
                            titre=f'Commande C-{cs[0].id} · {f.nom}', jour=jour, province=f.province.nom))
    choix = {'État': [('VALIDEE', 'Valider'), ('REFUSEE', 'Refuser (motif obligatoire)')]}
    return Tableau(lignes, choix=choix, peut_modifier=True,
                   colonnes_en_plus=('Motif',), vide='Aucune commande.')


def dge_arbitrages(user, conflits=None):
    from app.models.hors_ligne import ConflitHorsLigne, GenreVerification as G, StatutVerification as SV
    from app.services import verifications
    tous = filtre_perimetre(ConflitHorsLigne.query)
    if conflits is None:
        conflits = verifications.a_trancher(tous).order_by(ConflitHorsLigne.cree_le).all() + \
            tous.filter(db.or_(ConflitHorsLigne.statut.is_(None), ConflitHorsLigne.statut != SV.A_VERIFIER)).order_by(ConflitHorsLigne.cree_le.desc()).limit(100).all()
    lignes = []
    for c in conflits:
        v = c.versions or []
        def version(i):
            if isinstance(v, list) and len(v) > i:
                x = v[i]
                return ' · '.join(f'{k} {val}' for k, val in x.items() if k not in ('utilisateur_id',)) if isinstance(x, dict) else str(x)
            return '—'
        age_h = _heures_depuis(c.cree_le)
        prio = 'haute' if age_h > 48 else 'normale'
        etat = 'À trancher' if c.a_trancher else ('Tranché' if c.statut == SV.TRANCHE else ('Vu' if c.vu_le else 'À voir'))
        genres = {G.MESSAGE: 'Saisie refusée', G.SAISIE_JOUR: 'Saisie du jour', G.LIVRAISON: 'Livraison', G.SORTIE: 'Sortie'}
        cell = {'Type': genres.get(c.genre, c.genre), 'Ferme': f'{c.ferme.numero} · {c.ferme.nom}' if c.ferme else '—',
                'Bande': c.bande.numero if c.bande else '—', 'Version 1': version(0), 'Version 2': version(1), 'Écart': c.quoi,
                'Depuis': _d(_date_de(c.cree_le), '%d/%m %H:%M') if c.cree_le else '—', 'Agent': c.ferme.agent.nom_complet if c.ferme and c.ferme.agent else '—',
                'Priorité': _badge(prio, 'danger' if prio == 'haute' else 'neutre'), 'État': _badge(etat, 'warn' if c.a_trancher else 'ok')}
        droits = ['modifier'] if c.a_trancher else []
        lignes.append(ligne(cell, str(c.id), valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Détail': c.detail},
                            action=url_for('bureau.fiche_conforme', cle='DGE-5', ident=str(c.id)), droits=droits, pied=pied(c),
                            titre=f'Arbitrage · {c.quoi}', jour=_date_de(c.cree_le), province=c.ferme.province.nom if c.ferme else None))
    choix = {'État': [('0', 'Garder la version 1'), ('1', 'Garder la version 2')]}
    choix['Ferme'] = _fermes_choix(user)
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='DGE-5' if user.profil != Profil.AGENT else 'AGENT-6'),
                   choix=choix, peut_modifier=True, colonnes_en_plus=('Détail',), noms={'État': 'choix'}, vide='Aucun écart à arbitrer.')


def dge_classement(user, r=None):
    from app.services import dge as regles_dge
    r = r or regles_dge.classement(user)
    lignes = []
    for x in r['classees']:
        f = x['ferme']
        cell = {'Rang': str(x['rang']), 'Ferme': _lien(url_for('fermes.fiche', numero=f.numero), f'{f.numero} · {f.nom}'),
                'Province': f.province.nom, 'Bandes': str(x['bandes']), 'Mortalité': str(x['notes'].get('mortalite', '—')),
                'IC': str(x['notes'].get('ic', '—')), 'GMQ': str(x['notes'].get('gmq', '—')), 'Régularité': str(x['notes'].get('regularite', '—')),
                'Biosécurité': '—', 'Note': str(x['score']), 'Évolution': '—'}
        lignes.append(ligne(cell, str(f.id), province=f.province.nom, lien=url_for('fermes.fiche', numero=f.numero)))
    return Tableau(lignes, vide='Aucune ferme classée : pas encore de bande clôturée complète.')


def dge_rapports(user, rapports):
    lignes = []
    for r in rapports:
        cell = {'Période': r.periode, 'Type': r.libelle_type, 'Périmètre': r.cible, 'Généré le': _d(_date_de(r.genere_le)),
                'Pages': str(r.pages) if r.pages else '—', 'Diffusion': '—', 'Validé MAEDR': '—',
                'Fichier': _lien(url_for('actions.telecharger', ident=r.id), '📄 PDF')}
        lignes.append(ligne(cell, str(r.id), lien=url_for('actions.telecharger', ident=r.id), jour=_date_de(r.genere_le),
                            province=r.province.nom if getattr(r, 'province', None) else None))
    return Tableau(lignes, vide='Aucun rapport gardé.')


# ══════════════════════════════════════════════════════════════════════
# Vétérinaire
# ══════════════════════════════════════════════════════════════════════

def _age(b):
    return str(ind.age(b)) if b else '—'


def _effectif(b):
    if not b:
        return '—'
    try:
        return _n(ind.calculer(b)['effectif_present'])
    except Exception:
        return '—'


def _morts_24h(b):
    if not b:
        return '—'
    s = ind.saisie_du(b, date.today()) or ind.saisie_du(b, date.today() - timedelta(days=1))
    return str(s.morts) if s else '—'


def veto_accueil(user):
    from app.models.sante import AlerteSanitaire, StatutAlerte as SA
    from app.services import sante
    alertes = sante.alertes_visibles(user).filter(AlerteSanitaire.statut.in_(SA.OUVERTES)).order_by(AlerteSanitaire.cree_le.desc()).all()
    lignes = []
    for a in alertes:
        b = a.bande
        cell = {'Ferme': f'{a.ferme.numero} · {a.ferme.nom}', 'Bande': b.numero if b else '—', 'Âge': _age(b), 'Effectif': _effectif(b),
                'Signal': a.libelle_origine, 'Mortalité 24 h': _morts_24h(b), 'Depuis': _d(_date_de(a.cree_le), '%d/%m %H:%M'),
                'Réponse': 'oui' if a.reponses else 'pas encore', 'État': _badge(a.libelle_statut, 'warn' if a.statut == SA.NOUVELLE else 'info')}
        lignes.append(ligne(cell, str(a.id), lien=url_for('sante.alerte', numero=a.numero), jour=_date_de(a.cree_le),
                            province=a.ferme.province.nom))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='VETO-1'), choix={'Ferme': _fermes_choix(user)}, vide='Aucune alerte ouverte ✓')


def veto_signalements(user, alertes):
    from app.models.sante import StatutAlerte as SA
    lignes = []
    for a in alertes:
        d, b = a.declaration, a.bande
        delai = '—'
        if a.reponses:
            h = (a.reponses[0].cree_le - a.cree_le).total_seconds() / 3600
            delai = f'{quantite(round(h))} h'
        cell = {'N°': _lien(url_for('sante.alerte', numero=a.numero), a.numero), 'Ferme': f'{a.ferme.numero} · {a.ferme.nom}',
                'Bande': b.numero if b else '—', 'Âge': _age(b), 'Effectif': _effectif(b),
                'Signes observés': ', '.join(d.signes) if d and d.signes else a.libelle_origine,
                'Photos': str(len(d.photos)) if d else '—', 'Déclaré par': (d.auteur.nom_complet if d and d.auteur else ('agent' if d and d.saisi_par_agent else 'système')),
                'Le': _d(_date_de(a.cree_le)), 'Délai': delai,
                'État': _badge(a.libelle_statut, {'NOUVELLE': 'warn', 'EN_ANALYSE': 'info', 'CONFIRMEE': 'danger', 'INFIRMEE': 'ok', 'CLOSE': 'off'}.get(a.statut, 'neutre'))}
        lignes.append(ligne(cell, str(a.id), lien=url_for('sante.alerte', numero=a.numero), jour=_date_de(a.cree_le),
                            province=a.ferme.province.nom, archivee=a.statut == SA.CLOSE))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='VETO-2'), choix={'Ferme': _fermes_choix(user)},
                   colonnes_en_plus=(), vide='Aucun signalement.')


def veto_seuils(user, parametres, propositions):
    from app.models.parametre import TypeParametre
    en_cours = {p.cle: p for p in propositions}
    lignes = []
    for p in parametres:
        prop = en_cours.get(p.cle)
        unite = {'POURCENT': '%', 'JOURS': 'jours', 'ENTIER': '', 'DECIMAL': '', 'HEURES': 'h'}.get(p.type.value if hasattr(p.type, 'value') else str(p.type), '')
        cell = {'Paramètre': p.description or p.cle, 'Valeur en vigueur': p.valeur, 'Unité': unite or '—',
                'Appliqué à': 'Toutes les bandes', 'Proposition en cours': prop.apres if prop else '—',
                'Proposé par': prop.auteur.nom_complet if prop else '—',
                'Dernière modification': _d(_date_de(p.modifie_le)) if p.modifie_le else '—'}
        lignes.append(ligne(cell, p.cle, valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Clé': p.cle, 'Nouvelle valeur': '', 'Motif': ''},
                            action=url_for('bureau.fiche_conforme', cle='VETO-3', ident=p.cle), droits=['modifier'] if not prop else [],
                            pied='quatre yeux : la nouvelle valeur s\'applique après approbation par une autre personne · inscrit au journal',
                            titre=p.description or p.cle))
    return Tableau(lignes, peut_modifier=True,
                   colonnes_en_plus=('Nouvelle valeur', 'Motif'), vide='Aucun paramètre sanitaire.')


def veto_calendrier(user, bandes):
    from app.services import sante
    from app.models.sante import Vaccination
    lignes = []
    for b in bandes:
        for v in sante.vaccins_de_la_bande(b):
            c, fait = v['calendrier'], v['fait']
            etat = {'fait': 'Fait', 'aujourdhui': "Aujourd'hui", 'demain': 'Demain', 'retard': 'En retard', 'a_faire': 'À faire',
                    'a_venir': 'À venir', 'avant_suivi': 'Avant le suivi'}.get(v['etat'], v['etat'])
            cell = {'Ferme': f'{b.ferme.numero} · {b.ferme.nom}', 'Bande': b.numero, 'Âge': _age(b), 'Vaccin': c.produit.nom,
                    'Prévu à': f'J{c.age_jours}', 'Date prévue': _d(v['prevu']), 'Fait le': _d(fait.date) if fait else '—',
                    'Lot du vaccin': (getattr(fait, 'lot', None) or getattr(fait, 'numero_lot', None) or '—') if fait else '—',
                    'État': _badge(etat, 'ok' if v['etat'] == 'fait' else 'danger' if v['etat'] == 'retard' else 'neutre')}
            lignes.append(ligne(cell, f'{b.id}:{c.id}', lien=url_for('bandes.fiche', numero=b.numero), jour=v['prevu'],
                                province=b.ferme.province.nom, archivee=v['etat'] == 'avant_suivi'))
    return Tableau(lignes, vide='Aucune bande en cours dans la zone.')


def veto_diagnostics(user, alertes):
    from app.services import sante
    lignes = []
    for a in alertes:
        b = a.bande
        r = a.reponses[-1] if a.reponses else None
        hist = [h for h in a.historique if h.commentaire]
        diag = hist[-1].commentaire if hist else a.libelle_statut
        delai = sante.fin_delai_attente(b) if b else None
        cell = {'N°': _lien(url_for('sante.alerte', numero=a.numero), a.numero), 'Bande': b.numero if b else '—',
                'Signalement': a.libelle_origine, 'Diagnostic': diag, 'Traitement': ', '.join(r.conseils) if r and r.conseils else '—',
                'Délai avant vente': _d(delai) if delai else '—', "Réponse à l'éleveur": (r.texte or '—') if r else '—',
                'Le': _d(_date_de(a.modifie_le)), 'Suivi': _badge(a.libelle_statut, 'ok' if a.statut == 'CLOSE' else 'info')}
        lignes.append(ligne(cell, str(a.id), lien=url_for('sante.alerte', numero=a.numero), jour=_date_de(a.modifie_le),
                            province=a.ferme.province.nom, archivee=a.statut == 'CLOSE'))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='VETO-5'), choix={'Ferme': _fermes_choix(user)}, vide='Aucun diagnostic.')


def veto_bloquees(user, actifs, leves):
    from app.services import veto
    lignes = []
    for bl in list(actifs) + list(leves):
        b = bl.bande
        leve = bl.leve_le is not None
        cell = {'Bande / lot': b.numero, 'Ferme': f'{bl.ferme.numero} · {bl.ferme.nom}', 'Décision': 'Blocage levé' if leve else 'Ventes bloquées',
                'Motif': bl.motif, 'Effectif': _effectif(b), 'Lots retenus': '—', 'Depuis': _d(_date_de(bl.cree_le)),
                'Prochain contrôle': '—', 'État': _badge('Levé' if leve else 'Actif', 'ok' if leve else 'danger')}
        droits = ['modifier'] if not leve and user.profil in (Profil.VETO, Profil.ADMIN) else []
        lignes.append(ligne(cell, str(bl.id), valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Motif de la levée': ''},
                            action=url_for('bureau.fiche_conforme', cle='VETO-6', ident=str(bl.id)), droits=droits, pied=pied(bl),
                            titre=f'Blocage · {b.numero}', jour=_date_de(bl.cree_le), province=bl.ferme.province.nom, archivee=leve))
    return Tableau(lignes, peut_modifier=True,
                   colonnes_en_plus=('Motif de la levée',), vide='Aucune bande bloquée.')


def veto_tracabilite(user, q, r):
    from app.models import JournalAudit
    from app.services.journal import Action
    lignes = []
    if r:
        for f in r.get('fiches', []):
            b = f['bande']
            poussins = (f.get('amont') or {}).get('poussins') or []
            aval = f.get('aval') or []
            cell = {'Point de départ': q, 'Type': (r.get('quoi') or 'bande').split(' ')[0], 'Amont (origine)': ' ; '.join(str(x.get('fournisseur') or x.get('livraison') or x.get('date') or '') for x in poussins) or '—',
                    'Aval (bandes / lots)': ', '.join(x['lot'] for x in aval if x.get('lot')) or '—', 'Lots': str(sum(1 for x in aval if x.get('lot'))),
                    'Têtes': _n(sum(x.get('nombre') or 0 for x in aval)), 'Établissements': str(len({x.get('destinataire') for x in aval if x.get('destinataire')})),
                    'Le': _d(date.today()), 'Par': user.nom_complet}
            lignes.append(ligne(cell, getattr(b, 'numero', q), lien=url_for('bandes.fiche', numero=b.numero) if getattr(b, 'numero', None) else None))
    historique = (JournalAudit.query.filter(JournalAudit.action == Action.RECHERCHE).order_by(JournalAudit.horodatage.desc()).limit(50).all())
    for j in historique:
        import re
        m = re.search(r'« (.+?) »', j.detail or '')
        cell = {'Point de départ': m.group(1) if m else '—', 'Type': 'recherche', 'Amont (origine)': '—', 'Aval (bandes / lots)': '—',
                'Lots': '—', 'Têtes': '—', 'Établissements': '—', 'Le': _d(_date_de(j.horodatage), '%d/%m %H:%M'),
                'Par': j.identifiant or '—'}
        lignes.append(ligne(cell, str(j.id), lien=url_for('veto.recherche', q=m.group(1)) if m else None, jour=_date_de(j.horodatage)))
    return Tableau(lignes, vide='Aucune recherche pour le moment.')


def validations(user, a_decider, mes_propositions, historique, cle):
    from app.services import approbations
    lignes = []
    for p in list(a_decider) + list(mes_propositions) + list(historique):
        peut = approbations.peut_decider(user, p) and p.statut == 'EN_ATTENTE'
        decision = p.libelle_statut if p.statut != 'EN_ATTENTE' else 'En attente'
        if p.decideur:
            decision += f' · {p.decideur.nom_complet}'
        cell = {'Paramètre': p.libelle, 'Avant': p.avant or '—', 'Après': p.apres, 'Proposé par': p.auteur.nom_complet,
                'Le': _d(_date_de(p.propose_le)), 'Motif': p.motif, 'Impact': {'SANITAIRE': 'sanitaire', 'GENERAL': 'général'}.get(p.domaine, p.domaine),
                'Décision': _badge(decision, 'warn' if p.statut == 'EN_ATTENTE' else 'ok' if p.statut == 'APPROUVEE' else 'off')}
        if cle == 'ADMIN-5':
            cell = {**cell, 'Élément': p.libelle, 'Peut approuver': 'vous' if peut else ('pas vous (votre proposition)' if p.propose_par == user.id else 'une autre personne')}
        lignes.append(ligne(cell, str(p.id), valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Décision': '', 'Motif de la décision': ''},
                            action=url_for('bureau.fiche_conforme', cle=cle, ident=str(p.id)), droits=['modifier'] if peut else [],
                            pied=pied(p), titre=f'Proposition · {p.libelle}', jour=_date_de(p.propose_le), archivee=p.statut != 'EN_ATTENTE'))
    choix = {'Décision': [('approuver', 'Approuver'), ('refuser', 'Refuser')]}
    return Tableau(lignes, choix=choix, peut_modifier=True,
                   colonnes_en_plus=('Motif de la décision',), vide='Aucune proposition en attente.')


# ══════════════════════════════════════════════════════════════════════
# Gestes de la fiche (POST /bureau/fiche/<cle>/<ident>)
# ══════════════════════════════════════════════════════════════════════

def geste(cle, ident, user, form):
    """Applique « Enregistrer la modification » ou « Archiver » selon l'écran, par les règles existantes.
    Rend un message pour l'utilisateur."""
    action = form.get('action', 'modifier')
    h = GESTES.get(cle)
    if h is None:
        raise RegleConformite('Cet écran est en lecture seule.')
    return h(ident, user, form, action)


def _ferme(ident, user, form, action):
    import uuid
    from app.services import fermes as regles, fiches
    f = db.session.get(Ferme, uuid.UUID(ident))
    if f is None or not regles.peut_modifier(user, f):
        raise RegleConformite('Vous ne pouvez pas modifier cette ferme.')
    if action == 'archiver':
        fiches.archiver_entite(f, user, form.get('motif') or 'archivée depuis la liste des élevages')
        return f'{f.numero} archivée.'
    avant = f'{f.nom} · {f.libelle_programme} · {f.agent.nom_complet if f.agent else "—"}'
    if form.get('Élevage', '').strip():
        f.nom = form['Élevage'].strip()[:150]
    if form.get('Programme') in ('POUFA', 'HORS'):
        f.programme_poufa = form['Programme'] == 'POUFA'
    if form.get('Agent'):
        a = db.session.get(Utilisateur, uuid.UUID(form['Agent']))
        if a and a.profil == Profil.AGENT:
            f.agent_id = a.id
    if (form.get('Province') or '').isdigit() and user.profil in (Profil.DGE, Profil.ADMIN):
        f.province_id = int(form['Province'])
    from app.services.journal import enregistrer, Action as J
    enregistrer(J.MODIFICATION, table='ferme', enregistrement_id=f.id,
                detail=f'{f.numero} modifiée (liste des élevages) : {avant} → {f.nom} · {f.libelle_programme} · {f.agent.nom_complet if f.agent else "—"}')
    return f'{f.numero} enregistrée.'


def _livraison(ident, user, form, action):
    import uuid
    from app.models.intrant import Livraison, LivraisonLigne, StatutLivraison as S
    from app.services import dge as regles_dge
    liv_id, ligne_id = ident.split(':')
    liv = db.session.get(Livraison, uuid.UUID(liv_id))
    l = db.session.get(LivraisonLigne, int(ligne_id))
    if liv is None or l is None or user.profil not in (Profil.DGE, Profil.ADMIN):
        raise RegleConformite('Vous ne pouvez pas modifier cette livraison.')
    if action == 'archiver':
        if liv.statut != S.PREVUE:
            raise RegleConformite("Seule une livraison prévue s'annule ; une livraison reçue reste dans l'historique.")
        regles_dge.annuler_prevue(liv, form.get('motif') or 'annulée depuis la liste des livraisons', user)
        return 'Livraison annulée.'
    if liv.statut not in (S.PREVUE, S.A_CONFIRMER):
        raise RegleConformite('Cette livraison est confirmée : elle ne se modifie plus.')
    from app.services.journal import enregistrer, Action as J
    avant = f'{l.quantite_livree} le {liv.date_livraison:%d/%m/%Y}'
    if form.get('date_prevue'):
        liv.date_livraison = date.fromisoformat(form['date_prevue'])
    if form.get('quantite'):
        try:
            l.quantite_livree = float(form['quantite'].replace(',', '.').replace(' ', ''))
        except ValueError:
            raise RegleConformite('La quantité prévue est un nombre.')
    enregistrer(J.MODIFICATION, table='livraison', enregistrement_id=liv.id,
                detail=f'Livraison {liv.numero} modifiée (liste) : {avant} → {l.quantite_livree} le {liv.date_livraison:%d/%m/%Y}')
    return 'Livraison enregistrée.'


def _commande(ident, user, form, action):
    from app.models.agent import CommandeIntrant
    from app.services import agent as regles
    cs = [db.session.get(CommandeIntrant, int(i)) for i in ident.split(',')]
    decision = form.get('État') or form.get('etat')
    if decision not in ('VALIDEE', 'REFUSEE'):
        raise RegleConformite('Choisissez : valider ou refuser (avec motif).')
    try:
        for c in cs:
            regles.decider_commande(c, user, decision == 'VALIDEE', form.get('Motif') or form.get('motif'))
    except regles.RegleAgent as e:
        raise RegleConformite(str(e))
    return 'Commande validée.' if decision == 'VALIDEE' else 'Commande refusée.'


def _arbitrage(ident, user, form, action):
    from app.models.hors_ligne import ConflitHorsLigne
    from app.services import verifications
    c = db.session.get(ConflitHorsLigne, int(ident))
    if c is None:
        raise RegleConformite('Arbitrage introuvable.')
    choix = form.get('choix') or form.get('État')
    try:
        verifications.trancher(c, int(choix) if (choix or '').isdigit() else choix, form.get('Motif') or form.get('motif'), user)
    except verifications.RegleVerification as e:
        raise RegleConformite(str(e))
    return 'Écart tranché.'


def _seuil(ident, user, form, action):
    from app.models import Parametre
    from app.services import approbations
    p = Parametre.query.filter_by(cle=ident).first()
    if p is None:
        raise RegleConformite('Paramètre introuvable.')
    apres = (form.get('Nouvelle valeur') or '').strip()
    motif = (form.get('Motif') or '').strip()
    if not apres or not motif:
        raise RegleConformite('Indiquez la nouvelle valeur et le motif.')
    approbations.proposer('PARAMETRE', p.cle, p.description or p.cle, p.valeur, apres, {'cle': p.cle, 'valeur': apres}, motif, user)
    return 'Proposition enregistrée : elle s\'appliquera après approbation par une autre personne.'


def _blocage(ident, user, form, action):
    from app.models.veto import BlocageSorties
    from app.services import veto
    bl = db.session.get(BlocageSorties, int(ident))
    if bl is None:
        raise RegleConformite('Blocage introuvable.')
    motif = (form.get('Motif de la levée') or form.get('motif') or '').strip()
    if not motif:
        raise RegleConformite('Indiquez le motif de la levée.')
    try:
        veto.lever(bl, motif, user)
    except Exception as e:
        raise RegleConformite(str(e))
    return 'Blocage levé.'


def _validation(ident, user, form, action):
    from app.models.securite import Proposition
    from app.services import approbations
    p = db.session.get(Proposition, int(ident))
    if p is None or not approbations.peut_decider(user, p):
        raise RegleConformite('Vous ne pouvez pas décider cette proposition (jamais la sienne).')
    decision = form.get('Décision')
    if decision not in ('approuver', 'refuser'):
        raise RegleConformite('Choisissez : approuver ou refuser.')
    try:
        approbations.decider(p, user, decision == 'approuver', form.get('Motif de la décision') or '')
    except Exception as e:
        raise RegleConformite(str(e))
    return 'Proposition approuvée.' if decision == 'approuver' else 'Proposition refusée.'


def _fermes_choix(user):
    return [(f.numero, f'{f.numero} · {f.nom}') for f in filtre_perimetre(Ferme.query, utilisateur=user).order_by(Ferme.numero_metier)]


def _bande_de(form, ferme):
    from app.models.bande import Bande, StatutBande
    num = (form.get('Bande') or form.get('Bande / lot') or '').strip()
    if num:
        b = Bande.query.filter_by(numero_metier=num).first()
        if b is None or b.ferme_id != ferme.id:
            raise RegleConformite('Cette bande n\'appartient pas à la ferme choisie.')
        return b
    return Bande.query.filter_by(ferme_id=ferme.id, statut=StatutBande.EN_COURS).order_by(Bande.date_mise_en_place.desc()).first()


def _ferme_du_form(form, user):
    num = (form.get('Ferme') or '').strip()
    f = filtre_perimetre(Ferme.query, utilisateur=user).filter(Ferme.du_numero(num)).first() if num else None
    if f is None:
        raise RegleConformite('Choisissez la ferme.')
    return f


def _creer_alerte(user, form):
    """VETO : alerte sanitaire ouverte par le vétérinaire lui-même (origine VETO), avec son commentaire."""
    from app.services import sante
    from app.models.sante import OrigineAlerte
    f = _ferme_du_form(form, user)
    b = _bande_de(form, f)
    commentaire = (form.get('Signal') or form.get('Signalement') or form.get('Diagnostic') or '').strip() or None
    a = sante._nouvelle_alerte(f, b, OrigineAlerte.VETO, commentaire=commentaire)
    db.session.flush()
    from app.services.journal import enregistrer, Action as J
    enregistrer(J.CREATION, table='alerte_sanitaire', enregistrement_id=a.id,
                detail=f'Alerte {a.numero} créée par le vétérinaire {user.nom_complet} · {f.numero}' + (f' — {commentaire}' if commentaire else ''))
    return f'Alerte {a.numero} créée.'


def _creer_signalement(user, form):
    """VETO : signalement enregistré pour un éleveur (déclaration, sans photo)."""
    from app.services import sante
    f = _ferme_du_form(form, user)
    b = _bande_de(form, f)
    signes = [x.strip() for x in (form.get('Signes observés') or '').replace(';', ',').split(',') if x.strip()]
    try:
        nombre = int(form.get('Effectif') or form.get('Nombre') or 1)
    except ValueError:
        nombre = 1
    try:
        d = sante.declarer(f, b, signes, nombre, [], None, user)
    except sante.RegleSante as e:
        raise RegleConformite(str(e))
    return 'Signalement enregistré.'


def _signaler_ecart(user, form):
    """DGE / agent : écart signalé à la main (à voir par l'agent de la ferme), genre MESSAGE."""
    from app.models.hors_ligne import ConflitHorsLigne, GenreVerification as G
    f = _ferme_du_form(form, user)
    quoi = (form.get('Écart') or form.get('Type') or 'Écart signalé').strip()[:150]
    detail = ' · '.join(x for x in (form.get('Version 1'), form.get('Version 2'), form.get('Détail')) if x) or quoi
    c = ConflitHorsLigne(ferme_id=f.id, utilisateur_id=user.id, quoi=quoi, detail=detail[:2000], genre=G.MESSAGE,
                         bande_id=_bande_de(form, f).id if _bande_de(form, f) else None)
    db.session.add(c)
    db.session.flush()
    from app.services.journal import enregistrer, Action as J
    enregistrer(J.CREATION, table='conflit_hors_ligne', enregistrement_id=c.id, detail=f'Écart signalé par {user.nom_complet} · {f.numero} · {quoi}')
    return 'Écart signalé : il apparaît dans « À vérifier » de l\'agent.'


CREATIONS = {'VETO-1': _creer_alerte, 'VETO-2': _creer_signalement, 'VETO-5': _creer_alerte, 'DGE-5': _signaler_ecart,
             'AGENT-6': _signaler_ecart}


def creation(cle, user, form):
    h = CREATIONS.get(cle)
    if h is None:
        raise RegleConformite('Cet écran n\'a pas de création directe.')
    return h(user, form)


GESTES = {'DGE-2': _ferme, 'AGENT-2': _ferme, 'DGE-3': _livraison, 'DGE-4': _commande, 'AGENT-8': _commande,
          'DGE-5': _arbitrage, 'AGENT-6': _arbitrage, 'VETO-3': _seuil, 'VETO-6': _blocage, 'VETO-8': _validation,
          'ADMIN-5': _validation}
