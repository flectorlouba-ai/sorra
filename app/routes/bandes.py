from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db, indicateurs
from app.models import Ferme, Province, Profil, Batiment, Operateur, LivraisonLigne
from app.models.bande import Bande, Pesee, Sortie, StatutBande, MotifSortie
from app.models.sante import Traitement
from app.models.intrant import Produit, TYPE_ALIMENT
from app.services import bandes as regles, parametres, sante
from app.services.journal import enregistrer, Action
from app.utils.nombres import quantite
from app.utils.permissions import profil_requis, filtre_perimetre

bandes_bp = Blueprint('bandes', __name__)

LECTEURS = (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO)
SAISIE = (Profil.ELEVEUR, Profil.AGENT)


def charger(numero):
    bande = Bande.query.filter_by(numero_metier=numero).first()
    if bande is None:
        abort(404)
    if filtre_perimetre(Bande.query.filter(Bande.id == bande.id)).first() is None:
        abort(403)
    return bande


def charger_ferme(numero):
    ferme = Ferme.query.filter_by(numero_metier=numero).first() if numero else None
    if ferme is None:
        return None
    if filtre_perimetre(Ferme.query.filter(Ferme.id == ferme.id)).first() is None:
        abort(403)
    return ferme


def _retour(bande):
    if current_user.profil == Profil.ELEVEUR:
        return redirect(url_for('accueil.index') + f'#bande-{bande.numero}')
    return redirect(url_for('bandes.fiche', numero=bande.numero))


def _nombre(texte, entier=False):
    texte = (texte or '').strip().replace(',', '.').replace(' ', '')
    if not texte:
        return None
    try:
        v = float(texte)
    except ValueError:
        raise regles.RegleBande('Écrivez les quantités en chiffres.')
    return int(v) if entier else v


def _jour(texte):
    try:
        return date.fromisoformat(texte) if texte else date.today()
    except ValueError:
        raise regles.RegleBande('Date invalide.')


def contexte_bloc(bande):
    """Tout ce qu'affiche le bloc « Ma bande aujourd'hui » d'une bande."""
    v = indicateurs.calculer(bande)
    couleur, raison = indicateurs.feu(bande, valeurs=v)
    aliments, stock = regles.aliments_disponibles(bande.ferme, bande)
    return {
        'bande': bande, 'v': v, 'couleur': couleur, 'raison': raison,
        'phrase': indicateurs.phrase(bande, couleur, raison, v),
        'a_faire': [{'texte': t, 'lien': None} for t in indicateurs.a_faire(bande)]
                   + [{'texte': t['texte'], 'lien': url_for('sante.vacciner', numero=bande.numero,
                                                            calendrier=t['calendrier']) if t['calendrier'] else None}
                      for t in sante.a_faire(bande)],
        'encouragement': indicateurs.encouragement(bande, v, regles.precedente(bande)),
        'aliments': aliments, 'stock': stock,
        'deja': indicateurs.saisie_du(bande, date.today()),
        'historique': list(reversed(bande.saisies[-7:])),
        'cloture_proposee': v['effectif_present'] <= 0,
    }


# ── Liste ───────────────────────────────────────────────────────────────

@bandes_bp.route('/')
@profil_requis(*LECTEURS)
def liste():
    f = {k: request.args.get(k, '').strip() for k in ('province', 'ferme', 'statut', 'feu')}
    q = filtre_perimetre(Bande.query).join(Ferme, Bande.ferme_id == Ferme.id)
    if f['province'].isdigit():
        q = q.filter(Ferme.province_id == int(f['province']))
    if f['ferme']:
        q = q.filter(Ferme.numero_metier == f['ferme'])
    statut = f['statut'] or StatutBande.EN_COURS
    if statut != 'toutes':
        q = q.filter(Bande.statut == statut)
    lignes = []
    for b in q.order_by(Bande.numero_metier).all():
        v = indicateurs.calculer(b)
        couleur, _ = indicateurs.feu(b, valeurs=v)
        if f['feu'] and f['feu'] != couleur:
            continue
        lignes.append({'bande': b, 'v': v, 'couleur': couleur})
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    provinces = [p for p in Province.query.order_by(Province.ordre) if p.id in {fe.province_id for fe in fermes}]
    return render_template('bandes/liste.html', lignes=lignes, filtre={**f, 'statut': statut},
                           fermes=fermes, provinces=provinces,
                           peut_ouvrir=current_user.profil in (Profil.AGENT, Profil.ADMIN))


