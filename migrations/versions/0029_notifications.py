"""Lot T — notifications Web Push : abonnements des téléphones, préférences par type, journal des envois
(sans donnée personnelle) ; paramètres des rappels.

Revision ID: 0029
Revises: 0028
Create Date: 2026-11-11 09:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0029'
down_revision = '0028'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('notifications.rappel_saisie_heure', '18', 'ENTIER', "Heure par défaut du rappel « saisie du jour oubliée » (17, 18 ou 19)."),
    ('notifications.ferme_sans_saisie_jours', '2', 'JOURS', "L'agent est prévenu quand une ferme n'a rien saisi depuis ce nombre de jours."),
]


def upgrade():
    bind = op.get_bind()
    op.create_table(
        'abonnement_push',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
        sa.Column('appareil', sa.String(length=64), nullable=True),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.String(length=200), nullable=False),
        sa.Column('auth', sa.String(length=100), nullable=False),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('dernier_envoi_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], name=op.f('fk_abonnement_push_utilisateur_id_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_abonnement_push')),
    )
    with op.batch_alter_table('abonnement_push', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_abonnement_push_utilisateur_id'), ['utilisateur_id'], unique=False)
    op.create_table(
        'preference_notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('actif', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('heure', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], name=op.f('fk_preference_notification_utilisateur_id_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_preference_notification')),
        sa.UniqueConstraint('utilisateur_id', 'type', name=op.f('uq_preference_notification_utilisateur_id_type')),
    )
    op.create_table(
        'notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('utilisateur_id', sa.Uuid(), nullable=False),
        sa.Column('type', sa.String(length=30), nullable=False),
        sa.Column('cle', sa.String(length=120), nullable=False),
        sa.Column('titre', sa.String(length=80), nullable=False),
        sa.Column('texte', sa.String(length=200), nullable=False),
        sa.Column('lien', sa.String(length=200), nullable=True),
        sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('envoyee_le', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resultat', sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], name=op.f('fk_notification_utilisateur_id_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_notification')),
        sa.UniqueConstraint('utilisateur_id', 'cle', name=op.f('uq_notification_utilisateur_id_cle')),
    )
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notification_utilisateur_id'), ['utilisateur_id'], unique=False)
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    with op.batch_alter_table('notification', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_notification_utilisateur_id'))
    op.drop_table('notification')
    op.drop_table('preference_notification')
    with op.batch_alter_table('abonnement_push', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_abonnement_push_utilisateur_id'))
    op.drop_table('abonnement_push')
