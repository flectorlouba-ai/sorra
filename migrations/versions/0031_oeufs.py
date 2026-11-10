"""Lot F — suivi des œufs des bandes de ponte : œufs ramassés / cassés dans la saisie du jour, ventes d'œufs, paramètres
(œufs par plateau, seuil de chute de ponte — sensible, quatre yeux).

Revision ID: 0031
Revises: 0030
Create Date: 2026-11-10 16:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0031'
down_revision = '0030'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('ponte.oeufs_par_plateau', '30', 'ENTIER', "Nombre d'œufs par plateau (stock et ventes d'œufs)."),
    ('ponte.chute_pct', '15', 'ENTIER', "Baisse du taux de ponte (%, moyenne 7 jours contre les 7 jours précédents) qui déclenche l'alerte « chute de ponte »."),
]


def upgrade():
    bind = op.get_bind()
    with op.batch_alter_table('saisie_jour', schema=None) as batch_op:
        batch_op.add_column(sa.Column('oeufs_ramasses', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('oeufs_casses', sa.Integer(), nullable=True))
    op.create_table(
        'vente_oeufs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('numero_metier', sa.String(length=40), nullable=True),
        sa.Column('numero_provisoire', sa.Boolean(), nullable=False),
        sa.Column('appareil_id', sa.String(length=64), nullable=True),
        sa.Column('statut_synchro', sa.String(length=12), nullable=False),
        sa.Column('cree_par', sa.Uuid(), nullable=True),
        sa.Column('modifie_par', sa.Uuid(), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archive_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archive_par', sa.Uuid(), nullable=True),
        sa.Column('bande_id', sa.Uuid(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('oeufs', sa.Integer(), nullable=False),
        sa.Column('montant_fcfa', sa.Integer(), nullable=True),
        sa.Column('acheteur', sa.String(length=150), nullable=True),
        sa.Column('saisi_par_agent', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['bande_id'], ['bande.id'], name=op.f('fk_vente_oeufs_bande_id_bande')),
        sa.ForeignKeyConstraint(['cree_par'], ['utilisateur.id'], name=op.f('fk_vente_oeufs_cree_par_utilisateur')),
        sa.ForeignKeyConstraint(['modifie_par'], ['utilisateur.id'], name=op.f('fk_vente_oeufs_modifie_par_utilisateur')),
        sa.ForeignKeyConstraint(['archive_par'], ['utilisateur.id'], name=op.f('fk_vente_oeufs_archive_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_vente_oeufs')),
        sa.UniqueConstraint('numero_metier', name=op.f('uq_vente_oeufs_numero_metier')),
    )
    with op.batch_alter_table('vente_oeufs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_vente_oeufs_bande_id'), ['bande_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_vente_oeufs_date'), ['date'], unique=False)
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    with op.batch_alter_table('vente_oeufs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_vente_oeufs_date'))
        batch_op.drop_index(batch_op.f('ix_vente_oeufs_bande_id'))
    op.drop_table('vente_oeufs')
    with op.batch_alter_table('saisie_jour', schema=None) as batch_op:
        batch_op.drop_column('oeufs_casses')
        batch_op.drop_column('oeufs_ramasses')
