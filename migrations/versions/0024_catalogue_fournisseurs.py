"""Lot A2 — catalogue des intrants et fournisseurs : table fournisseur ; l'article (produit) reçoit une
référence, un fournisseur et un conditionnement ; l'inventaire garde le stock Externe théorique (écart sur le
Programme seulement). Reprise sans perte : les valeurs de la liste « Fournisseurs » deviennent des fournisseurs
(type « Autre »), la liste reste ; aucune donnée existante n'est modifiée.

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-10 22:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'fournisseur',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nom', sa.String(length=150), nullable=False),
        sa.Column('telephone', sa.String(length=30), nullable=True),
        sa.Column('ville', sa.String(length=80), nullable=True),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False),
        sa.Column('archive_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archive_par', sa.Uuid(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['archive_par'], ['utilisateur.id'], name=op.f('fk_fournisseur_archive_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_fournisseur')),
        sa.UniqueConstraint('nom', name=op.f('uq_fournisseur_nom')),
    )
    with op.batch_alter_table('produit', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('fournisseur_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('conditionnement', sa.String(length=60), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_produit_fournisseur_id_fournisseur'), 'fournisseur',
                                    ['fournisseur_id'], ['id'])
    op.execute("INSERT INTO fournisseur (nom, type, actif, cree_le, modifie_le) "
               "SELECT valeur, 'Autre', actif, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP FROM liste_deroulante "
               "WHERE categorie = 'fournisseurs'")
    op.execute("UPDATE fournisseur SET archive_le = CURRENT_TIMESTAMP WHERE NOT actif")
    with op.batch_alter_table('inventaire_stock', schema=None) as batch_op:
        batch_op.add_column(sa.Column('externe', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=True))


def downgrade():
    with op.batch_alter_table('inventaire_stock', schema=None) as batch_op:
        batch_op.drop_column('externe')
    with op.batch_alter_table('produit', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_produit_fournisseur_id_fournisseur'), type_='foreignkey')
        batch_op.drop_column('conditionnement')
        batch_op.drop_column('fournisseur_id')
        batch_op.drop_column('reference')
    op.drop_table('fournisseur')
