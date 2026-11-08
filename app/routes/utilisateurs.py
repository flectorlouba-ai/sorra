import re
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Utilisateur, Profil, Province, PROFILS_NATIONAUX
from app.services import parametres
from app.utils.permissions import profil_requis

utilisateurs_bp = Blueprint('utilisateurs', __name__)

_IDENTIFIANT = re.compile(r'^[a-z0-9._-]{3,64}$')


def _charger(user_id):
    try:
        user = db.session.get(Utilisateur, uuid.UUID(user_id))
    except ValueError:
        user = None
    if user is None:
        abort(404)
    return user


def _lire_formulaire(user=None):
    """Contrôle le formulaire ; renvoie (données, erreur)."""
    f = request.form
    donnees = {
        'nom': f.get('nom', '').strip(),
        'prenom': f.get('prenom', '').strip() or None,
        'email': f.get('email', '').strip() or None,
        'telephone': f.get('telephone', '').strip() or None,
    }
    try:
        donnees['profil'] = Profil(f.get('profil', ''))
    except ValueError:
        return None, 'Choisissez un profil.'
    ids = [int(i) for i in f.getlist('provinces') if i.isdigit()]
    donnees['provinces'] = Province.query.filter(Province.id.in_(ids)).all() if ids else []
    if not donnees['nom']:
        return None, 'Le nom est obligatoire.'
    if donnees['profil'] in PROFILS_NATIONAUX:
        donnees['provinces'] = []   # voit tout : un rattachement n'aurait pas de sens
    elif not donnees['provinces']:
        return None, 'Cochez au moins une province pour ce profil.'
    mdp = f.get('mot_de_passe', '')
    longueur_min = parametres.obtenir('securite.mdp_longueur_min', 10)
    if user is None and not mdp:
        return None, 'Le mot de passe provisoire est obligatoire.'
    if mdp and len(mdp) < longueur_min:
        return None, f'Le mot de passe doit contenir au moins {longueur_min} caractères.'
    donnees['mot_de_passe'] = mdp
    if user is not None:
        donnees['actif'] = f.get('actif') == 'on'
    return donnees, None


def _admins_actifs_hors(user):
    return Utilisateur.query.filter(Utilisateur.profil == Profil.ADMIN,
                                    Utilisateur.actif.is_(True),
                                    Utilisateur.id != user.id).count()


@utilisateurs_bp.route('/')
@profil_requis(Profil.ADMIN)
def index():
    profil = request.args.get('profil', '')
    province = request.args.get('province', '')
    statut = request.args.get('statut', 'actifs')
    q = Utilisateur.query
    if profil in Profil.__members__:
        q = q.filter(Utilisateur.profil == Profil[profil])
    if province.isdigit():
        q = q.filter(Utilisateur.provinces.any(Province.id == int(province)))
    if statut == 'actifs':
        q = q.filter(Utilisateur.actif.is_(True))
    elif statut == 'inactifs':
        q = q.filter(Utilisateur.actif.is_(False))
    utilisateurs = q.order_by(Utilisateur.nom, Utilisateur.prenom).all()
    return render_template('administration/utilisateurs.html',
                           utilisateurs=utilisateurs, profils=list(Profil),
                           provinces=Province.query.order_by(Province.ordre).all(),
                           nationaux=[p.value for p in PROFILS_NATIONAUX],
                           filtre={'profil': profil, 'province': province, 'statut': statut},
                           longueur_min=parametres.obtenir('securite.mdp_longueur_min', 10))


@utilisateurs_bp.route('/creer', methods=['POST'])
@profil_requis(Profil.ADMIN)
def creer():
    identifiant = request.form.get('identifiant', '').strip().lower()
    donnees, erreur = _lire_formulaire()
    if not erreur and not _IDENTIFIANT.match(identifiant):
        erreur = ('L\'identifiant doit faire 3 caractères au moins : lettres sans accent, '
                  'chiffres, point, tiret.')
    if not erreur and Utilisateur.query.filter_by(identifiant=identifiant).first():
        erreur = f'L\'identifiant « {identifiant} » est déjà utilisé.'
    if erreur:
        flash(erreur, 'danger')
        return redirect(url_for('utilisateurs.index'))
    mdp = donnees.pop('mot_de_passe')
    user = Utilisateur(identifiant=identifiant, actif=True, doit_changer_mdp=True, **donnees)
    user.set_password(mdp)
    db.session.add(user)
    db.session.commit()
    flash(f'Compte « {identifiant} » créé. Le mot de passe devra être changé à la '
          'première connexion.', 'success')
    return redirect(url_for('utilisateurs.index'))


@utilisateurs_bp.route('/<user_id>/modifier', methods=['POST'])
@profil_requis(Profil.ADMIN)
def modifier(user_id):
    user = _charger(user_id)
    donnees, erreur = _lire_formulaire(user)
    if not erreur and user.id == current_user.id and not donnees['actif']:
        erreur = 'Vous ne pouvez pas désactiver votre propre compte.'
    if (not erreur and user.profil == Profil.ADMIN and user.actif
            and (donnees['profil'] != Profil.ADMIN or not donnees['actif'])
            and _admins_actifs_hors(user) == 0):
        erreur = 'Il doit rester au moins un administrateur actif.'
    if erreur:
        flash(erreur, 'danger')
        return redirect(url_for('utilisateurs.index'))
    mdp = donnees.pop('mot_de_passe')
    for cle, valeur in donnees.items():
        setattr(user, cle, valeur)
    if mdp:
        user.set_password(mdp)
        user.doit_changer_mdp = True
    db.session.commit()
    message = f'Compte « {user.identifiant} » mis à jour.'
    if mdp:
        message += ' Le nouveau mot de passe devra être changé à la prochaine connexion.'
    flash(message, 'success')
    return redirect(url_for('utilisateurs.index'))


@utilisateurs_bp.route('/<user_id>/debloquer', methods=['POST'])
@profil_requis(Profil.ADMIN)
def debloquer(user_id):
    from app.routes.auth import _debloquer
    user = _charger(user_id)
    if user.bloque_jusqu_a:
        _debloquer(user, 'par l\'administrateur')
        db.session.commit()
        flash(f'Compte « {user.identifiant} » débloqué.', 'success')
    return redirect(url_for('utilisateurs.index'))
