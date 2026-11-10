import re
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import current_user

from app import db
from app.models import Utilisateur, Profil, Province, PROFILS_NATIONAUX, Ferme, UtilisateurFerme, Operateur
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
    donnees['fermes'] = []
    donnees['operateur_id'] = None
    if donnees['profil'] == Profil.ELEVEUR:
        # L'éleveur est rattaché à ses fermes, pas à des provinces
        ids = []
        for i in f.getlist('fermes'):
            try:
                ids.append(uuid.UUID(i))
            except ValueError:
                pass
        donnees['fermes'] = Ferme.query.filter(Ferme.id.in_(ids)).all() if ids else []
        donnees['provinces'] = []
        if not donnees['fermes']:
            return None, 'Cochez au moins une ferme pour cet éleveur.'
    elif donnees['profil'] in PROFILS_NATIONAUX:
        donnees['provinces'] = []   # voit tout : un rattachement n'aurait pas de sens
    elif donnees['profil'] == Profil.OPERATEUR:
        # Lot 19 : rattaché à UNE fiche du registre des opérateurs ; sa province est celle de l'établissement
        op_id = f.get('operateur_id', '')
        op = db.session.get(Operateur, int(op_id)) if op_id.isdigit() else None
        if op is None or not op.actif:
            return None, "Choisissez l'établissement (registre des opérateurs) de ce compte."
        donnees['operateur_id'] = op.id
        donnees['provinces'] = [op.province]
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
        donnees['actif'] = user.actif        # lot A1 : seul « 🗄️ Archiver » archive (plus de case à décocher)
    return donnees, None


def _rattacher_fermes(user, fermes):
    voulues = {fe.id: fe for fe in fermes}
    for lien in list(user.fermes):
        if lien.ferme_id not in voulues:
            user.fermes.remove(lien)
    actuelles = {lien.ferme_id for lien in user.fermes}
    for fid, fe in voulues.items():
        if fid not in actuelles:
            user.fermes.append(UtilisateurFerme(ferme=fe))


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
    fermes = [{'id': str(fe.id), 'numero': fe.numero_metier, 'nom': fe.nom,
               'province_id': fe.province_id}
              for fe in Ferme.query.order_by(Ferme.numero_metier)]
    from app.services import conformite
    return render_template('administration/utilisateurs.html',
                           conforme=('ADMIN-2', conformite.spec('ADMIN', 2), conformite.admin_utilisateurs(current_user, utilisateurs)),
                           utilisateurs=utilisateurs, profils=list(Profil), fermes=fermes,
                           operateurs=Operateur.query.filter_by(actif=True).order_by(Operateur.nom).all(),
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
    fermes = donnees.pop('fermes')
    user = Utilisateur(identifiant=identifiant, actif=True, doit_changer_mdp=True, **donnees)
    user.fermes = [UtilisateurFerme(ferme=fe) for fe in fermes]
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
    from app.utils import demo
    if request.form.get('archiver') or request.form.get('restaurer'):
        # Lot A1 : « Archiver » remplace « Désactiver » (journal : archivage / restauration)
        actif, erreur = bool(request.form.get('restaurer')), None
        if not actif and demo.active():
            erreur = f'{demo.MESSAGE} (mot de passe et désactivation des comptes)'
        elif not actif and user.id == current_user.id:
            erreur = 'Vous ne pouvez pas archiver votre propre compte.'
        elif not actif and user.profil == Profil.ADMIN and user.actif and _admins_actifs_hors(user) == 0:
            erreur = 'Il doit rester au moins un administrateur actif.'
        if erreur:
            flash(erreur, 'danger')
        else:
            user.actif = actif
            db.session.commit()
            flash(f'Compte « {user.identifiant} » ' + ('restauré.' if actif else 'archivé : la personne ne peut plus se connecter.'),
                  'success')
        return redirect(url_for('utilisateurs.index'))
    donnees, erreur = _lire_formulaire(user)
    if not erreur and demo.active() and (donnees['mot_de_passe'] or not donnees['actif']):
        erreur = f'{demo.MESSAGE} (mot de passe et désactivation des comptes)'
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
    _rattacher_fermes(user, donnees.pop('fermes'))
    nouveau_profil = donnees.pop('profil')
    profil_propose = False
    if nouveau_profil != user.profil:
        # Lot 15 : quatre yeux — le profil actuel s'applique jusqu'à l'approbation
        from app.services import approbations
        try:
            approbations.proposer('PROFIL', f'profil.{user.id}', f'Profil de « {user.identifiant} »',
                                  user.profil.libelle, nouveau_profil.libelle,
                                  {'utilisateur_id': str(user.id), 'profil': nouveau_profil.value},
                                  request.form.get('motif') or 'Changement de profil (écran Utilisateurs)', current_user)
            profil_propose = True
        except approbations.RegleApprobation as e:
            flash(str(e), 'danger')
    for cle, valeur in donnees.items():
        setattr(user, cle, valeur)
    if mdp:
        user.set_password(mdp)
        user.doit_changer_mdp = True
    db.session.commit()
    message = f'Compte « {user.identifiant} » mis à jour.'
    if profil_propose:
        message += ' Le changement de profil attend l\'approbation d\'une autre personne.'
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


@utilisateurs_bp.route('/<user_id>/reinitialiser-2fa', methods=['POST'])
@profil_requis(Profil.ADMIN)
def reinitialiser_2fa(user_id):
    """Lot 15 : téléphone perdu — la mise en place recommencera à la connexion suivante."""
    from app.services import securite
    from app.services.journal import enregistrer, Action
    user = _charger(user_id)
    motif = (request.form.get('motif') or '').strip()
    if not motif:
        flash('Indiquez le motif de la réinitialisation.', 'danger')
        return redirect(url_for('utilisateurs.index'))
    securite.reinitialiser(user)
    enregistrer(Action.MODIFICATION, table='utilisateur', enregistrement_id=user.id,
                detail=f'Double authentification de « {user.identifiant} » réinitialisée par '
                       f'{current_user.identifiant} : {motif}')
    db.session.commit()
    flash(f'Double authentification de « {user.identifiant} » réinitialisée.', 'success')
    return redirect(url_for('utilisateurs.index'))

