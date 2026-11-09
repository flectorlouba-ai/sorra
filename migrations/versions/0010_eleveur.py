"""Lot 8 — espace éleveur « illustré doux » : seuils des étoiles du bilan et conseil
affiché à l'éleveur au feu rouge (paramètres, à valider par les vétérinaires).

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None

PARAMETRES = [
    ('bandes.etoiles_mortalite_3_pct', '3', 'DECIMAL',
     "Bilan : 3 étoiles si la mortalité est au plus de ce % (et l'indice de consommation au plus du seuil). À valider par les vétérinaires."),
    ('bandes.etoiles_ic_3', '1.7', 'DECIMAL',
     'Bilan : indice de consommation maximal pour 3 étoiles. À valider par les vétérinaires.'),
    ('bandes.etoiles_mortalite_2_pct', '5', 'DECIMAL',
     'Bilan : 2 étoiles si la mortalité est au plus de ce % (sinon 1 étoile, jamais 0). À valider par les vétérinaires.'),
    ('sante.conseil_feu_rouge', "Isolez les poulets malades et ne vendez pas avant l'avis du vétérinaire.", 'TEXTE',
     "Conseil affiché à l'éleveur quand le feu de sa bande est rouge. À faire valider par les services vétérinaires."),
]


def upgrade():
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=ty, description=d) for c, v, ty, d in PARAMETRES])


def downgrade():
    op.execute("DELETE FROM parametre WHERE cle IN ('bandes.etoiles_mortalite_3_pct', 'bandes.etoiles_ic_3', "
               "'bandes.etoiles_mortalite_2_pct', 'sante.conseil_feu_rouge')")
