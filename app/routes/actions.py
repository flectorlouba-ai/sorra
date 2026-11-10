"""Lot D — plans d'actions (tableau, création en fenêtre, modification, clôture) et rapports standards (liste,
génération à la demande, téléchargement, bilan de bande)."""
import uuid
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response
from flask_login import login_required, current_user

from app import db
from app.models import Ferme, Profil, Province, Utilisateur
from app.models.action import Action, OrigineAction, Priorite
from app.models.bande import Bande
from app.models.rapport import Rapport, TypeRapport
from app.services import actions as regles, rapports as services_rapports, sante
from app.services.journal import enregistrer, Action as J
from app.utils.permissions import filtre_perimetre, profil_requis

actions_bp = Blueprint('actions', __name__)
GESTIONNAIRES = (Profil.DGE, Profil.ADMIN, Profil.AGENT)


def _retour(defaut):
    r = request.form.get('retour') or request.args.get('retour') or ''
    return r if r.startswith('/') and not r.startswith('//') else defaut


def _ferme(numero):
    if not numero:
        return None
    return filtre_perimetre(Ferme.query).filter(Ferme.du_numero(numero)).first()


def _contexte(user):
    return dict(responsables=regles.responsables_possibles(user), priorites=Priorite.TOUTES,
                libelles_priorite=Priorite.LIBELLES, origines=OrigineAction.LIBELLES,
                fermes=filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all(),
                provinces=Province.query.order_by(Province.ordre).all() if user.profil in (Profil.DGE, Profil.ADMIN) else [],
                phrase=regles.phrase_echeance)


@actions_bp.route('/actions')
@profil_requis(*GESTIONNAIRES)
def liste():
    etat = request.args.get('etat', '')
    actions = regles.visibles(current_user).filter(Action.archive_le.is_(None)).order_by(Action.echeance).all()
    if etat:
        actions = [a for a in actions if a.etat == etat]
    return render_template('actions/liste.html', actions=actions, etat=etat, **_contexte(current_user),
                           prerempli={'origine': request.args.get('origine', OrigineAction.MANUEL),
                                      'origine_table': request.args.get('table', ''), 'origine_id': request.args.get('id', ''),
                                      'intitule': request.args.get('intitule', ''), 'ferme': request.args.get('ferme', '')},
                           ouvrir=bool(request.args.get('nouvelle')))


