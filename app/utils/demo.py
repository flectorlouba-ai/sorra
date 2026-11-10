"""Démonstration publique (YL2_DEMO=1) : le mot de passe des comptes est connu de tous. Rien de ce qu'un
visiteur fait ne doit empêcher les autres de se connecter."""
from datetime import timedelta

from flask import current_app

MESSAGE = 'Désactivé en démonstration.'


def active():
    return bool(current_app.config.get('DEMO'))


def echecs_recents(identifiant, ip):
    """Échecs de connexion de ce compte DEPUIS CETTE ADRESSE, dans la fenêtre de blocage, depuis sa dernière
    connexion réussie depuis cette adresse (lus dans le journal, qui note identifiant et adresse)."""
    from app.models import JournalAudit
    from app.models.base import maintenant
    from app.services import parametres
    from app.services.journal import Action
    depuis = maintenant() - timedelta(minutes=parametres.obtenir('securite.blocage_minutes', 15))
    q = JournalAudit.query.filter(JournalAudit.identifiant == identifiant, JournalAudit.adresse_ip == ip,
                                  JournalAudit.horodatage >= depuis)
    reussie = q.filter(JournalAudit.action == Action.CONNEXION).order_by(JournalAudit.horodatage.desc()).first()
    if reussie is not None:
        q = q.filter(JournalAudit.horodatage > reussie.horodatage)
    return q.filter(JournalAudit.action == Action.ECHEC_CONNEXION,
                    JournalAudit.detail == 'identifiant ou mot de passe incorrect').count()


def bloque(identifiant, ip):
    from app.services import parametres
    return echecs_recents(identifiant, ip) >= parametres.obtenir('securite.echecs_avant_blocage', 5)


class ProxyDeConfiance:
    """X-Forwarded-For / X-Forwarded-Proto lus SEULEMENT si la requête vient de nginx sur la même machine
    (127.0.0.1) ; sinon l'adresse directe est gardée (en-tête inventé par un visiteur : ignoré)."""
    LOCALES = ('127.0.0.1', '::1')

    def __init__(self, application):
        from werkzeug.middleware.proxy_fix import ProxyFix
        self.direct = application
        self.derriere_nginx = ProxyFix(application, x_for=1, x_proto=1)

    def __call__(self, environ, start_response):
        cible = self.derriere_nginx if environ.get('REMOTE_ADDR') in self.LOCALES else self.direct
        return cible(environ, start_response)


# ── Lot L : comptes de démonstration en un clic (page de connexion) ─────

LIBELLES_COURTS = {'ADMIN': 'Administrateur', 'DGE': 'DGE (POUFA)', 'AGENT': 'Agent technique', 'ELEVEUR': 'Éleveur',
                   'VETO': 'Vétérinaire', 'BCEG': 'BCEG', 'MAEDR': 'MAEDR', 'AUDITEUR': 'Auditeur ANINF',
                   'OPERATEUR': 'Opérateur'}
PILOTAGE = ('DGE', 'VETO', 'ADMIN', 'AUDITEUR', 'BCEG', 'MAEDR')
TERRAIN = ('ELEVEUR', 'AGENT', 'OPERATEUR')


# Les cinq comptes montrés sur la page de connexion (décision du propriétaire, 10/11/2026) ; les autres existent mais ne sont pas listés
COMPTES_AFFICHES = ('dge', 'veto', 'admin', 'agent.est', 'eleveur')


def comptes_en_un_clic():
    """{'actif', 'mot_de_passe', 'pilotage': [...], 'terrain': [...]} : les comptes actifs de la base de
    démonstration, lus (jamais inventés), rangés en deux groupes. Vide si le réglage SORRA_DEMO_COMPTES est absent."""
    if not (active() and current_app.config.get('DEMO_COMPTES')):
        return None
    from app.models import Utilisateur
    groupes = {'pilotage': [], 'terrain': []}
    for u in Utilisateur.query.filter(Utilisateur.actif.is_(True), Utilisateur.identifiant.in_(COMPTES_AFFICHES)).order_by(Utilisateur.identifiant):
        p = u.profil.value
        if p == 'OPERATEUR':
            libelle = f'{u.operateur.type} · {u.operateur.nom}' if u.operateur else LIBELLES_COURTS[p]
        elif p == 'AGENT' and u.provinces:
            libelle = f'{LIBELLES_COURTS[p]} · {", ".join(pr.nom for pr in u.provinces)}'
        elif p == 'ELEVEUR' and u.fermes:
            libelle = f'{LIBELLES_COURTS[p]} · {", ".join(uf.numero_ferme for uf in u.fermes)}'
        else:
            libelle = LIBELLES_COURTS.get(p, p)
        groupe = 'pilotage' if p in PILOTAGE else 'terrain'
        groupes[groupe].append({'identifiant': u.identifiant, 'libelle': libelle,
                                'ordre': (PILOTAGE + TERRAIN).index(p) if p in PILOTAGE + TERRAIN else 99})
    for g in groupes.values():
        g.sort(key=lambda c: COMPTES_AFFICHES.index(c['identifiant']))
    return {'mot_de_passe': current_app.config['DEMO_MOT_DE_PASSE'], **groupes}
