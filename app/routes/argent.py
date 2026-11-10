"""Argent de l'éleveur (lot 11) : « Mon argent », « J'ai payé » (l'éleveur, ou l'agent pour lui),
annulation 10 s, montant d'une vente complété plus tard, corrections de l'agent avec motif."""
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, session, send_file
from flask_login import current_user

from app import db
from app.models import Ferme, Profil
from app.models.argent import Depense
from app.models.bande import Bande, Sortie, StatutBande
from app.models.base import maintenant
from app.services import fiches, argent as regles, hors_ligne, sante
from app.utils.dates import en_utc
from app.utils.permissions import profil_requis, filtre_perimetre

argent_bp = Blueprint('argent', __name__)


def _fermes():
    return filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all()


def _ferme(fermes):
    voulue = request.values.get('ferme')
    if voulue:
        return next((f for f in fermes if voulue in (f.numero, f.numero_terrain)), None)
    return fermes[0] if len(fermes) == 1 else None


def _montant(texte):
    texte = ''.join(c for c in (texte or '') if not c.isspace()).replace('.', '')
    if not texte:
        return None
    if not texte.isdigit():
        raise regles.RegleArgent('Écrivez le montant en chiffres.')
    return int(texte)


def _jour(texte):
    try:
        return date.fromisoformat(texte) if texte else hors_ligne.jour_de_saisie()
    except ValueError:
        raise regles.RegleArgent('Date invalide.')


def _bandeau_depense():
    """Dépense enregistrée à l'instant : « Enregistré ✓ — Annuler (10) »."""
    numero = session.get('depense_recente')
    d = Depense.query.filter_by(numero_metier=numero).first() if numero else None
    if d is None or not regles.annulable(d, current_user):
        session.pop('depense_recente', None)
        return None
    ecoule = (maintenant() - en_utc(d.cree_le)).total_seconds()
    return {'depense': d, 'secondes': max(1, round(regles.DELAI_ANNULATION_SECONDES - ecoule))}


# ── Mon argent (éleveur) ────────────────────────────────────────────────

@argent_bp.route('/mon-argent')
@profil_requis(Profil.ELEVEUR)
def mon_argent():
    fermes = _fermes()
    periode = request.args.get('periode') if request.args.get('periode') in regles.PERIODES else 'mois'
    tous = regles.mouvements([f.id for f in fermes])
    en_cours = (filtre_perimetre(Bande.query).filter(Bande.statut == StatutBande.EN_COURS)
                .order_by(Bande.date_mise_en_place).all())
    choix_bandes = en_cours or (filtre_perimetre(Bande.query).filter(Bande.statut == StatutBande.CLOTUREE)
                                .order_by(Bande.date_cloture.desc()).limit(1).all())
    bande = None
    if periode == 'bande':
        bande = next((b for b in choix_bandes if b.numero == request.args.get('bande')),
                     choix_bandes[0] if choix_bandes else None)
    mvts = regles.filtrer(tous, periode, bande)
    t = regles.totaux(mvts, bande.id if bande else None)
    from app.utils import terrain as style
    conforme = None
    if style.profil_terrain(current_user) is None and current_user.profil == Profil.ELEVEUR:
        from app.services import conformite
        conforme = ('ELEVEUR-4', conformite.spec('ELEVEUR', 4), conformite.eleveur_argent(current_user, fermes))
    return render_template('argent/mon_argent.html', conforme=conforme, periode=periode, periodes=regles.PERIODES, totaux=t,
                           mouvements=mvts[:30], bande=bande, choix_bandes=choix_bandes if periode == 'bande' else [],
                           aide=regles.aide_etat(bande) if bande else None, bandeau=_bandeau_depense(),
                           n_archivees=fiches.nombre_archivees('depense', fermes=fermes))


# ── J'ai payé (éleveur, ou agent pour lui) ──────────────────────────────

