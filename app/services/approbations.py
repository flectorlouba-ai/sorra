"""Double validation (« quatre yeux », lot 15) : un paramètre sensible modifié devient une PROPOSITION
(avant, après, motif) ; une AUTRE personne habilitée l'approuve ou la refuse. L'ancienne valeur
s'applique jusqu'à l'approbation. Tout est inscrit au journal."""
from app import db
from app.models import Parametre, Profil, Utilisateur
from app.models.base import maintenant
from app.models.securite import Proposition, StatutProposition as S
from app.services.journal import enregistrer, Action

# Paramètres sensibles (préfixes de clé). Les autres paramètres restent modifiables directement.
SENSIBLES = ('bandes.seuil_', 'bandes.ecart_courbe', 'bandes.courbe_poids', 'intrants.seuil_', 'sante.',
             'verifications.', 'classement.', 'securite.profils_2fa', 'stock.seuil_', 'reception.',
             'production.poids_', 'production.rendement_', 'production.objectif_',   # lot A3
             'fiscalite.')   # lot G / K4 : seuils fiscaux estimés
SANITAIRES = ('sante.', 'bandes.seuil_', 'bandes.ecart_courbe', 'bandes.courbe_poids', 'reception.')


class RegleApprobation(Exception):
    pass


def sensible(cle):
    return cle.startswith(SENSIBLES) or cle.startswith('formule.')


def domaine(genre, cle):
    return 'SANITAIRE' if genre == 'CALENDRIER' or cle.startswith(SANITAIRES) else 'GENERAL'


def proposer(genre, cle, libelle, avant, apres, donnees, motif, user):
    if not (motif or '').strip():
        raise RegleApprobation('Indiquez le motif de la modification.')
    if Proposition.query.filter_by(genre=genre, cle=cle, statut=S.EN_ATTENTE).first():
        raise RegleApprobation('Une modification de ce réglage attend déjà son approbation.')
    p = Proposition(genre=genre, cle=cle, libelle=libelle[:200], domaine=domaine(genre, cle),
                    avant=None if avant is None else str(avant), apres=str(apres), donnees=donnees,
                    motif=motif.strip(), propose_par=user.id)
    db.session.add(p)
    db.session.flush()
    enregistrer(Action.PROPOSITION, table='proposition', enregistrement_id=p.id,
                detail=f'{libelle} : {avant} → {apres} proposé par {user.nom_complet} — {motif.strip()}')
    return p


def peut_decider(user, p):
    if p.propose_par == user.id:
        return False                                       # jamais sa propre proposition
    if user.profil in (Profil.ADMIN, Profil.DGE):
        return True
    return user.profil == Profil.VETO and p.domaine == 'SANITAIRE'


def a_decider(user):
    return [p for p in Proposition.query.filter_by(statut=S.EN_ATTENTE).order_by(Proposition.propose_le)
            if peut_decider(user, p)]


def _appliquer(p):
    d = p.donnees or {}
    if p.genre in ('PARAMETRE', 'FORMULE'):
        param = Parametre.query.filter_by(cle=p.cle).first()
        if d.get('origine'):                               # formule : retour à celle d'origine
            if param is not None:
                db.session.delete(param)
            return
        if param is None:
            from app.models import TypeParametre
            param = Parametre(cle=p.cle, type=TypeParametre(d.get('type', 'TEXTE')), description=d.get('description', p.libelle))
            db.session.add(param)
        param.valeur = d['valeur']
    elif p.genre == 'CALENDRIER':
        from app.models import Produit
        from app.models.sante import CalendrierVaccinal
        entree = db.session.get(CalendrierVaccinal, d['id']) if d.get('id') else CalendrierVaccinal()
        entree.age_jours, entree.produit = d['age_jours'], db.session.get(Produit, d['produit_id'])
        entree.mode, entree.actif = d['mode'], d['actif']
        db.session.add(entree)
    elif p.genre == 'POSITION':                            # lot E : position corrigée à la main, loin
        import uuid
        from app.models import Ferme
        from app.services import positions
        ferme = db.session.get(Ferme, uuid.UUID(d['ferme_id']))
        auteur = db.session.get(Utilisateur, uuid.UUID(d['auteur_id'])) if d.get('auteur_id') else None
        positions.appliquer_correction(ferme, d['latitude'], d['longitude'], p.motif, auteur)
    elif p.genre == 'PROFIL':
        import uuid
        u = db.session.get(Utilisateur, uuid.UUID(d['utilisateur_id']))
        u.profil = Profil(d['profil'])
    from app.services import parametres
    parametres.oublier_cache()


def decider(p, user, approuver, motif=''):
    if p.statut != S.EN_ATTENTE:
        raise RegleApprobation('Cette proposition est déjà décidée.')
    if not peut_decider(user, p):
        raise RegleApprobation("Une autre personne habilitée doit décider (jamais l'auteur).")
    if not approuver and not (motif or '').strip():
        raise RegleApprobation('Indiquez le motif du refus.')
    p.statut = S.APPROUVEE if approuver else S.REFUSEE
    p.decide_par, p.decide_le, p.motif_decision = user.id, maintenant(), (motif or '').strip() or None
    if approuver:
        _appliquer(p)
    enregistrer(Action.APPROBATION if approuver else Action.REFUS, table='proposition', enregistrement_id=p.id,
                detail=f'{p.libelle} : {p.avant} → {p.apres} {"approuvé" if approuver else "refusé"} par '
                       f'{user.nom_complet}' + (f' — {p.motif_decision}' if p.motif_decision else ''))
    db.session.flush()
    return p
