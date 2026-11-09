"""Espace de l'éleveur (lot 9) : accueil en tuiles, « Saisie du jour », accès directs
(Peser, Sortie, Poulet malade, Vaccins), « Mon stock », « J'ai acheté ».
Les écrans eux-mêmes sont ceux des lots 2 à 8 : ici on organise l'accès."""
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
                         'pesee': indicateurs.prochaine_pesee(b),
                         'vaccins': sante.vaccins_de_la_bande(b)})
    return resultat


def accueil(user):
    """Tout ce qu'affiche l'accueil en tuiles. Une tuile sans objet n'est pas rendue."""
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
    poussins = sum(sum(d for _, d in regles_bandes.poussins_en_attente(f)) for f in fermes
                   if regles_bandes.batiments_libres(f))
    from app.services import entretien
    a_faire_entretien = sum(entretien.a_faire_aujourdhui(f) for f in fermes)
    pannes = sum(len(entretien.pannes_en_cours(f)) for f in fermes)
    pesees = sorted(sit, key=lambda s: s['pesee'])
    pesee_due = [s for s in pesees if s['pesee'] <= auj]
    etats_vaccins = {v['etat'] for s in sit for v in s['vaccins']}
    vaccin = ('en retard' if 'retard' in etats_vaccins else
              "aujourd'hui" if etats_vaccins & {'aujourdhui', 'a_faire'} else
              'demain' if 'demain' in etats_vaccins else None)
    # Ordre FIXE (décision du propriétaire) : il ne dépend jamais des pastilles ; une tuile sans
    # objet disparaît, les autres gardent leur rang. « Saisie du jour » (en tête) et « Appeler
    # mon agent » (en dernier) sont en pleine largeur, hors de cette grille.
    tuiles = [
        {'cle': 'livraisons', 'ico': '📦', 'nom': 'Livraisons', 'lien': url_for('livraisons.mes_livraisons'),
         'sous': 'à confirmer' if livraisons else 'tout est confirmé', 'pastille': livraisons or None},
        {'cle': 'bande', 'ico': '🐣', 'nom': 'Nouvelle bande', 'lien': url_for('bandes.ouvrir'),
         'sous': 'poussins en attente', 'pastille': poussins, 'visible': poussins > 0},
        {'cle': 'peser', 'ico': '⚖️', 'nom': 'Peser', 'lien': url_for('eleveur.aller', quoi='peser'),
         'sous': (f'{pesee_due[0]["code"]} : pesée prévue aujourd\'hui' if pesee_due else
                  f'prochaine : {pesees[0]["code"]} le {pesees[0]["pesee"].strftime("%d/%m")}' if pesees else ''),
         'pastille': '!' if pesee_due else None, 'visible': bool(sit)},
        {'cle': 'vaccins', 'ico': '💉', 'nom': 'Vaccins', 'lien': url_for('eleveur.aller', quoi='vaccins'),
         'sous': 'et traitements', 'pastille': vaccin, 'pastille_classe': 'rouge' if vaccin == 'en retard' else 'bleue',
         'visible': bool(sit)},
        {'cle': 'malade', 'ico': '🩺', 'nom': 'Poulet malade', 'lien': url_for('eleveur.aller', quoi='malade'),
         'sous': 'prévenir le vétérinaire', 'classe': 'tuile-malade', 'visible': bool(fermes)},
        {'cle': 'sortie', 'ico': '🚚', 'nom': 'Sortie', 'lien': url_for('eleveur.aller', quoi='sortie'),
         'sous': 'vente, abattoir', 'visible': bool(sit)},
        {'cle': 'achat', 'ico': '🛒', 'nom': "J'ai acheté", 'lien': url_for('eleveur.achat'),
         'sous': 'aliment, poussins…', 'visible': bool(fermes)},
        {'cle': 'entretien', 'ico': '🔧', 'nom': 'Entretien', 'lien': url_for('entretien.ecran'),
         'sous': 'pannes en cours' if pannes else ('tâches à faire' if a_faire_entretien else 'tout est fait'),
         'pastille': (a_faire_entretien + pannes) or None, 'pastille_classe': 'rouge' if pannes else '',
         'visible': bool(fermes)},
        {'cle': 'bandes', 'ico': '📈', 'nom': 'Mes bandes', 'lien': url_for('bandes.mes_bandes'),
         'sous': 'en cours et passées'},
        {'cle': 'stock', 'ico': '🧺', 'nom': 'Mon stock', 'lien': url_for('eleveur.stock'),
         'sous': 'aliment, vaccins…', 'visible': bool(fermes)},
    ]
    tuiles = [t for t in tuiles if t.get('visible', True)]
    agent = next((f.agent for f in fermes if f.agent and f.agent.telephone), None)
    rouges = [s for s in sit if s['couleur'] == 'rouge']
    return {'fermes': fermes, 'situation': sit, 'pire': pire, 'etat': etat, 'tuiles': tuiles,
            'saisie': {'visible': bool(sit), 'a_saisir': a_saisir}, 'agent': agent, 'rouges': rouges}


# ── « Saisie du jour » (écran « Ma bande aujourd'hui » du lot 8) ─────────

@eleveur_bp.route('/saisie-du-jour')
@profil_requis(Profil.ELEVEUR)
def saisie():
    from app.routes.accueil import _espace_eleveur
    return render_template('eleveur/saisie.html', espace=_espace_eleveur(_fermes()),
                           bien_recu=session.pop('bien_recu', None))


# ── Accès directs : la tuile ouvre la bande la plus utile ───────────────

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
    if not sit:
        return redirect(url_for('accueil.index'))
    if quoi == 'peser':
        s = min(sit, key=lambda s: s['pesee'])          # pesée prévue la plus proche
        return redirect(url_for('bandes.pesee', numero=s['bande'].numero))
    if quoi == 'sortie':
        s = max(sit, key=lambda s: s['age'])            # la bande la plus âgée
        return redirect(url_for('bandes.sortie', numero=s['bande'].numero))
    if quoi == 'vaccins':
        a_faire = [(s, v) for s in sit for v in s['vaccins'] if v['etat'] in ('retard', 'aujourdhui', 'a_faire')]
        if a_faire:
            s, v = min(a_faire, key=lambda x: (x[1]['etat'] != 'retard', x[1]['prevu']))
            return redirect(url_for('sante.vacciner', numero=s['bande'].numero, calendrier=v['calendrier'].id))
        return render_template('eleveur/vaccins.html', situation=sit)
    abort(404)


# ── Mon stock ───────────────────────────────────────────────────────────

@eleveur_bp.route('/mon-stock')
@profil_requis(Profil.ELEVEUR)
def stock():
    fermes = _fermes()
    achats = (filtre_perimetre(Livraison.query).filter(Livraison.origine == OrigineLivraison.ACHAT)
              .order_by(Livraison.date_livraison.desc(), Livraison.numero_metier.desc()).limit(5).all())
    return render_template('eleveur/stock.html', stocks=[(f, intrants.stock_ferme(f)) for f in fermes], achats=achats)


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
            a = intrants.enregistrer_achat(ferme, produit, _nombre(f.get('quantite')), _entier(f.get('morts')),
                                           _entier(f.get('prix')), f.get('lieu'), _jour(f.get('date')),
                                           current_user, photo)
            db.session.commit()
            if current_user.profil == Profil.ELEVEUR:
                session['achat_recent'] = a.numero      # « Enregistré ✓ — Annuler (10) »
                return redirect(url_for('accueil.index'))
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
    return redirect(url_for('accueil.index'))


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
