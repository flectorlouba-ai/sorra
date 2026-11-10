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
    ('ELEVEUR', 1): {'Quoi': 'A', 'Bande': 'A', 'Pour quand': 'C', 'État': 'C'},
    ('ELEVEUR', 2): {'Bande': 'A', 'État': 'A'},
    ('ELEVEUR', 3): {'Jour': 'A', 'Saisi par': 'A', 'Modifiée': 'A'},
    ('ELEVEUR', 4): {'Mois': 'A', 'Recettes': 'C', 'Dépenses': 'C', 'Poussins': 'C', 'Aliment': 'C', 'Vaccins et soins': 'C', "Main-d'œuvre": 'C', 'Autres': 'C'},
    ('ELEVEUR', 5): {'Date': 'A', 'Bande': 'A', 'Réponse du vétérinaire': 'A', 'État': 'A'},
    ('ELEVEUR', 6): {'Article': 'A', 'Origine': 'A', 'Prévu': 'A', 'Date': 'A', 'État': 'A'},
    ('ELEVEUR', 7): {'Lot': 'A', 'Bande': 'A', 'Date': 'A', 'QR': 'A', 'Suivi': 'A'},
    ('ELEVEUR', 8): {'Date': 'A', 'Ce que la BCEG voit': 'C', 'Par': 'A'},
    ('AGENT', 1): {'Demandée par': 'A', 'État': 'C'},
    ('AGENT', 2): {'Bande en cours': 'C', 'Urgence': 'C'},
    ('AGENT', 3): {'Position': 'C', 'Compte': 'A', 'État': 'A'},
    ('AGENT', 4): {'Ordre': 'A', 'Raison': 'C', 'État': 'A'},
    ('AGENT', 5): {'Présence': 'C', 'État': 'A'},
    ('AGENT', 6): {'Ferme': 'A', 'Bande': 'A', 'Jour': 'A', 'Donnée': 'A', 'Version éleveur': 'A', 'Ma version': 'A'},
    ('AGENT', 7): {'Ferme': 'A', 'Article': 'A', 'Origine': 'A', 'Reçu': 'C', 'Utilisé': 'C'},
    ('AGENT', 8): {'État': 'A'},
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
                 choix=None, peut_modifier=False, peut_archiver=False, colonnes_en_plus=(), vide=None, titre=None,
                 libelle_modifier='Enregistrer la modification'):
        self.lignes = lignes
        self.libelle_modifier = libelle_modifier
        self.titre = titre                                        # titre vivant (nombre, bande, date) ; sinon celui du cahier
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


# ══════════════════════════════════════════════════════════════════════
# Éleveur (version ordinateur) — K3
# ══════════════════════════════════════════════════════════════════════

def _fiche_lot_a1(objets, user):
    """Les fiches préremplies du lot A1 (genres saisie, pesée, sortie, vaccin…) : {id: Info}."""
    from app.services import fiches
    try:
        return fiches.infos(objets, user)
    except Exception:
        return {}


def eleveur_accueil(user):
    """Mes alertes et rappels : ce que l'éleveur a à faire (saisie du jour, pesée, vaccins, livraisons à confirmer,
    réponses du vétérinaire) ; un clic ouvre l'écran concerné."""
    from app.models.bande import Bande, StatutBande
    from app.models.intrant import Livraison, StatutLivraison
    from app.models.sante import AlerteSanitaire
    from app.services import sante
    fermes = filtre_perimetre(Ferme.query, utilisateur=user).all()
    ids = [f.id for f in fermes]
    lignes = []
    bandes = Bande.query.filter(Bande.ferme_id.in_(ids), Bande.statut == StatutBande.EN_COURS).all() if ids else []
    auj = date.today()
    for b in bandes:
        if not ind.saisie_du(b, auj):
            lignes.append(ligne({'Quoi': '📝 Saisie du jour', 'Bande': b.numero, 'Pour quand': "aujourd'hui", 'État': _badge('À faire', 'warn')},
                                f'saisie:{b.id}', lien=url_for('eleveur.saisie'), jour=auj))
        pesee = ind.prochaine_pesee(b)
        if pesee:
            lignes.append(ligne({'Quoi': '⚖️ Pesée de la semaine', 'Bande': b.numero, 'Pour quand': _d(pesee),
                                 'État': _badge('En retard', 'danger') if pesee < auj else _badge('Prévue', 'neutre')},
                                f'pesee:{b.id}', lien=url_for('bandes.pesee', numero=b.numero), jour=pesee))
        for v in sante.vaccins_de_la_bande(b):
            if v['etat'] in ('aujourdhui', 'demain', 'retard', 'a_faire'):
                lignes.append(ligne({'Quoi': f'💉 Vaccin {v["calendrier"].produit.nom}', 'Bande': b.numero, 'Pour quand': _d(v['prevu']),
                                     'État': _badge('En retard', 'danger') if v['etat'] == 'retard' else _badge('À faire', 'warn')},
                                    f'vaccin:{b.id}:{v["calendrier"].id}', lien=url_for('eleveur.soins'), jour=v['prevu']))
    for liv in (Livraison.query.filter(Livraison.ferme_id.in_(ids), Livraison.statut == StatutLivraison.A_CONFIRMER).all() if ids else []):
        lignes.append(ligne({'Quoi': '🚚 Livraison à confirmer', 'Bande': '—', 'Pour quand': _d(liv.date_livraison), 'État': _badge('À confirmer', 'warn')},
                            f'liv:{liv.id}', lien=url_for('eleveur.produits'), jour=liv.date_livraison))
    for a in (AlerteSanitaire.query.filter(AlerteSanitaire.ferme_id.in_(ids)).all() if ids else []):
        for r in a.reponses:
            if r.lue_le is None:
                lignes.append(ligne({'Quoi': '💬 Réponse du vétérinaire', 'Bande': a.bande.numero if a.bande else '—',
                                     'Pour quand': _d(_date_de(r.cree_le)), 'État': _badge('À lire', 'info')},
                                    f'rep:{r.id}', lien=url_for('sante.mes_declarations'), jour=_date_de(r.cree_le)))
    lignes.sort(key=lambda l: l['date'] or '')
    return Tableau(lignes, vide='Rien à faire pour le moment ✓')


def eleveur_bandes(user, bandes):
    from app.models.bande import TypeProduction
    lignes = []
    for b in bandes:
        v = ind.calculer(b)
        cell = {'Bande': _lien(url_for('bandes.fiche', numero=b.numero), b.numero), 'Bâtiment': b.batiment.code,
                'Type': TypeProduction.LIBELLES.get(b.type_production, b.type_production),
                'Mise en place': _d(b.date_mise_en_place), 'Poussins': _n(b.effectif_initial), 'Effectif': _n(v['effectif_present']),
                'Âge': f'{v["age"]} j', 'Mortalité': _pct(v['mortalite'], 2), 'Poids moyen': _n(v['poids_moyen_g'], 0, ' g'),
                'IC': 'sans objet' if v.get('ponte') else _n(v['indice_consommation'], 2),
                'État': _badge('En cours', 'ok') if b.en_cours else _badge('Clôturée', 'off')}
        lignes.append(ligne(cell, str(b.id), lien=url_for('bandes.fiche', numero=b.numero), jour=b.date_mise_en_place,
                            archivee=not b.en_cours))
    return Tableau(lignes, vide='Aucune bande.')


