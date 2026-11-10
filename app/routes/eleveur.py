"""Espace de l'éleveur (lot 9) : accueil en tuiles, « Saisie du jour », accès directs
(Peser, Sortie, Poulet malade, Vaccins), « Mon stock », « J'ai acheté ».
Les écrans eux-mêmes sont ceux des lots 2 à 8 : ici on organise l'accès."""
import re
from datetime import date

from flask import (Blueprint, render_template, request, redirect, url_for, flash, abort, session,
                   send_file)
from flask_login import current_user

from app import db, indicateurs
from app.models import Ferme, Profil, Livraison, Produit
from app.models.bande import Bande, StatutBande
from app.models.base import maintenant
from app.models.intrant import StatutLivraison, OrigineLivraison
from app.services import bandes as regles_bandes, intrants, sante
from app.utils import terrain as style
from app.utils.dates import en_utc
from app.utils.permissions import profil_requis, filtre_perimetre

eleveur_bp = Blueprint('eleveur', __name__)

ORDRE_FEU = {'gris': 0, 'vert': 1, 'orange': 2, 'rouge': 3}


def _fermes():
    return filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()


def bandes_en_cours():
    """Bandes en cours de l'éleveur (ou de l'agent), rangées par ferme puis bâtiment."""
    bandes = filtre_perimetre(Bande.query).filter(Bande.statut == StatutBande.EN_COURS).all()
    return sorted(bandes, key=lambda b: (b.ferme.numero, b.batiment.code))


def _situation(bandes):
    """Pour chaque bande en cours : feu, âge, saisie du jour faite ou non, prochaine pesée, vaccins."""
    auj = date.today()
    resultat = []
    for b in bandes:
        v = indicateurs.calculer(b)
        couleur, raison = indicateurs.feu(b, valeurs=v)
        resultat.append({'bande': b, 'code': b.batiment.code, 'age': v['age'], 'couleur': couleur, 'raison': raison,
                         'a_saisir': indicateurs.saisie_du(b, auj) is None and v['effectif_present'] > 0,
                         'pesee': indicateurs.prochaine_pesee(b), 'present': v['effectif_present'],
                         'vaccins': sante.vaccins_de_la_bande(b)})
    return resultat


A_FAIRE_VACCIN = ('retard', 'aujourdhui', 'a_faire')


def vaccins_a_faire(sit, avec_demain=True):
    """Vaccins en retard, du jour (et de demain) : de quoi valider « ✓ C'est fait » d'un toucher
    (vaccin, mode, poulets présents, doses : comme l'écran du vaccin du lot 4)."""
    etats = A_FAIRE_VACCIN + (('demain',) if avec_demain else ())
    liste = []
    for s in sit:
        for v in s['vaccins']:
            if v['etat'] not in etats:
                continue
            c = v['calendrier']
            liste.append({'bande': s['bande'], 'code': s['code'], 'calendrier': c, 'prevu': v['prevu'],
                          'etat': v['etat'], 'nombre': s['present'],
                          'quantite': s['present'] if c.produit.unite == 'doses' else 1})
    ordre = {'retard': 0, 'a_faire': 1, 'aujourdhui': 2, 'demain': 3}
    return sorted(liste, key=lambda x: (ordre[x['etat']], x['prevu'], x['code']))