@actions_bp.route('/actions/creer', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def creer():
    f = request.form
    try:
        responsable = None
        if f.get('responsable_id'):
            responsable = db.session.get(Utilisateur, uuid.UUID(f['responsable_id']))
        province = db.session.get(Province, int(f['province_id'])) if (f.get('province_id') or '').isdigit() else None
        a = regles.creer(current_user, f.get('intitule'), f.get('echeance'), responsable, f.get('priorite'),
                         _ferme(f.get('ferme')), province, f.get('origine') if f.get('origine') in OrigineAction.TOUS else OrigineAction.MANUEL,
                         f.get('origine_table') or None, f.get('origine_id') or None, f.get('commentaire'))
        db.session.commit()
        flash(f'Action {a.numero} créée, confiée à {a.responsable.nom_complet} pour le {a.echeance:%d/%m}.', 'success')
    except (regles.RegleAction, ValueError) as e:
        db.session.rollback()
        flash(str(e) if str(e) else 'Saisie invalide.', 'danger')
    return redirect(_retour(url_for('actions.liste')))


@actions_bp.route('/actions/<int:ident>', methods=['POST'])
@profil_requis(*GESTIONNAIRES)
def modifier(ident):
    a = regles.visibles(current_user).filter(Action.id == ident).first_or_404()
    f = request.form
    try:
        photo = None
        if request.files.get('photo') and request.files['photo'].filename:
            try:
                enregistre = sante._enregistrer(request.files['photo'], sante._SIGNATURES, sous_dossier='actions')
                photo = enregistre[0] if enregistre else None
            except sante.RegleSante as e:
                raise regles.RegleAction(str(e))
        if f.get('action') == 'cloturer':
            regles.cloturer(current_user, a, f.get('commentaire'), photo)
            flash(f'Action {a.numero} faite ✓', 'success')
        elif f.get('action') == 'rouvrir':
            regles.rouvrir(current_user, a)
            flash(f'Action {a.numero} rouverte.', 'info')
        elif f.get('action') == 'archiver':
            if not regles.peut_modifier(current_user, a):
                raise regles.RegleAction('Vous ne pouvez pas archiver cette action.')
            from app.models.base import maintenant
            a.archive_le, a.archive_par = maintenant(), current_user.id
            flash(f'Action {a.numero} archivée.', 'success')
        else:
            responsable = db.session.get(Utilisateur, uuid.UUID(f['responsable_id'])) if f.get('responsable_id') else None
            regles.modifier(current_user, a, intitule=f.get('intitule'), echeance=f.get('echeance'), priorite=f.get('priorite'),
                            responsable=responsable, avancement=f.get('avancement'), commentaire=f.get('commentaire'), photo=photo)
            if f.get('avancement') == '100' and a.faite_le is None:
                regles.cloturer(current_user, a)
            flash(f'Action {a.numero} enregistrée.', 'success')
        db.session.commit()
    except (regles.RegleAction, ValueError) as e:
        db.session.rollback()
        flash(str(e) or 'Saisie invalide.', 'danger')
    return redirect(_retour(url_for('actions.liste')))


@actions_bp.route('/actions/<int:ident>/photo')
@login_required
def photo(ident):
    a = regles.visibles(current_user).filter(Action.id == ident).first_or_404()
    if not a.photo:
        abort(404)
    chemin = sante.chemin_fichier(a.photo, sous_dossier='actions')
    if chemin is None:
        abort(404)
    from flask import send_file
    return send_file(chemin)


# ── Rapports ────────────────────────────────────────────────────────────

@actions_bp.route('/rapports/standards')
@profil_requis(Profil.DGE, Profil.ADMIN, Profil.AGENT, Profil.AUDITEUR, Profil.VETO)
def rapports():
    type_ = request.args.get('type', '')
    q = services_rapports.visibles(current_user)
    if type_ in TypeRapport.LIBELLES:
        q = q.filter(Rapport.type == type_)
    from app.services.dge import mois_termines
    return render_template('actions/rapports.html', rapports=q.order_by(Rapport.genere_le.desc()).limit(300).all(),
                           type=type_, types=TypeRapport.LIBELLES, mois=mois_termines(12),
                           fermes=filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all(),
                           agents=Utilisateur.query.filter_by(profil=Profil.AGENT, actif=True).order_by(Utilisateur.nom).all()
                           if current_user.profil in (Profil.DGE, Profil.ADMIN) else [current_user] if current_user.profil == Profil.AGENT else [],
                           provinces=Province.query.order_by(Province.ordre).all(),
                           peut_generer=current_user.profil in (Profil.DGE, Profil.ADMIN, Profil.AGENT))


@actions_bp.route('/rapports/standards/generer', methods=['POST'])
@profil_requis(Profil.DGE, Profil.ADMIN, Profil.AGENT)
def generer():
    f = request.form
    type_, mois = f.get('type'), f.get('mois', '')
    if type_ not in TypeRapport.LIBELLES or type_ == TypeRapport.BANDE or len(mois) != 7:
        abort(400)
    kw = {}
    if type_ == TypeRapport.FERME:
        kw['ferme'] = _ferme(f.get('ferme')) or abort(404)
    elif type_ == TypeRapport.AGENT:
        agent = db.session.get(Utilisateur, uuid.UUID(f['agent_id'])) if f.get('agent_id') else current_user
        if current_user.profil == Profil.AGENT and agent.id != current_user.id:
            abort(403)
        kw['agent'] = agent
    elif type_ == TypeRapport.PROVINCE:
        kw['province'] = db.session.get(Province, int(f['province_id'])) if (f.get('province_id') or '').isdigit() else abort(400)
        if current_user.profil == Profil.AGENT:
            abort(403)
    elif current_user.profil == Profil.AGENT:
        abort(403)
    r, nouveau = services_rapports.generer(type_, mois, current_user, **kw)
    db.session.commit()
    flash(f'Rapport {r.libelle_type.lower()} {r.periode} · {r.cible} ' + ('généré.' if nouveau else 'déjà disponible.'), 'success')
    return redirect(url_for('actions.rapports'))


@actions_bp.route('/rapports/standards/<int:ident>.pdf')
@login_required
def telecharger(ident):
    r = services_rapports.visibles(current_user).filter(Rapport.id == ident).first_or_404()
    if current_user.profil == Profil.VETO and r.type in (TypeRapport.FERME, TypeRapport.BANDE):
        abort(403)                                     # jamais de donnée financière pour le vétérinaire
    enregistrer(J.EXPORT, table='rapport', enregistrement_id=r.id,
                detail=f'Téléchargement du rapport {r.libelle_type.lower()} {r.periode} · {r.cible}')
    db.session.commit()
    return Response(services_rapports.lire(r), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={r.fichier}'})


@actions_bp.route('/bandes/<numero>/bilan.pdf')
@login_required
def bilan_bande(numero):
    bande = filtre_perimetre(Bande.query.filter_by(numero_metier=numero)).first_or_404()
    if current_user.profil == Profil.VETO:
        abort(403)
    if bande.en_cours:
        flash('Le bilan de la bande est disponible après la clôture.', 'warning')
        return redirect(url_for('bandes.fiche', numero=numero))
    r, _ = services_rapports.bilan_bande(bande, current_user)
    db.session.commit()
    return Response(services_rapports.lire(r), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={r.fichier}'})
