"""Indicateurs d'élevage — TOUS les calculs sont ici, et nulle part ailleurs.

Les formules sont écrites comme des expressions (+ − × ÷, parenthèses, variables
nommées) et évaluées par un petit moteur sûr : l'arbre de l'expression est lu
nœud par nœud, sans eval ni exec. Seuils et coefficients viennent des Paramètres.
Un lot ultérieur rendra les formules modifiables par l'ADMIN (FORMULES ci-dessous
sert alors de « formule d'origine »).
"""
import ast
from datetime import date, timedelta

from app.services import parametres

# ── Moteur d'expressions sûr ────────────────────────────────────────────

_OPERATEURS = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b,
               ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}


class FormuleInvalide(ValueError):
    pass


def _verifier(noeud, autorisees):
    if isinstance(noeud, ast.Expression):
        return _verifier(noeud.body, autorisees)
    if isinstance(noeud, ast.BinOp) and type(noeud.op) in _OPERATEURS:
        _verifier(noeud.left, autorisees)
        _verifier(noeud.right, autorisees)
        return
    if isinstance(noeud, ast.UnaryOp) and isinstance(noeud.op, (ast.USub, ast.UAdd)):
        return _verifier(noeud.operand, autorisees)
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, (int, float)) \
            and not isinstance(noeud.value, bool):
        return
    if isinstance(noeud, ast.Name):
        if noeud.id not in autorisees:
            raise FormuleInvalide(f'Variable inconnue : « {noeud.id} ».')
        return
    raise FormuleInvalide('Seuls + − × ÷, les parenthèses, les nombres et les variables listées '
                          'sont permis.')


def analyser(expression, autorisees):
    """Arbre vérifié de l'expression ; lève FormuleInvalide."""
    texte = (expression or '').replace('×', '*').replace('÷', '/').replace('−', '-').replace(',', '.')
    if not texte.strip() or len(texte) > 300:
        raise FormuleInvalide('Formule vide ou trop longue.')
    try:
        arbre = ast.parse(texte, mode='eval')
    except SyntaxError:
        raise FormuleInvalide('Formule mal écrite (vérifiez les parenthèses et les opérateurs).')
    _verifier(arbre, autorisees)
    return arbre


def _calculer(noeud, valeurs):
    if isinstance(noeud, ast.Expression):
        return _calculer(noeud.body, valeurs)
    if isinstance(noeud, ast.BinOp):
        a, b = _calculer(noeud.left, valeurs), _calculer(noeud.right, valeurs)
        if a is None or b is None:
            return None
        if isinstance(noeud.op, ast.Div) and b == 0:
            return None
        return _OPERATEURS[type(noeud.op)](a, b)
    if isinstance(noeud, ast.UnaryOp):
        v = _calculer(noeud.operand, valeurs)
        return None if v is None else (-v if isinstance(noeud.op, ast.USub) else v)
    if isinstance(noeud, ast.Constant):
        return float(noeud.value)
    return valeurs.get(noeud.id)


def evaluer(expression, valeurs):
    """Valeur de l'expression (None si une donnée manque ou division par zéro)."""
    return _calculer(analyser(expression, set(valeurs)), valeurs)


# Variables de base, calculées à partir des saisies (affichées à l'écran des formules)
VARIABLES = {
    'mis_en_place': 'Poussins mis en place',
    'morts_cumules': 'Morts depuis la mise en place (y compris avant le suivi)',
    'sorties': 'Poulets sortis',
    'poids_sorties_kg': 'Poids total des sorties (kg)',
    'poids_initial_g': 'Poids moyen d\'un poussin à la mise en place (g)',
    'poids_moyen_g': 'Poids moyen à la dernière pesée (g)',
    'age_pesee': 'Âge de la bande le jour de la dernière pesée (jours)',
    'aliment_kg': 'Aliment consommé (kg)',
    'jours_saisis': 'Jours avec une saisie',
    'jours_ecoules': 'Jours écoulés depuis le début du suivi',
    'morts_jour': 'Morts du jour considéré',
    'effectif_avant_jour': 'Effectif présent avant les morts du jour considéré',
}

