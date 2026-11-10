"""Santé animale : déclarations, alertes sanitaires, vaccins, traitements."""
import os
import secrets
from datetime import date, timedelta

from flask import current_app

from app import db, indicateurs
from app.models import Profil
from app.models.bande import Bande, StatutBande
from app.models.sante import (Declaration, DeclarationPhoto, AlerteSanitaire, AlerteHistorique,
                              CalendrierVaccinal, Vaccination, Traitement, StatutAlerte as SA, OrigineAlerte)
from app.services import parametres
from app.services.journal import enregistrer, Action
from app.services.numerotation import generer_numero
from app.utils.permissions import filtre_perimetre

MAX_PHOTOS = 3
TAILLE_MAX = 6 * 1024 * 1024

# Pictogramme de chaque signe (la liste est configurable : un signe inconnu prend l'icône par défaut)
ICONES_SIGNES = [('mortalit', 'exclamation-octagon'), ('abattement', 'emoji-dizzy'), ('mange', 'egg-fried'),
                 ('diarrh', 'droplet-half'), ('toux', 'lungs'), ('respir', 'lungs'), ('plume', 'feather'),
                 ('boiter', 'person-walking'), ('tête', 'emoji-expressionless'), ('tete', 'emoji-expressionless')]


def icone_signe(signe):
    s = (signe or '').lower()
    return next((icone for mot, icone in ICONES_SIGNES if mot in s), 'question-circle')


class RegleSante(ValueError):
    pass


# ── Fichiers (photos, message vocal) : hors de static, servis après contrôle ──

_SIGNATURES = {b'\xff\xd8\xff': ('image/jpeg', '.jpg'), b'\x89PNG': ('image/png', '.png'),
               b'RIFF': ('image/webp', '.webp')}
_AUDIO = {b'\x1aE\xdf\xa3': ('audio/webm', '.webm'), b'OggS': ('audio/ogg', '.ogg')}


def dossier(sous_dossier='sante'):
    d = os.path.join(current_app.instance_path, 'televersements', sous_dossier)
    os.makedirs(d, exist_ok=True)
    return d


def _enregistrer(fichier, signatures, mp4_audio=False, sous_dossier='sante'):
    contenu = fichier.read(TAILLE_MAX + 1)
    if not contenu:
        return None
    if len(contenu) > TAILLE_MAX:
        raise RegleSante('Fichier trop lourd (6 Mo au plus).')
    genre = next((v for k, v in signatures.items() if contenu.startswith(k)), None)
    if genre is None and mp4_audio and contenu[4:8] == b'ftyp':
        genre = ('audio/mp4', '.m4a')
    if genre is None:
        raise RegleSante('Ce fichier n\'est pas reconnu.')
    nom = secrets.token_hex(16) + genre[1]
    with open(os.path.join(dossier(sous_dossier), nom), 'wb') as f:
        f.write(contenu)
    return nom, genre[0]


def chemin_fichier(nom, sous_dossier='sante'):
    if not nom or '/' in nom or '\\' in nom or '..' in nom:
        return None
    return os.path.join(dossier(sous_dossier), nom)


TYPES_AUDIO = {'.webm': 'audio/webm', '.ogg': 'audio/ogg', '.m4a': 'audio/mp4'}


# ── Déclarations et alertes ─────────────────────────────────────────────

def declarations_visibles(user):
    """Transmises aux seuls vétérinaires de la province ; l'éleveur voit les siennes ; l'ADMIN tout."""
    q = Declaration.query.filter(Declaration.archive_le.is_(None))          # lot A : archivées masquées
    if user.profil == Profil.ADMIN:
        return q
    if user.profil == Profil.VETO:
        return filtre_perimetre(q, utilisateur=user)
    if user.profil == Profil.ELEVEUR:
        return q.filter(Declaration.cree_par == user.id)
    return q.filter(db.false())


def alertes_visibles(user):
    """VETO : sa province ; DGE : alertes confirmées seulement ; ADMIN : toutes."""
    q = AlerteSanitaire.query
    if user.profil == Profil.ADMIN:
        return q
    if user.profil == Profil.VETO:
        return filtre_perimetre(q, utilisateur=user)
    if user.profil == Profil.DGE:
        return q.filter(AlerteSanitaire.confirmee.is_(True))
    return q.filter(db.false())


