"""Lot M — diffusion des rapports : soumission par la DGE au visa du MAEDR, validation ou refus (motif).

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-10 17:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0033'
down_revision = '0032'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('rapport', schema=None) as batch_op:
        batch_op.add_column(sa.Column('diffusion', sa.String(length=12), nullable=True))        # SOUMIS, VALIDE, REFUSE
        batch_op.add_column(sa.Column('soumis_le', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('soumis_par', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('vise_le', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('vise_par', sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column('motif_visa', sa.String(length=300), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_rapport_soumis_par_utilisateur'), 'utilisateur', ['soumis_par'], ['id'])
        batch_op.create_foreign_key(batch_op.f('fk_rapport_vise_par_utilisateur'), 'utilisateur', ['vise_par'], ['id'])


def downgrade():
    with op.batch_alter_table('rapport', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_rapport_vise_par_utilisateur'), type_='foreignkey')
        batch_op.drop_constraint(batch_op.f('fk_rapport_soumis_par_utilisateur'), type_='foreignkey')
        for c in ('motif_visa', 'vise_par', 'vise_le', 'soumis_par', 'soumis_le', 'diffusion'):
            batch_op.drop_column(c)
