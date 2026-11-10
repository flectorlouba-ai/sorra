"""Lot P — code PIN du terrain (éleveur, agent, opérateur) : haché, échecs comptés, coupé après 5 échecs.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-10 18:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0034'
down_revision = '0033'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('utilisateur', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pin_hash', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('pin_echecs', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('utilisateur', schema=None) as batch_op:
        batch_op.drop_column('pin_echecs')
        batch_op.drop_column('pin_hash')
