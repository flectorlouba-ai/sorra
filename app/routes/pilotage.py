"""Tableaux de bord, carte des fermes, rapports PDF, exports, formules des indicateurs."""
import csv
import io
from datetime import date, timedelta

from flask import Blueprint, render_template, request, Response, redirect, url_for, flash, abort
from flask_login import current_user
from openpyxl import Workbook
from openpyxl.styles import Font

from app import db, indicateurs
from app.models import Province, Profil, Ferme, Livraison, Parametre, TypeParametre
from app.models.bande import Bande
from app.models.liste_deroulante import ld_choices
from app.models.sante import AlerteSanitaire
from app.services import pilotage, rapports_pdf, sante, intrants
from app.services.journal import enregistrer, Action
from app.utils.nombres import quantite
from app.utils.permissions import profil_requis, filtre_perimetre

pilotage_bp = Blueprint('pilotage', __name__)

TABLEAU = (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO)
NATIONAL = (Profil.ADMIN, Profil.DGE)
XLSX = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _provinces_visibles():
    if current_user.est_national:
        return Province.query.order_by(Province.ordre).all()
    ids = {fe.province_id for fe in filtre_perimetre(Ferme.query)} | set(current_user.province_ids)
    return [p for p in Province.query.order_by(Province.ordre) if p.id in ids]


def _barres(lignes, cle, largeur=100, unite=''):
    """Barres horizontales simples (dessinées sur place) : [(libellé, valeur, largeur en %)]."""
    valeurs = [l[cle] or 0 for l in lignes]
    maximum = max(valeurs + [0]) or 1
    return [{'libelle': l['province'].nom, 'valeur': l[cle], 'largeur': round((l[cle] or 0) / maximum * largeur),
             'unite': unite} for l in lignes]


@pilotage_bp.route('/tableau-de-bord')
@profil_requis(*TABLEAU)
def tableau():
    f = pilotage.lire_filtres(request.args)
    donnees = pilotage.tableau(current_user, f)
    argent_eleveurs = None
    if current_user.profil in (Profil.DGE, Profil.ADMIN):
        # Lot 11 : totaux agrégés par province seulement (moins de 3 fermes : « — »)
        from app.services import argent
        argent_eleveurs = argent.agregats(pilotage.fermes_filtrees(current_user, f).all(),
                                          f.get('du_date'), f.get('au_date'))
    alertes = sante.alertes_visibles(current_user).filter(AlerteSanitaire.statut.in_(('NOUVELLE', 'EN_ANALYSE', 'CONFIRMEE'))).count()
    return render_template('pilotage/tableau.html', d=donnees, f=f, provinces=_provinces_visibles(),
                           statuts=[v for v, _ in ld_choices('statuts_ferme')], alertes=alertes,
                           barres_mortalite=_barres(donnees['par_province'], 'mortalite', unite=' %'),
                           barres_presents=_barres(donnees['par_province'], 'effectifs_presents'),
                           national=current_user.est_national, argent_eleveurs=argent_eleveurs)


@pilotage_bp.route('/carte')
@profil_requis(*NATIONAL)
def carte():
    pid = request.args.get('province', type=int)
    programme = request.args.get('programme', '')
    return render_template('pilotage/carte.html', carte=pilotage.carte(current_user, pid, programme=programme),
                           province=pid, programme=programme,
                           provinces=Province.query.order_by(Province.ordre).all())


# ── Rapports PDF ────────────────────────────────────────────────────────