def accueil(user):
    """Accueil en 8 tuiles (lot 11) : ordre FIXE, les tuiles ne disparaissent plus."""
    fermes = _fermes()
    sit = _situation(bandes_en_cours())
    auj = date.today()
    pire = max((s['couleur'] for s in sit), key=lambda c: ORDRE_FEU[c], default='gris')
    attention = [s['code'] for s in sit if s['couleur'] in ('orange', 'rouge')]
    if not sit:
        etat = 'Aucune bande en cours'
    elif attention:
        etat = f'{", ".join(attention)} demande{"nt" if len(attention) > 1 else ""} votre attention'
    else:
        etat = f'{len(sit)} bâtiment{"s" if len(sit) > 1 else ""} · tout va bien'
    a_saisir = [s['code'] for s in sit if s['a_saisir']]
    livraisons = (intrants.livraisons_de_l_etat(filtre_perimetre(Livraison.query))
                  .filter(Livraison.statut == StatutLivraison.A_CONFIRMER).count())
    poussins = _poussins_en_attente(fermes)
    from app.services import entretien
    a_faire_entretien = sum(entretien.a_faire_aujourdhui(f) for f in fermes)
    pannes = sum(len(entretien.pannes_en_cours(f)) for f in fermes)
    etats_vaccins = {v['etat'] for s in sit for v in s['vaccins']}
    vaccin = ('en retard' if 'retard' in etats_vaccins else
              "aujourd'hui" if etats_vaccins & {'aujourdhui', 'a_faire'} else
              'demain' if 'demain' in etats_vaccins else None)
    # Raccourci sous la saisie : pesée prévue aujourd'hui (ou passée)
    pesees = [s for s in sorted(sit, key=lambda s: s['pesee']) if s['pesee'] <= auj]
    # Ordre FIXE (lot 11) : Saisie du jour (pleine largeur, en tête), 6 tuiles, Entretien (pleine largeur)
    tuiles = [
        {'cle': 'ma_bande', 'ico': '🐔', 'nom': 'Ma bande', 'lien': url_for('eleveur.ma_bande'),
         'sous': 'poussins en attente' if poussins else 'peser, mes bandes', 'pastille': poussins or None},
        {'cle': 'ventes', 'ico': '🚚', 'nom': 'Ventes et sorties', 'lien': url_for('eleveur.aller', quoi='sortie'),
         'sous': 'abattoir, vente'},
        {'cle': 'soins', 'ico': '💉', 'nom': 'Vaccins et soins', 'lien': url_for('eleveur.soins'),
         'sous': 'vaccins, traitements', 'pastille': vaccin,
         'pastille_classe': 'rouge' if vaccin == 'en retard' else 'bleue'},
        {'cle': 'malade', 'ico': '🩺', 'nom': 'Poulet malade', 'lien': url_for('eleveur.aller', quoi='malade'),
         'sous': 'prévenir le vétérinaire', 'classe': 'tuile-malade'},
        {'cle': 'produits', 'ico': '📦', 'nom': 'Mes produits', 'lien': url_for('eleveur.produits'),
         'sous': 'à confirmer' if livraisons else 'achats, stock', 'pastille': livraisons or None},
        {'cle': 'argent', 'ico': '💰', 'nom': 'Mon argent', 'lien': url_for('argent.mon_argent'),
         'sous': 'gagné, dépensé'},
    ]
    entretien_tuile = {'cle': 'entretien', 'ico': '🔧', 'nom': 'Entretien', 'lien': url_for('entretien.ecran'),
                       'sous': 'pannes en cours' if pannes else ('tâches à faire' if a_faire_entretien else 'tout est fait'),
                       'pastille': (a_faire_entretien + pannes) or None, 'pastille_classe': 'rouge' if pannes else ''}
    # Lot 12 : réponse du vétérinaire non lue (pastille 💬), prochaine visite de l'agent
    reponses = sante.reponses_non_lues(user)
    if reponses:
        tuiles[2]['pastille'], tuiles[2]['pastille_classe'] = '💬', 'bleue'
    from app.services import visites
    visite = visites.prochaine([f.id for f in fermes])
    rouges = [s for s in sit if s['couleur'] == 'rouge']
    from app.services import oeufs as services_oeufs                 # lot F : tuile des œufs si une bande pond
    pontes = services_oeufs.bandes_de_ponte(fermes)
    oeufs = None
    if pontes:
        sit_o = services_oeufs.situation(pontes[0])
        oeufs = {'cle': 'oeufs', 'ico': '🥚', 'nom': 'Mes œufs', 'lien': url_for('eleveur.oeufs'),
                 'sous': f"{sit_o['plateaux']} plateau{'x' if sit_o['plateaux'] != 1 else ''} en stock" + (f" · ponte {sit_o['taux']:g} %" if sit_o['taux'] is not None else ''),
                 'pastille': '⚠️' if sit_o['chute'] else None, 'pastille_classe': 'rouge' if sit_o['chute'] else ''}
    return {'fermes': fermes, 'situation': sit, 'pire': pire, 'etat': etat, 'tuiles': tuiles, 'oeufs': oeufs,
            'reponse_veto': bool(reponses),
            'visite': {'qui': visite.agent.prenom or visite.agent.nom, 'quand': visites.quand(visite.date_prevue),
                       'objet': visite.objet} if visite else None,
            'entretien': entretien_tuile, 'saisie': {'avec_bande': bool(sit), 'a_saisir': a_saisir},
            'pesee': pesees[0] if pesees else None,
            'vaccins': vaccins_a_faire(sit, avec_demain=False), 'rouges': rouges}