def eleveur_saisies(user, bande):
    """Mes saisies · bande <code> : une ligne par jour saisi ; le clic ouvre la fiche du lot A1 (modifiable tant que la
    bande est ouverte)."""
    if bande is None:
        return Tableau([], vide='Aucune bande en cours.', titre='Mes saisies · bande —')
    saisies = sorted(bande.saisies, key=lambda s: s.date, reverse=True)
    pesees = {p.date: p for p in bande.pesees}
    sorties = {}
    for s in bande.sorties:
        sorties[s.date] = sorties.get(s.date, 0) + s.nombre
    infos = _fiche_lot_a1(saisies, user)
    lignes = []
    for s in saisies:
        p = pesees.get(s.date)
        aliments = ', '.join(a.produit.nom for a in s.aliments) or '—'
        auteur = db.session.get(Utilisateur, s.cree_par) if s.cree_par else None
        info = infos.get(s.id)
        cell = {'Jour': _d(s.date), 'Âge': str(ind.age(bande, s.date)), 'Morts': str(s.morts), 'Aliment': aliments,
                'Sacs': _n(s.sacs, 1), 'Pesée': _n(p.poids_moyen_g, 0, ' g') if p else '—',
                'Sorties': _n(sorties[s.date]) if s.date in sorties else '—',
                'Saisi par': 'agent' if s.saisi_par_agent else (auteur.nom_complet if auteur else 'éleveur'),
                'Modifiée': f'{info.nb} fois' if info is not None and info.nb else '—'}
        l = ligne(cell, str(s.id), lien=url_for('bandes.fiche', numero=bande.numero), jour=s.date)
        if info is not None:
            l['fiche_a1'] = info
        lignes.append(l)
    return Tableau(lignes, vide='Aucune saisie pour cette bande.', titre=f'Mes saisies · bande {bande.batiment.code}')


def eleveur_argent(user, fermes):
    """Mon argent mois par mois (12 mois) : recettes, dépenses, bénéfice, dépenses par poste."""
    from app.services import argent
    ids = [f.id for f in fermes]
    mvts = argent.mouvements(ids) if ids else []
    auj = date.today()
    mois = []
    for i in range(11, -1, -1):
        y, m = auj.year, auj.month - i
        while m <= 0:
            y, m = y - 1, m + 12
        mois.append((y, m))
    postes = {'Poussins': ('poussin',), 'Aliment': ('aliment',),
              'Vaccins et soins': ('vaccin', 'soin', 'médicament', 'veto', 'vétérinaire'),
              "Main-d'œuvre": ('main', 'salaire', 'ouvrier', 'personnel')}
    noms_mois = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    lignes = []
    for (y, m) in mois:
        rec = dep = autres = 0
        par_poste = {k: 0 for k in postes}
        for mv in mvts:
            if (mv['date'].year, mv['date'].month) != (y, m) or not mv['montant']:
                continue
            if mv['signe'] > 0:
                rec += mv['montant']
                continue
            dep += mv['montant']
            texte = mv['texte'].lower()
            if mv['genre'] == 'achat':
                texte = mv['objet'].lignes[0].produit.type.lower() + ' ' + texte
            else:
                texte = (getattr(mv['objet'], 'categorie', '') or '').lower() + ' ' + texte
            for k, mots in postes.items():
                if any(mot in texte for mot in mots):
                    par_poste[k] += mv['montant']
                    break
            else:
                autres += mv['montant']
        cell = {'Mois': f'{noms_mois[m - 1].capitalize()} {y}', 'Recettes': _n(rec), 'Dépenses': _n(dep), 'Bénéfice': _n(rec - dep),
                'Poussins': _n(par_poste['Poussins']), 'Aliment': _n(par_poste['Aliment']),
                'Vaccins et soins': _n(par_poste['Vaccins et soins']), "Main-d'œuvre": _n(par_poste["Main-d'œuvre"]), 'Autres': _n(autres)}
        lignes.append(ligne(cell, f'{y}-{m:02d}', lien=url_for('argent.mon_argent', periode='tout'), jour=date(y, m, 1)))
    return Tableau(lignes, vide='Aucun mouvement.', titre=f'Mon argent mois par mois · {auj.year} (FCFA)')


def eleveur_sante(user, fermes):
    """Ma santé des poulets : déclarations (signalements), traitements, vaccinations faites."""
    from app.models.sante import Declaration, Traitement, Vaccination, AlerteSanitaire
    from app.models.bande import Bande
    ids = [f.id for f in fermes]
    bandes = Bande.query.filter(Bande.ferme_id.in_(ids)).all() if ids else []
    bids = [b.id for b in bandes]
    lignes = []
    for d in (Declaration.query.filter(Declaration.ferme_id.in_(ids)).all() if ids else []):
        a = AlerteSanitaire.query.filter_by(declaration_id=d.id).first()
        r = a.reponses[-1] if a and a.reponses else None
        cell = {'Date': _d(_date_de(d.cree_le)), 'Bande': d.bande.numero if d.bande else '—', 'Quoi': '🤒 Poulet malade signalé',
                'Signes / produit': ', '.join(d.signes), 'Photos': str(len(d.photos)),
                'Réponse du vétérinaire': (r.texte or ', '.join(r.conseils)) if r else 'pas encore',
                'État': _badge(a.libelle_statut if a else 'Envoyé', 'ok' if a and a.statut in ('INFIRMEE', 'CLOSE') else 'warn')}
        lignes.append(ligne(cell, f'decl:{d.id}', lien=url_for('sante.mes_declarations'), jour=_date_de(d.cree_le)))
    for t in (Traitement.query.filter(Traitement.bande_id.in_(bids)).all() if bids else []):
        en_cours = t.date_fin >= date.today()
        cell = {'Date': _d(t.date_debut), 'Bande': t.bande.numero, 'Quoi': '💊 Traitement', 'Signes / produit': f'{t.produit.nom} · {t.motif}',
                'Photos': '—', 'Réponse du vétérinaire': '—', 'État': _badge('En cours' if en_cours else 'Terminé', 'info' if en_cours else 'off')}
        lignes.append(ligne(cell, f'trait:{t.id}', lien=url_for('eleveur.soins'), jour=t.date_debut))
    for v in (Vaccination.query.filter(Vaccination.bande_id.in_(bids)).all() if bids else []):
        cell = {'Date': _d(v.date), 'Bande': v.bande.numero, 'Quoi': '💉 Vaccin fait', 'Signes / produit': f'{v.produit.nom} ({v.mode.lower()})',
                'Photos': '—', 'Réponse du vétérinaire': '—', 'État': _badge('Fait', 'ok')}
        lignes.append(ligne(cell, f'vac:{v.id}', lien=url_for('eleveur.soins'), jour=v.date))
    lignes.sort(key=lambda l: l['date'] or '', reverse=True)
    return Tableau(lignes, vide='Rien à signaler ✓')