def _nouvelle_alerte(ferme, bande, origine, declaration=None, commentaire=None):
    a = AlerteSanitaire(numero=generer_numero('ALERTE', 'ALS', annuel=True, largeur=4), ferme=ferme,
                        bande=bande, origine=origine, declaration=declaration, statut=SA.NOUVELLE)
    a.historique.append(AlerteHistorique(statut=SA.NOUVELLE, commentaire=commentaire))
    db.session.add(a)
    db.session.flush()
    try:                                                    # lot T : l'agent, le vétérinaire et la DGE tout de suite
        from app.services import notifications
        notifications.alerte_immediate(a)
    except Exception:
        pass
    return a


def declarer(ferme, bande, signes, nombre, photos, audio, user):
    if not signes:
        raise RegleSante('Touchez au moins un signe observé.')
    if not nombre or nombre < 1:
        raise RegleSante('Indiquez combien d\'animaux sont touchés.')
    photos = [p for p in photos if p and p.filename][:MAX_PHOTOS]
    d = Declaration(ferme=ferme, bande=bande, signes=signes, nombre_animaux=nombre,
                    saisi_par_agent=user.profil == Profil.AGENT)
    for p in photos:
        enregistre = _enregistrer(p, _SIGNATURES)
        if enregistre:
            d.photos.append(DeclarationPhoto(fichier=enregistre[0], type_mime=enregistre[1]))
    if audio and audio.filename:
        enregistre = _enregistrer(audio, _AUDIO, mp4_audio=True)
        d.audio = enregistre[0] if enregistre else None
    db.session.add(d)
    db.session.flush()
    _nouvelle_alerte(ferme, bande, OrigineAlerte.DECLARATION, declaration=d,
                     commentaire=f'{nombre} animal(aux) touché(s) : {", ".join(signes)}')
    if user.profil == Profil.AGENT:
        enregistrer(Action.POUR_ELEVEUR, table='declaration', enregistrement_id=d.id,
                    detail=f'Déclaration sanitaire ({ferme.numero_metier}) — agent {user.nom_complet} pour l\'éleveur.')
    return d


def alerte_si_feu_rouge(bande):
    """Une alerte naît d'un feu rouge (une seule ouverte à la fois par bande)."""
    if not bande.en_cours or indicateurs.feu(bande)[0] != 'rouge':
        return None
    ouverte = AlerteSanitaire.query.filter(AlerteSanitaire.bande_id == bande.id,
                                           AlerteSanitaire.origine == OrigineAlerte.FEU_ROUGE,
                                           AlerteSanitaire.statut.in_(SA.OUVERTES)).first()
    if ouverte:
        return None
    v = indicateurs.calculer(bande)
    return _nouvelle_alerte(bande.ferme, bande, OrigineAlerte.FEU_ROUGE,
                            commentaire=f'{v["morts_jour"]} morts le {v["jour_considere"].strftime("%d/%m")} '
                                        f'({indicateurs.arrondi(v["mortalite_jour"], 1)} % de l\'effectif)')


def changer_statut(alerte, nouveau, commentaire, user):
    if user.profil != Profil.VETO:
        raise RegleSante('Seuls les services vétérinaires qualifient une alerte.')
    if nouveau not in SA.SUIVANTS.get(alerte.statut, []):
        raise RegleSante('Ce changement de statut n\'est pas possible.')
    if not commentaire:
        raise RegleSante('Un commentaire est obligatoire.')
    alerte.statut = nouveau
    if nouveau == SA.CONFIRMEE:
        alerte.confirmee = True
    alerte.historique.append(AlerteHistorique(statut=nouveau, utilisateur_id=user.id, commentaire=commentaire))


# ── Calendrier vaccinal, vaccinations, traitements ──────────────────────

def calendrier():
    return CalendrierVaccinal.query.filter_by(actif=True).order_by(CalendrierVaccinal.age_jours).all()


