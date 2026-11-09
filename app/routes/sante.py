from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, send_file, session
from flask_login import current_user

from app import db
from app.models import Ferme, Profil, Produit, Province
from app.models.bande import Bande, StatutBande
from app.models.liste_deroulante import ld_choices
from app.models.sante import (Declaration, AlerteSanitaire, CalendrierVaccinal, Vaccination, Traitement,
                              StatutAlerte as SA)
from app.services import sante as regles, parametres
from app.utils.permissions import profil_requis, filtre_perimetre

sante_bp = Blueprint('sante', __name__)


def _bande(numero):
    b = Bande.query.filter_by(numero_metier=numero).first() if numero else None
    if b is None:
        abort(404)
    if filtre_perimetre(Bande.query.filter(Bande.id == b.id)).first() is None:
        abort(403)
    return b


def _retour(bande):
    if current_user.profil == Profil.ELEVEUR:
        return redirect(url_for('accueil.index'))
    return redirect(url_for('bandes.fiche', numero=bande.numero))


def _entier(texte):
    try:
        return int((texte or '').strip())
    except ValueError:
        return None


def _decimal(texte):
    try:
        return float((texte or '').strip().replace(',', '.')) if (texte or '').strip() else None
    except ValueError:
        return None


# ── Déclaration sanitaire (éleveur, ou agent pour l'éleveur) ────────────

@sante_bp.route('/declarer', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def declarer():
    bande = _bande(request.values.get('bande')) if request.values.get('bande') else None
    ferme = bande.ferme if bande else None
    if ferme is None:
        ferme = Ferme.query.filter_by(numero_metier=request.values.get('ferme', '')).first()
        if ferme is None or filtre_perimetre(Ferme.query.filter(Ferme.id == ferme.id)).first() is None:
            abort(404)
    signes = [v for v, _ in ld_choices('signes_cliniques')]
    erreur = None
    if request.method == 'POST':
        try:
            choisis = [s for s in request.form.getlist('signes') if s in signes]
            regles.declarer(ferme, bande, choisis, _entier(request.form.get('nombre')),
                            request.files.getlist('photos'), request.files.get('audio'), current_user)
            db.session.commit()
            flash('Envoyé au vétérinaire ✓ : les services vétérinaires de la province vont l\'examiner.', 'success')
            return _retour(bande) if bande else redirect(url_for('accueil.index'))
        except regles.RegleSante as e:
            db.session.rollback()
            erreur = str(e)
    return render_template('sante/declarer.html', bande=bande, ferme=ferme, erreur=erreur, saisie=request.form,
                           signes=[(s, regles.icone_signe(s)) for s in signes])


@sante_bp.route('/declarations')
@profil_requis(Profil.VETO, Profil.ADMIN)
def declarations():
    liste = regles.declarations_visibles(current_user).order_by(Declaration.cree_le.desc()).all()
    alertes = {a.declaration_id: a for a in AlerteSanitaire.query.filter(
        AlerteSanitaire.declaration_id.in_([d.id for d in liste]))} if liste else {}
    return render_template('sante/declarations.html', declarations=liste, alertes=alertes, mes=False)


@sante_bp.route('/mes-declarations')
@profil_requis(Profil.ELEVEUR)
def mes_declarations():
    if current_user.profil == Profil.ELEVEUR:
        # Lot 12 : « Mes signalements », états simples, réponses du vétérinaire en gros ; lues à l'ouverture
        elements = regles.signalements_eleveur(current_user)
        nouvelles = {r.id for r in regles.reponses_non_lues(current_user)}
        from app.models.base import maintenant
        for r in regles.reponses_non_lues(current_user):
            r.lue_le = maintenant()
        db.session.commit()
        return render_template('sante/mes_signalements.html', elements=elements, nouvelles=nouvelles,
                               etats=regles.ETATS_ELEVEUR, icone=regles.icone_signe)
    liste = regles.declarations_visibles(current_user).order_by(Declaration.cree_le.desc()).all()
    alertes = {a.declaration_id: a for a in AlerteSanitaire.query.filter(
        AlerteSanitaire.declaration_id.in_([d.id for d in liste]))} if liste else {}
    return render_template('sante/declarations.html', declarations=liste, alertes=alertes, mes=True)


@sante_bp.route('/declarations/<uuid:ident>/<genre>/<nom>')
@profil_requis(Profil.VETO, Profil.ADMIN, Profil.ELEVEUR)
def fichier(ident, genre, nom):
    """Photo ou message vocal : servis seulement à ceux qui voient la déclaration."""
    d = regles.declarations_visibles(current_user).filter(Declaration.id == ident).first()
    if d is None:
        abort(403)
    if genre == 'photo':
        p = next((p for p in d.photos if p.fichier == nom), None)
        if p is None:
            abort(404)
        return send_file(regles.chemin_fichier(p.fichier), mimetype=p.type_mime)
    if genre == 'audio' and d.audio == nom:
        ext = '.' + nom.rsplit('.', 1)[-1]
        return send_file(regles.chemin_fichier(nom), mimetype=regles.TYPES_AUDIO.get(ext, 'audio/webm'))
    abort(404)


# ── Alertes sanitaires ──────────────────────────────────────────────────

@sante_bp.route('/alertes')
@profil_requis(Profil.VETO, Profil.ADMIN, Profil.DGE)
def alertes():
    statut = request.args.get('statut', '')
    q = regles.alertes_visibles(current_user)
    if statut in SA.LIBELLES:
        q = q.filter(AlerteSanitaire.statut == statut)
    elif statut != 'toutes':
        if current_user.profil == Profil.DGE:
            q = q.filter(AlerteSanitaire.statut == SA.CONFIRMEE)
        else:
            q = q.filter(AlerteSanitaire.statut.in_(SA.OUVERTES + (SA.CONFIRMEE,)))
    return render_template('sante/alertes.html', alertes=q.order_by(AlerteSanitaire.cree_le.desc()).all(),
                           statut=statut, statuts=SA.LIBELLES)


@sante_bp.route('/alertes/<numero>', methods=['GET', 'POST'])
@profil_requis(Profil.VETO, Profil.ADMIN, Profil.DGE)
def alerte(numero):
    a = regles.alertes_visibles(current_user).filter(AlerteSanitaire.numero == numero).first()
    if a is None:
        abort(404 if not AlerteSanitaire.query.filter_by(numero=numero).first() else 403)
    erreur = None
    if request.method == 'POST':
        try:
            regles.changer_statut(a, request.form.get('statut'), request.form.get('commentaire', '').strip(),
                                  current_user)
            db.session.commit()
            flash(f'Alerte {a.numero} : {a.libelle_statut}.', 'success')
            return redirect(url_for('sante.alerte', numero=a.numero))
        except regles.RegleSante as e:
            db.session.rollback()
            erreur = str(e)
    from app.models.liste_deroulante import ld_choices as _ld
    return render_template('sante/alerte.html', a=a, erreur=erreur, icone=regles.icone_signe,
                           conseils=[v for v, _ in _ld('conseils_veterinaire')],
                           suivants=[(s, SA.LIBELLES[s]) for s in SA.SUIVANTS.get(a.statut, [])]
                           if current_user.profil == Profil.VETO else [])


@sante_bp.route('/alertes/<numero>/repondre', methods=['POST'])
@profil_requis(Profil.VETO)
def repondre(numero):
    """Réponse du vétérinaire à l'éleveur (lot 12)."""
    a = regles.alertes_visibles(current_user).filter(AlerteSanitaire.numero == numero).first_or_404()
    try:
        regles.repondre(a, request.form.get('texte'), request.form.getlist('conseils'), current_user)
        db.session.commit()
        flash("Réponse envoyée à l'éleveur ✓", 'success')
    except regles.RegleSante as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('sante.alerte', numero=a.numero) + '#reponse')


