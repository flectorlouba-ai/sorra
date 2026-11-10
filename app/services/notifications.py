"""Lot T — notifications Web Push (cahier § 7.6). Qui reçoit quoi suit le profil et le périmètre ; texte court,
sans donnée personnelle ; un toucher ouvre le bon écran après connexion. Les clés VAPID sont dans le .env du serveur
(SORRA_VAPID_PRIVEE, SORRA_VAPID_PUBLIQUE, SORRA_VAPID_CONTACT) ; sans clés, rien n'est envoyé et le journal le dit.
Envoi : `flask notifications-envoyer` toutes les 15 min (cron), et tout de suite pour une alerte sanitaire."""
import json
import os
from datetime import date, datetime, timedelta

from flask import current_app, has_request_context, url_for

from app import db
from app.models import Ferme, Profil, Utilisateur
from app.models.base import maintenant
from app.models.notification import AbonnementPush, Notification, PreferenceNotification, TypeNotification as T
from app.services import parametres
from app.utils.permissions import filtre_perimetre


def lien(endpoint, **valeurs):
    """Adresse relative, aussi hors requête (commande cron)."""
    if has_request_context():
        return url_for(endpoint, **valeurs)
    with current_app.test_request_context():
        return url_for(endpoint, **valeurs)


def cles():
    privee, publique = os.environ.get('SORRA_VAPID_PRIVEE'), os.environ.get('SORRA_VAPID_PUBLIQUE')
    return (privee, publique, os.environ.get('SORRA_VAPID_CONTACT', 'mailto:contact@performyl.com')) if privee and publique else None


def cle_publique():
    c = cles()
    return c[1] if c else None


# ── Préférences ─────────────────────────────────────────────────────────

def types_du_profil(user):
    return T.PAR_PROFIL.get(user.profil.value, ())


def preferences(user):
    """{type: PreferenceNotification} ; une préférence manquante vaut « actif »."""
    return {p.type: p for p in PreferenceNotification.query.filter_by(utilisateur_id=user.id)}


def actif(user, type_, prefs=None):
    if type_ in T.TOUJOURS:
        return True
    p = (prefs if prefs is not None else preferences(user)).get(type_)
    return p.actif if p is not None else True


def regler(user, type_, actif_, heure=None):
    if type_ in T.TOUJOURS and not actif_:
        return                                        # les alertes sanitaires ne se coupent pas
    p = PreferenceNotification.query.filter_by(utilisateur_id=user.id, type=type_).first()
    if p is None:
        p = PreferenceNotification(utilisateur_id=user.id, type=type_)
        db.session.add(p)
    p.actif = bool(actif_)
    if heure in (17, 18, 19):
        p.heure = heure


def heure_rappel(user, prefs=None):
    p = (prefs if prefs is not None else preferences(user)).get(T.SAISIE_OUBLIEE)
    return p.heure if p is not None and p.heure else int(parametres.obtenir('notifications.rappel_saisie_heure', 18))


# ── Abonnements ─────────────────────────────────────────────────────────

def abonner(user, abonnement, appareil=None):
    """Garde (ou remet à jour) l'abonnement envoyé par le navigateur : {endpoint, keys: {p256dh, auth}}."""
    endpoint = (abonnement or {}).get('endpoint')
    keys = (abonnement or {}).get('keys') or {}
    if not endpoint or not keys.get('p256dh') or not keys.get('auth'):
        raise ValueError('Abonnement incomplet.')
    a = AbonnementPush.query.filter_by(endpoint=endpoint).first()
    if a is None:
        a = AbonnementPush(endpoint=endpoint)
        db.session.add(a)
    a.utilisateur_id, a.p256dh, a.auth, a.actif = user.id, keys['p256dh'][:200], keys['auth'][:100], True
    a.appareil = (appareil or '')[:64] or None
    return a


def desabonner(user, endpoint=None):
    q = AbonnementPush.query.filter_by(utilisateur_id=user.id)
    if endpoint:
        q = q.filter_by(endpoint=endpoint)
    for a in q:
        a.actif = False


# ── Création et envoi ───────────────────────────────────────────────────