# Formules d'origine, évaluées dans cet ordre (chaque résultat devient une variable)
FORMULES = {
    'effectif_present': ('Effectif présent', 'mis_en_place - morts_cumules - sorties'),
    'mortalite': ('Mortalité (%)', 'morts_cumules / mis_en_place * 100'),
    'viabilite': ('Viabilité (%)', '100 - mortalite'),
    'gmq': ('Gain moyen quotidien (g/jour)', '(poids_moyen_g - poids_initial_g) / age_pesee'),
    'poids_vif_produit': ('Poids vif produit (kg)',
                          'poids_sorties_kg + effectif_present * poids_moyen_g / 1000'
                          ' - mis_en_place * poids_initial_g / 1000'),
    'indice_consommation': ('Indice de consommation', 'aliment_kg / poids_vif_produit'),
    'regularite': ('Régularité des saisies (%)', 'jours_saisis / jours_ecoules * 100'),
    'mortalite_jour': ('Mortalité du jour (% de l\'effectif présent)', 'morts_jour / effectif_avant_jour * 100'),
}


def formule(nom):
    """Formule en vigueur : celle réglée par l'ADMIN (Paramètres) ou celle d'origine."""
    reglee = parametres.obtenir(f'formule.{nom}')
    return reglee or FORMULES[nom][1]


def calculer_formules(base):
    valeurs = dict(base)
    for nom in FORMULES:
        try:
            valeurs[nom] = evaluer(formule(nom), valeurs)
        except FormuleInvalide:
            valeurs[nom] = evaluer(FORMULES[nom][1], valeurs)
    return valeurs


# ── Courbe de croissance attendue ───────────────────────────────────────

def lire_courbe(texte):
    """« 0:42; 7:180; … » → [(0, 42.0), (7, 180.0), …] trié. Lève ValueError."""
    points = []
    for morceau in (texte or '').replace(',', '.').split(';'):
        if not morceau.strip():
            continue
        try:
            age, poids = morceau.split(':')
            points.append((int(age), float(poids)))
        except ValueError:
            raise ValueError('Écrivez la courbe « âge:poids » séparés par des points-virgules, '
                             'par exemple « 0:42; 7:180; 14:450 ».')
    if len(points) < 2:
        raise ValueError('La courbe doit avoir au moins deux points.')
    return sorted(points)


def courbe():
    try:
        return lire_courbe(parametres.obtenir('bandes.courbe_poids', ''))
    except ValueError:
        return [(0, 42.0), (49, 3150.0)]


def poids_attendu(age):
    pts = courbe()
    if age <= pts[0][0]:
        return pts[0][1]
    for (a1, p1), (a2, p2) in zip(pts, pts[1:]):
        if a1 <= age <= a2:
            return p1 + (p2 - p1) * (age - a1) / (a2 - a1)
    (a1, p1), (a2, p2) = pts[-2], pts[-1]
    return p2 + (p2 - p1) * (age - a2) / (a2 - a1)


def dans_la_courbe(poids_moyen, age):
    tolerance = parametres.obtenir('bandes.ecart_courbe_pct', 10)
    return poids_moyen >= poids_attendu(age) * (1 - float(tolerance) / 100)


# ── Indicateurs d'une bande ─────────────────────────────────────────────

def age(bande, jour=None):
    return ((jour or date.today()) - bande.date_mise_en_place).days


def debut_suivi(bande):
    """Premier jour suivi dans l'application (la mise en place, ou l'ouverture d'un rattrapage)."""
    if bande.rattrapage and bande.cree_le:
        return max(bande.date_mise_en_place, bande.cree_le.date())
    return bande.date_mise_en_place


def saisie_du(bande, jour):
    return next((s for s in bande.saisies if s.date == jour), None)