def eleveur_livraisons(user, fermes):
    from app.models.intrant import Livraison, StatutLivraison as S
    ids = [f.id for f in fermes]
    livs = Livraison.query.filter(Livraison.ferme_id.in_(ids)).order_by(Livraison.date_livraison.desc()).limit(300).all() if ids else []
    lignes = []
    for liv in livs:
        for l in liv.lignes:
            diff = None if l.quantite_recue is None else l.quantite_recue - l.quantite_livree
            cell = {'N°': liv.numero or '—', 'Article': l.produit.nom, 'Origine': liv.libelle_origine, 'Prévu': _n(l.quantite_livree, 1),
                    'Reçu': _n(l.quantite_recue, 1), 'Différence': ('0' if diff == 0 else _n(diff, 1)) if diff is not None else '—',
                    'Date': _d(liv.date_livraison),
                    'État': _badge(liv.libelle_statut, {'A_CONFIRMER': 'warn', 'PREVUE': 'neutre', 'RECUE': 'ok', 'RECUE_ECART': 'warn', 'ANNULEE': 'off'}.get(liv.statut, 'neutre'))}
            lignes.append(ligne(cell, f'{liv.id}:{l.id}',
                                lien=url_for('eleveur.produits') if liv.statut == S.A_CONFIRMER else url_for('livraisons.mes_livraisons'),
                                jour=liv.date_livraison, archivee=liv.statut == S.ANNULEE))
    return Tableau(lignes, vide='Aucune livraison.')


def eleveur_lots(user, lots, etat):
    lignes = []
    for lot in lots:
        s = lot.sortie
        e = etat(s)
        cell = {'Lot': _lien(url_for('tracabilite.lot', numero=lot.numero), lot.numero), 'Bande': s.bande.numero, 'Date': _d(s.date),
                'Poulets': _n(s.nombre), 'Poids': _n(s.poids_total_kg, 1, ' kg'), 'Destinataire': s.destinataire or '—',
                'QR': 'annulé' if lot.annule else _lien(url_for('tracabilite.etiquettes', numero=lot.numero), 'étiquettes'),
                'Suivi': e['texte'] if e else '—'}
        lignes.append(ligne(cell, str(lot.id), lien=url_for('tracabilite.lot', numero=lot.numero), jour=s.date, archivee=lot.annule))
    return Tableau(lignes, vide='Aucun lot.')


def eleveur_bceg(user, fermes):
    from app.models.bceg import ConsentementBceg, DecisionBceg
    ids = [f.id for f in fermes]
    lignes = []
    consentements = (ConsentementBceg.query.filter(ConsentementBceg.ferme_id.in_(ids))
                     .order_by(ConsentementBceg.cree_le.desc()).all() if ids else [])
    for c in consentements:
        qui = db.session.get(Utilisateur, c.utilisateur_id) if c.utilisateur_id else None
        voit = 'bandes, mortalité, production, argent de la ferme (12 mois)' if c.decision == DecisionBceg.ACCEPTE else 'rien'
        cell = {'Date': _d(_date_de(c.cree_le)),
                'Décision': _badge(DecisionBceg.LIBELLES.get(c.decision, c.decision), 'ok' if c.decision == DecisionBceg.ACCEPTE else 'off'),
                'Ce que la BCEG voit': voit, 'Par': qui.nom_complet if qui else 'système'}
        lignes.append(ligne(cell, str(c.id), jour=_date_de(c.cree_le)))
    return Tableau(lignes, vide="Aucune décision pour l'instant : votre ferme n'est pas financée par la BCEG, ou vous n'avez pas encore répondu.")


# ══════════════════════════════════════════════════════════════════════
# Agent (version ordinateur) — K3
# ══════════════════════════════════════════════════════════════════════

def agent_accueil(user, actions):
    lignes = []
    for a in actions:
        cell = {'N°': a.numero, 'Action': a.intitule, 'Ferme': a.libelle_perimetre, 'Demandée par': a.createur.nom_complet,
                'Échéance': _d(a.echeance), 'Priorité': a.priorite.lower(),
                'État': _badge(a.libelle_etat, 'danger' if a.etat == 'RETARD' else 'neutre')}
        lignes.append(ligne(cell, str(a.id), lien=url_for('actions.liste', etat=a.etat), jour=a.echeance, archivee=a.etat == 'FAITE'))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='AGENT-1'), choix={'Ferme': _fermes_choix(user)}, vide='Aucune action en cours.')


def agent_fermes(user, fermes, details, production, urgences):
    from app.models.bande import Bande, StatutBande
    from app.services import fermes as regles_fermes
    lignes = []
    for f in fermes:
        i = details[f.id]
        u = (urgences or {}).get(f.id) or {}
        bande = Bande.query.filter_by(ferme_id=f.id, statut=StatutBande.EN_COURS).order_by(Bande.date_mise_en_place.desc()).first()
        pr = production.get(f.id) or {}
        position = ('✓ relevée' + (f' (±{f.gps_precision_m} m)' if f.gps_precision_m else '')) if f.a_une_position else '📍 à relever'
        if f.position_a_verifier:
            position += ' · à vérifier'
        couleur = u.get('couleur')
        cell = {'N°': _lien(url_for('fermes.fiche', numero=f.numero), f.numero), 'Éleveur': f.exploitant_nom,
                'Bande en cours': bande.numero if bande else '—', 'Effectif': _n(i['effectif']), 'Mortalité': _pct(i['mortalite'], 2),
                'Dernière saisie': _d(i['derniere_saisie'], '%d/%m'), 'Atteinte': _pct(pr.get('atteinte'), 0), 'Position': position,
                'Urgence': _badge({'rouge': 'Urgent', 'orange': 'À surveiller', 'vert': 'OK'}.get(couleur, '—'),
                                  {'rouge': 'danger', 'orange': 'warn', 'vert': 'ok'}.get(couleur, 'neutre'))}
        peut = regles_fermes.peut_modifier(user, f)
        lignes.append(ligne(cell, str(f.id), valeurs={**{k: _texte(v) for k, v in cell.items()}, 'N°': f.numero, 'Éleveur': f.exploitant_nom},
                            action=url_for('bureau.fiche_conforme', cle='AGENT-2', ident=str(f.id)), droits=['modifier'] if peut else [],
                            pied=pied(f), titre=f'{f.numero} · {f.nom}', jour=_date_de(f.cree_le), province=f.province.nom))
    return Tableau(lignes, peut_modifier=True, vide='Aucune ferme.', titre=f'Mes {len(fermes)} ferme{"s" if len(fermes) != 1 else ""}')


def agent_enrolement(user, fermes):
    """Enrôlements récents : les fermes créées (90 jours), avec le compte de l'éleveur et l'état."""
    from app.models.utilisateur import UtilisateurFerme
    limite = date.today() - timedelta(days=90)
    lignes = []
    for f in fermes:
        cree = _date_de(f.cree_le)
        if cree and cree < limite:
            continue
        compte = UtilisateurFerme.query.filter_by(ferme_id=f.id).first()
        cell = {'Ferme': _lien(url_for('fermes.fiche', numero=f.numero), f'{f.numero} · {f.nom}'), 'Éleveur': f.exploitant_nom,
                'Province': f.province.nom, 'Programme': f.libelle_programme, 'Capacité': _n(f.capacite),
                'Position': '✓' if f.a_une_position else '📍 à relever',
                'Compte': compte.utilisateur.identifiant if compte and getattr(compte, 'utilisateur', None) else 'pas encore',
                'Le': _d(cree), 'État': _badge('Provisoire' if f.numero_provisoire else f.statut, 'warn' if f.numero_provisoire else 'ok')}
        lignes.append(ligne(cell, str(f.id), lien=url_for('fermes.fiche', numero=f.numero), jour=cree, province=f.province.nom))
    return Tableau(lignes, vide='Aucun enrôlement ces 90 derniers jours.')


