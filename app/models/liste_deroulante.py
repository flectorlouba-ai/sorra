from app import db


class ListeDeroulante(db.Model):
    """Valeurs des listes configurables (repris de YL.1).
    Les catégories sont déclarées dans le code (`CATEGORIES`, routes/listes.py) ;
    l'administrateur gère seulement les valeurs. Une valeur ne se supprime pas,
    elle se désactive : des fiches pourront la référencer."""
    __tablename__ = 'liste_deroulante'
    __table_args__ = (db.UniqueConstraint('categorie', 'valeur'),)

    id        = db.Column(db.Integer, primary_key=True)
    categorie = db.Column(db.String(80), nullable=False, index=True)
    valeur    = db.Column(db.String(150), nullable=False)
    ordre     = db.Column(db.Integer, nullable=False, default=0)
    actif     = db.Column(db.Boolean, nullable=False, default=True)

    def __repr__(self):
        return f'<ListeDeroulante {self.categorie}: {self.valeur}>'


def ld_choices(categorie):
    """Valeurs actives d'une catégorie, dans l'ordre — pour remplir un <select>."""
    items = (ListeDeroulante.query
             .filter_by(categorie=categorie, actif=True)
             .order_by(ListeDeroulante.ordre, ListeDeroulante.id)
             .all())
    return [(v.valeur, v.valeur) for v in items]
