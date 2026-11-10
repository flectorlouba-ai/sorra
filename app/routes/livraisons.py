import re
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session
from flask_login import current_user

from app import db
from app.models import Ferme, Province, Profil, Produit, Livraison, LivraisonLigne
from app.models.intrant import StatutLivraison as S, TYPE_POUSSINS
from app.models.liste_deroulante import ld_choices
from app.services import intrants as regles, hors_ligne
from app.utils.nombres import quantite
from app.utils.permissions import profil_requis, filtre_perimetre

livraisons_bp = Blueprint('livraisons', __name__)

GESTION = (Profil.ADMIN, Profil.DGE, Profil.AGENT)
CONFIRMATION = (Profil.ELEVEUR, Profil.AGENT)
_LIGNE = re.compile(r'^ligne-(\d+)-produit$')


def charger(numero):
    liv = Livraison.query.filter_by(numero_metier=numero).first()
    if liv is None:
        abort(404)
    if filtre_perimetre(Livraison.query.filter(Livraison.id == liv.id)).first() is None:
        abort(403)
    return liv


def _nombre(texte, entier=False):
    texte = (texte or '').strip().replace(',', '.').replace(' ', '')
    if not texte:
        return None
    v = float(texte)
    return int(v) if entier else v


def _retour_confirmation(liv):
    if current_user.profil == Profil.ELEVEUR:
        return redirect(url_for('eleveur.produits'))        # lot 11 : écran « Mes produits »
    return redirect(url_for('livraisons.fiche', numero=liv.numero))


# ── Liste ───────────────────────────────────────────────────────────────

@livraisons_bp.route('/')
@profil_requis(*GESTION)
def liste():
    base = regles.livraisons_de_l_etat(filtre_perimetre(Livraison.query))
    f = {k: request.args.get(k, '').strip() for k in
         ('province', 'ferme', 'produit', 'statut', 'du', 'au', 'alerte')}
    q = base.join(Ferme, Livraison.ferme_id == Ferme.id)
    if f['province'].isdigit():
        q = q.filter(Ferme.province_id == int(f['province']))
    if f['ferme']:
        q = q.filter(Ferme.numero_metier == f['ferme'])
    if f['produit'].isdigit():
        q = q.filter(Livraison.lignes.any(LivraisonLigne.produit_id == int(f['produit'])))
    if f['statut'] in S.LIBELLES:
        q = q.filter(Livraison.statut == f['statut'])
    for cle, op in (('du', '__ge__'), ('au', '__le__')):
        try:
            if f[cle]:
                q = q.filter(getattr(Livraison.date_livraison, op)(date.fromisoformat(f[cle])))
        except ValueError:
            pass
    if f['alerte'] == 'retard':
        q = regles.requete_retard(q)
    elif f['alerte'] == 'ecart':
        q = regles.requete_ecart(q)
    livraisons = q.order_by(Livraison.date_livraison.desc(), Livraison.numero_metier.desc()).all()
    fermes = filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()
    provinces = [p for p in Province.query.order_by(Province.ordre) if p.id in {fe.province_id for fe in fermes}]
    return render_template('livraisons/liste.html', livraisons=livraisons, filtre=f, fermes=fermes,
                           provinces=provinces, statuts=S.LIBELLES,
                           produits=Produit.query.order_by(Produit.nom).all(),
                           total=base.count(), a_confirmer=base.filter(Livraison.statut == S.A_CONFIRMER).count(),
                           peut_creer=regles.peut_creer(current_user))


# ── Fiche ───────────────────────────────────────────────────────────────

@livraisons_bp.route('/<numero>')
@profil_requis(*GESTION)
def fiche(numero):
    liv = charger(numero)
    return render_template('livraisons/fiche.html', liv=liv,
                           peut_modifier=regles.peut_modifier(current_user, liv),
                           peut_confirmer=regles.peut_confirmer(current_user, liv),
                           peut_annuler=regles.peut_annuler(current_user, liv),
                           peut_corriger=regles.peut_corriger(current_user, liv),
                           annulable=_annulable_recente(liv))


# ── Création / modification ─────────────────────────────────────────────