def agent_tournee(user, lignes_tournee):
    lignes = []
    for i, l in enumerate(lignes_tournee, start=1):
        f, v, u = l['ferme'], l.get('visite'), l.get('urgence') or {}
        raisons = ' · '.join(t for _, t in (u.get('raisons') or [])) or (v.objet if v else '—')
        dist = l.get('distance_m')
        cell = {'Ordre': str(i), 'Ferme': _lien(url_for('fermes.fiche', numero=f.numero), f'{f.numero} · {f.nom}'), 'Raison': raisons,
                'Distance': _n(dist / 1000, 1, ' km') if dist else '—', 'À faire': v.objet if v else 'visite de contrôle',
                'Heure prévue': '—', 'État': _badge('Prévue' if v else 'Proposée', 'neutre' if v else 'warn')}
        lignes.append(ligne(cell, str(v.id) if v else f'f:{f.id}', lien=url_for('fermes.fiche', numero=f.numero), province=f.province.nom))
    jours = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    mois = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
    auj = date.today()
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='AGENT-4'), choix={'Ferme': _fermes_choix(user)},
                   vide="Rien de prévu aujourd'hui.", titre=f'Tournée du {jours[auj.weekday()]} {auj.day} {mois[auj.month - 1]}')


def agent_visites(user, visites, etat):
    lignes = []
    for v in visites:
        e = etat(v)
        presence = {'confirmee': '✓ sur place', 'eloignee': '⚠️ éloignée', 'sans_position': '—'}.get(e, '—')
        conseils = ', '.join(v.recommandations or [])
        if v.recommandation_libre:
            conseils = (conseils + ' · ' if conseils else '') + v.recommandation_libre
        cell = {'Date': _d(v.faite_le or v.date_prevue), 'Ferme': _lien(url_for('fermes.fiche', numero=v.ferme.numero), f'{v.ferme.numero} · {v.ferme.nom}'),
                'Objet': v.objet, 'Présence': presence, 'Constats': v.constats or '—', 'Conseils': conseils or '—',
                'Biosécurité': str(getattr(v, 'score_biosecurite', None) or '—'),
                'État': _badge({'PREVUE': 'Prévue', 'FAITE': 'Faite', 'ANNULEE': 'Annulée'}.get(v.statut, v.statut),
                               'ok' if v.statut == 'FAITE' else 'off' if v.statut == 'ANNULEE' else 'neutre')}
        droits = (['modifier'] + (['archiver'] if v.statut == 'PREVUE' else [])) if v.agent_id == user.id and v.statut != 'ANNULEE' else []
        lignes.append(ligne(cell, str(v.id), valeurs={**{k: _texte(x) for k, x in cell.items()}, 'Constats': v.constats or '',
                                                     'Conseils': v.recommandation_libre or ''},
                            action=url_for('bureau.fiche_conforme', cle='AGENT-5', ident=str(v.id)), droits=droits, pied=pied(v),
                            titre=f'Visite · {v.ferme.nom}', jour=v.faite_le or v.date_prevue, province=v.ferme.province.nom,
                            archivee=v.statut == 'ANNULEE'))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='AGENT-5'), choix={'Ferme': _fermes_choix(user)},
                   peut_modifier=True, peut_archiver=True, vide='Aucune visite.')


def agent_controle(user, conflits):
    from app.models.hors_ligne import GenreVerification as G, StatutVerification as SV
    genres = {G.MESSAGE: 'Saisie refusée', G.SAISIE_JOUR: 'Saisie du jour', G.LIVRAISON: 'Livraison', G.SORTIE: 'Sortie'}
    lignes = []
    for c in conflits:
        v = c.versions or []

        def version(i, v=v):
            if isinstance(v, list) and len(v) > i and isinstance(v[i], dict):
                return ' · '.join(f'{k} {val}' for k, val in v[i].items() if k != 'utilisateur_id')
            return '—'
        etat = 'À trancher' if c.a_trancher else ('Tranché' if c.statut == SV.TRANCHE else ('Vu' if c.vu_le else 'À voir'))
        cell = {'Ferme': f'{c.ferme.numero} · {c.ferme.nom}' if c.ferme else '—', 'Bande': c.bande.numero if c.bande else '—',
                'Jour': _d(_date_de(c.cree_le)), 'Donnée': genres.get(c.genre, c.genre), 'Version éleveur': version(0), 'Ma version': version(1),
                'Écart': c.quoi, 'Depuis': _d(_date_de(c.cree_le), '%d/%m %H:%M'), 'État': _badge(etat, 'warn' if c.a_trancher else 'ok')}
        lignes.append(ligne(cell, str(c.id), valeurs={**{k: _texte(x) for k, x in cell.items()}, 'Détail': c.detail},
                            action=url_for('bureau.fiche_conforme', cle='AGENT-6', ident=str(c.id)), droits=['modifier'] if c.a_trancher else [],
                            pied=pied(c), titre=f'Vérification · {c.quoi}', jour=_date_de(c.cree_le),
                            province=c.ferme.province.nom if c.ferme else None, archivee=not c.a_trancher and c.statut == SV.TRANCHE))
    choix = {'État': [('0', 'Garder la version de l’éleveur'), ('1', 'Garder ma version')], 'Ferme': _fermes_choix(user)}
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='AGENT-6'), choix=choix, peut_modifier=True,
                   colonnes_en_plus=('Détail',), noms={'État': 'choix'}, vide='Aucune saisie à vérifier ✓')


def agent_stocks(user, fermes):
    from app.services import intrants
    lignes = []
    for f in fermes:
        for r in intrants.stock_ferme(f):
            for origine, recu, utilise, reste in (('Programme', r['etat'], r['utilise_programme'], r['programme']),
                                                  ('Achat', r['achat'], r['utilise_externe'], r['externe'])):
                if not recu and not utilise:
                    continue
                cell = {'Ferme': f'{f.numero} · {f.nom}', 'Article': r['produit'].nom, 'Origine': origine, 'Reçu': _n(recu, 1),
                        'Utilisé': _n(utilise, 1), 'Reste': _n(reste, 1), 'Écart': '—'}
                lignes.append(ligne(cell, f'{f.id}:{r["produit"].id}:{origine}', lien=url_for('terrain.stock', ferme=f.numero),
                                    province=f.province.nom))
    return Tableau(lignes, vide='Aucun stock.')


def _visite(ident, user, form, action):
    from app.models.visite import Visite
    from app.services import visites as regles
    import uuid
    v = db.session.get(Visite, uuid.UUID(ident))
    if v is None or v.agent_id != user.id:
        raise RegleConformite('Vous ne pouvez modifier que vos comptes rendus.')
    if action == 'archiver':
        regles.annuler(v, form.get('motif') or 'archivée depuis la liste des visites', user)
        return 'Visite archivée.'
    from app.services.journal import enregistrer, Action as J
    avant = f'{v.objet} · {v.constats or "—"}'
    if form.get('Objet'):
        v.objet = form['Objet'][:60]
    if 'Constats' in form:
        v.constats = (form.get('Constats') or '')[:500] or None
    if 'Conseils' in form:
        v.recommandation_libre = (form.get('Conseils') or '')[:300] or None
    enregistrer(J.MODIFICATION, table='visite', enregistrement_id=v.id,
                detail=f'Visite modifiée (liste) : {avant} → {v.objet} · {v.constats or "—"}')
    return 'Compte rendu enregistré.'


