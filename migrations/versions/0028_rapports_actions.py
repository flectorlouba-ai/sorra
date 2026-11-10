"""Lot D — rapports standards (ferme, agent, national / provincial, bilan de bande) et plans d'actions.
- rapport : tout PDF produit et gardé (type, période, cible, fichier) ; les rapports mensuels nationaux existants
  (rapport_mensuel) sont recopiés, l'ancienne table reste ;
- action : plan d'actions (origine, périmètre, responsable, échéance, priorité, avancement, clôture), archivable.

Revision ID: 0028
Revises: 0027
Create Date: 2026-11-11 07:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0028'
down_revision = '0027'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rapport',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=10), nullable=False),
        sa.Column('periode', sa.String(length=10), nullable=False),
        sa.Column('province_id', sa.Integer(), nullable=True),
        sa.Column('ferme_id', sa.Uuid(), nullable=True),
        sa.Column('agent_id', sa.Uuid(), nullable=True),
        sa.Column('bande_id', sa.Uuid(), nullable=True),
        sa.Column('fichier', sa.String(length=120), nullable=False),
        sa.Column('pages', sa.Integer(), nullable=True),
        sa.Column('genere_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('genere_par', sa.Uuid(), nullable=True),
        sa.Column('automatique', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(['province_id'], ['province.id'], name=op.f('fk_rapport_province_id_province')),
        sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_rapport_ferme_id_ferme')),
        sa.ForeignKeyConstraint(['agent_id'], ['utilisateur.id'], name=op.f('fk_rapport_agent_id_utilisateur')),
        sa.ForeignKeyConstraint(['bande_id'], ['bande.id'], name=op.f('fk_rapport_bande_id_bande')),
        sa.ForeignKeyConstraint(['genere_par'], ['utilisateur.id'], name=op.f('fk_rapport_genere_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rapport')),
    )
    with op.batch_alter_table('rapport', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rapport_type'), ['type'], unique=False)
        batch_op.create_index(batch_op.f('ix_rapport_ferme_id'), ['ferme_id'], unique=False)
    op.execute("INSERT INTO rapport (type, periode, fichier, genere_le, genere_par, automatique) "
               "SELECT 'NATIONAL', mois, fichier, genere_le, genere_par, true FROM rapport_mensuel")
    op.create_table(
        'action',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('numero', sa.String(length=20), nullable=False),
        sa.Column('intitule', sa.String(length=200), nullable=False),
        sa.Column('origine', sa.String(length=10), nullable=False),
        sa.Column('origine_table', sa.String(length=40), nullable=True),
        sa.Column('origine_id', sa.String(length=64), nullable=True),
        sa.Column('perimetre', sa.String(length=10), nullable=False),
        sa.Column('ferme_id', sa.Uuid(), nullable=True),
        sa.Column('province_id', sa.Integer(), nullable=True),
        sa.Column('responsable_id', sa.Uuid(), nullable=False),
        sa.Column('creee_par', sa.Uuid(), nullable=False),
        sa.Column('echeance', sa.Date(), nullable=False),
        sa.Column('priorite', sa.String(length=8), nullable=False),
        sa.Column('avancement', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('faite_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('commentaire', sa.String(length=1000), nullable=True),
        sa.Column('photo', sa.String(length=80), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archive_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archive_par', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_action_ferme_id_ferme')),
        sa.ForeignKeyConstraint(['province_id'], ['province.id'], name=op.f('fk_action_province_id_province')),
        sa.ForeignKeyConstraint(['responsable_id'], ['utilisateur.id'], name=op.f('fk_action_responsable_id_utilisateur')),
        sa.ForeignKeyConstraint(['creee_par'], ['utilisateur.id'], name=op.f('fk_action_creee_par_utilisateur')),
        sa.ForeignKeyConstraint(['archive_par'], ['utilisateur.id'], name=op.f('fk_action_archive_par_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_action')),
        sa.UniqueConstraint('numero', name=op.f('uq_action_numero')),
    )
    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_action_responsable_id'), ['responsable_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_action_ferme_id'), ['ferme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_action_echeance'), ['echeance'], unique=False)


def downgrade():
    with op.batch_alter_table('action', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_action_echeance'))
        batch_op.drop_index(batch_op.f('ix_action_ferme_id'))
        batch_op.drop_index(batch_op.f('ix_action_responsable_id'))
    op.drop_table('action')
    with op.batch_alter_table('rapport', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_rapport_ferme_id'))
        batch_op.drop_index(batch_op.f('ix_rapport_type'))
    op.drop_table('rapport')
