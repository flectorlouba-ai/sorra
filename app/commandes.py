import secrets
import string

import click
from flask.cli import with_appcontext

from app import db
from app.models import Utilisateur, Profil, Province, Parametre
from app.models.referentiel import PROVINCES_GABON
from app.models.parametre import PARAMETRES_DEFAUT


def _mot_de_passe_aleatoire(longueur=14):
    alphabet = string.ascii_letters + string.digits + '@#%+=?'
    while True:
        mdp = ''.join(secrets.choice(alphabet) for _ in range(longueur))
        if any(c.isdigit() for c in mdp) and any(c.isupper() for c in mdp):
            return mdp


@click.command('init-kimba')
@click.option('--identifiant', default='admin', show_default=True)
@with_appcontext
def init_kimba(identifiant):
    """Crée le compte ADMIN initial (mot de passe à changer à la première connexion).
    Complète aussi provinces et paramètres s'ils manquent (normalement posés par la migration)."""
    for i, (code, nom) in enumerate(PROVINCES_GABON, start=1):
        if not Province.query.filter_by(code=code).first():
            db.session.add(Province(code=code, nom=nom, ordre=i, actif=True))
    for cle, valeur, type_, description in PARAMETRES_DEFAUT:
        if not Parametre.query.filter_by(cle=cle).first():
            db.session.add(Parametre(cle=cle, valeur=valeur, type=type_, description=description))

    identifiant = identifiant.strip().lower()
    if Utilisateur.query.filter_by(identifiant=identifiant).first():
        db.session.commit()
        click.echo(f'Le compte « {identifiant} » existe déjà : rien n\'a été changé.')
        return
    mdp = _mot_de_passe_aleatoire()
    admin = Utilisateur(identifiant=identifiant, nom='Administrateur', profil=Profil.ADMIN,
                        actif=True, doit_changer_mdp=True)
    admin.set_password(mdp)
    db.session.add(admin)
    db.session.commit()
    click.echo('Compte administrateur créé.')
    click.echo(f'  Identifiant       : {identifiant}')
    click.echo(f'  Mot de passe      : {mdp}')
    click.echo('Notez-le maintenant : il ne sera plus affiché. '
               'Il devra être changé à la première connexion.')
