"""Lot 18 — écrans de la DGE : rapports mensuels gardés, pondérations du classement (quatre yeux),
e-mail des rapports préparé mais coupé. Le statut « Prévue » des livraisons ne change pas le schéma.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-09 12:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('classement.poids_mortalite', '35', 'ENTIER', 'Classement des fermes : poids de la mortalité. Quatre yeux.'),
    ('classement.poids_ic', '25', 'ENTIER', "Classement des fermes : poids de l'indice de consommation. Quatre yeux."),
    ('classement.poids_gmq', '20', 'ENTIER', 'Classement des fermes : poids de la croissance (GMQ). Quatre yeux.'),
    ('classement.poids_regularite', '20', 'ENTIER', 'Classement des fermes : poids de la régularité des saisies. Quatre yeux.'),
    ('rapports.email_destinataires', '', 'TEXTE',
     'Adresses qui recevront le rapport mensuel national (séparées par des virgules). Envoi coupé tant que '
     'rapports.email_actif vaut 0.'),
    ('rapports.email_actif', '0', 'BOOLEEN',
     "Envoi du rapport mensuel par e-mail (0 = coupé). Il faut aussi un serveur de messagerie configuré."),
]


def upgrade():
    op.create_table('rapport_mensuel',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('mois', sa.String(length=7), nullable=False),
    sa.Column('fichier', sa.String(length=80), nullable=False),
    sa.Column('genere_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('genere_par', sa.Uuid(), nullable=True),
    sa.Column('email_prepare_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('email_envoye_le', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['genere_par'], ['utilisateur.id'], name=op.f('fk_rapport_mensuel_genere_par_utilisateur')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rapport_mensuel')),
    sa.UniqueConstraint('mois', name=op.f('uq_rapport_mensuel_mois'))
    )
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in op.get_bind().execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])


def downgrade():
    op.execute("DELETE FROM parametre WHERE cle IN ('classement.poids_mortalite', 'classement.poids_ic', "
               "'classement.poids_gmq', 'classement.poids_regularite', 'rapports.email_destinataires', "
               "'rapports.email_actif')")
    op.drop_table('rapport_mensuel')