def _poussins_en_attente(fermes):
    return sum(sum(d for _, d in regles_bandes.poussins_en_attente(f)) for f in fermes
               if regles_bandes.batiments_libres(f))


def _sans_bande(titre):
    """Tuile ouverte sans bande en cours : une petite page simple (lot 11, écart 1)."""
    return render_template('eleveur/sans_bande.html', titre=titre, poussins=_poussins_en_attente(_fermes()))


# ── « Saisie du jour » (écran « Ma bande aujourd'hui » du lot 8) ─────────

@eleveur_bp.route('/saisie-du-jour')
@profil_requis(Profil.ELEVEUR)
def saisie():
    if not bandes_en_cours():
        return _sans_bande('✏️ Saisie du jour')
    from app.routes.accueil import _espace_eleveur
    return render_template('eleveur/saisie.html', espace=_espace_eleveur(_fermes()), conforme=_conforme('ELEVEUR', 3),
                           bien_recu=session.pop('bien_recu', None))


def _conforme(profil, n):
    """Lot K : le tableau du cahier, en version ordinateur seulement (le téléphone ne change pas)."""
    from app.utils import terrain as style
    if style.profil_terrain(current_user) is not None:
        return None
    from app.services import conformite
    fermes = _fermes()
    if n == 3:
        bandes = sorted(bandes_en_cours(), key=lambda b: b.date_mise_en_place, reverse=True)
        t = conformite.eleveur_saisies(current_user, bandes[0] if bandes else None)
    elif n == 5:
        t = conformite.eleveur_sante(current_user, fermes)
    elif n == 6:
        t = conformite.eleveur_livraisons(current_user, fermes)
    else:
        return None
    return (f'{profil}-{n}', conformite.spec(profil, n), t)


# ── Accès directs : la tuile ouvre la bande la plus utile ───────────────

SANS_BANDE = {'peser': '⚖️ Peser', 'sortie': '🚚 Ventes et sorties', 'traitement': '💊 Traitement'}


@eleveur_bp.route('/aller/<quoi>')
@profil_requis(Profil.ELEVEUR)
def aller(quoi):
    sit = _situation(bandes_en_cours())
    if quoi == 'malade':
        if not sit:
            fermes = _fermes()
            if not fermes:
                abort(404)
            return redirect(url_for('sante.declarer', ferme=fermes[0].numero))
        s = max(sit, key=lambda s: (ORDRE_FEU[s['couleur']] if s['raison'] == 'mortalite' else 0))
        return redirect(url_for('sante.declarer', bande=s['bande'].numero))
    if quoi == 'vaccins':
        return redirect(url_for('eleveur.soins'))
    if quoi not in SANS_BANDE:
        abort(404)
    if not sit:
        return _sans_bande(SANS_BANDE[quoi])
    if quoi == 'peser':
        s = min(sit, key=lambda s: s['pesee'])          # pesée prévue la plus proche
        return redirect(url_for('bandes.pesee', numero=s['bande'].numero))
    if quoi == 'sortie':
        s = max(sit, key=lambda s: s['age'])            # la bande la plus âgée
        return redirect(url_for('bandes.sortie', numero=s['bande'].numero))
    s = max(sit, key=lambda s: (ORDRE_FEU[s['couleur']], s['age']))   # traitement : la plus inquiétante
    return redirect(url_for('sante.traiter', numero=s['bande'].numero))


# ── Écrans de regroupement (lot 11) ─────────────────────────────────────

@eleveur_bp.route('/ma-bande')
@profil_requis(Profil.ELEVEUR)
def ma_bande():
    sit = _situation(bandes_en_cours())
    pesees = sorted(sit, key=lambda s: s['pesee'])
    return render_template('eleveur/ma_bande.html', poussins=_poussins_en_attente(_fermes()),
                           pesee=pesees[0] if pesees else None,
                           bandes_fiche=[s['bande'] for s in sit])          # lot T : fiche papier de la semaine