@argent_bp.route('/j-ai-paye', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def payer():
    fermes = _fermes()
    ferme = _ferme(fermes)
    erreur = None
    if request.method == 'POST' and ferme is not None:
        f = request.form
        try:
            batiment = next((b for b in ferme.batiments if str(b.id) == f.get('batiment')), None)
            photo = None
            if request.files.get('recu') and request.files['recu'].filename:
                try:
                    enregistre = sante._enregistrer(request.files['recu'], sante._SIGNATURES, sous_dossier='depenses')
                except sante.RegleSante as e:
                    raise regles.RegleArgent(str(e))
                photo = enregistre[0] if enregistre else None
            categories = [v for v, _, _ in regles.categories()]
            categorie = f.get('categorie') if f.get('categorie') in categories else None
            d = regles.payer(ferme, categorie, _montant(f.get('montant')), batiment, _jour(f.get('date')),
                             current_user, photo)
            db.session.commit()
            if current_user.profil == Profil.ELEVEUR:
                if not hors_ligne.actif():
                    session['depense_recente'] = d.numero      # « Enregistré ✓ — Annuler (10) »
                return redirect(url_for('argent.mon_argent'))
            flash(f'Dépense {d.numero} enregistrée pour l\'éleveur.', 'success')
            return redirect(url_for('fermes.fiche', numero=ferme.numero) + '#argent')
        except regles.RegleArgent as e:
            db.session.rollback()
            erreur = str(e)
    from app.services import intrants
    return render_template('argent/payer.html', fermes=fermes, ferme=ferme, categories=regles.categories(),
                           erreur=erreur, saisie=request.form, limite=intrants.jour_le_plus_ancien_achat(current_user))


def _charger_depense(numero):
    d = filtre_perimetre(Depense.query.filter_by(numero_metier=numero)).first()
    if d is None:
        abort(404)
    return d


@argent_bp.route('/depenses/<numero>/annuler', methods=['POST'])
@profil_requis(Profil.ELEVEUR)
def annuler(numero):
    d = _charger_depense(numero)
    session.pop('depense_recente', None)
    if regles.annulable(d, current_user):
        regles.annuler(d)
        db.session.commit()
        flash('Dépense annulée.', 'info')
    else:
        flash('Le délai pour annuler est passé : demandez une correction à votre agent.', 'warning')
    return redirect(url_for('argent.mon_argent'))


@argent_bp.route('/depenses/<numero>/recu')
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.ADMIN)
def recu(numero):
    d = _charger_depense(numero)
    chemin = sante.chemin_fichier(d.photo_recu, sous_dossier='depenses') if d.photo_recu else None
    if chemin is None:
        abort(404)
    return send_file(chemin)


@argent_bp.route('/depenses/<numero>/corriger', methods=['GET', 'POST'])
@profil_requis(Profil.AGENT, Profil.ADMIN)
def corriger(numero):
    d = _charger_depense(numero)
    if d.annule:
        abort(404)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            regles.corriger_depense(d, current_user, f.get('categorie'), _montant(f.get('montant')),
                                    _jour(f.get('date')), f.get('motif', '').strip())
            db.session.commit()
            flash('Correction enregistrée (inscrite au journal).', 'success')
            return redirect(url_for('fermes.fiche', numero=d.ferme.numero) + '#argent')
        except regles.RegleArgent as e:
            db.session.rollback()
            erreur = str(e)
    categories = regles.categories()
    if d.categorie not in [v for v, _, _ in categories]:
        categories.append((d.categorie, d.icone, d.libelle))     # catégorie désactivée depuis
    return render_template('argent/corriger.html', d=d, categories=categories, erreur=erreur, saisie=request.form)


# ── Montant d'une vente : complété par l'éleveur, corrigé par l'agent ──

@argent_bp.route('/ventes/<uuid:ident>/montant', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT, Profil.ADMIN)
def montant_vente(ident):
    s = db.session.get(Sortie, ident)
    if s is None or s.bande.ferme_id not in {f.id for f in _fermes()}:
        abort(404)
    if current_user.profil == Profil.ELEVEUR and s.montant_fcfa is not None and request.method == 'GET':
        flash('Le montant est déjà indiqué : demandez une correction à votre agent.', 'info')
        return redirect(url_for('argent.mon_argent'))
    erreur = None
    if request.method == 'POST':
        try:
            regles.completer_vente(s, current_user, _montant(request.form.get('montant')),
                                   request.form.get('motif', '').strip())
            db.session.commit()
            if current_user.profil == Profil.ELEVEUR:
                flash('Montant enregistré ✓', 'success')
                return redirect(url_for('argent.mon_argent'))
            flash('Montant enregistré (inscrit au journal).', 'success')
            return redirect(url_for('fermes.fiche', numero=s.bande.ferme.numero) + '#argent')
        except regles.RegleArgent as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('argent/montant_vente.html', s=s, erreur=erreur, saisie=request.form)