GESTES['AGENT-5'] = _visite


def _planifier_visite(user, form):
    """AGENT 1 / 4 : « ＋ Nouvelle visite », « ＋ Planifier une tournée » : une visite prévue (ferme, date, objet)."""
    from app.services import visites as regles
    f = _ferme_du_form(form, user)
    jour = form.get('Échéance') or form.get('Heure prévue') or form.get('Date') or form.get('date')
    try:
        jour = date.fromisoformat(jour) if jour else None
    except ValueError:
        raise RegleConformite('La date est au format AAAA-MM-JJ.')
    objet = (form.get('Action') or form.get('À faire') or form.get('Objet') or form.get('Raison') or 'Visite de contrôle').strip()
    try:
        v = regles.planifier(f, jour, objet, user)
    except regles.RegleVisite as e:
        raise RegleConformite(str(e))
    from app.services.journal import enregistrer, Action as J
    enregistrer(J.CREATION, table='visite', enregistrement_id=v.id, detail=f'Visite prévue le {jour:%d/%m/%Y} · {f.numero} · {objet} ({user.nom_complet})')
    return f'Visite prévue le {jour:%d/%m/%Y} à {f.numero}.'


def _compte_rendu(user, form):
    """AGENT 5 : « ＋ Nouveau compte rendu » depuis l'ordinateur (sans position : présence « — »)."""
    from app.services import visites as regles
    f = _ferme_du_form(form, user)
    jour = form.get('Date')
    try:
        jour = date.fromisoformat(jour) if jour else date.today()
    except ValueError:
        raise RegleConformite('La date est au format AAAA-MM-JJ.')
    try:
        v = regles.compte_rendu(f, None, user, (form.get('Objet') or 'Visite de contrôle').strip(), form.get('Constats'), [],
                                form.get('Conseils'), None, None, None, jour)
    except regles.RegleVisite as e:
        raise RegleConformite(str(e))
    return 'Compte rendu enregistré.'


CREATIONS['AGENT-1'] = _planifier_visite
CREATIONS['AGENT-4'] = _planifier_visite
CREATIONS['AGENT-5'] = _compte_rendu


# ══════════════════════════════════════════════════════════════════════
# Administrateur — K2
# ══════════════════════════════════════════════════════════════════════

def _journal_cle(j):
    from app.models.securite import JournalChaine
    c = db.session.get(JournalChaine, j.id) if j.id else None
    return (c.empreinte[:8] + '…') if c and c.empreinte else '—'


def admin_accueil(user):
    """Événements nécessitant une intervention : échecs de connexion répétés, comptes bloqués, propositions en
    attente, sessions anciennes, chaîne du journal rompue."""
    from app.models import JournalAudit
    from app.models.securite import Proposition
    from app.services.journal import Action as J, verifier_chaine
    from app.services import securite
    lignes = []
    depuis = maintenant() - timedelta(days=7)
    for u in Utilisateur.query.filter(Utilisateur.bloque_jusqu_a.isnot(None)).all():
        lignes.append(ligne({'Événement': '🔒 Compte bloqué (échecs de connexion)', 'Gravité': _badge('haute', 'danger'), 'Qui': u.nom_complet,
                             'Profil': u.profil.libelle, 'Appareil': '—', 'Quand': _d(_date_de(u.bloque_jusqu_a), '%d/%m %H:%M'),
                             'État': _badge('À traiter', 'warn')}, f'bloque:{u.id}', lien=url_for('utilisateurs.index'), jour=_date_de(u.bloque_jusqu_a)))
    echecs = {}
    for j in JournalAudit.query.filter(JournalAudit.action == J.ECHEC_CONNEXION, JournalAudit.horodatage >= depuis):
        echecs.setdefault(j.identifiant or '?', []).append(j)
    for ident, js in echecs.items():
        if len(js) >= 3:
            lignes.append(ligne({'Événement': f'⚠️ {len(js)} échecs de connexion en 7 jours', 'Gravité': _badge('moyenne', 'warn'), 'Qui': ident,
                                 'Profil': '—', 'Appareil': js[-1].adresse_ip or '—', 'Quand': _d(_date_de(js[-1].horodatage), '%d/%m %H:%M'),
                                 'État': _badge('À surveiller', 'neutre')}, f'echecs:{ident}', lien=url_for('journal.index', action=J.ECHEC_CONNEXION),
                                jour=_date_de(js[-1].horodatage)))
    for p in Proposition.query.filter_by(statut='EN_ATTENTE'):
        lignes.append(ligne({'Événement': f'👀 Proposition à approuver · {p.libelle}', 'Gravité': _badge('moyenne', 'warn'), 'Qui': p.auteur.nom_complet,
                             'Profil': p.auteur.profil.libelle, 'Appareil': '—', 'Quand': _d(_date_de(p.propose_le), '%d/%m %H:%M'),
                             'État': _badge('En attente', 'warn')}, f'prop:{p.id}', lien=url_for('controle.approbations_ecran'), jour=_date_de(p.propose_le)))
    for s in securite.ouvertes():
        age = _heures_depuis(s.derniere_activite)
        if age > 24:
            u = db.session.get(Utilisateur, s.utilisateur_id)
            lignes.append(ligne({'Événement': '🔐 Session ouverte depuis plus de 24 h', 'Gravité': _badge('basse', 'neutre'),
                                 'Qui': u.nom_complet if u else '—', 'Profil': u.profil.libelle if u else '—', 'Appareil': (s.appareil or '—')[:40],
                                 'Quand': _d(_date_de(s.derniere_activite), '%d/%m %H:%M'), 'État': _badge('À fermer ?', 'neutre')},
                                f'session:{s.id}', lien=url_for('controle.sessions'), jour=_date_de(s.derniere_activite)))
    try:
        intact, n, rompue = verifier_chaine()
    except Exception:
        intact, n, rompue = True, 0, None
    if not intact:
        lignes.append(ligne({'Événement': '⛓️ Chaîne du journal rompue', 'Gravité': _badge('critique', 'danger'), 'Qui': 'système', 'Profil': '—',
                             'Appareil': '—', 'Quand': _d(date.today()), 'État': _badge('À traiter', 'danger')}, 'chaine', lien=url_for('controle.integrite')))
    lignes.sort(key=lambda l: l['date'] or '', reverse=True)
    return Tableau(lignes, vide='Aucun événement à traiter ✓')