def _jour_considere(bande, jour):
    return jour if saisie_du(bande, jour) else jour - timedelta(days=1)


def calculer(bande, jour=None):
    """Tous les indicateurs de la bande à la date `jour` (aujourd'hui par défaut)."""
    jour = jour or date.today()
    fin = bande.date_cloture or jour
    morts = bande.morts_avant_suivi + sum(s.morts for s in bande.saisies if s.date <= fin)
    sorties = [s for s in bande.sorties if s.date <= fin]
    pesees = [p for p in bande.pesees if p.date <= fin]
    derniere = pesees[-1] if pesees else None
    jc = _jour_considere(bande, min(jour, fin))
    morts_jour = (saisie_du(bande, jc).morts if saisie_du(bande, jc) else 0)
    jours_ecoules = max(1, (fin - debut_suivi(bande)).days + (1 if saisie_du(bande, fin) else 0))
    base = {
        'mis_en_place': bande.effectif_initial,
        'morts_cumules': morts,
        'sorties': sum(s.nombre for s in sorties),
        'poids_sorties_kg': sum(s.poids_total_kg for s in sorties),
        'poids_initial_g': bande.poids_initial_g,
        'poids_moyen_g': derniere.poids_moyen_g if derniere else None,
        'age_pesee': age(bande, derniere.date) if derniere else None,
        'aliment_kg': sum(s.kg for s in bande.saisies if s.date <= fin),
        'jours_saisis': len({s.date for s in bande.saisies if debut_suivi(bande) <= s.date <= fin}),
        'jours_ecoules': jours_ecoules,
        'morts_jour': morts_jour,
    }
    present = base['mis_en_place'] - base['morts_cumules'] - base['sorties']
    base['effectif_avant_jour'] = present + morts_jour
    v = calculer_formules(base)
    v['age'] = age(bande, min(jour, fin))
    v['jour_considere'] = jc
    v['derniere_pesee'] = derniere
    v['sacs'] = sum(s.sacs for s in bande.saisies if s.date <= fin)
    v['effectif_present'] = int(round(v['effectif_present'])) if v['effectif_present'] is not None else present
    v['partiels'] = bande.rattrapage
    return v


# ── Feu tricolore, phrases, « À faire aujourd'hui » ─────────────────────

def feu(bande, jour=None, valeurs=None):
    """(couleur, raison) : vert, orange, rouge ; gris sans bande en cours."""
    jour = jour or date.today()
    if not bande.en_cours:
        return 'gris', None
    v = valeurs or calculer(bande, jour)
    taux = v['mortalite_jour'] or 0
    if taux > float(parametres.obtenir('bandes.seuil_rouge_pct', 1)):
        return 'rouge', 'mortalite'
    if taux > float(parametres.obtenir('bandes.seuil_orange_pct', 0.5)):
        return 'orange', 'mortalite'
    hier = jour - timedelta(days=1)
    # Pas d'alerte « pas de saisie hier » le jour de la mise en place ni le lendemain
    if hier > debut_suivi(bande) and not saisie_du(bande, hier):
        return 'orange', 'saisie'
    return 'vert', None


def phrase(bande, couleur, raison, valeurs):
    if couleur == 'gris':
        return None
    if raison == 'mortalite':
        return 'Plus de morts que d\'habitude'
    if raison == 'saisie':
        return 'Vous n\'avez pas envoyé hier'
    p = valeurs['derniere_pesee']
    if p is not None:
        if dans_la_courbe(p.poids_moyen_g, age(bande, p.date)):
            return 'Vos poulets grossissent bien'
        return 'Vos poulets sont un peu légers'
    return 'Tout va bien aujourd\'hui'


def prochaine_pesee(bande):
    frequence = int(parametres.obtenir('bandes.frequence_pesee_jours', 7))
    depuis = bande.pesees[-1].date if bande.pesees else debut_suivi(bande)
    return depuis + timedelta(days=frequence)