def _lire(f, liv=None):
    erreurs, d = [], {}
    fermes = filtre_perimetre(Ferme.query).all()
    if liv is None:
        d['ferme'] = next((fe for fe in fermes if fe.numero_metier == f.get('ferme')), None)
        if d['ferme'] is None:
            erreurs.append('Choisissez la ferme.')
    try:
        d['date'] = date.fromisoformat(f.get('date_livraison', ''))
        if d['date'] > date.today():
            erreurs.append('La date de livraison ne peut pas être dans le futur.')
    except ValueError:
        d['date'] = None
        erreurs.append('Indiquez la date de livraison.')
    fournisseurs = noms_fournisseurs() + ([liv.fournisseur] if liv and liv.fournisseur else [])
    d['fournisseur'] = f.get('fournisseur') if f.get('fournisseur') in fournisseurs else None

    lignes, vus = [], set()
    indices = sorted(int(m.group(1)) for k in f.keys() if (m := _LIGNE.match(k)))
    for i in indices:
        pid = f.get(f'ligne-{i}-produit', '')
        if not pid:
            continue
        produit = Produit.query.filter_by(id=int(pid)).first() if pid.isdigit() else None
        if produit is None or (not produit.actif and not (liv and produit.id in {l.produit_id for l in liv.lignes})):
            erreurs.append('Produit inconnu.')
            continue
        if produit.id in vus:
            erreurs.append(f'« {produit.nom} » figure deux fois : regroupez la quantité sur une seule ligne.')
            continue
        vus.add(produit.id)
        try:
            qte = _nombre(f.get(f'ligne-{i}-quantite'))
            part = _nombre(f.get(f'ligne-{i}-part'), entier=True)
            valeur = _nombre(f.get(f'ligne-{i}-valeur'), entier=True)
        except ValueError:
            erreurs.append(f'« {produit.nom} » : les quantités et montants doivent être des nombres.')
            continue
        sub = f.get(f'ligne-{i}-subventionne') == 'on'
        if not qte or qte <= 0:
            erreurs.append(f'« {produit.nom} » : indiquez la quantité livrée.')
        if produit.type == TYPE_POUSSINS and qte and qte != int(qte):
            erreurs.append('Le nombre de poussins doit être un nombre entier.')
        if sub and (part is None or not 0 < part <= 100):
            erreurs.append(f'« {produit.nom} » : la part subventionnée doit être entre 1 et 100 %.')
        if valeur is not None and valeur < 0:
            erreurs.append(f'« {produit.nom} » : la valeur unitaire ne peut pas être négative.')
        lignes.append({'produit': produit, 'quantite_livree': qte, 'subventionne': sub,
                       'part_subventionnee': part, 'valeur_unitaire': valeur})
    if not lignes and not erreurs:
        erreurs.append('Ajoutez au moins un produit.')
    d['lignes'] = lignes
    return d, erreurs


def _contexte(liv, saisie, erreurs):
    lignes = []
    if saisie:
        indices = sorted(int(m.group(1)) for k in saisie.keys() if (m := _LIGNE.match(k)))
        lignes = [{'produit': saisie.get(f'ligne-{i}-produit', ''), 'quantite': saisie.get(f'ligne-{i}-quantite', ''),
                   'subventionne': saisie.get(f'ligne-{i}-subventionne') == 'on',
                   'part': saisie.get(f'ligne-{i}-part', ''), 'valeur': saisie.get(f'ligne-{i}-valeur', '')}
                  for i in indices]
    elif liv:
        lignes = [{'produit': str(l.produit_id), 'quantite': quantite(l.quantite_livree).replace(' ', ''),
                   'subventionne': l.subventionne,
                   'part': l.part_subventionnee or '', 'valeur': l.valeur_unitaire or ''} for l in liv.lignes]
    produits = Produit.query.filter(db.or_(Produit.actif.is_(True),
                                           Produit.id.in_([l.produit_id for l in liv.lignes] if liv else [])))
    return dict(liv=liv, saisie=saisie, erreurs=erreurs, lignes=lignes or [{}],
                fermes=filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all(),
                fournisseurs=noms_fournisseurs(),
                produits=produits.order_by(Produit.type, Produit.nom).all(),
                aujourdhui=date.today().isoformat())


@livraisons_bp.route('/nouvelle', methods=['GET', 'POST'])
@profil_requis(*GESTION)
def nouvelle():
    if request.method == 'GET':
        ctx = _contexte(None, None, [])
        ctx['ferme_choisie'] = request.args.get('ferme', '')
        return render_template('livraisons/formulaire.html', **ctx)
    d, erreurs = _lire(request.form)
    if erreurs:
        ctx = _contexte(None, request.form, erreurs)
        ctx['ferme_choisie'] = request.form.get('ferme', '')
        return render_template('livraisons/formulaire.html', **ctx)
    liv = regles.nouvelle_livraison(d['ferme'], d['date'], d['fournisseur'])
    db.session.add(liv)
    regles.remplacer_lignes(liv, d['lignes'])
    db.session.commit()
    flash(f'Livraison {liv.numero} enregistrée : l\'éleveur doit maintenant confirmer la réception.', 'success')
    return redirect(url_for('livraisons.fiche', numero=liv.numero))


