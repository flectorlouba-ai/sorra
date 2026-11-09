"""Barème des notes du classement et seuil « bande incomplète » en paramètres (quatre yeux) :
seuls les seuils des étoiles restaient en dehors du classement.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-09 13:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('classement.seuil_complet_pct', '80', 'ENTIER',
     'Classement : % de jours saisis en dessous duquel une bande est incomplète (ignorée). Quatre yeux.'),
    ('classement.mortalite_note_zero_pct', '10', 'DECIMAL',
     'Classement : mortalité (%) qui donne la note 0 (0 % donne 100). Quatre yeux.'),
    ('classement.ic_note_100', '1.4', 'DECIMAL',
     'Classement : indice de consommation qui donne la note 100. Quatre yeux.'),
    ('classement.ic_note_zero', '2.6', 'DECIMAL',
     'Classement : indice de consommation qui donne la note 0. Quatre yeux.'),
    ('classement.gmq_note_zero', '30', 'DECIMAL',
     'Classement : GMQ (g/j) qui donne la note 0. Quatre yeux.'),
    ('classement.gmq_note_100', '70', 'DECIMAL',
     'Classement : GMQ (g/j) qui donne la note 100. Quatre yeux.'),
]


def upgrade():
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in op.get_bind().execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