def a_faire(bande, jour=None):
    """Liste de phrases pour l'encadré « À faire aujourd'hui »."""
    jour = jour or date.today()
    if not bande.en_cours:
        return []
    taches = []
    if not saisie_du(bande, jour):
        taches.append('Envoyez les morts et l\'aliment d\'aujourd\'hui')
    hier = jour - timedelta(days=1)
    if hier > debut_suivi(bande) and not saisie_du(bande, hier):
        taches.append('Hier n\'a pas été envoyé : utilisez « Oublié un jour ? »')
    if prochaine_pesee(bande) <= jour:
        n = parametres.obtenir('bandes.pesee_nombre_defaut', 10)
        taches.append(f'Peser {n} poulets')
    proche = int(parametres.obtenir('bandes.fin_proche_jours', 3))
    if 0 <= (bande.date_fin_prevue - jour).days <= proche:
        taches.append(f'Fin de bande prévue le {bande.date_fin_prevue.strftime("%d/%m")}')
    return taches


def encouragement(bande, valeurs, precedente=None):
    """Phrase tirée des propres chiffres de l'éleveur (la comparaison à la province
    viendra avec les tableaux de bord)."""
    js, je = valeurs['jours_saisis'], valeurs['jours_ecoules']
    if je >= 3 and js >= je:
        return f'{js} jours envoyés sur {je} : bravo !'
    if precedente and precedente.bilan and valeurs['mortalite'] is not None \
            and valeurs['mortalite'] < precedente.bilan.get('mortalite', 0):
        return (f'Mortalité {arrondi(valeurs["mortalite"], 1)} % : mieux que la bande précédente '
                f'({arrondi(precedente.bilan["mortalite"], 1)} %)')
    return None


# ── Bilan de clôture ────────────────────────────────────────────────────

def arrondi(v, n=1):
    return None if v is None else round(v, n)


def bilan(bande):
    """Bilan figé à la clôture (enregistré dans la bande)."""
    from app.services import ludique
    v = calculer(bande, bande.date_cloture)
    par_destinataire = {}
    for s in bande.sorties:
        d = par_destinataire.setdefault(s.destinataire, {'destinataire': s.destinataire, 'motif': s.motif,
                                                         'nombre': 0, 'poids_kg': 0})
        d['nombre'] += s.nombre
        d['poids_kg'] = round(d['poids_kg'] + s.poids_total_kg, 2)
    sortis = v['sorties']
    return {
        'duree_jours': (bande.date_cloture - bande.date_mise_en_place).days,
        'mis_en_place': bande.effectif_initial,
        'morts': v['morts_cumules'],
        'mortalite': arrondi(v['mortalite'], 2),
        'viabilite': arrondi(v['viabilite'], 2),
        'sortis': sortis,
        'poids_moyen_sortie_kg': arrondi(v['poids_sorties_kg'] / sortis, 3) if sortis else None,
        'gmq': arrondi(v['gmq'], 1),
        'indice_consommation': arrondi(v['indice_consommation'], 2),
        'poids_vif_produit_kg': arrondi(v['poids_vif_produit'], 1),
        'aliment_kg': arrondi(v['aliment_kg'], 1),
        'regularite': arrondi(v['regularite'], 0),
        'partiels': bande.rattrapage,
        'sorties_par_destinataire': list(par_destinataire.values()),
        # Lot 8 : étoiles gardées à la clôture, série record de la bande, poulets vendus
        'etoiles': ludique.etoiles(arrondi(v['mortalite'], 2), arrondi(v['indice_consommation'], 2)),
        'serie_record': ludique.plus_longue_serie(bande),
        'vendus': sum(s.nombre for s in bande.sorties if s.motif in ('Abattoir', 'Vente')),
    }


# ── Comparaisons et tableaux de bord (lot 5) ────────────────────────────

MIN_BANDES_COMPARAISON = 3