@livraisons_bp.route('/<numero>/modifier', methods=['GET', 'POST'])
@profil_requis(*GESTION)
def modifier(numero):
    liv = charger(numero)
    if not regles.peut_modifier(current_user, liv):
        abort(403)
    if request.method == 'GET':
        return render_template('livraisons/formulaire.html', **_contexte(liv, None, []))
    d, erreurs = _lire(request.form, liv)
    if erreurs:
        return render_template('livraisons/formulaire.html', **_contexte(liv, request.form, erreurs))
    liv.date_livraison, liv.fournisseur = d['date'], d['fournisseur']
    regles.remplacer_lignes(liv, d['lignes'])
    db.session.commit()
    flash(f'Livraison {liv.numero} enregistrée.', 'success')
    return redirect(url_for('livraisons.fiche', numero=liv.numero))


# ── Confirmation (éleveur, ou agent pour son compte) ────────────────────

def _morts(liv, f):
    morts, erreurs = {}, []
    for l in liv.lignes:
        if l.produit.type == TYPE_POUSSINS:
            try:
                n = int(f.get(f'morts-{l.id}', '0') or 0)
            except ValueError:
                n = -1
            limite = _nombre(f.get(f'recue-{l.id}')) if f.get(f'recue-{l.id}') else l.quantite_livree
            if n < 0 or (limite is not None and n > limite):
                erreurs.append('Le nombre de morts à l\'arrivée doit être entre 0 et le nombre de poussins reçus.')
            morts[l.id] = n
    return morts, erreurs


def _annulable_recente(liv):
    recente = session.get('confirmation_recente')
    return recente == liv.numero and regles.annulation_possible(liv, current_user)


@livraisons_bp.route('/<numero>/confirmer')
@profil_requis(Profil.AGENT)
def confirmer(numero):
    """Écran de confirmation de l'agent pour le compte de l'éleveur (même carte que l'éleveur)."""
    liv = charger(numero)
    if not regles.peut_confirmer(current_user, liv):
        abort(403)
    return render_template('livraisons/confirmer.html', liv=liv)


@livraisons_bp.route('/<numero>/tout-recu', methods=['POST'])
@profil_requis(*CONFIRMATION)
def tout_recu(numero):
    liv = charger(numero)
    if not regles.peut_confirmer(current_user, liv):
        morts, erreurs = _morts(liv, request.form)
        gagne = _conflit_confirmation(liv, None, morts) if not erreurs else None
        if gagne:
            regles.confirmer(liv, current_user, morts=morts)
            db.session.commit()
        elif gagne is None:
            flash('Cette livraison n\'est plus à confirmer.', 'warning')
        return _retour_confirmation(liv)
    morts, erreurs = _morts(liv, request.form)
    if erreurs:
        for e in erreurs:
            flash(e, 'danger')
        return _retour_confirmation(liv)
    regles.confirmer(liv, current_user, morts=morts)
    db.session.commit()
    session['confirmation_recente'] = liv.numero
    return _retour_confirmation(liv)


def _conflit_confirmation(liv, receptions=None, morts=None):
    """Confirmation faite sans réseau d'une livraison déjà confirmée entre-temps (lot 12) :
    même personne : vrai (sa nouvelle confirmation s'applique, pas de conflit) ;
    deux personnes, valeurs différentes : les deux versions sont gardées (celle de l'éleveur compte),
    à trancher par l'agent ou la DGE ; faux. None hors de ce cas."""
    if not (hors_ligne.actif() and liv.confirmee and current_user.profil in (Profil.ELEVEUR, Profil.AGENT)):
        return None
    if liv.confirmee_par == current_user.id:
        return True
    from app.services import verifications
    if verifications.deux_versions_livraison(liv, receptions, morts, current_user, hors_ligne.saisi_le()):
        hors_ligne.conflit()
    db.session.commit()
    return False


def _lire_receptions(liv, f, exiger_moins):
    receptions, erreurs = {}, []
    for l in liv.lignes:
        try:
            recue = _nombre(f.get(f'recue-{l.id}'))
        except ValueError:
            recue = None
        if recue is None or recue < 0:
            erreurs.append(f'« {l.produit.nom} » : indiquez la quantité reçue.')
            continue
        if exiger_moins and recue > l.quantite_livree:
            erreurs.append(f'« {l.produit.nom} » : la quantité reçue ne peut pas dépasser la quantité livrée.')
        motif = f.get(f'motif-{l.id}') or None
        if recue != l.quantite_livree and not motif:
            erreurs.append(f'« {l.produit.nom} » : choisissez le motif de l\'écart.')
        receptions[l.id] = (recue, motif)
    return receptions, erreurs