def admin_utilisateurs(user, utilisateurs):
    from app.services import securite
    exige = securite.profils_obligatoires()
    lignes = []
    for u in utilisateurs:
        perimetre = 'national' if u.est_national else (', '.join(p.nom for p in u.provinces) or ('ferme(s) : ' + ', '.join(f.ferme.numero for f in u.fermes) if u.fermes else '—'))
        bloque = u.bloque_jusqu_a is not None
        cell = {'Nom': u.nom_complet, 'Identifiant': u.identifiant, 'Profil': u.profil.libelle, 'Périmètre': perimetre, 'Téléphone': u.telephone or '—',
                '2FA': '✓ active' if u.totp_active else ('exigée' if u.profil.value in exige else '—'),
                'Dernière connexion': _d(_date_de(u.derniere_connexion), '%d/%m/%Y %H:%M') if u.derniere_connexion else '—',
                'Échecs': str(u.echecs_connexion or 0) + (' · bloqué' if bloque else ''),
                'État': _badge('Actif' if u.actif else '🗄️ Archivé', 'ok' if u.actif else 'off'), 'Créé le': _d(_date_de(getattr(u, 'cree_le', None)))}
        valeurs = {**{k: _texte(v) for k, v in cell.items()}, 'Profil': u.profil.value, 'État': 'actif' if u.actif else 'inactif',
                   '2FA': 'reinitialiser' if u.totp_active else ''}
        droits = ['modifier', 'archiver'] if u.actif and u.id != user.id else (['modifier'] if u.id != user.id else [])
        lignes.append(ligne(cell, str(u.id), valeurs=valeurs, action=url_for('bureau.fiche_conforme', cle='ADMIN-2', ident=str(u.id)),
                            droits=droits, pied=pied(u), titre=f'{u.identifiant} · {u.nom_complet}', jour=_date_de(getattr(u, 'cree_le', None)),
                            archivee=not u.actif))
    choix = {'Profil': [(p.value, p.libelle) for p in Profil], 'État': [('actif', 'Actif'), ('inactif', 'Archivé (désactivé)'), ('debloquer', 'Débloquer (échecs remis à zéro)')],
             '2FA': [('', 'Inchangée'), ('reinitialiser', 'Réinitialiser la 2FA')]}
    return Tableau(lignes, creation=url_for('utilisateurs.index') + '#nouveau', choix=choix, peut_modifier=True, peut_archiver=True,
                   noms={'Nom': 'nom', 'Identifiant': 'identifiant', 'Téléphone': 'telephone'}, vide='Aucun compte.')


def admin_droits(user):
    """Profils et permissions : une ligne par profil, lue dans le code (registre des fonctions et droits des routes)."""
    from app.services.bureau import FONCTIONS
    from app.services import securite
    from flask import current_app
    from app.routes.bureau import _profils_de
    exige = securite.profils_obligatoires()
    saisir, valider, consulter = {}, {}, {}
    for regle in current_app.url_map.iter_rules():
        vue = current_app.view_functions.get(regle.endpoint)
        profils, login = _profils_de(vue) if vue else (None, False)
        for p in (profils or ()):
            if 'POST' in regle.methods:
                (valider if any(m in regle.rule for m in ('approuv', 'valid', 'decid', 'tranch', 'confirm')) else saisir).setdefault(p, set()).add(regle.rule)
            else:
                consulter.setdefault(p, set()).add(regle.rule)
    comptes = {}
    for u in Utilisateur.query.filter_by(actif=True):
        comptes[u.profil] = comptes.get(u.profil, 0) + 1
    lignes = []
    for p in Profil:
        fonctions = ', '.join(f[2] for f in FONCTIONS.get(p, [])) or '—'
        perimetre = 'national' if p in (Profil.ADMIN, Profil.DGE, Profil.MAEDR, Profil.AUDITEUR) else ('province(s)' if p in (Profil.AGENT, Profil.VETO) else 'ses fermes' if p == Profil.ELEVEUR else 'son établissement' if p == Profil.OPERATEUR else 'fermes financées (avec accord)')
        cell = {'Profil': p.libelle, 'Comptes': str(comptes.get(p, 0)), 'Périmètre': perimetre, 'Fonctionnalités': fonctions,
                'Saisir': str(len(saisir.get(p, ()))), 'Valider': str(len(valider.get(p, ()))), 'Consulter': str(len(consulter.get(p, ()))),
                '2FA': 'exigée' if p.value in exige else 'facultative', 'Modifié le': '—'}
        lignes.append(ligne(cell, p.value, lien=url_for('bureau.droits', profil=p.value)))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='ADMIN-3'), vide='—')


def admin_parametres(user):
    """Paramètres, listes, catalogues et référentiels : une ligne par élément (paramètre, valeur de liste, article)."""
    from app.models import Parametre, Produit
    from app.models.liste_deroulante import ListeDeroulante
    from app.services.approbations import SENSIBLES
    lignes = []
    for p in Parametre.query.order_by(Parametre.cle):
        sensible = any(p.cle.startswith(s) for s in SENSIBLES) if isinstance(SENSIBLES, (tuple, list, set)) else p.cle in SENSIBLES
        qui = db.session.get(Utilisateur, p.modifie_par) if p.modifie_par else None
        unite = {'POURCENT': '%', 'JOURS': 'jours', 'HEURES': 'h'}.get(p.type.value if hasattr(p.type, 'value') else str(p.type), '')
        cell = {'Élément': p.description or p.cle, 'Catégorie': 'Paramètre · ' + p.cle.split('.')[0], 'Valeur': p.valeur, 'Unité': unite or '—',
                'Sensible': 'oui (quatre yeux)' if sensible else 'non', 'Modifié par': qui.nom_complet if qui else '—', 'Le': _d(_date_de(p.modifie_le))}
        lignes.append(ligne(cell, f'param:{p.cle}', valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Motif': ''},
                            action=url_for('bureau.fiche_conforme', cle='ADMIN-4', ident=f'param:{p.cle}'), droits=['modifier'],
                            pied='quatre yeux si sensible · inscrit au journal', titre=p.description or p.cle, jour=_date_de(p.modifie_le)))
    for l in ListeDeroulante.query.order_by(ListeDeroulante.categorie, ListeDeroulante.ordre):
        cell = {'Élément': l.valeur, 'Catégorie': 'Liste · ' + l.categorie, 'Valeur': l.valeur, 'Unité': '—', 'Sensible': 'non', 'Modifié par': '—', 'Le': '—'}
        lignes.append(ligne(cell, f'liste:{l.id}', valeurs={**{k: _texte(v) for k, v in cell.items()}},
                            action=url_for('bureau.fiche_conforme', cle='ADMIN-4', ident=f'liste:{l.id}'), droits=['modifier', 'archiver'],
                            pied='inscrit au journal', titre=f'{l.categorie} · {l.valeur}', archivee=not getattr(l, 'actif', True)))
    for a in Produit.query.order_by(Produit.type, Produit.nom):
        cell = {'Élément': a.nom, 'Catégorie': 'Catalogue · ' + a.type, 'Valeur': a.conditionnement or '—', 'Unité': a.unite, 'Sensible': 'non',
                'Modifié par': '—', 'Le': _d(_date_de(a.modifie_le))}
        lignes.append(ligne(cell, f'article:{a.id}', lien=url_for('catalogue.index'), jour=_date_de(a.modifie_le), archivee=a.archive_le is not None))
    return Tableau(lignes, creation=url_for('parametres.index'), peut_modifier=True, peut_archiver=True, colonnes_en_plus=('Motif',),
                   vide='Aucun paramètre.')


