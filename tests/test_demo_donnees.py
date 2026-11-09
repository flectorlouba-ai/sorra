"""Données fictives de la démonstration : le fichier livré (deploiement/demo/donnees_demo.json) se charge dans
une base neuve, dates décalées à aujourd'hui, journal vide et chaîne intacte, comptes avec le mot de passe de
démo ; la commande refuse hors démonstration et sur une base qui a déjà un journal."""
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy as sa

from app import db
from app.services import demo_donnees

FICHIER = Path(__file__).resolve().parent.parent / 'deploiement' / 'demo' / 'donnees_demo.json'


def base_neuve(tmp_path):
    moteur = sa.create_engine(f'sqlite:///{tmp_path / "demo_neuve.db"}')
    db.metadata.create_all(moteur)
    return moteur


def test_fichier_livre_charge_dans_une_base_neuve_dates_decalees(app, tmp_path):
    donnees = demo_donnees.lire(FICHIER)
    reference = date.fromisoformat(donnees['reference'])
    moteur = base_neuve(tmp_path)
    with moteur.begin() as c:
        comptes = demo_donnees.charger(c, db.metadata, donnees, 'https://sorra.performyl.com',
                                       aujourdhui=reference + timedelta(days=10))
    assert comptes['utilisateur'] >= 9 and comptes['ferme'] >= 4
    with moteur.connect() as c:
        identifiants = {r[0] for r in c.execute(sa.text('SELECT identifiant FROM utilisateur'))}
        assert {'admin', 'dge', 'agent.est', 'veto', 'eleveur', 'auditeur'} <= identifiants
        assert {'abattoir.owendo', 'marche.montbouet'} <= identifiants                 # lot 19
        etats = {r[0] for r in c.execute(sa.text('SELECT etat FROM reception'))}
        assert etats == {'VALIDEE', 'SOUS_RESERVE'} and c.execute(sa.text('SELECT count(*) FROM scan')).scalar() >= 3
        assert c.execute(sa.text("SELECT count(*) FROM reception WHERE motif_ecart IS NOT NULL")).scalar() == 1
        prevue = min(date.fromisoformat(v['date_prevue']) for v in donnees['tables']['visite'] if v['date_prevue'])
        assert c.execute(sa.text('SELECT min(date_prevue) FROM visite')).scalar()[:10] == \
            (prevue + timedelta(days=10)).isoformat()                      # dates décalées
        assert c.execute(sa.text("SELECT valeur FROM parametre WHERE cle = 'tracabilite.adresse_publique'")).scalar() \
            == 'https://sorra.performyl.com'
        assert c.execute(sa.text('SELECT count(*) FROM journal_audit')).scalar() == 0
        assert c.execute(sa.text('SELECT count(*) FROM session_utilisateur')).scalar() == 0
        h = c.execute(sa.text("SELECT mot_de_passe_hash FROM utilisateur WHERE identifiant = 'abattoir.owendo'")).scalar()
    from werkzeug.security import check_password_hash
    assert check_password_hash(h, 'Demo-yl2-2026')
    # Aucun nom réel ni ancien nom dans le fichier publié
    texte = FICHIER.read_text(encoding='utf-8')
    assert 'Flector' not in texte and ''.join(['K', 'I', 'M', 'B', 'A']).lower() not in texte.lower()


def test_export_puis_chargement_rend_les_memes_donnees(app, tmp_path):
    from tests.conftest import creer_utilisateur, creer_ferme
    from app.models import Profil
    creer_utilisateur('agent1', Profil.AGENT, ['EST'])
    creer_ferme('Ferme Un', 'EST', 'Ntoum')
    db.session.commit()
    with db.engine.connect() as c:
        donnees = demo_donnees.exporter(c, db.metadata)
    moteur = base_neuve(tmp_path)
    with moteur.begin() as c:
        demo_donnees.charger(c, db.metadata, donnees)
    with moteur.connect() as c:
        assert c.execute(sa.text("SELECT nom FROM ferme")).scalar() == 'Ferme Un'
        assert c.execute(sa.text("SELECT count(*) FROM province")).scalar() == 9


def test_refus_sur_une_base_avec_journal_et_hors_demonstration(app):
    from app.services.journal import enregistrer, Action
    enregistrer(Action.CONNEXION, detail='essai')
    db.session.commit()
    with db.engine.begin() as c:
        try:
            demo_donnees.charger(c, db.metadata, demo_donnees.lire(FICHIER))
            assert False
        except demo_donnees.RegleDemo as e:
            assert 'base neuve' in str(e)
    res = app.test_cli_runner().invoke(args=['demo-charger'])
    assert res.exit_code != 0 and 'YL2_DEMO=1' in res.output