def notifier(user, type_, cle, titre, texte, lien=None, prefs=None, tout_de_suite=False):
    """Crée la notification si elle n'existe pas déjà (clé d'unicité) et si la personne la veut. Rend la notification
    ou None. L'envoi se fait par `envoyer_en_attente`, ou tout de suite pour une alerte sanitaire."""
    if not actif(user, type_, prefs):
        return None
    if Notification.query.filter_by(utilisateur_id=user.id, cle=cle[:120]).first() is not None:
        return None
    n = Notification(utilisateur_id=user.id, type=type_, cle=cle[:120], titre=titre[:80], texte=texte[:200],
                     lien=(lien or '')[:200] or None)
    db.session.add(n)
    db.session.flush()
    if tout_de_suite:
        envoyer(n)
    return n


def envoyer(n):
    """Envoie à tous les téléphones abonnés de la personne. Le résultat est gardé (sans le contenu personnel)."""
    from app.services.journal import enregistrer, Action
    abonnements = AbonnementPush.query.filter_by(utilisateur_id=n.utilisateur_id, actif=True).all()
    c = cles()
    if not abonnements:
        n.resultat, n.envoyee_le = 'sans_abonnement', maintenant()
        return False
    if c is None:
        n.resultat, n.envoyee_le = 'sans_cles', maintenant()
        return False
    from pywebpush import webpush, WebPushException
    privee, _, contact = c
    charge = json.dumps({'titre': n.titre, 'texte': n.texte, 'lien': n.lien or '/', 'type': n.type})
    envoyes = 0
    for a in abonnements:
        try:
            webpush(subscription_info={'endpoint': a.endpoint, 'keys': {'p256dh': a.p256dh, 'auth': a.auth}},
                    data=charge, vapid_private_key=privee, vapid_claims={'sub': contact}, ttl=6 * 3600, timeout=10)
            a.dernier_envoi_le = maintenant()
            envoyes += 1
        except WebPushException as e:
            code = getattr(getattr(e, 'response', None), 'status_code', None)
            if code in (404, 410):
                a.actif = False                          # abonnement périmé
        except Exception:
            pass
    n.envoyee_le = maintenant()
    n.resultat = f'envoyee:{envoyes}' if envoyes else 'erreur'
    enregistrer(Action.EXPORT, table='notification', enregistrement_id=n.id,
                detail=f'Notification {n.type} envoyée à {envoyes} appareil(s)')
    return envoyes > 0


def envoyer_en_attente():
    n_envoyees = 0
    for n in Notification.query.filter(Notification.envoyee_le.is_(None)).order_by(Notification.id):
        n_envoyees += 1 if envoyer(n) else 0
    return n_envoyees


# ── Les événements du moment, par profil ────────────────────────────────

def _jour():
    return date.today().isoformat()