def bandeau_vaccin(user):
    """Vaccin validé à l'instant d'un toucher : « Fait ✓ — Annuler (10) »."""
    from app.models.sante import Vaccination
    import uuid
    try:
        ident = uuid.UUID(session.get('vaccin_recent') or '')
    except ValueError:
        return None
    v = db.session.get(Vaccination, ident)
    if v is None or not sante.vaccination_annulable(v, user):
        session.pop('vaccin_recent', None)
        return None
    ecoule = (maintenant() - en_utc(v.cree_le)).total_seconds()
    return {'vaccination': v, 'secondes': max(1, round(sante.DELAI_ANNULATION_SECONDES - ecoule))}


@eleveur_bp.route('/vaccins-et-soins')
@profil_requis(Profil.ELEVEUR)
def soins():
    sit = _situation(bandes_en_cours())
    prochains = sorted(((s, v) for s in sit for v in s['vaccins'] if v['etat'] == 'a_venir'),
                       key=lambda x: x[1]['prevu'])
    # Lot A1 : vaccins et traitements enregistrés (bandes en cours), touchables pour les modifier ou les archiver
    from app.models.sante import Vaccination, Traitement
    from app.services import fiches
    ids = [b.id for b in bandes_en_cours()]
    faits = []
    if ids:
        faits = sorted(Vaccination.query.filter(Vaccination.bande_id.in_(ids), Vaccination.annule.is_(False)).all()
                       + Traitement.query.filter(Traitement.bande_id.in_(ids)).all(),
                       key=lambda o: getattr(o, 'date', None) or o.date_debut, reverse=True)[:12]
    n_archives = {g: sum(fiches.nombre_archivees(g, bande=b) for b in bandes_en_cours()) for g in ('vaccin', 'traitement')}
    return render_template('eleveur/soins.html', conforme=_conforme('ELEVEUR', 5), vaccins=vaccins_a_faire(sit), avec_bande=bool(sit),
                           prochain=prochains[0] if prochains else None, bandeau=bandeau_vaccin(current_user),
                           faits=faits, n_archives=n_archives)


@eleveur_bp.route('/vaccinations/<uuid:ident>/annuler', methods=['POST'])
@profil_requis(Profil.ELEVEUR)
def annuler_vaccin(ident):
    from app.models.sante import Vaccination
    v = db.session.get(Vaccination, ident)
    session.pop('vaccin_recent', None)
    if v is None or v.bande.ferme_id not in {f.id for f in _fermes()}:
        abort(404)
    if sante.vaccination_annulable(v, current_user):
        v.annule = True                                  # journal : ANNULATION automatique
        db.session.commit()
        flash('Annulé : le vaccin est de nouveau à faire.', 'info')
    else:
        flash('Le délai pour annuler est passé.', 'warning')
    return redirect(url_for('accueil.index') if request.form.get('retour') == 'accueil' else url_for('eleveur.soins'))


@eleveur_bp.route('/mes-produits')
@profil_requis(Profil.ELEVEUR)
def produits():
    a_confirmer = (intrants.livraisons_de_l_etat(filtre_perimetre(Livraison.query))
                   .filter(Livraison.statut == StatutLivraison.A_CONFIRMER)
                   .order_by(Livraison.date_livraison, Livraison.numero_metier).all())
    from app.routes.accueil import _bandeau_annulation
    return render_template('eleveur/produits.html', conforme=_conforme('ELEVEUR', 6), a_confirmer=a_confirmer,
                           bandeau=_bandeau_annulation(current_user), bandeau_achat=bandeau_achat(current_user))


@eleveur_bp.route('/moi')
@profil_requis(Profil.ELEVEUR)
def moi():
    from app.services import bceg
    return render_template('eleveur/moi.html', fermes=_fermes(), banque=bool(bceg.fermes_du_responsable(current_user)),
                           banque_a_repondre=bool(bceg.a_repondre(current_user)))


# ── Tutoriel au premier lancement (lot 13) ──────────────────────────────

@eleveur_bp.route('/presentation')
@profil_requis(Profil.ELEVEUR)
def presentation():
    agent = next((f.agent for f in _fermes() if f.agent), None)
    return render_template('eleveur/presentation.html', agent=agent)


