"""Lot 13 — tutoriel (une fois par compte, Passer, Revoir), « Comment faire ? » (bon écran, sans réseau,
modification ADMIN au journal), Mon compte (seuls téléphone et mot de passe, vétérinaires de la zone,
déconnexion sans jamais effacer les saisies en attente), consentement BCEG (responsable seulement,
accord, refus, retrait, changement de responsable, journal, règle d'accès du profil BCEG)."""
import re

from app import db
from app.models import JournalAudit, Profil, Ferme, UtilisateurFerme
from app.models.aide import Aide
from app.models.bceg import ConsentementBceg, DecisionBceg as D
from app.models.sante import AlerteSanitaire, ReponseVeterinaire
from app.services import sante
from app.services.journal import Action
from app.utils.permissions import filtre_perimetre
from tests.conftest import connecter, creer_utilisateur
from tests.test_bandes import monde, bande_ouverte  # noqa: F401


def changer(client, identifiant):
    client.post('/auth/deconnexion')
    connecter(client, identifiant)


# ── A. Tutoriel ─────────────────────────────────────────────────────────

def test_tutoriel_une_seule_fois_par_compte_passer_et_revoir(client, monde):
    monde['el'].presentation_vue_le = None
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    connecter(client, 'eleveur1')
    r = client.get('/')
    assert r.status_code == 302 and r.location.endswith('/presentation')
    page = client.get('/presentation').get_data(as_text=True)
    assert page.count('class="pres-ecran"') == 4 and 'Chaque jour, notez vos morts et votre aliment.' in page
    assert 'Votre agent Paul est là pour vous aider.' in page and 'href="tel:+24177123456"' in page
    assert 'Passer' in page and 'Suivant' in page and "C'est parti !" in page
    client.post('/presentation/vue')                              # « Passer »
    assert monde['el'].presentation_vue_le is not None
    assert client.get('/').status_code == 200                     # plus jamais redirigé
    # Gardé sur le serveur : un autre téléphone (nouvelle session) ne le revoit pas
    changer(client, 'eleveur1')
    assert client.get('/').status_code == 200
    # Revoir depuis 👤 Moi
    assert 'href="/presentation"' in client.get('/moi').get_data(as_text=True)
    assert client.get('/presentation').status_code == 200
    # Un autre compte le voit à son tour
    autre = creer_utilisateur('eleveur2', Profil.ELEVEUR)
    autre.presentation_vue_le = None
    autre.fermes = [UtilisateurFerme(ferme=monde['f2'])]
    db.session.commit()
    changer(client, 'eleveur2')
    assert client.get('/').location.endswith('/presentation')
    page = client.get('/presentation').get_data(as_text=True)
    assert 'Votre agent Agent2 est là pour vous aider.' in page and 'tel:' not in page   # pas de téléphone


def test_tutoriel_sans_agent(client, monde):
    monde['f'].agent_id = None
    db.session.commit()
    connecter(client, 'eleveur1')
    assert 'Votre agent technique est là pour vous aider.' in client.get('/presentation').get_data(as_text=True)


# ── B. « Comment faire ? » ──────────────────────────────────────────────

ECRANS = {'saisie': '/saisie-du-jour', 'sortie': '/aller/sortie', 'pesee': '/aller/peser', 'malade': '/aller/malade',
          'achat': '/j-ai-achete', 'depense': '/j-ai-paye', 'entretien': '/entretien', 'argent': '/mon-argent'}