def vaccins_de_la_bande(bande, jour=None):
    """État de chaque vaccin du calendrier : fait, aujourd'hui, demain, à venir, en retard."""
    jour = jour or date.today()
    retard = int(parametres.obtenir('sante.retard_vaccin_jours', 2))
    faits = {v.calendrier_id: v for v in Vaccination.query.filter_by(bande_id=bande.id, annule=False)}
    resultat = []
    for c in calendrier():
        prevu = bande.date_mise_en_place + timedelta(days=c.age_jours)
        if c.id in faits:
            etat = 'fait'
        elif bande.rattrapage and prevu < indicateurs.debut_suivi(bande):
            etat = 'avant_suivi'
        elif prevu == jour:
            etat = 'aujourdhui'
        elif prevu == jour + timedelta(days=1):
            etat = 'demain'
        elif jour > prevu + timedelta(days=retard):
            etat = 'retard'
        elif jour > prevu:
            etat = 'a_faire'
        else:
            etat = 'a_venir'
        resultat.append({'calendrier': c, 'prevu': prevu, 'etat': etat, 'fait': faits.get(c.id)})
    return resultat


def a_faire(bande, jour=None):
    """Vaccins du jour et du lendemain (pour « À faire aujourd'hui »)."""
    if not bande.en_cours:
        return []
    taches = []
    for v in vaccins_de_la_bande(bande, jour):
        nom = f'{v["calendrier"].produit.nom} ({v["calendrier"].mode.lower()})'
        if v['etat'] in ('aujourdhui', 'a_faire', 'retard'):
            taches.append({'texte': f'Vaccin {"en retard" if v["etat"] == "retard" else "du jour"} : {nom}',
                           'calendrier': v['calendrier'].id})
        elif v['etat'] == 'demain':
            taches.append({'texte': f'Demain : vaccin {nom}', 'calendrier': None})
    return taches


def vaccins_en_retard(base_bandes):
    """[(bande, [vaccins en retard])] parmi les bandes en cours visibles."""
    resultat = []
    for b in base_bandes.filter(Bande.statut == StatutBande.EN_COURS).order_by(Bande.numero_metier):
        retards = [v for v in vaccins_de_la_bande(b) if v['etat'] == 'retard']
        if retards:
            resultat.append((b, retards))
    return resultat


def _jour_valide(bande, jour):
    if jour > date.today() or jour < bande.date_mise_en_place:
        raise RegleSante('La date doit être entre la mise en place et aujourd\'hui.')


DELAI_ANNULATION_SECONDES = 10
TOLERANCE_RESEAU_SECONDES = 20


def vaccination_annulable(v, user):
    """« Fait ✓ — Annuler (10) » après « ✓ C'est fait » (lot 11) : même personne, juste après."""
    from app.models.base import maintenant
    from app.utils.dates import en_utc
    if v.annule or v.cree_par != user.id:
        return False
    return (maintenant() - en_utc(v.cree_le)).total_seconds() <= DELAI_ANNULATION_SECONDES + TOLERANCE_RESEAU_SECONDES


def vacciner(bande, jour, produit, mode, nombre, quantite, entree, user):
    _jour_valide(bande, jour)
    if produit is None or produit.type != 'Vaccin':
        raise RegleSante('Choisissez le vaccin.')
    if not mode:
        raise RegleSante('Choisissez le mode d\'administration.')
    if not nombre or nombre < 1:
        raise RegleSante('Indiquez le nombre d\'animaux vaccinés.')
    v = Vaccination(bande=bande, date=jour, produit=produit, mode=mode, nombre_animaux=nombre,
                    quantite=quantite if quantite is not None else nombre, calendrier=entree,
                    saisi_par_agent=user.profil == Profil.AGENT)
    db.session.add(v)
    if user.profil == Profil.AGENT:
        enregistrer(Action.POUR_ELEVEUR, table='bande', enregistrement_id=bande.id,
                    detail=f'Bande {bande.numero} : vaccination {produit.nom} — agent {user.nom_complet} pour l\'éleveur.')
    return v


def traiter(bande, debut, fin, produit, motif, nombre, quantite, user):
    _jour_valide(bande, debut)
    if fin < debut:
        raise RegleSante('La date de fin doit être après le début.')
    if produit is None or produit.type != 'Médicament':
        raise RegleSante('Choisissez le médicament.')
    if not motif:
        raise RegleSante('Indiquez le motif du traitement.')
    if not nombre or nombre < 1:
        raise RegleSante('Indiquez le nombre d\'animaux traités.')
    if quantite is None or quantite < 0:
        raise RegleSante('Indiquez la quantité de médicament utilisée.')
    t = Traitement(bande=bande, date_debut=debut, date_fin=fin, produit=produit, motif=motif,
                   nombre_animaux=nombre, quantite=quantite, saisi_par_agent=user.profil == Profil.AGENT)
    db.session.add(t)
    if user.profil == Profil.AGENT:
        enregistrer(Action.POUR_ELEVEUR, table='bande', enregistrement_id=bande.id,
                    detail=f'Bande {bande.numero} : traitement {produit.nom} — agent {user.nom_complet} pour l\'éleveur.')
    return t