@eleveur_bp.route('/presentation/vue', methods=['POST'])
@profil_requis(Profil.ELEVEUR)
def presentation_vue():
    """« Passer » ou « C'est parti ! » : vue une fois pour ce compte (gardé sur le serveur)."""
    if current_user.presentation_vue_le is None:
        current_user.presentation_vue_le = maintenant()
        db.session.commit()
    return redirect(url_for('accueil.index'))


# ── Mon compte (lot 13) : seuls le téléphone et le mot de passe se modifient ─

def veterinaires_de_la_zone(user, fermes):
    """Vétérinaires des provinces des fermes ; au-delà de 3, d'abord ceux qui ont répondu aux
    signalements de l'éleveur, puis les autres (« Voir les autres »)."""
    from app.models import Utilisateur
    from app.models.sante import ReponseVeterinaire, AlerteSanitaire
    provinces = {f.province_id for f in fermes}
    vetos = sorted([u for u in Utilisateur.query.filter_by(profil=Profil.VETO, actif=True)
                    if provinces & set(u.province_ids)], key=lambda u: u.nom_complet)
    ont_repondu = {r.veto_id for r in ReponseVeterinaire.query.join(AlerteSanitaire)
                   .filter(AlerteSanitaire.ferme_id.in_([f.id for f in fermes]))} if fermes else set()
    if len(vetos) <= 3:
        return vetos, []
    premiers = [u for u in vetos if u.id in ont_repondu] or vetos[:1]
    return premiers, [u for u in vetos if u not in premiers]


TELEPHONE = re.compile(r'^\+?[0-9 ]{6,20}$')


@eleveur_bp.route('/mon-compte', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR)
def mon_compte():
    fermes = _fermes()
    erreur = None
    from app.utils import demo
    if request.method == 'POST' and demo.active():
        erreur = demo.MESSAGE
    elif request.method == 'POST':
        tel = ' '.join((request.form.get('telephone') or '').split())
        if tel and not TELEPHONE.match(tel):
            erreur = 'Écrivez le numéro avec des chiffres, par exemple +241 77 12 34 56.'
        else:
            current_user.telephone = tel or None         # journal : MODIFICATION automatique
            db.session.commit()
            flash('Téléphone enregistré ✓', 'success')
            return redirect(url_for('eleveur.mon_compte'))
    premiers, autres = veterinaires_de_la_zone(current_user, fermes)
    agent = next((f.agent for f in fermes if f.agent), None)
    return render_template('eleveur/mon_compte.html', fermes=fermes, agent=agent, vetos=premiers,
                           autres_vetos=autres, erreur=erreur)


# ── Ma banque : consentement BCEG du responsable de la ferme (lot 13) ────

def _ferme_du_responsable(numero):
    from app.services import bceg
    f = next((f for f in bceg.fermes_du_responsable(current_user) if f.numero == numero), None)
    if f is None:
        abort(404)
    return f


@eleveur_bp.route('/ma-banque')
@profil_requis(Profil.ELEVEUR)
def ma_banque():
    from app.services import bceg
    fermes = bceg.fermes_du_responsable(current_user)
    from app.services import conformite
    conforme = ('ELEVEUR-8', conformite.spec('ELEVEUR', 8), conformite.eleveur_bceg(current_user, _fermes())) \
        if style.profil_terrain(current_user) is None else None
    if not fermes and conforme is None:
        abort(404)                                      # ferme non financée, ou pas le responsable (téléphone)
    return render_template('eleveur/ma_banque.html', etats=[(f, bceg.derniere(f)) for f in fermes], conforme=conforme)


@eleveur_bp.route('/ma-banque/<numero>', methods=['POST'])
@profil_requis(Profil.ELEVEUR)
def repondre_banque(numero):
    from app.services import bceg
    f = _ferme_du_responsable(numero)
    try:
        c = bceg.repondre(f, current_user, request.form.get('decision'))
        db.session.commit()
        flash({'ACCEPTE': 'Merci : votre accord est enregistré ✓', 'REFUSE': 'Votre refus est enregistré.',
               'RETIRE': 'Votre accord est retiré : la BCEG ne voit plus vos chiffres.'}[c.decision], 'success')
    except bceg.RegleBceg as e:
        db.session.rollback()
        flash(str(e), 'warning')
    return redirect(url_for('eleveur.ma_banque'))


