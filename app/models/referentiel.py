from app import db


# (code, nom) dans l'ordre officiel G1 → G9. Le code sert au numéro de ferme.
PROVINCES_GABON = [
    ('EST', 'Estuaire'),
    ('HOG', 'Haut-Ogooué'),
    ('MOG', 'Moyen-Ogooué'),
    ('NGO', 'Ngounié'),
    ('NYA', 'Nyanga'),
    ('OGI', 'Ogooué-Ivindo'),
    ('OGL', 'Ogooué-Lolo'),
    ('OGM', 'Ogooué-Maritime'),
    ('WNT', 'Woleu-Ntem'),
]


class Province(db.Model):
    __tablename__ = 'province'
    __perimetre__ = 'id'   # colonne utilisée par filtre_perimetre

    id     = db.Column(db.Integer, primary_key=True)
    code   = db.Column(db.String(10), unique=True, nullable=False)
    nom    = db.Column(db.String(80), unique=True, nullable=False)
    ordre  = db.Column(db.Integer, nullable=False, default=0)
    actif  = db.Column(db.Boolean, nullable=False, default=True)

    localites = db.relationship('Localite', back_populates='province',
                                order_by='Localite.nom', lazy='selectin')

    def __repr__(self):
        return f'<Province {self.code}>'


class Localite(db.Model):
    __tablename__ = 'localite'
    __perimetre__ = 'province_id'
    __table_args__ = (db.UniqueConstraint('province_id', 'nom'),)

    id          = db.Column(db.Integer, primary_key=True)
    province_id = db.Column(db.Integer, db.ForeignKey('province.id'), nullable=False, index=True)
    nom         = db.Column(db.String(120), nullable=False)
    actif       = db.Column(db.Boolean, nullable=False, default=True)
    # Saisie sur le terrain par un agent : l'administrateur la valide ou la fusionne
    a_verifier  = db.Column(db.Boolean, nullable=False, default=False,
                            server_default=db.false())

    province = db.relationship('Province', back_populates='localites')

    def __repr__(self):
        return f'<Localite {self.nom}>'