# ── Vaccins et traitements ──────────────────────────────────────────────

@sante_bp.route('/vaccins')
@profil_requis(Profil.VETO, Profil.ADMIN, Profil.AGENT)
def vaccins():
    bandes = filtre_perimetre(Bande.query)
    en_cours = bandes.filter(Bande.statut == StatutBande.EN_COURS).order_by(Bande.numero_metier).all()
    delais = [(b, regles.fin_delai_attente(b)) for b in en_cours]
    return render_template('sante/vaccins.html', calendrier=regles.calendrier(),
                           retards=regles.vaccins_en_retard(bandes),
                           delais=[(b, f) for b, f in delais if f],
                           valide=parametres.obtenir('sante.calendrier_valide', False),
                           peut_modifier=current_user.profil in (Profil.VETO, Profil.ADMIN),
                           conseil=parametres.obtenir('sante.conseil_feu_rouge'),
                           vaccins_catalogue=Produit.query.filter_by(type='Vaccin', actif=True).order_by(Produit.nom).all(),
                           modes=[v for v, _ in ld_choices('modes_administration')])


@sante_bp.route('/calendrier', methods=['POST'])
@profil_requis(Profil.VETO, Profil.ADMIN)
def calendrier_enregistrer():
    f = request.form
    entree = db.session.get(CalendrierVaccinal, f.get('id', type=int)) if f.get('id') else CalendrierVaccinal()
    age, produit = _entier(f.get('age_jours')), db.session.get(Produit, f.get('produit_id', type=int) or 0)
    if age is None or age < 0 or produit is None or produit.type != 'Vaccin' or not f.get('mode'):
        flash('Indiquez l\'âge, le vaccin et le mode d\'administration.', 'danger')
        return redirect(url_for('sante.vaccins'))
    # Lot 15 : quatre yeux — le calendrier actuel s'applique jusqu'à l'approbation
    from app.services import approbations
    actif = f.get('actif', 'on') == 'on'
    avant = f'J{entree.age_jours} {entree.produit.nom} ({entree.mode})' if entree.id else 'nouvelle ligne'
    apres = f'J{age} {produit.nom} ({f.get("mode")})' + ('' if actif else ' · désactivée')
    try:
        approbations.proposer('CALENDRIER', f'calendrier.{entree.id or "nouveau"}.{age}.{produit.id}',
                              'Calendrier vaccinal', avant, apres,
                              {'id': entree.id, 'age_jours': age, 'produit_id': produit.id, 'mode': f.get('mode'),
                               'actif': actif}, f.get('motif', '') or 'Mise à jour du calendrier', current_user)
        db.session.commit()
        flash('Modification du calendrier proposée : elle s\'appliquera après approbation par une autre personne.', 'info')
    except approbations.RegleApprobation as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('sante.vaccins'))


