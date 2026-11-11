"""Bandes « légères » pour les tableaux de bord (lot J, volume réel : 150 élevages, 12 mois, ~70 000 saisies).

Charger des milliers de bandes par l'ORM, avec leurs saisies, aliments, pesées et sorties, coûte une quinzaine de
secondes ; les mêmes lignes lues directement en SQL, une seconde. `charger(requete)` lit les seuls champs dont les
indicateurs ont besoin (colonnes de la bande, saisies non archivées avec leurs kg / sacs d'aliment, pesées, sorties)
et renvoie des objets qui se lisent comme une `Bande` : `indicateurs.calculer`, les séries hebdomadaires et le feu
donnent EXACTEMENT les mêmes chiffres. Tout autre attribut (ferme, bâtiment, poussins…) est lu sur la vraie bande,
chargée seulement à ce moment-là.
"""
from types import SimpleNamespace

from app import db
from app.models.bande import Bande, SaisieJour, SaisieAliment, Pesee, Sortie, StatutBande, TypeProduction


class BandeLegere:
    __slots__ = ('_cols', 'saisies', 'pesees', 'sorties', '_orm')

    def __init__(self, cols):
        self._cols, self.saisies, self.pesees, self.sorties, self._orm = cols, [], [], [], None

    def __getattr__(self, nom):
        cols = object.__getattribute__(self, '_cols')
        if nom in cols:
            return cols[nom]
        if object.__getattribute__(self, '_orm') is None:          # attribut rare : la vraie bande, une fois
            object.__setattr__(self, '_orm', db.session.get(Bande, cols['id']))
        return getattr(object.__getattribute__(self, '_orm'), nom)

    @property
    def sorties_comptees(self):
        return [s for s in self.sorties if not s.mise_de_cote]

    @property
    def numero(self):
        return self._cols['numero_metier']

    @property
    def ponte(self):
        return self._cols['type_production'] == TypeProduction.PONTE

    @property
    def en_cours(self):
        return self._cols['statut'] == StatutBande.EN_COURS

    def __repr__(self):
        return f'<BandeLegere {self._cols.get("numero_metier")}>'


def charger(requete):
    """`requete` : une requête sur Bande (filtres de périmètre, de dates…). Renvoie des BandeLegere, même ordre."""
    t = Bande.__table__
    sous = requete.with_entities(Bande.id).subquery()
    lignes = db.session.execute(db.select(*t.c).where(t.c.id.in_(db.select(sous.c.id)))).mappings().all()
    bandes = {r['id'].hex: BandeLegere(dict(r)) for r in lignes}
    if not bandes:
        return []
    ids = db.select(sous.c.id)

    def cle(colonne):                       # identifiant lu en texte : pas de conversion UUID ligne par ligne
        return db.cast(colonne, db.String)

    def norme(texte):
        return texte.replace('-', '').lower()
    for r in db.session.execute(db.select(cle(SaisieJour.bande_id).label('b'), SaisieJour.date, SaisieJour.morts,
                                          SaisieJour.oeufs_ramasses, SaisieJour.oeufs_casses,
                                          db.func.sum(SaisieAliment.sacs).label('sacs'), db.func.sum(SaisieAliment.kg).label('kg'))
                                .outerjoin(SaisieAliment, SaisieAliment.saisie_id == SaisieJour.id)
                                .where(SaisieJour.bande_id.in_(ids), SaisieJour.archive_le.is_(None))
                                .group_by(SaisieJour.id).order_by(SaisieJour.date)):
        bandes[norme(r.b)].saisies.append(SimpleNamespace(date=r.date, morts=r.morts, sacs=float(r.sacs or 0), kg=float(r.kg or 0),
                                                          oeufs_ramasses=r.oeufs_ramasses, oeufs_casses=r.oeufs_casses))
    for r in db.session.execute(db.select(cle(Pesee.bande_id).label('b'), Pesee.date, Pesee.nombre_pesees, Pesee.poids_total_kg,
                                          Pesee.poids_moyen_g, Pesee.poids_attendu_g)
                                .where(Pesee.bande_id.in_(ids), Pesee.archive_le.is_(None)).order_by(Pesee.date)):
        bandes[norme(r.b)].pesees.append(SimpleNamespace(date=r.date, nombre_pesees=r.nombre_pesees, poids_total_kg=r.poids_total_kg,
                                                         poids_moyen_g=r.poids_moyen_g, poids_attendu_g=r.poids_attendu_g))
    for r in db.session.execute(db.select(cle(Sortie.bande_id).label('b'), Sortie.id, Sortie.date, Sortie.motif, Sortie.nombre,
                                          Sortie.poids_total_kg, Sortie.montant_fcfa, Sortie.operateur_id, Sortie.destinataire_libre,
                                          Sortie.mise_de_cote)
                                .where(Sortie.bande_id.in_(ids), Sortie.archive_le.is_(None)).order_by(Sortie.date)):
        x = dict(r._mapping)
        bandes[norme(x.pop('b'))].sorties.append(SimpleNamespace(**x))
    ordre = [i for (i,) in requete.with_entities(Bande.id).all()]
    return [bandes[i.hex] for i in ordre if i.hex in bandes]