def calculer(maintenant_=None):
    """Parcourt les comptes terrain et pilotage et crée les notifications dues (pas encore envoyées = pas encore
    créées, grâce à la clé). Rend le nombre créé."""
    from app import indicateurs
    from app.models.bande import Bande, StatutBande
    from app.models.intrant import Livraison, StatutLivraison
    from app.models.sante import AlerteSanitaire, StatutAlerte
    from app.models.hors_ligne import ConflitHorsLigne, StatutVerification
    from app.models.visite import Visite, StatutVisite
    from app.models.securite import Proposition
    from app.services import sante, veto, actions as services_actions
    heure = (maintenant_ or datetime.now()).hour
    aujourd_hui, demain = date.today(), date.today() + timedelta(days=1)
    crees = 0
    for u in Utilisateur.query.filter_by(actif=True):
        prefs = preferences(u)
        p = u.profil
        if p == Profil.ELEVEUR:
            fermes = [uf.ferme for uf in u.fermes]
            bandes = [b for f in fermes for b in Bande.query.filter_by(ferme_id=f.id, statut=StatutBande.EN_COURS)]
            for b in bandes:
                if heure >= heure_rappel(u, prefs) and not indicateurs.saisie_du(b, aujourd_hui):
                    crees += bool(notifier(u, T.SAISIE_OUBLIEE, f'saisie:{b.id}:{_jour()}', '📝 Saisie du jour',
                                           "Vous n'avez pas encore fait la saisie du jour.", lien('eleveur.saisie'), prefs))
                prochaine = indicateurs.prochaine_pesee(b)
                if prochaine and prochaine < aujourd_hui:
                    crees += bool(notifier(u, T.PESEE_RETARD, f'pesee:{b.id}:{_jour()}', '⚖️ Pesée en retard',
                                           'Pensez à peser vos poulets : la pesée de la semaine est en retard.',
                                           lien('bandes.pesee', numero=b.numero), prefs))
                for v in sante.vaccins_de_la_bande(b):
                    if v.get('etat') == 'demain':
                        crees += bool(notifier(u, T.VACCIN_DEMAIN, f'vaccin:{b.id}:{v["calendrier"].id}', '💉 Vaccin demain',
                                               f'Un vaccin est à faire demain ({v["calendrier"].produit.nom}).', lien('eleveur.soins'), prefs))
                if veto.blocage_actif(b) is not None:
                    crees += bool(notifier(u, T.VENTES_BLOQUEES, f'blocage:{veto.blocage_actif(b).id}', '⛔ Ventes bloquées',
                                           'Le vétérinaire a bloqué les ventes de votre bande. Aucun poulet ne doit sortir.',
                                           lien('bandes.sortie', numero=b.numero), prefs))
            # Lot G : rappels fiscaux (une fois par an et par rappel)
            from app.services import bilan as services_bilan
            for code, titre, texte, echeance, du in services_bilan.rappels(fermes, aujourd_hui):
                if du:
                    crees += bool(notifier(u, T.RAPPEL_FISCAL, f'fiscal:{code}:{aujourd_hui.year}', f'🏛️ {titre}', texte,
                                           lien('argent.fiscalite'), prefs))
            for f in fermes:
                for a in AlerteSanitaire.query.filter_by(ferme_id=f.id):
                    for r in a.reponses:
                        if r.lue_le is None:
                            crees += bool(notifier(u, T.REPONSE_VETO, f'reponse:{r.id}', '💬 Réponse du vétérinaire',
                                                   'Le vétérinaire vous a répondu.', lien('sante.mes_declarations'), prefs))
                for liv in Livraison.query.filter_by(ferme_id=f.id, statut=StatutLivraison.A_CONFIRMER):
                    crees += bool(notifier(u, T.LIVRAISON_A_CONFIRMER, f'livraison:{liv.id}', '🚚 Livraison à confirmer',
                                           'Une livraison attend votre confirmation.', lien('eleveur.produits'), prefs))
        elif p == Profil.AGENT:
            fermes = Ferme.query.filter_by(agent_id=u.id).all()
            jours = int(parametres.obtenir('notifications.ferme_sans_saisie_jours', 2))
            for f in fermes:
                for b in Bande.query.filter_by(ferme_id=f.id, statut=StatutBande.EN_COURS):
                    if indicateurs.feu(b)[0] == 'rouge':
                        crees += bool(notifier(u, T.FEU_ROUGE, f'rouge:{b.id}:{_jour()}', '🔴 Alerte sanitaire',
                                               f'{f.numero} : beaucoup de morts. Le vétérinaire est prévenu.',
                                               lien('bandes.fiche', numero=b.numero), prefs, tout_de_suite=True))
                    derniere = max((s.date for s in b.saisies), default=None)
                    if (derniere or b.date_mise_en_place) <= aujourd_hui - timedelta(days=jours):
                        crees += bool(notifier(u, T.FERME_SANS_SAISIE, f'sans_saisie:{b.id}:{_jour()}', '📵 Ferme sans saisie',
                                               f'{f.numero} : rien de noté depuis {jours} jours.', lien('terrain.fiche', numero=f.numero), prefs))
            ids = [f.id for f in fermes]
            if ids:
                for c in ConflitHorsLigne.query.filter(ConflitHorsLigne.ferme_id.in_(ids), ConflitHorsLigne.statut == StatutVerification.A_VERIFIER):
                    crees += bool(notifier(u, T.DEUX_VERSIONS, f'conflit:{c.id}', '⚖️ Deux versions à trancher',
                                           'Une saisie a deux versions : à vous de trancher.', lien('hors_ligne.conflits'), prefs))
                for v in Visite.query.filter(Visite.ferme_id.in_(ids), Visite.statut == StatutVisite.PREVUE, Visite.date_prevue == demain):
                    crees += bool(notifier(u, T.VISITE_DEMAIN, f'visite:{v.id}', '📋 Visite demain',
                                           f'Visite prévue demain : {v.ferme.numero}.', lien('terrain.tournee'), prefs))
            for a in services_actions.en_retard(u):
                if a.responsable_id == u.id:
                    crees += bool(notifier(u, T.ACTION_RETARD, f'action:{a.id}:{_jour()}', '🎯 Action en retard',
                                           f'{a.numero} est en retard de {a.retard_jours} jour(s).', lien('notifications.actions_terrain'), prefs))
        elif p == Profil.OPERATEUR and u.operateur is not None:
            from app.services import receptions
            for lot in receptions.attendus(u.operateur, jours=3):
                crees += bool(notifier(u, T.LOT_EN_ROUTE, f'lot:{lot.id}', '🚚 Lot en route',
                                       f'Le lot {lot.numero} est parti vers vous.', lien('operateur.attendus'), prefs))
            from app.models.tracabilite import Reception
            for r in Reception.query.filter(Reception.operateur_id == u.operateur.id, Reception.decision_par.isnot(None),
                                            Reception.vu_le.is_(None)):
                crees += bool(notifier(u, T.LOT_DECIDE, f'decision:{r.id}', '🩺 Décision du vétérinaire',
                                       'Le vétérinaire a décidé pour un lot gardé à part.', lien('operateur.receptions'), prefs))
        elif p in (Profil.VETO, Profil.DGE):
            from app.services import sante as services_sante
            for a in services_sante.alertes_visibles(u).filter(AlerteSanitaire.statut.in_(StatutAlerte.OUVERTES)):
                type_ = T.ALERTE_SANITAIRE if a.origine != 'DECLARATION' else T.SIGNALEMENT
                crees += bool(notifier(u, type_, f'alerte:{a.id}', '🔴 Alerte sanitaire' if type_ == T.ALERTE_SANITAIRE else '📨 Nouveau signalement',
                                       f'{a.ferme.numero} : {a.libelle_origine.lower()}.', lien('sante.alerte', numero=a.numero), prefs,
                                       tout_de_suite=type_ == T.ALERTE_SANITAIRE))
            limite = maintenant() - timedelta(hours=48)
            for c in filtre_perimetre(ConflitHorsLigne.query, utilisateur=u).filter(
                    ConflitHorsLigne.statut == StatutVerification.A_VERIFIER, ConflitHorsLigne.cree_le <= limite):
                crees += bool(notifier(u, T.ECART_48H, f'ecart48:{c.id}', '⏳ Écart à trancher', 'Un écart attend depuis plus de 48 h.',
                                       lien('hors_ligne.conflits'), prefs))
            for prop in Proposition.query.filter_by(statut='EN_ATTENTE'):
                if prop.propose_par != u.id:
                    crees += bool(notifier(u, T.PARAMETRE_A_APPROUVER, f'proposition:{prop.id}', '👀 Paramètre à approuver',
                                           'Un changement de paramètre attend votre approbation.', lien('controle.approbations_ecran'), prefs))
    return crees


def alerte_immediate(alerte):
    """Appelée à la création d'une alerte sanitaire : l'agent, le vétérinaire et la DGE sont prévenus tout de suite."""
    ferme = alerte.ferme
    destinataires = []
    if ferme.agent:
        destinataires.append(ferme.agent)
    destinataires += [u for u in Utilisateur.query.filter(Utilisateur.actif.is_(True), Utilisateur.profil.in_((Profil.VETO, Profil.DGE)))
                      if u.est_national or ferme.province_id in u.province_ids]
    for u in destinataires:
        notifier(u, T.ALERTE_SANITAIRE if u.profil != Profil.AGENT else T.FEU_ROUGE, f'alerte:{alerte.id}', '🔴 Alerte sanitaire',
                 f'{ferme.numero} : {alerte.libelle_origine.lower()}.', lien('sante.alerte', numero=alerte.numero), tout_de_suite=True)