def moyenne_mortalite_province(province_id, jour=None):
    """Mortalité moyenne des bandes en cours de la province (pondérée par les mises en place),
    ou None s'il y a moins de 3 bandes en cours."""
    from app.models.bande import Bande, StatutBande
    from app.models.ferme import Ferme
    bandes = (Bande.query.join(Ferme, Bande.ferme_id == Ferme.id)
              .filter(Ferme.province_id == province_id, Bande.statut == StatutBande.EN_COURS).all())
    if len(bandes) < MIN_BANDES_COMPARAISON:
        return None
    morts = mis = 0
    for b in bandes:
        v = calculer(b, jour)
        morts += v['morts_cumules']
        mis += v['mis_en_place']
    return morts / mis * 100 if mis else None


def comparaison_province(bande, valeurs):
    """Phrase qui encourage : seulement si l'éleveur fait mieux que la moyenne ou s'y trouve."""
    moyenne = moyenne_mortalite_province(bande.ferme.province_id)
    m = valeurs.get('mortalite')
    if moyenne is None or m is None:
        return None
    nom = de_la_province(bande.ferme.province.nom)
    if m < moyenne * 0.9:
        return f'Votre mortalité ({arrondi(m, 1)} %) est meilleure que la moyenne {nom} ({arrondi(moyenne, 1)} %)'
    if m <= moyenne * 1.1:
        return f'Votre mortalité est dans la moyenne {nom} ({arrondi(moyenne, 1)} %)'
    return None


_ARTICLES = {'Estuaire': "de l'", 'Haut-Ogooué': 'du ', 'Moyen-Ogooué': 'du ', 'Ngounié': 'de la ',
             'Nyanga': 'de la ', 'Ogooué-Ivindo': "de l'", 'Ogooué-Lolo': "de l'",
             'Ogooué-Maritime': "de l'", 'Woleu-Ntem': 'du '}


def de_la_province(nom):
    """« de l'Estuaire », « du Haut-Ogooué », « de la Ngounié »."""
    return _ARTICLES.get(nom, 'de ') + nom


def mortalite_arrivee(ligne):
    """% de poussins morts à l'arrivée sur une ligne de livraison confirmée."""
    if not ligne.quantite_recue:
        return None
    return (ligne.morts_arrivee or 0) / ligne.quantite_recue * 100


def synthese(bandes, du=None, au=None):
    """Chiffres agrégés d'un ensemble de bandes ; sorties et aliment comptés sur la période."""
    from app.models.bande import StatutBande
    s = {'bandes_en_cours': 0, 'effectifs_presents': 0, 'mis_en_place': 0, 'morts': 0, 'poids_vif_kg': 0.0,
         'sortis_tetes': 0, 'sortis_kg': 0.0, 'aliment_kg': 0.0, 'regularites': [], 'feux': {'vert': 0, 'orange': 0, 'rouge': 0}}
    for b in bandes:
        v = calculer(b)
        if b.statut == StatutBande.EN_COURS:
            s['bandes_en_cours'] += 1
            s['effectifs_presents'] += v['effectif_present']
            if v['regularite'] is not None:
                s['regularites'].append(v['regularite'])
            couleur = feu(b, valeurs=v)[0]
            if couleur in s['feux']:
                s['feux'][couleur] += 1
        s['mis_en_place'] += v['mis_en_place']
        s['morts'] += v['morts_cumules']
        s['poids_vif_kg'] += v['poids_vif_produit'] or 0
        for o in b.sorties:
            if (du is None or o.date >= du) and (au is None or o.date <= au):
                s['sortis_tetes'] += o.nombre
                s['sortis_kg'] += o.poids_total_kg
        for j in b.saisies:
            if (du is None or j.date >= du) and (au is None or j.date <= au):
                s['aliment_kg'] += j.kg
    s['mortalite'] = s['morts'] / s['mis_en_place'] * 100 if s['mis_en_place'] else None
    s['regularite'] = sum(s['regularites']) / len(s['regularites']) if s['regularites'] else None
    return s
