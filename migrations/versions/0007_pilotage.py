"""Lot 5 — tableaux de bord : seuil de mortalité à l'arrivée des poussins (alerte DGE).
Les formules réglées par l'ADMIN sont rangées dans la table parametre (clés formule.*).

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None

PARAMETRES = [
    ('intrants.seuil_mortalite_arrivee_pct', '2', 'DECIMAL',
     "Alerte DGE : poussins morts à l'arrivée au-delà de ce % d'une livraison, à valider par les vétérinaires."),
]


def upgrade():
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=ty, description=d) for c, v, ty, d in PARAMETRES])


def downgrade():
    op.execute("DELETE FROM parametre WHERE cle = 'intrants.seuil_mortalite_arrivee_pct' OR cle LIKE 'formule.%'")
