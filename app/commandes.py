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


@click.command('init-yl2')
@click.option('--identifiant', default='admin', show_default=True)
@with_appcontext
def init_performyl2(identifiant):
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


@click.command('rapports-mensuels')
@with_appcontext
def rapports_mensuels():
    """Lot 18 : produit et garde le rapport mensuel national du dernier mois terminé (à lancer chaque mois,
    par exemple le 1er à 6 h, dans le cron du VPS). Sans effet s'il existe déjà."""
    from app import db
    from app.models import Utilisateur, Profil
    from app.services import dge
    auteur = (Utilisateur.query.filter_by(profil=Profil.DGE, actif=True).first()
              or Utilisateur.query.filter_by(profil=Profil.ADMIN, actif=True).first())
    nouveaux = dge.generer_manquants(auteur)
    from app.services import rapports
    standards = rapports.generer_mensuels(dge.mois_termines(1)[0], auteur)        # lot D : ferme, agent, provinces
    db.session.commit()
    click.echo((', '.join(r.mois for r in nouveaux) + ' produit(s). ' if nouveaux else 'Rien à produire. ')
               + f'{len(standards)} rapport(s) standard(s).')


@click.command('notifications-envoyer')
@with_appcontext
def notifications_envoyer():
    """Lot T : calcule les événements du moment (par profil) et envoie les notifications pas encore envoyées.
    À lancer toutes les 15 minutes (cron du VPS). Sans clés VAPID dans le .env, rien ne part et le journal le dit."""
    from app import db
    from app.services import notifications
    creees = notifications.calculer()
    envoyees = notifications.envoyer_en_attente()
    db.session.commit()
    click.echo(f'{creees} notification(s) créée(s), {envoyees} envoyée(s)' + ('' if notifications.cles() else ' — clés VAPID absentes'))


DONNEES_DEMO = 'deploiement/demo/donnees_demo.json'


@click.command('demo-exporter')
@click.option('--fichier', default=DONNEES_DEMO, show_default=True)
@with_appcontext
def demo_exporter(fichier):
    """Exporte la base courante (une base de démo locale) en données fictives pour la démonstration."""
    import json
    from app.services import demo_donnees
    with db.engine.connect() as c:
        donnees = demo_donnees.exporter(c, db.metadata)
    with open(fichier, 'w', encoding='utf-8') as f:
        json.dump(donnees, f, ensure_ascii=False, indent=0, sort_keys=True)
    click.echo(f'{sum(len(v) for v in donnees["tables"].values())} lignes exportées dans {fichier}.')


@click.command('demo-jeu-complet')
@click.option('--adresse', default='', help="Adresse publique des QR codes (ex. https://sorra.performyl.com)")
@with_appcontext
def demo_jeu_complet(adresse):
    """Lot J : jeu de données complet de la DÉMONSTRATION (150 élevages, 12 mois), dans une base NEUVE.
    Refusé hors démonstration (YL2_DEMO=1) et sur une base qui contient déjà des comptes ou des élevages."""
    from flask import current_app
    from app.services import demo_jeu
    if not current_app.config.get('DEMO'):
        raise click.ClickException('Refusé : YL2_DEMO=1 est obligatoire (jamais sur une base réelle).')
    mdp = current_app.config.get('DEMO_MOT_DE_PASSE')
    if not mdp:
        raise click.ClickException('Refusé : DEMO_MOT_DE_PASSE (mot de passe public des comptes de démonstration) manque.')
    try:
        volumes = demo_jeu.generer(mdp, adresse or None)
        db.session.commit()
    except demo_jeu.RegleJeu as e:
        db.session.rollback()
        raise click.ClickException(str(e))
    click.echo('Jeu de démonstration créé : ' + ', '.join(f'{k} {v}' for k, v in sorted(volumes.items())))


@click.command('demo-charger')
@click.option('--fichier', default=DONNEES_DEMO, show_default=True)
@click.option('--adresse', default='', help="Adresse publique des QR codes (ex. https://sorra.performyl.com)")
@with_appcontext
def demo_charger(fichier, adresse):
    """Charge les données fictives dans la base de la DÉMONSTRATION (YL2_DEMO=1 obligatoire, base neuve)."""
    from flask import current_app
    from app.services import demo_donnees
    if not current_app.config.get('DEMO'):
        raise click.ClickException('Refusé : YL2_DEMO=1 est obligatoire (jamais sur une base réelle).')
    try:
        with db.engine.begin() as c:
            comptes = demo_donnees.charger(c, db.metadata, demo_donnees.lire(fichier), adresse or None)
    except demo_donnees.RegleDemo as e:
        raise click.ClickException(str(e))
    click.echo(f'{sum(comptes.values())} lignes chargées ({comptes.get("utilisateur", 0)} comptes, '
               f'{comptes.get("ferme", 0)} fermes).')