def test_bouton_aide_ouvre_l_aide_de_cet_ecran(client, monde):
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    for cle, chemin in ECRANS.items():
        r = client.get(chemin)
        page = (client.get(r.location) if r.status_code == 302 else r).get_data(as_text=True)
        lien = re.search(r'<a class="btn-aide" href="([^"]+)"[^>]*data-aide="(\w+)"', page)
        assert lien and lien.group(2) == cle, chemin
        aide = client.get(lien.group(1).replace('&amp;', '&')).get_data(as_text=True)
        assert aide.count('class="etape-aide"') <= 3 and Aide.query.filter_by(cle=cle).one().titre in aide.replace('&#39;', "'")
        assert '‹ Retour' in aide                                  # 1 toucher pour revenir à l'écran
    # Vaccin : l'écran du vaccin a aussi son « ? »
    from app.models import Produit
    from app.models.sante import CalendrierVaccinal
    v = Produit(nom='Vaccin Gumboro', type='Vaccin', unite='doses')
    db.session.add(v)
    db.session.add(CalendrierVaccinal(age_jours=0, produit=v, mode='Eau de boisson'))
    db.session.commit()
    c = CalendrierVaccinal.query.one()
    assert 'data-aide="vaccin"' in client.get(f'/sante/vacciner/{b.numero}?calendrier={c.id}').get_data(as_text=True)
    # Liste complète par grandes actions
    page = client.get('/aide').get_data(as_text=True)
    for groupe in ('Chaque jour', 'Ma bande', 'Santé', 'Mon argent'):
        assert groupe in page
    assert page.count('data-aide=') == 9
    # L'agent qui saisit pour l'éleveur n'a pas de « ? »
    changer(client, 'agent1')
    assert 'btn-aide' not in client.get(f'/bandes/{b.numero}/sortie').get_data(as_text=True)


def test_modification_des_aides_par_l_admin_au_journal(client_admin, client):
    a = Aide.query.filter_by(cle='saisie').one()
    page = client_admin.get('/administration/aides?modifier=saisie').get_data(as_text=True)
    assert 'à faire relire' in page and 'Étape 3' in page
    client_admin.post('/administration/aides', data={'cle': 'saisie', 'titre': 'Noter la journée', 'actif': 'on',
                                                     'texte-0': 'Comptez les morts.', 'capture-0': 'aucun_mort',
                                                     'texte-1': 'Notez les sacs.', 'capture-1': 'comme_hier'})
    db.session.refresh(a)
    assert a.titre == 'Noter la journée' and len(a.etapes) == 2
    j = JournalAudit.query.filter_by(table_nom='aide', action=Action.MODIFICATION).all()
    assert j and 'Noter la journée' in str(j[-1].__dict__)
    # Désactivée : plus de « ? » sur l'écran
    client_admin.post('/administration/aides', data={'cle': 'saisie', 'titre': 'Noter la journée',
                                                     'texte-0': 'Comptez les morts.'})
    db.session.refresh(a)
    assert not a.actif


# ── E. Toutes les pages de l'éleveur gardées pour le mode sans réseau ──

def test_toutes_les_pages_eleveur_sont_gardees_sans_reseau(client, monde, app):
    """Chaque page HTML que l'éleveur peut ouvrir (sans paramètre) est dans la liste que le téléphone
    garde à chaque ouverture de l'accueil — pour que l'oubli des lots 10 à 12 ne se reproduise pas."""
    b = bande_ouverte(monde)
    connecter(client, 'eleveur1')
    gardees = set(client.get('/hors-ligne/pages').get_json()['pages'])
    oubliees = []
    for regle in app.url_map.iter_rules():
        if 'GET' not in regle.methods or regle.arguments or regle.rule.startswith(('/static', '/q/')):
            continue
        r = client.get(regle.rule)
        if r.status_code == 200 and r.mimetype == 'text/html':
            if regle.rule not in gardees:
                oubliees.append(regle.rule)
    assert oubliees == []
    # Pages avec un paramètre : celles des bandes en cours, et les 9 aides
    for chemin in (f'/bandes/{b.numero}/pesee', f'/bandes/{b.numero}/sortie', f'/sante/declarer?bande={b.numero}',
                   f'/sante/traiter/{b.numero}', '/aide/saisie', '/aide/argent'):
        assert chemin in gardees, chemin
    assert not any(p.startswith(('/aide/ag_', '/aide/op_')) for p in gardees)   # lot 19 ter : pas les aides des autres
    js = client.get('/static/js/hors_ligne.js').get_data(as_text=True)
    assert "fetch('/hors-ligne/pages'" in js


# ── C. Mon compte ───────────────────────────────────────────────────────