# ── Fiche, bilan ────────────────────────────────────────────────────────

def courbe_svg(bande, largeur=560, hauteur=220, marge=34):
    """Points de la courbe réelle (pesées) et attendue (Paramètres), à l'échelle."""
    age_max = max(indicateurs.age(bande, bande.date_cloture or date.today()), 42)
    reels = [(0, bande.poids_initial_g)] + [(indicateurs.age(bande, p.date), p.poids_moyen_g) for p in bande.pesees]
    attendus = [(a, indicateurs.poids_attendu(a)) for a in range(0, age_max + 1, 7)]
    p_max = max([p for _, p in reels + attendus] + [100]) * 1.1

    def xy(a, p):
        return (round(marge + a / age_max * (largeur - 2 * marge), 1),
                round(hauteur - marge - p / p_max * (hauteur - 2 * marge), 1))

    graduations = [(xy(a, 0)[0], a) for a in range(0, age_max + 1, 7)]
    poids = [(xy(0, g)[1], g) for g in range(0, int(p_max), 500)]
    return {'largeur': largeur, 'hauteur': hauteur, 'marge': marge,
            'reelle': ' '.join(f'{x},{y}' for x, y in (xy(a, p) for a, p in reels)),
            'points': [xy(a, p) for a, p in reels],
            'attendue': ' '.join(f'{x},{y}' for x, y in (xy(a, p) for a, p in attendus)),
            'graduations': graduations, 'poids': poids}


def journal_bande(bande):
    jours = {}
    for s in bande.saisies:
        jours.setdefault(s.date, {})['saisie'] = s
    for p in bande.pesees:
        jours.setdefault(p.date, {}).setdefault('pesees', []).append(p)
    for s in bande.sorties:
        jours.setdefault(s.date, {}).setdefault('sorties', []).append(s)
    return [{'date': j, 'age': indicateurs.age(bande, j), **d} for j, d in sorted(jours.items(), reverse=True)]


@bandes_bp.route('/<numero>')
@profil_requis(*LECTEURS)
def fiche(numero):
    bande = charger(numero)
    v = indicateurs.calculer(bande)
    couleur, raison = indicateurs.feu(bande, valeurs=v)
    stock = {s['produit'].id: s for s in regles.intrants.stock_ferme(bande.ferme)}
    consomme = {}
    for s in bande.saisies:
        for a in s.aliments:
            c = consomme.setdefault(a.produit_id, {'produit': a.produit, 'sacs': 0, 'kg': 0})
            c['sacs'] += a.sacs
            c['kg'] += a.kg
    return render_template('bandes/fiche.html', bande=bande, v=v, couleur=couleur,
                           vaccins=sante.vaccins_de_la_bande(bande),
                           traitements=Traitement.query.filter_by(bande_id=bande.id).order_by(Traitement.date_debut).all(),
                           delai=sante.fin_delai_attente(bande),
                           phrase=indicateurs.phrase(bande, couleur, raison, v),
                           courbe=courbe_svg(bande), journal=journal_bande(bande),
                           consomme=list(consomme.values()), stock=stock,
                           prochaine_pesee=indicateurs.prochaine_pesee(bande),
                           peut_saisir=regles.peut_saisir(current_user, bande),
                           peut_cloturer=regles.peut_cloturer(current_user, bande),
                           peut_corriger=regles.peut_corriger(current_user, bande),
                           capacite_depassee=regles.depasse_capacite(bande))


@bandes_bp.route('/<numero>/bilan')
@profil_requis(*LECTEURS, Profil.ELEVEUR)
def bilan(numero):
    bande = charger(numero)
    if bande.en_cours or not bande.bilan:
        return redirect(url_for('bandes.fiche', numero=numero))
    return render_template('bandes/bilan.html', bande=bande, b=bande.bilan)


# ── Ouverture ───────────────────────────────────────────────────────────

def _ferme_pour_ouvrir():
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    ferme = charger_ferme(request.values.get('ferme'))
    if ferme is None and len(fermes) == 1:
        ferme = fermes[0]
    if current_user.profil == Profil.AGENT and ferme is not None and ferme.agent_id != current_user.id:
        abort(403)
    return ferme, fermes


