"""Traçabilité : lots et QR codes (pages internes) et page publique du QR code."""
from flask import Blueprint, render_template, request, Response, redirect, url_for, flash, abort
from flask_login import current_user
from markupsafe import Markup

from app import db
from app.models import Profil
from app.models.bande import Sortie
from app.models.tracabilite import LotTrace
from app.services import tracabilite
from app.services.journal import enregistrer, Action
from app.utils.permissions import profil_requis, filtre_perimetre

tracabilite_bp = Blueprint('tracabilite', __name__)
public_bp = Blueprint('public', __name__)

LECTEURS = (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO)


def charger(numero):
    lot = filtre_perimetre(LotTrace.query.filter_by(numero=numero)).first()
    if lot is None:
        abort(404)
    return lot


@tracabilite_bp.route('/lots')
@profil_requis(*LECTEURS)
def lots():
    q = request.args.get('q', '').strip()
    requete = filtre_perimetre(LotTrace.query).join(Sortie, LotTrace.sortie_id == Sortie.id)
    if q:
        requete = requete.filter(LotTrace.numero.ilike(f'%{q}%'))
    liste = requete.order_by(Sortie.date.desc(), LotTrace.id.desc()).limit(200).all()
    return render_template('tracabilite/lots.html', lots=liste, q=q)


@tracabilite_bp.route('/lots/<numero>')
@profil_requis(*LECTEURS)
def lot(numero):
    lot = charger(numero)
    lectures = tracabilite.lectures(lot)
    return render_template('tracabilite/lot.html', lot=lot, adresse=tracabilite.adresse(lot),
                           provisoire=tracabilite.adresse_provisoire(),
                           qr=Markup(tracabilite.svg(tracabilite.adresse(lot))),
                           nb_lectures=lectures.count(), lectures=lectures.limit(10).all())


@tracabilite_bp.route('/lots/<numero>/etiquettes.pdf')
@profil_requis(*LECTEURS)
def etiquettes(numero):
    lot = charger(numero)
    if lot.annule:
        flash('Ce lot est annulé : ses étiquettes ne sont plus imprimables.', 'warning')
        return redirect(url_for('tracabilite.lot', numero=numero))
    enregistrer(Action.EXPORT, table='lot_trace', enregistrement_id=lot.id,
                detail=f'Étiquettes QR du lot {lot.numero}')
    db.session.commit()
    return Response(tracabilite.etiquettes(lot), mimetype='application/pdf',
                    headers={'Content-Disposition': f'inline; filename=etiquettes_{lot.numero}.pdf'})


@tracabilite_bp.route('/lots/<numero>/annuler', methods=['POST'])
@profil_requis(Profil.ADMIN)
def annuler(numero):
    lot = charger(numero)
    motif = request.form.get('motif', '').strip()
    if not motif:
        flash("Indiquez le motif de l'annulation.", 'danger')
    elif not lot.annule:
        tracabilite.annuler(lot, motif)
        db.session.commit()
        flash(f'Lot {lot.numero} annulé : son QR code affiche désormais « Code inconnu ».', 'success')
    return redirect(url_for('tracabilite.lot', numero=numero))


# ── Page publique (sans connexion) ──────────────────────────────────────

@public_bp.route('/q/<code>')
def qr(code):
    lot = tracabilite.lot_du_code(code)
    tracabilite.noter_lecture(code, lot)
    db.session.commit()
    if lot is None:
        return render_template('tracabilite/public.html', lot=None), 404
    from app.services import receptions
    return render_template('tracabilite/public.html', lot=lot, etape=receptions.etape_publique(lot))