def admin_sessions(user, sessions):
    from app.services import securite, parametres
    duree = int(parametres.obtenir('securite.duree_session_minutes', 30))
    lignes = []
    for s in sessions:
        u = db.session.get(Utilisateur, s.utilisateur_id)
        expire = s.derniere_activite + timedelta(minutes=duree) if u and securite.expire_par_inactivite(u) else None
        cell = {'Utilisateur': u.nom_complet if u else '—', 'Profil': u.profil.libelle if u else '—', 'Appareil': (s.appareil or '—')[:60],
                'Adresse': s.adresse_ip or '—', 'Ouverte': _d(_date_de(s.ouverte_le), '%d/%m %H:%M'),
                'Dernière activité': _d(_date_de(s.derniere_activite), '%d/%m %H:%M'),
                'Expire': _d(_date_de(expire), '%d/%m %H:%M') if expire else 'jamais (terrain)',
                '2FA': '✓' if u and u.totp_active else '—', 'État': _badge('Ouverte', 'ok')}
        lignes.append(ligne(cell, s.id, valeurs={**{k: _texte(v) for k, v in cell.items()}, 'Motif': ''},
                            action=url_for('bureau.fiche_conforme', cle='ADMIN-6', ident=s.id), droits=['modifier'] if s.id != flask_session_id() else [],
                            pied='la fermeture est inscrite au journal', titre=f'Session · {u.nom_complet if u else "?"}', jour=_date_de(s.ouverte_le)))
    return Tableau(lignes, creation=url_for('bureau.creation_conforme', cle='ADMIN-6'), choix={'Utilisateur': [(str(u.id), u.nom_complet) for u in Utilisateur.query.filter_by(actif=True).order_by(Utilisateur.nom)]},
                   peut_modifier=True, colonnes_en_plus=('Motif',), vide='Aucune session ouverte.', libelle_modifier='Fermer la session')


def flask_session_id():
    from flask import session
    return session.get('sid')


def journal(user, entrees, cle):
    from app.services.journal import Action as J
    lignes = []
    for j in entrees:
        u = db.session.get(Utilisateur, j.utilisateur_id) if j.utilisateur_id else None
        cell = {'Quand': _d(_date_de(j.horodatage), '%d/%m/%Y %H:%M'), 'Qui': j.identifiant or (u.identifiant if u else 'système'),
                'Profil': u.profil.libelle if u else '—', 'Action': J.LIBELLES.get(j.action, j.action), 'Objet': ' · '.join(x for x in (j.table_nom, j.enregistrement_id) if x) or '—',
                'Avant': (str(j.avant)[:80] if j.avant else '—'), 'Après': (str(j.apres)[:80] if j.apres else '—'), 'Adresse': j.adresse_ip or '—',
                'Chaîne': _journal_cle(j)}
        if cle.startswith('AUDITEUR'):
            cell['Objet'] = ((j.detail or '')[:120]) or cell['Objet']
        lignes.append(ligne(cell, str(j.id), lien=url_for('journal.detail', ligne_id=j.id), jour=_date_de(j.horodatage)))
    return Tableau(lignes, vide='Aucune entrée.')


# ══════════════════════════════════════════════════════════════════════
# Auditeur — K2
# ══════════════════════════════════════════════════════════════════════

def auditeur_verifications(user, limite=50):
    """Dernières vérifications de la chaîne (chacune est inscrite au journal : table « journal », action VERIFICATION)."""
    from app.models import JournalAudit
    from app.services.journal import Action as J
    import re
    lignes = []
    for j in JournalAudit.query.filter(JournalAudit.table_nom == 'journal', JournalAudit.action == J.VERIFICATION).order_by(JournalAudit.horodatage.desc()).limit(limite):
        m = re.search(r'(\d[\d ]*) entrée', j.detail or '')
        intact = 'intacte' in (j.detail or '')
        cell = {'Quand': _d(_date_de(j.horodatage), '%d/%m/%Y %H:%M'), 'Résultat': _badge('Chaîne intacte' if intact else 'Chaîne rompue', 'ok' if intact else 'danger'),
                'Entrées': m.group(1) if m else '—'}
        lignes.append(ligne(cell, str(j.id), lien=url_for('controle.integrite'), jour=_date_de(j.horodatage)))
    return Tableau(lignes, vide='Aucune vérification enregistrée : « ＋ Lancer une vérification ».')


def auditeur_scans(user, scans):
    from app.models.tracabilite import ResultatScan
    lignes = []
    for s in scans:
        cell = {'Quand': _d(_date_de(s.horodatage), '%d/%m/%Y %H:%M'), 'Opérateur': s.operateur.nom if s.operateur else '—',
                'Lot': s.lot.numero if s.lot else (s.saisie or '—'),
                'Résultat': _badge(ResultatScan.LIBELLES.get(s.resultat, s.resultat), {'VERT': 'ok', 'ORANGE': 'warn'}.get(s.resultat, 'danger'))}
        lignes.append(ligne(cell, str(s.id), lien=url_for('tracabilite.lot', numero=s.lot.numero) if s.lot else None, jour=_date_de(s.horodatage)))
    return Tableau(lignes, vide='Aucun scan.')


def auditeur_exports(user, entrees):
    lignes = []
    for j in entrees:
        cell = {'Quand': _d(_date_de(j.horodatage), '%d/%m/%Y %H:%M'), 'Qui': j.identifiant or '—', 'Contenu': (j.detail or '')[:160]}
        lignes.append(ligne(cell, str(j.id), lien=url_for('journal.detail', ligne_id=j.id), jour=_date_de(j.horodatage)))
    return Tableau(lignes, vide='Aucun export.')


def auditeur_recherche(user, q, entrees):
    lignes = []
    for j in entrees:
        cell = {'Critère': q, 'Résultats': f'{_d(_date_de(j.horodatage), "%d/%m %H:%M")} · {j.identifiant or "—"} · {j.action} · {(j.detail or "")[:100]}'}
        lignes.append(ligne(cell, str(j.id), lien=url_for('journal.detail', ligne_id=j.id), jour=_date_de(j.horodatage)))
    return Tableau(lignes, vide='Tapez un identifiant, un numéro de lot ou de ferme dans « ＋ Nouvelle recherche ».' if not q else 'Aucun résultat.')


# ── Gestes K2 ────────────────────────────────────────────────────────────