@livraisons_bp.route('/<numero>/recu-moins', methods=['GET', 'POST'])
@profil_requis(*CONFIRMATION)
def recu_moins(numero):
    liv = charger(numero)
    if not regles.peut_confirmer(current_user, liv):
        gagne = None
        if request.method == 'POST':
            receptions, e1 = _lire_receptions(liv, request.form, exiger_moins=True)
            morts, e2 = _morts(liv, request.form)
            gagne = _conflit_confirmation(liv, receptions, morts) if not (e1 or e2) else None
        if not gagne:
            if gagne is None:
                flash('Cette livraison n\'est plus à confirmer.', 'warning')
            return _retour_confirmation(liv)
    erreurs = []
    if request.method == 'POST':
        receptions, erreurs = _lire_receptions(liv, request.form, exiger_moins=True)
        morts, e2 = _morts(liv, request.form)
        erreurs += e2
        if not erreurs:
            regles.confirmer(liv, current_user, receptions, morts)
            db.session.commit()
            flash('Merci : la réception est enregistrée avec les quantités reçues.', 'success')
            return _retour_confirmation(liv)
    return render_template('livraisons/reception.html', liv=liv, erreurs=erreurs, saisie=request.form,
                           motifs=[v for v, _ in ld_choices('motifs_ecart')], correction=False)


@livraisons_bp.route('/<numero>/annuler-confirmation', methods=['POST'])
@profil_requis(*CONFIRMATION)
def annuler_confirmation(numero):
    liv = charger(numero)
    session.pop('confirmation_recente', None)
    if not regles.annulation_possible(liv, current_user):
        flash('Le délai pour annuler est passé : demandez une correction à votre agent.', 'warning')
        return _retour_confirmation(liv)
    regles.annuler_confirmation(liv, current_user)
    db.session.commit()
    flash('Confirmation annulée : la livraison est de nouveau à confirmer.', 'info')
    return _retour_confirmation(liv)


# ── Annulation, correction ──────────────────────────────────────────────

@livraisons_bp.route('/<numero>/annuler', methods=['POST'])
@profil_requis(Profil.ADMIN, Profil.DGE)
def annuler(numero):
    liv = charger(numero)
    motif = request.form.get('motif', '').strip()
    if not regles.peut_annuler(current_user, liv):
        flash('Seule une livraison à confirmer peut être annulée.', 'danger')
    elif not motif:
        flash('Indiquez le motif de l\'annulation.', 'danger')
    else:
        regles.annuler(liv, current_user, motif)
        db.session.commit()
        flash(f'Livraison {liv.numero} annulée.', 'success')
    return redirect(url_for('livraisons.fiche', numero=liv.numero))


@livraisons_bp.route('/<numero>/corriger', methods=['GET', 'POST'])
@profil_requis(Profil.ADMIN, Profil.AGENT)
def corriger(numero):
    liv = charger(numero)
    if not regles.peut_corriger(current_user, liv):
        abort(403)
    erreurs = []
    if request.method == 'POST':
        receptions, erreurs = _lire_receptions(liv, request.form, exiger_moins=False)
        morts, e2 = _morts(liv, request.form)
        erreurs += e2
        motif = request.form.get('motif_correction', '').strip()
        if not motif:
            erreurs.append('Indiquez le motif de la correction.')
        if not erreurs:
            regles.corriger(liv, current_user, receptions, morts, motif)
            db.session.commit()
            flash(f'Livraison {liv.numero} corrigée.', 'success')
            return redirect(url_for('livraisons.fiche', numero=liv.numero))
    return render_template('livraisons/reception.html', liv=liv, erreurs=erreurs, saisie=request.form,
                           motifs=[v for v, _ in ld_choices('motifs_ecart')], correction=True)


# ── Éleveur : historique ────────────────────────────────────────────────

@livraisons_bp.route('/mes-livraisons')
@profil_requis(Profil.ELEVEUR)
def mes_livraisons():
    livraisons = (regles.livraisons_de_l_etat(filtre_perimetre(Livraison.query))
                  .order_by(Livraison.date_livraison.desc(), Livraison.numero_metier.desc()).all())
    return render_template('livraisons/mes_livraisons.html', livraisons=livraisons)


def noms_fournisseurs():
    """Lot A2 : les fournisseurs du catalogue (en service), puis les anciennes valeurs de la liste « Fournisseurs »."""
    from app.models import Fournisseur
    noms = [f.nom for f in Fournisseur.query.filter_by(actif=True).order_by(Fournisseur.nom)]
    return noms + [v for v, _ in ld_choices('fournisseurs') if v not in noms]
