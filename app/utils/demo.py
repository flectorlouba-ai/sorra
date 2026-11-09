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