def test_mon_compte_seuls_telephone_et_mot_de_passe(client, monde):
    monde['agent'].telephone = '+241 77 12 34 56'
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/mon-compte').get_data(as_text=True)
    assert 'Eleveur1' in page and 'Ferme Un' in page and 'B1 · 1 500 places' in page
    assert 'Pour changer cela, appelez Paul.' in page and 'href="tel:+24177123456"' in page
    client.post('/mon-compte', data={'telephone': '+241 66 00 11 22', 'nom': 'Pirate'})
    db.session.refresh(monde['el'])
    assert monde['el'].telephone == '+241 66 00 11 22' and monde['el'].nom == 'Eleveur1'
    assert JournalAudit.query.filter_by(table_nom='utilisateur', action=Action.MODIFICATION).count() >= 1
    assert 'Écrivez le numéro' in client.post('/mon-compte', data={'telephone': 'abc'}).get_data(as_text=True)
    # Mot de passe : règles en clair, journal, retour sur « Mon compte »
    assert 'Au moins 10 caractères' in client.get('/auth/mot-de-passe').get_data(as_text=True)
    r = client.post('/auth/mot-de-passe', data={'actuel': 'MotDePasse-2026', 'nouveau': 'Nouveau-mdp-2026',
                                                'confirmation': 'Nouveau-mdp-2026'})
    assert r.location.endswith('/mon-compte')
    assert JournalAudit.query.filter_by(action=Action.CHANGEMENT_MDP).count() == 1


def test_veterinaires_de_la_zone_ceux_qui_ont_repondu_d_abord(client, monde):
    vetos = [creer_utilisateur(f'veto{i}', Profil.VETO, ['EST']) for i in range(4)]
    b = bande_ouverte(monde)
    a = sante._nouvelle_alerte(b.ferme, b, 'FEU_ROUGE')
    db.session.flush()
    db.session.add(ReponseVeterinaire(alerte=a, conseils=['Appelez-moi'], veto_id=vetos[2].id))
    db.session.commit()
    connecter(client, 'eleveur1')
    page = client.get('/mon-compte').get_data(as_text=True)
    avant, apres = page.split('Voir les autres')
    assert 'Veto2' in avant and 'Veto0' not in avant and 'Veto0' in apres and 'Veto3' in apres


def test_deconnexion_avertit_et_les_saisies_gardent_leur_auteur(client, monde):
    connecter(client, 'eleveur1')
    for chemin in ('/moi', '/mon-compte'):
        page = client.get(chemin).get_data(as_text=True)
        assert 'data-quitter="1"' in page and 'sorraEnAttente' in page
        assert 'pas encore partie' in page and 'quand vous vous reconnecterez' in page
    js = client.get('/static/js/hors_ligne.js').get_data(as_text=True)
    # Les saisies gardées sur le téléphone portent leur auteur et ne partent qu'avec sa session…
    assert 'return e.utilisateur === utilisateur;' in js and 'utilisateur: utilisateur' in js
    assert 'window.sorraEnAttente' in js
    # … et ne sont jamais effacées (ni à la déconnexion, ni à la connexion d'une autre personne)
    assert 'deleteDatabase' not in js and '.clear()' not in js


# ── D. Consentement BCEG ────────────────────────────────────────────────

def _financer(monde, responsable=None):
    f = monde['f']
    f.financee_bceg = True
    f.responsable_id = (responsable or monde['el']).id
    db.session.commit()
    return f


def test_ma_banque_invisible_si_non_financee(client, monde):
    connecter(client, 'eleveur1')
    assert 'data-moi="banque"' not in client.get('/moi').get_data(as_text=True)
    assert client.get('/ma-banque').status_code == 404
    assert 'pastille-nouveau' not in client.get('/').get_data(as_text=True)


def test_accord_refus_retrait_journal_et_historique(client, monde):
    f = _financer(monde)
    connecter(client, 'eleveur1')
    assert re.search(r'data-entete="moi">👤 Moi <span class="pastille-nouveau">', client.get('/').get_data(as_text=True))
    page = client.get('/ma-banque').get_data(as_text=True)
    assert 'vos ventes' in page and 'Elle ne verra rien d&#39;autre' in page.replace("rien d'autre", 'rien d&#39;autre')
    assert "J'accepte" in page and 'Je refuse' in page
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'REFUSE'})
    assert 'pastille-nouveau' not in client.get('/').get_data(as_text=True)          # a répondu
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'ACCEPTE'})
    page = client.get('/ma-banque').get_data(as_text=True)
    assert 'Vous avez accepté le' in page and 'Retirer mon accord' in page
    # Retrait : confirmation obligatoire
    assert 'Oui, retirer mon accord' in client.get(f'/ma-banque/{f.numero}/retirer').get_data(as_text=True)
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'RETIRE'})
    assert [c.decision for c in ConsentementBceg.query.order_by(ConsentementBceg.id)] == [D.REFUSE, D.ACCEPTE, D.RETIRE]
    assert JournalAudit.query.filter_by(action=Action.CONSENTEMENT).count() == 3
    # Pas de second retrait
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'RETIRE'})
    assert ConsentementBceg.query.count() == 3
    # L'agent voit l'historique sur la fiche ferme
    changer(client, 'agent1')
    fiche = client.get(f'/fermes/{f.numero}').get_data(as_text=True)
    assert 'Banque (BCEG)' in fiche and 'Accord retiré' in fiche and 'Refus' in fiche