def fin_delai_attente(bande, jour=None):
    """Dernier jour du délai d'attente avant abattage (None si aucun en cours)."""
    jour = jour or date.today()
    fins = [t.date_fin + timedelta(days=t.produit.delai_attente_jours or 0)
            for t in Traitement.query.filter_by(bande_id=bande.id, archive_le=None) if t.produit.delai_attente_jours]
    fins = [f for f in fins if f >= jour]
    return max(fins) if fins else None


# ── Réponse du vétérinaire à l'éleveur (lot 12) ─────────────────────────

ETATS_ELEVEUR = {'envoye': 'Envoyé ✓', 'regarde': 'Le vétérinaire regarde', 'reponse': '💬 Réponse du vétérinaire',
                 'termine': 'Terminé'}


def repondre(alerte, texte, conseils, user):
    """Réponse datée, signée du vétérinaire, inscrite au journal ; jamais effacée."""
    from app.models.sante import ReponseVeterinaire
    if user.profil != Profil.VETO:
        raise RegleSante("Seuls les vétérinaires répondent à l'éleveur.")
    texte = (texte or '').strip()[:300] or None
    conseils = [c for c in (conseils or []) if c]
    if not texte and not conseils:
        raise RegleSante('Cochez un conseil ou écrivez un message.')
    r = ReponseVeterinaire(alerte=alerte, texte=texte, conseils=conseils, veto_id=user.id)
    db.session.add(r)
    db.session.flush()
    enregistrer(Action.REPONSE_VETO, table='alerte_sanitaire', enregistrement_id=alerte.id,
                detail=f'Alerte {alerte.numero} : réponse de {user.nom_complet} à l\'éleveur'
                       f' ({", ".join(conseils) or "message"}).')
    return r


def etat_eleveur(alerte):
    """Les mots de l'éleveur : jamais « confirmée » ni « infirmée »."""
    if alerte is None or alerte.statut == SA.NOUVELLE and not alerte.reponses:
        return 'envoye'
    if alerte.statut in (SA.CONFIRMEE, SA.INFIRMEE, SA.CLOSE):
        return 'termine'
    if alerte.reponses:
        return 'reponse'
    return 'regarde'


def _alertes_eleveur(user):
    from app.models import Ferme
    fermes = [f.id for f in filtre_perimetre(Ferme.query, utilisateur=user)]
    return AlerteSanitaire.query.filter(AlerteSanitaire.ferme_id.in_(fermes)) if fermes else \
        AlerteSanitaire.query.filter(db.false())


def signalements_eleveur(user):
    """Mes signalements : ses déclarations (avec l'alerte qui en découle), et les alertes du feu rouge
    de ses fermes qui ont reçu une réponse du vétérinaire. Du plus récent au plus ancien."""
    declarations = declarations_visibles(user).order_by(Declaration.cree_le.desc()).all()
    alertes = {a.declaration_id: a for a in AlerteSanitaire.query.filter(
        AlerteSanitaire.declaration_id.in_([d.id for d in declarations]))} if declarations else {}
    elements = [{'date': d.cree_le, 'declaration': d, 'alerte': alertes.get(d.id), 'bande': d.bande,
                 'etat': etat_eleveur(alertes.get(d.id))} for d in declarations]
    for a in _alertes_eleveur(user).filter(AlerteSanitaire.origine == OrigineAlerte.FEU_ROUGE):
        if a.reponses:
            elements.append({'date': a.cree_le, 'declaration': None, 'alerte': a, 'bande': a.bande,
                             'etat': etat_eleveur(a)})
    return sorted(elements, key=lambda e: e['date'], reverse=True)


def reponses_non_lues(user):
    from app.models.sante import ReponseVeterinaire
    ids = [a.id for a in _alertes_eleveur(user)]
    if not ids:
        return []
    return ReponseVeterinaire.query.filter(ReponseVeterinaire.alerte_id.in_(ids),
                                           ReponseVeterinaire.lue_le.is_(None)).all()