def _utilisateur(ident, user, form, action):
    import uuid
    from app.services import securite
    from app.services.journal import enregistrer, Action as J
    u = db.session.get(Utilisateur, uuid.UUID(ident))
    if u is None or user.profil != Profil.ADMIN or u.id == user.id:
        raise RegleConformite('Vous ne pouvez pas modifier ce compte.')
    if action == 'archiver':
        u.actif = False
        for s in securite.ouvertes(u.id):
            securite.fermer(s.id, user, 'Compte désactivé')
        enregistrer(J.MODIFICATION, table='utilisateur', enregistrement_id=u.id, detail=f'Compte {u.identifiant} désactivé par {user.nom_complet}')
        return f'Compte {u.identifiant} désactivé.'
    avant = f'{u.nom_complet} · {u.profil.value} · {u.telephone or "—"} · {"actif" if u.actif else "inactif"}'
    if form.get('nom', '').strip():
        u.nom = form['nom'].strip()[:120]
    if form.get('telephone') is not None:
        u.telephone = (form.get('telephone') or '').strip()[:30] or None
    etat = form.get('État')
    if etat == 'actif':
        u.actif = True
    elif etat == 'inactif':
        u.actif = False
    elif etat == 'debloquer':
        u.bloque_jusqu_a, u.echecs_connexion = None, 0
    if form.get('2FA') == 'reinitialiser':
        u.totp_secret, u.totp_active, u.codes_secours = None, False, None
    if form.get('Profil') in Profil.__members__ and form['Profil'] != u.profil.value:
        from app.services import approbations
        approbations.proposer('PROFIL', str(u.id), f'Profil de {u.identifiant}', u.profil.value, form['Profil'],
                              {'utilisateur_id': str(u.id), 'profil': form['Profil']}, form.get('Motif') or 'changement de profil (liste des comptes)', user)
        enregistrer(J.MODIFICATION, table='utilisateur', enregistrement_id=u.id, detail=f'Compte {u.identifiant} modifié : {avant} → changement de profil proposé (quatre yeux)')
        return 'Changement de profil proposé : il s’appliquera après approbation par une autre personne.'
    enregistrer(J.MODIFICATION, table='utilisateur', enregistrement_id=u.id,
                detail=f'Compte {u.identifiant} modifié (liste) : {avant} → {u.nom_complet} · {u.profil.value} · {u.telephone or "—"} · {"actif" if u.actif else "inactif"}')
    return f'Compte {u.identifiant} enregistré.'


def _parametre_admin(ident, user, form, action):
    from app.models import Parametre
    from app.models.liste_deroulante import ListeDeroulante
    from app.services import approbations, parametres as regles
    from app.services.approbations import SENSIBLES
    from app.services.journal import enregistrer, Action as J
    genre, _, cle = ident.partition(':')
    if genre == 'param':
        p = Parametre.query.filter_by(cle=cle).first()
        if p is None:
            raise RegleConformite('Paramètre introuvable.')
        apres = (form.get('Valeur') or '').strip()
        if not apres:
            raise RegleConformite('Indiquez la valeur.')
        sensible = any(p.cle.startswith(s) for s in SENSIBLES) if isinstance(SENSIBLES, (tuple, list, set)) else p.cle in SENSIBLES
        if sensible:
            approbations.proposer('PARAMETRE', p.cle, p.description or p.cle, p.valeur, apres, {'cle': p.cle, 'valeur': apres},
                                  form.get('Motif') or 'modification depuis la liste des paramètres', user)
            return 'Paramètre sensible : proposition enregistrée, à approuver par une autre personne.'
        avant = p.valeur
        p.valeur, p.modifie_par, p.modifie_le = apres, user.id, maintenant()
        regles.oublier_cache()
        enregistrer(J.MODIFICATION, table='parametre', enregistrement_id=p.id, detail=f'{p.cle} : {avant} → {apres} ({user.nom_complet})')
        return 'Paramètre enregistré.'
    if genre == 'liste':
        l = db.session.get(ListeDeroulante, int(cle))
        if l is None:
            raise RegleConformite('Valeur introuvable.')
        if action == 'archiver':
            if hasattr(l, 'actif'):
                l.actif = False
            elif hasattr(l, 'archive_le'):
                l.archive_le = maintenant()
            enregistrer(J.ARCHIVAGE, table='liste_deroulante', enregistrement_id=l.id, detail=f'Valeur « {l.valeur} » ({l.categorie}) archivée par {user.nom_complet}')
            return 'Valeur archivée.'
        v = (form.get('Valeur') or form.get('Élément') or '').strip()
        if not v:
            raise RegleConformite('Indiquez la valeur.')
        avant = l.valeur
        l.valeur = v[:120]
        enregistrer(J.MODIFICATION, table='liste_deroulante', enregistrement_id=l.id, detail=f'{l.categorie} : « {avant} » → « {l.valeur} » ({user.nom_complet})')
        return 'Valeur enregistrée.'
    raise RegleConformite('Les articles du catalogue se modifient dans le catalogue.')


def _session(ident, user, form, action):
    from app.services import securite
    from app.services.journal import enregistrer, Action as J
    if user.profil != Profil.ADMIN:
        raise RegleConformite('Réservé à l’administrateur.')
    if ident == flask_session_id():
        raise RegleConformite('Vous ne fermez pas votre propre session ici : déconnectez-vous.')
    securite.fermer(ident, user, (form.get('Motif') or 'fermée par l’administrateur')[:200])
    enregistrer(J.DECONNEXION, table='session_utilisateur', enregistrement_id=ident, detail=f'Session fermée par {user.nom_complet}')
    return 'Session fermée.'


def _fermer_sessions_compte(user, form):
    """ADMIN 6 : « ＋ Fermer les sessions d'un compte »."""
    import uuid
    from app.services import securite
    from app.services.journal import enregistrer, Action as J
    ident = form.get('Utilisateur')
    try:
        u = db.session.get(Utilisateur, uuid.UUID(ident)) if ident else None
    except ValueError:
        u = None
    if u is None:
        raise RegleConformite('Choisissez le compte.')
    n = 0
    for s in securite.ouvertes(u.id):
        if s.id != flask_session_id():
            securite.fermer(s.id, user, (form.get('Motif') or 'fermeture par l’administrateur')[:200])
            n += 1
    enregistrer(J.DECONNEXION, table='session_utilisateur', detail=f'{n} session(s) de {u.identifiant} fermée(s) par {user.nom_complet}')
    return f'{n} session(s) fermée(s).'


def _proposer_droits(user, form):
    """ADMIN 3 : « ＋ Proposer un changement de droits » : proposition quatre yeux (genre PROFIL), appliquée à la main."""
    from app.services import approbations
    profil = form.get('Profil') or ''
    quoi = ' · '.join(f'{k} : {form.get(k)}' for k in ('Périmètre', 'Saisir', 'Valider', 'Consulter', '2FA') if form.get(k))
    if not profil or not quoi:
        raise RegleConformite('Indiquez le profil et le changement demandé.')
    approbations.proposer('PROFIL', f'droits:{profil}', f'Droits du profil {profil}', '—', quoi, {'profil': profil, 'changement': quoi},
                          form.get('Motif') or 'changement de droits', user)
    return 'Proposition enregistrée : elle sera appliquée après approbation.'


def _lancer_verification(user, form):
    """AUDITEUR 1 / 3 : « ＋ Lancer une vérification » : contrôle de la chaîne, résultat inscrit au journal."""
    from app.services.journal import enregistrer, Action as J, verifier_chaine
    intact, n, rompue = verifier_chaine()
    enregistrer(J.VERIFICATION, table='journal', detail=f'Vérification de la chaîne du journal : {"intacte" if intact else "ROMPUE à l’entrée " + str(rompue.id)} · {n} entrées')
    return f'Chaîne {"intacte" if intact else "rompue"} · {n} entrées vérifiées.'


GESTES.update({'ADMIN-2': _utilisateur, 'ADMIN-4': _parametre_admin, 'ADMIN-6': _session})
CREATIONS.update({'ADMIN-6': _fermer_sessions_compte, 'ADMIN-3': _proposer_droits, 'AUDITEUR-1': _lancer_verification, 'AUDITEUR-3': _lancer_verification})