def _pdf(contenu, nom, detail):
    enregistrer(Action.EXPORT, table='rapport', detail=detail)
    db.session.commit()
    return Response(contenu, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={nom}'})


@pilotage_bp.route('/rapports')
@profil_requis(*NATIONAL)
def rapports():
    from app.models.dge import RapportMensuel
    from app.services import dge
    if current_user.profil in (Profil.DGE, Profil.ADMIN):     # lot 18 : le mois terminé est produit et gardé
        if dge.generer_manquants(current_user):
            db.session.commit()
    return render_template('pilotage/rapports.html', provinces=Province.query.order_by(Province.ordre).all(),
                           mois=date.today().strftime('%Y-%m'),
                           gardes=RapportMensuel.query.order_by(RapportMensuel.mois.desc()).limit(24).all(),
                           destinataires=dge.destinataires(), email_actif=dge.email_actif())


@pilotage_bp.route('/rapports/hebdomadaire.pdf')
@profil_requis(*NATIONAL)
def rapport_hebdo():
    au = date.today()
    du = au - timedelta(days=6)
    pid = request.args.get('province', type=int)
    province = db.session.get(Province, pid) if pid else None
    f = {'province': str(pid) if pid else '', 'du_date': du, 'au_date': au}
    portee = province.nom if province else 'national'
    contenu = rapports_pdf.rapport_periode(
        f'Rapport hebdomadaire — {portee}', f'Du {du.strftime("%d/%m/%Y")} au {au.strftime("%d/%m/%Y")}',
        pilotage.tableau(current_user, f), _alertes_confirmees(pid))
    return _pdf(contenu, f'rapport_hebdo_{(province.code if province else "national").lower()}_{au:%Y%m%d}.pdf',
                f'Rapport hebdomadaire ({portee}) du {du:%d/%m} au {au:%d/%m/%Y}')


@pilotage_bp.route('/rapports/mensuel.pdf')
@profil_requis(*NATIONAL)
def rapport_mensuel():
    try:
        annee, mois = (int(x) for x in request.args.get('mois', date.today().strftime('%Y-%m')).split('-'))
        du = date(annee, mois, 1)
    except ValueError:
        abort(400)
    contenu = contenu_mensuel(du.strftime('%Y-%m'), current_user)
    return _pdf(contenu, f'rapport_mensuel_{du:%Y%m}.pdf', f'Rapport mensuel national {du:%m/%Y}')


def contenu_mensuel(mois, user):
    """PDF du rapport mensuel national (« 2026-10 ») ; sert aussi aux rapports gardés (lot 18)."""
    annee, m = (int(x) for x in mois.split('-'))
    du = date(annee, m, 1)
    au = (du.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return rapports_pdf.rapport_periode(
        f'Rapport mensuel national — {du.strftime("%m/%Y")}', f'Du {du:%d/%m/%Y} au {au:%d/%m/%Y}',
        pilotage.tableau(user, {'du_date': du, 'au_date': au}), _alertes_confirmees(None))


def _alertes_confirmees(province_id):
    q = AlerteSanitaire.query.filter(AlerteSanitaire.confirmee.is_(True))
    if province_id:
        q = q.join(Ferme, AlerteSanitaire.ferme_id == Ferme.id).filter(Ferme.province_id == province_id)
    return q.count()


@pilotage_bp.route('/rapports/bande/<numero>.pdf')
@profil_requis(*TABLEAU)
def rapport_bande(numero):
    bande = filtre_perimetre(Bande.query.filter_by(numero_metier=numero)).first()
    if bande is None:
        abort(404)
    if bande.en_cours or not bande.bilan:
        flash('Le rapport de fin de bande est disponible après la clôture.', 'warning')
        return redirect(url_for('bandes.fiche', numero=numero))
    return _pdf(rapports_pdf.rapport_fin_bande(bande), f'fin_de_bande_{numero}.pdf', f'Rapport de fin de bande {numero}')


# ── Exports Excel / CSV (selon les droits, journalisés) ────────────────

def _lignes_fermes():
    yield ['N°', 'Ferme', 'Exploitant', 'Téléphone', 'Province', 'Localité', 'Référence AMI', 'Cohorte',
           'Statut', 'Agent', 'Places', 'Latitude', 'Longitude']
    for fe in filtre_perimetre(Ferme.query).order_by(Ferme.numero_metier):
        yield [fe.numero, fe.nom, fe.exploitant_nom, fe.exploitant_telephone, fe.province.nom, fe.localite.nom,
               fe.reference_ami or '', fe.cohorte or '', fe.statut, fe.agent.nom_complet if fe.agent else '',
               fe.capacite, fe.latitude or '', fe.longitude or '']


def _lignes_livraisons():
    yield ['N°', 'Date', 'Ferme', 'Fournisseur', 'Statut', 'Produit', 'Livré', 'Reçu', 'Morts à l\'arrivée',
           'Subvention (%)', 'Valeur unitaire (FCFA)']
    for liv in intrants.livraisons_de_l_etat(filtre_perimetre(Livraison.query)).order_by(Livraison.date_livraison.desc()):
        for l in liv.lignes:
            yield [liv.numero, liv.date_livraison.strftime('%d/%m/%Y'), liv.ferme.numero, liv.fournisseur or '',
                   liv.libelle_statut, l.produit.nom, l.quantite_livree,
                   '' if l.quantite_recue is None else l.quantite_recue, l.morts_arrivee or '',
                   l.part_subventionnee or '', l.valeur_unitaire or '']


def _lignes_bandes():
    yield ['N°', 'Ferme', 'Bâtiment', 'Mise en place', 'Clôture', 'Statut', 'Mis en place', 'Présents', 'Morts',
           'Mortalité (%)', 'Poids moyen (g)', 'IC', 'Aliment (kg)', 'Rattrapage']
    for b in filtre_perimetre(Bande.query).order_by(Bande.numero_metier):
        v = indicateurs.calculer(b)
        yield [b.numero, b.ferme.numero, b.batiment.code, b.date_mise_en_place.strftime('%d/%m/%Y'),
               b.date_cloture.strftime('%d/%m/%Y') if b.date_cloture else '', b.libelle_statut,
               b.effectif_initial, v['effectif_present'], v['morts_cumules'],
               indicateurs.arrondi(v['mortalite'], 2), indicateurs.arrondi(v['poids_moyen_g'], 0),
               indicateurs.arrondi(v['indice_consommation'], 2), indicateurs.arrondi(v['aliment_kg'], 1),
               'oui' if b.rattrapage else '']


EXPORTS = {
    'fermes': (_lignes_fermes, (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO), 'Fermes'),
    'livraisons': (_lignes_livraisons, (Profil.ADMIN, Profil.DGE, Profil.AGENT), 'Livraisons'),
    'bandes': (_lignes_bandes, (Profil.ADMIN, Profil.DGE, Profil.AGENT, Profil.VETO), 'Bandes'),
}


@pilotage_bp.route('/exports/<quoi>.<format>')
@profil_requis(*TABLEAU)
def exporter(quoi, format):
    if quoi not in EXPORTS or format not in ('csv', 'xlsx'):
        abort(404)
    source, profils, titre = EXPORTS[quoi]
    if current_user.profil not in profils:
        abort(403)
    lignes = list(source())
    enregistrer(Action.EXPORT, table=quoi, detail=f'Export {format.upper()} « {titre} » : {len(lignes) - 1} ligne(s)')
    db.session.commit()
    nom = f'{quoi}_sorra_{date.today():%Y%m%d}.{format}'
    if format == 'csv':
        tampon = io.StringIO()
        tampon.write('﻿')
        csv.writer(tampon, delimiter=';').writerows(lignes)
        return Response(tampon.getvalue(), mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment; filename={nom}'})
    wb = Workbook()
    ws = wb.active
    ws.title = titre
    for l in lignes:
        ws.append(l)
    for c in ws[1]:
        c.font = Font(bold=True)
    tampon = io.BytesIO()
    wb.save(tampon)
    return Response(tampon.getvalue(), mimetype=XLSX, headers={'Content-Disposition': f'attachment; filename={nom}'})


# ── Formules des indicateurs (ADMIN) ────────────────────────────────────

EXEMPLE = {'mis_en_place': 1000, 'morts_cumules': 30, 'sorties': 500, 'poids_sorties_kg': 1250,
           'poids_initial_g': 40, 'poids_moyen_g': 2500, 'age_pesee': 42, 'aliment_kg': 4200,
           'jours_saisis': 40, 'jours_ecoules': 42, 'morts_jour': 3, 'effectif_avant_jour': 473}


def _autorisees(nom):
    noms = list(indicateurs.FORMULES)
    return set(indicateurs.VARIABLES) | set(noms[:noms.index(nom)])


@pilotage_bp.route('/formules', methods=['GET', 'POST'])
@profil_requis(Profil.ADMIN)
def formules():
    resultat = None
    if request.method == 'POST':
        nom, action = request.form.get('nom'), request.form.get('action')
        if nom not in indicateurs.FORMULES:
            abort(400)
        texte = request.form.get('formule', '').strip()
        p = Parametre.query.filter_by(cle=f'formule.{nom}').first()
        try:
            from app.services import approbations
            libelle = f'Formule : {indicateurs.FORMULES[nom][0]}'
            if action == 'origine':
                # Lot 15 : quatre yeux — la formule actuelle s'applique jusqu'à l'approbation
                approbations.proposer('FORMULE', f'formule.{nom}', libelle, indicateurs.formule(nom),
                                      indicateurs.FORMULES[nom][1], {'valeur': indicateurs.FORMULES[nom][1],
                                                                     'type': 'TEXTE', 'description': libelle},
                                      request.form.get('motif') or "Retour à la formule d'origine", current_user)
                db.session.commit()
                flash(f'« {indicateurs.FORMULES[nom][0]} » : retour à la formule d\'origine proposé (à approuver).', 'info')
                return redirect(url_for('pilotage.formules'))
            indicateurs.analyser(texte, _autorisees(nom))
            if action == 'tester':
                valeurs = indicateurs.calculer_formules(EXEMPLE)
                essai = indicateurs.evaluer(texte, {k: v for k, v in valeurs.items() if k in _autorisees(nom)})
                resultat = {'nom': nom, 'texte': texte, 'valeur': essai}
            else:
                approbations.proposer('FORMULE', f'formule.{nom}', libelle, indicateurs.formule(nom), texte,
                                      {'valeur': texte, 'type': 'TEXTE', 'description': libelle},
                                      request.form.get('motif', ''), current_user)
                db.session.commit()
                flash(f'« {indicateurs.FORMULES[nom][0]} » : formule proposée ; elle s\'appliquera après '
                      f'approbation par une autre personne.', 'info')
                return redirect(url_for('pilotage.formules'))
        except approbations.RegleApprobation as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except indicateurs.FormuleInvalide as e:
            flash(f'« {indicateurs.FORMULES[nom][0]} » : {e}', 'danger')
            resultat = {'nom': nom, 'texte': texte, 'invalide': True}
    lignes = []
    for nom, (libelle, origine) in indicateurs.FORMULES.items():
        lignes.append({'nom': nom, 'libelle': libelle, 'origine': origine, 'actuelle': indicateurs.formule(nom),
                       'autorisees': sorted(_autorisees(nom))})
    return render_template('pilotage/formules.html', lignes=lignes, variables=indicateurs.VARIABLES,
                           exemple=EXEMPLE, resultat=resultat)