@bandes_bp.route('/ouvrir', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.ADMIN)
def ouvrir():
    ferme, fermes = _ferme_pour_ouvrir()
    if ferme is None:
        return render_template('bandes/choisir_ferme.html', fermes=fermes, cible='bandes.ouvrir')
    attente = regles.poussins_en_attente(ferme)
    libres = regles.batiments_libres(ferme)
    erreur = None
    if request.method == 'POST':
        try:
            ligne = next((l for l, _ in attente if str(l.id) == request.form.get('ligne')), None)
            if ligne is None:
                raise regles.RegleBande('Choisissez les poussins à mettre en place.')
            batiment = Batiment.query.filter_by(id=request.form.get('batiment', type=int), ferme_id=ferme.id).first()
            bande = regles.ouvrir(ferme, batiment, ligne, _nombre(request.form.get('effectif'), entier=True),
                                  _jour(request.form.get('date')), _nombre(request.form.get('poids_g')),
                                  current_user)
            db.session.commit()
            flash(f'Bande {bande.numero} commencée : {bande.effectif_initial} poussins, '
                  f'fin prévue le {bande.date_fin_prevue.strftime("%d/%m")}.', 'success')
            if regles.depasse_capacite(bande):
                flash(f'Attention : {bande.effectif_initial} poussins pour {bande.batiment.capacite} places '
                      f'dans le bâtiment {bande.batiment.code}.', 'warning')
            return _retour(bande)
        except regles.RegleBande as e:
            db.session.rollback()
            erreur = str(e)
    duree = int(parametres.obtenir('bandes.duree_reference_jours', 45))
    etats = {b.id: regles.etat_batiment(b) for b in ferme.batiments}
    return render_template('bandes/ouvrir.html', ferme=ferme, attente=attente, libres=libres, etats=etats,
                           erreur=erreur, saisie=request.form, duree=duree,
                           poids_defaut=parametres.obtenir('bandes.poids_poussin_g', 40),
                           peut_rattrapage=regles.peut_rattrapage(current_user))


