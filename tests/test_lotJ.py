"""Lot J — jeu de données complet de la démonstration : il tourne sur une base vide, il est cohérent (totaux, stocks,
effectifs, journal), il contient les situations demandées, et chaque compte de démonstration se connecte."""
import time

import pytest
import sqlalchemy as sa

from app import db
from app.models import Ferme, Utilisateur, Profil

MDP_DEMO = 'Demo-yl2-2026'


@pytest.fixture
def jeu(app):
    from app.services import demo_jeu
    app.config['DEMO'] = True
    volumes = demo_jeu.generer(MDP_DEMO, 'http://localhost')
    db.session.commit()
    yield volumes
    app.config['DEMO'] = False


def test_refus_sur_une_base_non_vide(app):
    from app.services import demo_jeu
    from tests.conftest import creer_utilisateur
    creer_utilisateur('quelquun', Profil.ADMIN)
    with pytest.raises(demo_jeu.RegleJeu):
        demo_jeu.generer(MDP_DEMO)


def test_jeu_complet_coherent_et_utilisable(client, jeu):
    from app import indicateurs
    from app.services import demo_jeu, intrants, journal
    # Volumes et répartition
    assert Ferme.query.count() == 150
    for code, n in demo_jeu.REPARTITION:
        assert Ferme.query.join(Ferme.province).filter_by(code=code).count() == n, code
    assert Ferme.query.filter_by(statut='En préparation').count() == 8
    assert Ferme.query.filter_by(programme_poufa=False).count() == 3
    assert Utilisateur.query.filter_by(profil=Profil.AGENT).count() == 6
    assert Utilisateur.query.filter_by(profil=Profil.VETO).count() == 3
    assert Utilisateur.query.filter_by(identifiant='maedr', profil=Profil.MAEDR).count() == 1
    assert jeu['saisie_jour'] > 30000 and jeu['bande_ponte'] == 5 and jeu['lot_trace'] > 1000
    conn = db.session.connection()
    # Une bande en cours par élevage actif
    sans_bande = conn.execute(sa.text("""SELECT count(*) FROM ferme f WHERE f.statut = 'Opérationnelle' AND NOT EXISTS
        (SELECT 1 FROM bande b WHERE b.ferme_id = f.id AND b.statut = 'EN_COURS')""")).scalar()
    assert sans_bande == 0
    # Aucune sortie au-delà de l'effectif : mis en place − morts − sortis ≥ 0 pour chaque bande
    negatifs = conn.execute(sa.text("""SELECT count(*) FROM bande b WHERE b.effectif_initial
        - COALESCE((SELECT sum(s.morts) FROM saisie_jour s WHERE s.bande_id = b.id), 0)
        - COALESCE((SELECT sum(o.nombre) FROM sortie o WHERE o.bande_id = b.id AND o.archive_le IS NULL), 0) < 0""")).scalar()
    assert negatifs == 0
    # Aucun stock négatif
    for f in Ferme.query.filter_by(statut='Opérationnelle'):
        for s in intrants.stock_ferme(f):
            assert s['stock'] >= -0.01, (f.numero, s['produit'].nom, s['stock'])
    # Totaux : national = somme des provinces = somme des élevages
    fermes = Ferme.query.all()
    national = indicateurs.participation(fermes)['reelle']
    par_province = sum(indicateurs.participation([f for f in fermes if f.province.code == c])['reelle'] for c, _ in demo_jeu.REPARTITION)
    par_ferme = sum(indicateurs.production_reelle_t(fermes).values())
    assert national > 0 and abs(national - par_province) < 0.01 and abs(national - par_ferme) < 0.01
    # Journal : chaîne intacte
    assert journal.verifier_chaine()[0]
    # Situations demandées
    assert conn.execute(sa.text("""SELECT count(*) FROM livraison_ligne l JOIN livraison v ON v.id = l.livraison_id
        JOIN ferme f ON f.id = v.ferme_id WHERE f.numero_metier = 'NGO-003' AND l.quantite_livree - l.quantite_recue = 300""")).scalar() == 1
    assert conn.execute(sa.text("""SELECT count(*) FROM alerte_sanitaire a JOIN ferme f ON f.id = a.ferme_id
        WHERE f.numero_metier = 'EST-007' AND a.origine = 'FEU_ROUGE'""")).scalar() == 1
    assert conn.execute(sa.text("""SELECT count(*) FROM scan s JOIN lot_trace l ON l.id = s.lot_id JOIN ferme f ON f.id = l.ferme_id
        WHERE f.numero_metier = 'HOG-006' AND s.resultat = 'ROUGE'""")).scalar() == 3
    assert conn.execute(sa.text("""SELECT count(*) FROM conflit_hors_ligne c JOIN ferme f ON f.id = c.ferme_id
        WHERE f.numero_metier = 'EST-011' AND c.genre = 'SORTIE' AND c.statut = 'A_VERIFIER'""")).scalar() == 1
    assert conn.execute(sa.text("SELECT count(*) FROM reception WHERE etat = 'SOUS_RESERVE'")).scalar() >= 1
    assert conn.execute(sa.text("SELECT count(*) FROM blocage_sorties WHERE leve_le IS NULL")).scalar() >= 1
    assert conn.execute(sa.text("SELECT count(*) FROM proposition WHERE statut = 'EN_ATTENTE'")).scalar() == 2
    assert conn.execute(sa.text("SELECT count(*) FROM ferme WHERE financee_bceg")).scalar() == 6
    assert conn.execute(sa.text("SELECT count(*) FROM rapport WHERE diffusion = 'SOUMIS'")).scalar() == 1
    assert conn.execute(sa.text("SELECT count(*) FROM rapport WHERE diffusion = 'VALIDE'")).scalar() == 2
    assert conn.execute(sa.text("SELECT count(*) FROM utilisateur WHERE bloque_jusqu_a IS NOT NULL")).scalar() == 1
    # Chaque compte de démonstration se connecte et voit son accueil (rapidement)
    for ident in ('dge', 'veto', 'admin', 'agent.est', 'eleveur', 'bceg', 'maedr', 'aninf', 'marie.nze',
                  'abattoir.owendo', 'marche.montbouet'):
        r = client.post('/auth/connexion', data={'identifiant': ident, 'mot_de_passe': MDP_DEMO})
        assert r.status_code == 302 and '/auth/connexion' not in (r.location or ''), ident
        debut = time.perf_counter()
        assert client.get('/').status_code == 200, ident
        assert time.perf_counter() - debut < 20, ident
        client.post('/auth/deconnexion')
