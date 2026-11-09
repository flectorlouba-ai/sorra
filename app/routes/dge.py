"""Lot 18 — écrans de la DGE : planning des livraisons de l'État, « Créer la livraison » d'une commande,
classement pondéré des fermes, rapports mensuels gardés, agents (affectation et charge)."""
import csv
import io
import os
import uuid
from datetime import date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, Response, send_file
from flask_login import current_user

from app import db
from app.models import Ferme, Profil, Produit, Province, Livraison, Utilisateur
from app.models.agent import CommandeIntrant
from app.models.dge import RapportMensuel
from app.services import dge as regles
from app.services.journal import enregistrer, Action
from app.utils.permissions import profil_requis, filtre_perimetre

dge_bp = Blueprint('dge', __name__)
NATIONAUX = (Profil.DGE, Profil.ADMIN)


def _nombre(texte):
    try:
        return float((texte or '').replace(',', '.').replace(' ', ''))
    except ValueError:
        return None


def _livraison(numero):
    liv = filtre_perimetre(Livraison.query).filter(Livraison.numero_metier == numero).first()
    if liv is None:
        abort(404)
    return liv


# ── A. Planning ─────────────────────────────────────────────────────────

@dge_bp.route('/livraisons-etat/planning')
@profil_requis(*NATIONAUX)
def planning():
    colonnes, debut, fin = regles.planning(current_user)
    return render_template('dge/planning.html', colonnes=colonnes, titres=regles.COLONNES, debut=debut, fin=fin,
                           fermes=filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all(),
                           produits=Produit.query.filter_by(actif=True).order_by(Produit.type, Produit.nom).all())


@dge_bp.route('/livraisons-etat/prevoir', methods=['POST'])
@profil_requis(*NATIONAUX)
def prevoir():
    f = request.form
    ferme = filtre_perimetre(Ferme.query).filter(Ferme.numero_metier == f.get('ferme', '')).first()
    try:
        jour = date.fromisoformat(f.get('date', ''))
    except ValueError:
        jour = None
    try:
        liv = regles.prevoir(ferme, jour, db.session.get(Produit, f.get('produit_id', type=int) or 0),
                             _nombre(f.get('quantite')), (f.get('fournisseur') or '').strip(), current_user)
        db.session.commit()
        flash(f'Livraison {liv.numero} prévue le {liv.date_livraison:%d/%m/%Y}.', 'success')
    except regles.RegleDge as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('dge.planning'))


@dge_bp.route('/livraisons-etat/<numero>/livree', methods=['POST'])
@profil_requis(*NATIONAUX)
def livree(numero):
    liv = _livraison(numero)
    try:
        regles.marquer_livree(liv, current_user)
        db.session.commit()
        flash(f'Livraison {liv.numero} livrée : l’éleveur va la confirmer.', 'success')
    except regles.RegleDge as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('dge.planning'))


@dge_bp.route('/livraisons-etat/<numero>/annuler', methods=['POST'])
@profil_requis(*NATIONAUX)
def annuler(numero):
    liv = _livraison(numero)
    try:
        regles.annuler_prevue(liv, request.form.get('motif'), current_user)
        db.session.commit()
        flash(f'Livraison {liv.numero} annulée.', 'info')
    except regles.RegleDge as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('dge.planning'))


# ── B. Commande validée → livraison ─────────────────────────────────────

@dge_bp.route('/commandes/<int:ident>/creer-livraison', methods=['POST'])
@profil_requis(*NATIONAUX)
def creer_livraison(ident):
    c = filtre_perimetre(CommandeIntrant.query).filter(CommandeIntrant.id == ident).first_or_404()
    try:
        liv = regles.creer_livraison_commande(c, current_user)
        db.session.commit()
        flash(f'Livraison {liv.numero} prévue le {liv.date_livraison:%d/%m/%Y} : à suivre sur le planning.', 'success')
    except regles.RegleDge as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('agent.commandes'))


# ── D. Classement ───────────────────────────────────────────────────────

def _classement():
    pid = request.args.get('province', type=int)
    cohorte = request.args.get('cohorte', type=int)
    return regles.classement(current_user, pid, cohorte), pid, cohorte


@dge_bp.route('/classement')
@profil_requis(*NATIONAUX)
def classement():
    r, pid, cohorte = _classement()
    return render_template('dge/classement.html', r=r, criteres=regles.CRITERES, province=pid, cohorte=cohorte,
                           provinces=Province.query.order_by(Province.ordre).all(), seuil=regles.SEUIL_COMPLET)


@dge_bp.route('/classement.csv')
@profil_requis(*NATIONAUX)
def classement_csv():
    r, pid, cohorte = _classement()
    tampon = io.StringIO()
    w = csv.writer(tampon, delimiter=';')
    w.writerow(['Rang', 'N°', 'Ferme', 'Province', 'Score'] + [t for _, t in regles.CRITERES]
               + ['Bandes comptées', 'Bandes incomplètes ignorées'])
    for x in r['classees']:
        w.writerow([x['rang'], x['ferme'].numero, x['ferme'].nom, x['ferme'].province.nom, x['score']]
                   + [x['notes'][c] for c, _ in regles.CRITERES] + [x['bandes'], x['incompletes']])
    for x in r['non_classees']:
        w.writerow(['', x['ferme'].numero, x['ferme'].nom, x['ferme'].province.nom, 'non classée']
                   + [''] * len(regles.CRITERES) + [0, x['incompletes']])
    enregistrer(Action.EXPORT, table='classement', detail='Export du classement des fermes')
    db.session.commit()
    return Response('﻿' + tampon.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename=classement-{date.today():%Y%m%d}.csv'})


# ── E. Rapports mensuels gardés ─────────────────────────────────────────

@dge_bp.route('/rapports/mensuels/<mois>.pdf')
@profil_requis(*NATIONAUX)
def rapport_garde(mois):
    r = RapportMensuel.query.filter_by(mois=mois).first_or_404()
    chemin = os.path.join(regles.dossier_rapports(), r.fichier)
    if not os.path.exists(chemin):
        abort(404)
    enregistrer(Action.EXPORT, table='rapport_mensuel', enregistrement_id=str(r.id),
                detail=f'Téléchargement du rapport mensuel gardé {mois}')
    db.session.commit()
    return send_file(chemin, mimetype='application/pdf', as_attachment=True, download_name=r.fichier)


# ── F. Agents ───────────────────────────────────────────────────────────

@dge_bp.route('/agents')
@profil_requis(*NATIONAUX)
def agents():
    lignes = regles.charge_des_agents(current_user)
    return render_template('dge/agents.html', lignes=lignes, orange=regles.CHARGE_ORANGE, rouge=regles.CHARGE_ROUGE,
                           fermes=filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier).all(),
                           agents=[x['agent'] for x in lignes])


@dge_bp.route('/agents/reaffecter', methods=['POST'])
@profil_requis(*NATIONAUX)
def reaffecter():
    ferme = filtre_perimetre(Ferme.query).filter(Ferme.numero_metier == request.form.get('ferme', '')).first()
    if ferme is None:
        abort(404)
    try:
        nouvel = db.session.get(Utilisateur, uuid.UUID(request.form.get('agent', '')))
    except ValueError:
        nouvel = None
    try:
        regles.reaffecter(ferme, nouvel, request.form.get('motif'), current_user)
        db.session.commit()
        flash(f'Ferme {ferme.numero} confiée à {nouvel.nom_complet}.', 'success')
    except regles.RegleDge as e:
        db.session.rollback()
        flash(str(e), 'danger')
    return redirect(url_for('dge.agents'))