def test_seul_le_responsable_voit_ma_banque_et_changement_de_responsable(client, monde):
    autre = creer_utilisateur('eleveur2', Profil.ELEVEUR)
    autre.fermes = [UtilisateurFerme(ferme=monde['f'])]
    db.session.commit()
    f = _financer(monde)
    connecter(client, 'eleveur2')                                       # pas le responsable
    assert 'data-moi="banque"' not in client.get('/moi').get_data(as_text=True)
    assert client.get('/ma-banque').status_code == 404
    assert client.post(f'/ma-banque/{f.numero}', data={'decision': 'ACCEPTE'}).status_code == 404
    changer(client, 'eleveur1')
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'ACCEPTE'})
    # L'agent change de responsable : l'accord tombe, le nouveau responsable doit répondre
    changer(client, 'agent1')
    client.post(f'/fermes/{f.numero}/bceg', data={'financee': 'on', 'responsable': str(autre.id)})
    db.session.refresh(f)
    assert f.responsable_id == autre.id
    assert ConsentementBceg.query.order_by(ConsentementBceg.id.desc()).first().decision == D.CADUC
    changer(client, 'eleveur2')
    assert re.search(r'data-entete="moi">👤 Moi <span class="pastille-nouveau">', client.get('/').get_data(as_text=True))
    assert 'data-moi="banque"' in client.get('/moi').get_data(as_text=True)
    changer(client, 'eleveur1')
    assert 'data-moi="banque"' not in client.get('/moi').get_data(as_text=True)
    # Un autre agent ne règle pas cette ferme ; le responsable doit être rattaché à la ferme
    creer_utilisateur('agent9', Profil.AGENT, ['EST'])
    changer(client, 'agent9')
    assert client.post(f'/fermes/{f.numero}/bceg', data={'financee': 'on'}).status_code == 403
    changer(client, 'agent1')
    etranger = creer_utilisateur('eleveur3', Profil.ELEVEUR)
    r = client.post(f'/fermes/{f.numero}/bceg', data={'financee': 'on', 'responsable': str(etranger.id)},
                    follow_redirects=True)
    assert 'doit être un éleveur rattaché' in r.get_data(as_text=True)


def test_regle_d_acces_du_profil_bceg(client, monde):
    banque = creer_utilisateur('bceg', Profil.BCEG, ['EST'])
    f = monde['f']
    visibles = lambda: [x.id for x in filtre_perimetre(Ferme.query, utilisateur=banque)]   # noqa: E731
    assert visibles() == []                                             # non financée
    _financer(monde)
    assert visibles() == []                                             # financée, pas de réponse
    connecter(client, 'eleveur1')
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'REFUSE'})
    assert visibles() == []                                             # refus
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'ACCEPTE'})
    assert visibles() == [f.id]                                         # accord en cours : seulement elle
    assert [b.id for b in filtre_perimetre(AlerteSanitaire.query, utilisateur=banque)] == []
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'RETIRE'})
    assert visibles() == []                                             # après retrait : plus rien
    client.post(f'/ma-banque/{f.numero}', data={'decision': 'ACCEPTE'})
    assert visibles() == [f.id]
    f.financee_bceg = False                                             # plus financée : plus rien
    db.session.commit()
    assert visibles() == []
    f.financee_bceg = True
    autre = creer_utilisateur('eleveur2', Profil.ELEVEUR)
    autre.fermes = [UtilisateurFerme(ferme=f)]
    db.session.commit()
    from app.services import bceg
    bceg.regler(f, True, autre, monde['agent'])                         # changement de responsable
    db.session.commit()
    assert visibles() == []
