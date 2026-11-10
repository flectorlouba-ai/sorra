"""Lot B — moteur d'imports : lots d'import annulables, lignes créées, correspondances de colonnes mémorisées.

Revision ID: 0032
Revises: 0031
Create Date: 2026-11-10 17:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0032'
down_revision = '0031'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'lot_import',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('modele', sa.String(length=30), nullable=False),
        sa.Column('fichier', sa.String(length=150), nullable=True),
        sa.Column('cree_par', sa.Uuid(), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('nb_lignes', sa.Integer(), nullable=False),
        sa.Column('nb_importees', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('rapport', sa.Text(), nullable=True),
        sa.Column('annule_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('annule_par', sa.Uuid(), nullable=True),
        sa.Column('motif_annulation', sa.String(length=300), nullable=True),
        sa.ForeignKeyConstraint(['cree_par'], ['utilisateur.id'], name=op.f('fk_lot_import_cree_par_utilisateur')),
        sa.ForeignKeyConstraint(['annule_par'], ['utilisateur.id'], name=op.f('fk_lot_import_annule_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_lot_import')),
    )
    with op.batch_alter_table('lot_import', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lot_import_modele'), ['modele'], unique=False)
    op.create_table(
        'ligne_import',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lot_id', sa.Integer(), nullable=False),
        sa.Column('table_nom', sa.String(length=60), nullable=False),
        sa.Column('enregistrement_id', sa.String(length=64), nullable=False),
        sa.Column('ligne', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['lot_id'], ['lot_import.id'], name=op.f('fk_ligne_import_lot_id_lot_import')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ligne_import')),
    )
    with op.batch_alter_table('ligne_import', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_ligne_import_lot_id'), ['lot_id'], unique=False)
    op.create_table(
        'correspondance_import',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('modele', sa.String(length=30), nullable=False),
        sa.Column('entete', sa.String(length=120), nullable=False),
        sa.Column('colonne', sa.String(length=60), nullable=False),
        sa.Column('cree_par', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['cree_par'], ['utilisateur.id'], name=op.f('fk_correspondance_import_cree_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_correspondance_import')),
        sa.UniqueConstraint('modele', 'entete', name=op.f('uq_correspondance_import_modele_entete')),
    )


def downgrade():
    op.drop_table('correspondance_import')
    with op.batch_alter_table('ligne_import', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_ligne_import_lot_id'))
    op.drop_table('ligne_import')
    with op.batch_alter_table('lot_import', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_lot_import_modele'))
    op.drop_table('lot_import')