@eleveur_bp.route('/ma-banque/<numero>/retirer')
@profil_requis(Profil.ELEVEUR)
def retirer_banque(numero):
    """Retirer son accord : confirmation obligatoire (action rare et sensible, 4 touchers)."""
    return render_template('eleveur/ma_banque_retirer.html', ferme=_ferme_du_responsable(numero))


# ── Mon stock ───────────────────────────────────────────────────────────

@eleveur_bp.route('/mon-stock')
@profil_requis(Profil.ELEVEUR)
def stock():
    fermes = _fermes()
    achats = (filtre_perimetre(Livraison.query).filter(Livraison.origine == OrigineLivraison.ACHAT)
              .order_by(Livraison.date_livraison.desc(), Livraison.numero_metier.desc()).limit(5).all())
    from app.services import fiches
    return render_template('eleveur/stock.html', stocks=[(f, intrants.stock_ferme(f)) for f in fermes], achats=achats,
                           n_archivees=fiches.nombre_archivees('achat', fermes=fermes))


# ── J'ai acheté ─────────────────────────────────────────────────────────

def _entier(texte):
    texte = (texte or '').replace(' ', '').replace(' ', '').replace(',', '.').strip()
    if not texte:
        return None
    try:
        return int(round(float(texte)))
    except ValueError:
        raise intrants.RegleAchat('Nombre invalide.')


def _nombre(texte):
    texte = (texte or '').replace(' ', '').replace(',', '.').strip()
    if not texte:
        return None
    try:
        return float(texte)
    except ValueError:
        raise intrants.RegleAchat('Nombre invalide.')


def _jour(texte):
    from app.services import hors_ligne
    try:
        return date.fromisoformat(texte) if texte else hors_ligne.jour_de_saisie()
    except ValueError:
        raise intrants.RegleAchat('Date invalide.')


