"""Lot E-b — nouvelle ferme créée sans réseau : numéro de terrain provisoire (P-xxxx) gardé sur la ferme pour
rattacher les saisies envoyées après coup ; seuil du doublon « ferme tout près » ; raisons d'un « non ».

Revision ID: 0027
Revises: 0026
Create Date: 2026-11-11 05:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0027'
down_revision = '0026'
branch_labels = None
depends_on = None

LISTES = {'motifs_doublon': ['Voisin', 'Autre bâtiment', 'Autre exploitant', 'Autre']}
NOUVEAUX = [
    ('gps.doublon_m', '200', 'ENTIER',
     "Une ferme créée à moins de cette distance d'une autre est signalée comme doublon possible (mètres)."),
]


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('numero_terrain', sa.String(length=12), nullable=True))
        batch_op.create_unique_constraint(batch_op.f('uq_ferme_numero_terrain'), ['numero_terrain'])
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
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'motifs_doublon'")
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_ferme_numero_terrain'), type_='unique')
        batch_op.drop_column('numero_terrain')
