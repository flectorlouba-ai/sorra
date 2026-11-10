"""Lot A3 — programme POUFA, capacité, production, ponte.
- ferme : programme_poufa (oui pour les fermes existantes, issues de la liste POUFA), bandes_par_an (6) ;
- bande : type_production (CHAIR, PONTE), souche ;
- liste « Souches », paramètres de production (quatre yeux) et durée d'une bande de ponte.

Revision ID: 0025
Revises: 0024
Create Date: 2026-11-10 23:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None

LISTES = {'souches': ['Cobb 500', 'Ross 308', 'Arbor Acres', 'Hubbard', 'ISA Brown', 'Lohmann Brown']}
NOUVEAUX = [
    ('production.poids_sortie_kg', '2.1', 'DECIMAL',
     "Poids vif moyen d'un poulet de chair à la sortie (kg), pour la production théorique. Quatre yeux."),
    ('production.rendement_carcasse_pct', '75', 'DECIMAL',
     'Rendement carcasse (% du poids vif), pour l\'équivalent carcasse. Quatre yeux.'),
    ('production.objectif_national_t', '100000', 'ENTIER',
     'Objectif national de production de poulet de chair (tonnes de poids vif par an). Quatre yeux.'),
    ('production.bandes_par_an_defaut', '6', 'ENTIER', "Bandes par an proposées à la création d'une ferme."),
    ('bandes.duree_ponte_jours', '504', 'JOURS', "Durée prévue d'une bande de ponte (72 semaines)."),
]


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('programme_poufa', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('bandes_par_an', sa.Integer(), nullable=True, server_default='6'))
    with op.batch_alter_table('bande', schema=None) as batch_op:
        batch_op.add_column(sa.Column('type_production', sa.String(length=6), nullable=False, server_default='CHAIR'))
        batch_op.add_column(sa.Column('souche', sa.String(length=60), nullable=True))
    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'souches'")
    with op.batch_alter_table('bande', schema=None) as batch_op:
        batch_op.drop_column('souche')
        batch_op.drop_column('type_production')
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.drop_column('bandes_par_an')
        batch_op.drop_column('programme_poufa')