@sante_bp.route('/conseil', methods=['POST'])
@profil_requis(Profil.VETO, Profil.ADMIN)
def conseil():
    """Conseil affiché à l'éleveur au feu rouge (paramètre, inscrit au journal)."""
    from app.models import Parametre
    texte = request.form.get('conseil', '').strip()
    p = Parametre.query.filter_by(cle='sante.conseil_feu_rouge').first()
    if not texte or p is None:
        flash('Écrivez le conseil.', 'danger')
    else:
        p.valeur, p.modifie_par = texte[:500], current_user.id
        db.session.commit()
        flash("Conseil enregistré : il s'affiche chez l'éleveur quand le feu est rouge.", 'success')
    return redirect(url_for('sante.vaccins'))


@sante_bp.route('/calendrier/valider', methods=['POST'])
@profil_requis(Profil.VETO)
def calendrier_valider():
    from app.models import Parametre
    p = Parametre.query.filter_by(cle='sante.calendrier_valide').first()
    if p:
        p.valeur = 'oui'
        p.modifie_par = current_user.id
        db.session.commit()
    flash('Calendrier vaccinal validé par les services vétérinaires.', 'success')
    return redirect(url_for('sante.vaccins'))


@sante_bp.route('/vacciner/<numero>', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def vacciner(numero):
    bande = _bande(numero)
    if not bande.en_cours:
        abort(403)
    entree = db.session.get(CalendrierVaccinal, request.values.get('calendrier', type=int) or 0)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            jour = date.fromisoformat(f.get('date') or date.today().isoformat())
            produit = db.session.get(Produit, f.get('produit_id', type=int) or 0)
            v = regles.vacciner(bande, jour, produit, f.get('mode'), _entier(f.get('nombre')),
                                _decimal(f.get('quantite')), entree, current_user)
            db.session.commit()
            depuis = f.get('depuis')
            if current_user.profil == Profil.ELEVEUR and depuis in ('soins', 'accueil'):
                # Lot 11 : « ✓ C'est fait » d'un toucher, puis « Fait ✓ — Annuler (10) »
                from app.services import hors_ligne
                if not hors_ligne.actif():
                    session['vaccin_recent'] = str(v.id)
                return redirect(url_for('eleveur.soins') if depuis == 'soins' else url_for('accueil.index'))
            flash('Vaccination enregistrée ✓', 'success')
            return _retour(bande)
        except (regles.RegleSante, ValueError) as e:
            db.session.rollback()
            erreur = str(e) if isinstance(e, regles.RegleSante) else 'Date invalide.'
    from app import indicateurs
    from app.services import intrants
    stocks = {s['produit'].id: s['stock'] for s in intrants.stock_ferme(bande.ferme)}
    return render_template('sante/vacciner.html', bande=bande, entree=entree, erreur=erreur, saisie=request.form,
                           stocks=stocks,
                           present=indicateurs.calculer(bande)['effectif_present'],
                           vaccins=Produit.query.filter_by(type='Vaccin', actif=True).order_by(Produit.nom).all(),
                           modes=[v for v, _ in ld_choices('modes_administration')])


@sante_bp.route('/traiter/<numero>', methods=['GET', 'POST'])
@profil_requis(Profil.ELEVEUR, Profil.AGENT)
def traiter(numero):
    bande = _bande(numero)
    if not bande.en_cours:
        abort(403)
    erreur = None
    if request.method == 'POST':
        f = request.form
        try:
            debut = date.fromisoformat(f.get('date_debut') or '')
            fin = date.fromisoformat(f.get('date_fin') or '')
            produit = db.session.get(Produit, f.get('produit_id', type=int) or 0)
            t = regles.traiter(bande, debut, fin, produit, f.get('motif', '').strip(), _entier(f.get('nombre')),
                               _decimal(f.get('quantite')), current_user)
            db.session.commit()
            flash('Traitement enregistré ✓', 'success')
            if produit.delai_attente_jours:
                flash(f'Délai d\'attente avant abattage : {produit.delai_attente_jours} jours après la fin, '
                      f'soit jusqu\'au {regles.fin_delai_attente(bande).strftime("%d/%m/%Y")}.', 'warning')
            return _retour(bande)
        except (regles.RegleSante, ValueError) as e:
            db.session.rollback()
            erreur = str(e) if isinstance(e, regles.RegleSante) else 'Indiquez les dates de début et de fin.'
    from app import indicateurs
    return render_template('sante/traiter.html', bande=bande, erreur=erreur, saisie=request.form,
                           present=indicateurs.calculer(bande)['effectif_present'],
                           medicaments=Produit.query.filter_by(type='Médicament', actif=True).order_by(Produit.nom).all())