@eleveur_bp.route('/j-ai-achete', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def achat():
    fermes = _fermes()
    ferme = next((f for f in fermes if f.numero == request.values.get('ferme')), fermes[0] if len(fermes) == 1 else None)
    erreur = None
    if request.method == 'POST' and ferme is not None:
        f = request.form
        photo = None
        try:
            produit = db.session.get(Produit, f.get('produit', type=int) or 0)
            if request.files.get('recu') and request.files['recu'].filename:
                try:
                    enregistre = sante._enregistrer(request.files['recu'], sante._SIGNATURES, sous_dossier='achats')
                except sante.RegleSante as e:
                    raise intrants.RegleAchat(str(e))
                photo = enregistre[0] if enregistre else None
            batiment = next((b for b in ferme.batiments if str(b.id) == f.get('batiment')), None)
            a = intrants.enregistrer_achat(ferme, produit, _nombre(f.get('quantite')), _entier(f.get('morts')),
                                           _entier(f.get('prix')), f.get('lieu'), _jour(f.get('date')),
                                           current_user, photo, batiment=batiment)
            db.session.commit()
            if current_user.profil == Profil.ELEVEUR:
                session['achat_recent'] = a.numero      # « Enregistré ✓ — Annuler (10) »
                return redirect(url_for('eleveur.produits'))
            flash(f'Achat {a.numero} enregistré pour l\'éleveur.', 'success')
            return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#achats')
        except intrants.RegleAchat as e:
            db.session.rollback()
            erreur = str(e)
    tous = Produit.query.filter_by(actif=True).order_by(Produit.type, Produit.nom).all()
    frequents = intrants.produits_frequents(ferme) if ferme else tous[:6]
    autres = [p for p in tous if p not in frequents]
    limite = intrants.jour_le_plus_ancien_achat(current_user)
    return render_template('eleveur/achat.html', fermes=fermes, ferme=ferme, frequents=frequents, autres=autres,
                           erreur=erreur, saisie=request.form, limite=limite)


def charger_achat(numero):
    a = filtre_perimetre(Livraison.query.filter_by(numero_metier=numero,
                                                   origine=OrigineLivraison.ACHAT)).first()
    if a is None:
        abort(404)
    return a


def bandeau_achat(user):
    """Achat enregistré à l'instant : bandeau « Enregistré ✓ — Annuler (10) »."""
    numero = session.get('achat_recent')
    a = Livraison.query.filter_by(numero_metier=numero).first() if numero else None
    if a is None or not intrants.achat_annulable(a, user):
        session.pop('achat_recent', None)
        return None
    ecoule = (maintenant() - en_utc(a.confirmee_le)).total_seconds()
    return {'achat': a, 'secondes': max(1, round(intrants.DELAI_ANNULATION_SECONDES - ecoule))}


@eleveur_bp.route('/achats/<numero>/annuler', methods=['POST'])
@profil_requis(Profil.ELEVEUR)
def annuler_achat(numero):
    a = charger_achat(numero)
    session.pop('achat_recent', None)
    if not intrants.achat_annulable(a, current_user):
        flash('Le délai pour annuler est passé : demandez une correction à votre agent.', 'warning')
    else:
        intrants.annuler_achat(a, current_user)
        db.session.commit()
        flash('Achat annulé : il est retiré du stock.', 'info')
    return redirect(url_for('eleveur.produits'))


@eleveur_bp.route('/achats/<numero>/corriger', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def corriger_achat(numero):
    a = charger_achat(numero)
    if a.statut == StatutLivraison.ANNULEE:
        abort(404)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            intrants.corriger_achat(a, current_user, _nombre(f.get('quantite')), _entier(f.get('morts')),
                                    _entier(f.get('prix')), f.get('lieu'), _jour(f.get('date')),
                                    f.get('motif', '').strip())
            db.session.commit()
            flash('Correction enregistrée (inscrite au journal).', 'success')
            return redirect(url_for('fermes.fiche', numero=a.ferme.numero) + '#achats')
        except intrants.RegleAchat as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('eleveur/corriger_achat.html', a=a, l=a.lignes[0], erreur=erreur, saisie=request.form)


@eleveur_bp.route('/achats/<numero>/recu')
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.DGE, Profil.ADMIN)
def recu(numero):
    a = charger_achat(numero)
    chemin = sante.chemin_fichier(a.photo_recu, sous_dossier='achats') if a.photo_recu else None
    if chemin is None:
        abort(404)
    return send_file(chemin)


# ── Lot F : œufs d'une bande de ponte ────────────────────────────────────

@eleveur_bp.route('/oeufs')
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def oeufs():
    """🥚 Mes œufs : stock en plateaux, taux de ponte, ventes (fiches du lot A1), « ＋ J'ai vendu des œufs », réforme."""
    from app.services import oeufs as regles_oeufs
    fermes = _fermes() if current_user.profil == Profil.ELEVEUR else \
        filtre_perimetre(Ferme.query).filter(Ferme.du_numero(request.args.get('ferme') or '')).all()
    pontes = regles_oeufs.bandes_de_ponte(fermes)
    if not pontes:
        return _sans_bande('🥚 Mes œufs') if current_user.profil == Profil.ELEVEUR else abort(404)
    bande = next((b for b in pontes if b.numero == request.args.get('bande')), pontes[0])
    sit = regles_oeufs.situation(bande)
    return render_template('eleveur/oeufs.html', bande=bande, pontes=pontes, s=sit, par_plateau=regles_oeufs.par_plateau(),
                           bandeau=session.pop('vente_oeufs', None))


@eleveur_bp.route('/oeufs/<numero>/vendre', methods=['POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def vendre_oeufs(numero):
    from app.services import oeufs as regles_oeufs
    bande = filtre_perimetre(Bande.query).filter(Bande.numero_metier == numero).first_or_404()
    f = request.form
    try:
        jour = date.fromisoformat(f.get('jour')) if f.get('jour') else date.today()
        montant = f.get('montant', '').replace(' ', '').replace(',', '.')
        v = regles_oeufs.vendre(bande, jour, int(f.get('plateaux') or 0), int(f.get('oeufs') or 0),
                                int(float(montant)) if montant else None, f.get('acheteur'), current_user)
        db.session.commit()
        session['vente_oeufs'] = {'numero': v.numero, 'oeufs': v.oeufs, 'montant': v.montant_fcfa}
    except (regles_oeufs.RegleOeufs, ValueError) as e:
        db.session.rollback()
        flash(str(e) if str(e) else 'Saisie invalide.', 'danger')
    return redirect(url_for('eleveur.oeufs', bande=bande.numero))