@bandes_bp.route('/rattrapage', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def rattrapage():
    ferme, fermes = _ferme_pour_ouvrir()
    if ferme is None:
        return render_template('bandes/choisir_ferme.html', fermes=fermes, cible='bandes.rattrapage')
    erreur = None
    if request.method == 'POST':
        try:
            batiment = Batiment.query.filter_by(id=request.form.get('batiment', type=int), ferme_id=ferme.id).first()
            bande = regles.ouvrir_rattrapage(
                ferme, batiment, _jour(request.form.get('date')),
                _nombre(request.form.get('effectif'), entier=True),
                _nombre(request.form.get('morts'), entier=True) or 0,
                _nombre(request.form.get('poids_g')), current_user)
            db.session.commit()
            flash(f'Bande {bande.numero} enregistrée (rattrapage) : indicateurs partiels.', 'success')
            return _retour(bande)
        except regles.RegleBande as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('bandes/rattrapage.html', ferme=ferme, libres=regles.batiments_libres(ferme),
                           erreur=erreur, saisie=request.form)


# ── Saisie du jour ──────────────────────────────────────────────────────

@bandes_bp.route('/<numero>/saisir')
@profil_requis(Profil.AGENT)
def saisir(numero):
    """L'agent saisit pour l'éleveur, avec le même bloc que l'éleveur."""
    bande = charger(numero)
    if not regles.peut_saisir(current_user, bande):
        abort(403)
    return render_template('bandes/saisir.html', **contexte_bloc(bande))


@bandes_bp.route('/<numero>/oublie')
@profil_requis(*SAISIE)
def oublie(numero):
    bande = charger(numero)
    if not regles.peut_saisir(current_user, bande):
        abort(403)
    limite = max(filter(None, [regles.limite_jour_passe(current_user), indicateurs.debut_suivi(bande)]))
    hier = date.today() - timedelta(days=1)
    return render_template('bandes/oublie.html', **contexte_bloc(bande), limite=limite,
                           jour_saisie=max(hier, limite) if hier >= limite else date.today())


@bandes_bp.route('/<numero>/saisie', methods=['POST'])
@profil_requis(*SAISIE)
def saisie(numero):
    bande = charger(numero)
    if not regles.peut_saisir(current_user, bande):
        abort(403)
    f = request.form
    try:
        jour = _jour(f.get('jour'))
        morts = _nombre(f.get('morts'), entier=True) or 0
        aliments = {}
        sacs = _nombre(f.get('sacs')) or 0
        if sacs:
            pid = f.get('aliment_choisi', '')
            produit = Produit.query.filter_by(id=int(pid), type=TYPE_ALIMENT).first() if pid.isdigit() else None
            if produit is None:
                raise regles.RegleBande("Choisissez l'aliment donné.")
            aliments[produit] = sacs
        s, avertissements = regles.saisir(bande, jour, morts, aliments, current_user, ajouter=f.get('ajouter') == '1')
        db.session.flush()
        sante.alerte_si_feu_rouge(bande)
        db.session.commit()
        flash('Envoyé ✓' if jour == date.today() else f'Envoyé ✓ pour le {jour.strftime("%d/%m")}', 'success')
        for a in avertissements:
            flash(a, 'warning')
    except regles.DejaEnvoye as e:
        db.session.rollback()
        return render_template('bandes/deja_envoye.html', bande=bande, existante=e.saisie, form=f, jour=jour,
                               morts=morts, aliments=aliments)
    except regles.RegleBande as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return _retour(bande)


# ── Pesée, sortie ───────────────────────────────────────────────────────

@bandes_bp.route('/<numero>/pesee', methods=['GET', 'POST'])
@profil_requis(*SAISIE)
def pesee(numero):
    bande = charger(numero)
    if not regles.peut_saisir(current_user, bande):
        abort(403)
    erreur = None
    if request.method == 'POST':
        try:
            p = regles.peser(bande, _jour(request.form.get('jour')), _nombre(request.form.get('nombre'), entier=True),
                             _nombre(request.form.get('poids_total')), current_user)
            db.session.commit()
            dans = indicateurs.dans_la_courbe(p.poids_moyen_g, indicateurs.age(bande, p.date))
            flash(f'Pesée enregistrée : poids moyen {quantite(p.poids_moyen_g, 0)} g — '
                  + ('dans la courbe attendue ✓' if dans else 'en dessous de la courbe attendue'),
                  'success' if dans else 'warning')
            return _retour(bande)
        except regles.RegleBande as e:
            db.session.rollback()
            erreur = str(e)
    age = indicateurs.age(bande)
    return render_template('bandes/pesee.html', bande=bande, erreur=erreur, saisie=request.form,
                           nombre_defaut=parametres.obtenir('bandes.pesee_nombre_defaut', 10),
                           attendu=round(indicateurs.poids_attendu(age)),
                           tolerance=float(parametres.obtenir('bandes.ecart_courbe_pct', 10)))


@bandes_bp.route('/<numero>/sortie', methods=['GET', 'POST'])
@profil_requis(*SAISIE)
def sortie(numero):
    bande = charger(numero)
    if not regles.peut_saisir(current_user, bande):
        abort(403)
    erreur = None
    operateurs = Operateur.query.filter_by(actif=True).order_by(Operateur.type, Operateur.nom).all()
    if request.method == 'POST':
        f = request.form
        try:
            op = next((o for o in operateurs if str(o.id) == f.get('operateur')), None)
            s = regles.sortir(bande, _jour(f.get('jour')), f.get('motif'), op, f.get('destinataire_libre', '').strip(),
                              _nombre(f.get('nombre'), entier=True), _nombre(f.get('poids_total')), current_user)
            delai = sante.fin_delai_attente(bande, s.date)
            if delai and s.motif == MotifSortie.ABATTOIR:
                fin = delai.strftime('%d/%m/%Y')
                enregistrer(Action.DELAI_ATTENTE, table='sortie', enregistrement_id=s.id,
                            detail=f"Bande {bande.numero} : {s.nombre} poulets vers l'abattoir le "
                                   f"{s.date.strftime('%d/%m/%Y')}, pendant un délai d'attente (jusqu'au {fin}).")
                flash(f"ATTENTION : ces poulets sont encore en délai d'attente après traitement "
                      f"(jusqu'au {fin}). C'est inscrit au journal.", 'danger')
            db.session.commit()
            reste = indicateurs.calculer(bande)['effectif_present']
            flash(f'Sortie enregistrée. Il reste {reste} poulets dans la bande.', 'success')
            return _retour(bande)
        except regles.RegleBande as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('bandes/sortie.html', bande=bande, erreur=erreur, saisie=request.form,
                           operateurs=operateurs, motifs=MotifSortie.TOUS,
                           delai=sante.fin_delai_attente(bande),
                           present=indicateurs.calculer(bande)['effectif_present'])


# ── Clôture ─────────────────────────────────────────────────────────────

@bandes_bp.route('/<numero>/cloturer', methods=['POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.ADMIN)
def cloturer(numero):
    bande = charger(numero)
    if not regles.peut_cloturer(current_user, bande):
        abort(403)
    try:
        regles.cloturer(bande, current_user, request.form.get('motif', '').strip())
        db.session.commit()
        flash(f'Bande {bande.numero} clôturée : le bâtiment {bande.batiment.code} passe en vide sanitaire.',
              'success')
        return redirect(url_for('bandes.bilan', numero=bande.numero))
    except regles.RegleBande as e:
        db.session.rollback()
        flash(str(e), 'danger')
        return _retour(bande)


# ── Correction (agent pendant la bande, ADMIN toujours) ─────────────────

@bandes_bp.route('/<numero>/corriger/<quoi>/<ident>', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def corriger(numero, quoi, ident):
    bande = charger(numero)
    if not regles.peut_corriger(current_user, bande):
        abort(403)
    if quoi == 'saisie':
        objet = indicateurs.saisie_du(bande, _jour(ident))
    elif quoi == 'pesee':
        objet = next((p for p in bande.pesees if str(p.id) == ident), None)
    elif quoi == 'sortie':
        objet = next((s for s in bande.sorties if str(s.id) == ident), None)
    else:
        objet = None
    if objet is None:
        abort(404)
    erreur = None
    if request.method == 'POST':
        f = request.form
        motif = f.get('motif', '').strip()
        try:
            if not motif:
                raise regles.RegleBande('Indiquez le motif de la correction.')
            if quoi == 'saisie':
                morts = _nombre(f.get('morts'), entier=True) or 0
                if morts < 0:
                    raise regles.RegleBande('Nombre de morts invalide.')
                objet.morts = morts
                for a in objet.aliments:
                    a.sacs = _nombre(f.get(f'aliment-{a.produit_id}')) or 0
                    a.kg = a.sacs * float(a.produit.poids_sac_kg or 0)
                libelle = f'saisie du {objet.date.strftime("%d/%m")}'
            elif quoi == 'pesee':
                nombre, total = _nombre(f.get('nombre'), entier=True), _nombre(f.get('poids_total'))
                if not nombre or not total or nombre <= 0 or total <= 0:
                    raise regles.RegleBande('Nombre de poulets et poids total obligatoires.')
                objet.nombre_pesees, objet.poids_total_kg = nombre, total
                objet.poids_moyen_g = round(total / nombre * 1000, 1)
                libelle = f'pesée du {objet.date.strftime("%d/%m")}'
            else:
                nombre, poids = _nombre(f.get('nombre'), entier=True), _nombre(f.get('poids_total'))
                if not nombre or not poids or nombre <= 0 or poids <= 0:
                    raise regles.RegleBande('Nombre de poulets et poids total obligatoires.')
                objet.nombre, objet.poids_total_kg = nombre, poids
                libelle = f'sortie du {objet.date.strftime("%d/%m")}'
            db.session.flush()
            if indicateurs.calculer(bande)['effectif_present'] < 0:
                raise regles.RegleBande('Avec ces chiffres, l\'effectif deviendrait négatif.')
            regles.apres_correction(bande, current_user, libelle, motif)
            db.session.flush()
            sante.alerte_si_feu_rouge(bande)
            db.session.commit()
            flash('Correction enregistrée (inscrite au journal).', 'success')
            return redirect(url_for('bandes.fiche', numero=bande.numero))
        except regles.RegleBande as e:
            db.session.rollback()
            erreur = str(e)
            bande = charger(numero)
    return render_template('bandes/corriger.html', bande=bande, quoi=quoi, objet=objet, erreur=erreur)
