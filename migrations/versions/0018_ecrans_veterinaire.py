"""Lot 17 — écrans du vétérinaire : diagnostics (contenu réservé), blocage des sorties d'une bande,
sortie reçue après un blocage (lien vers le blocage), liste des maladies suspectées.

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-09 11:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None

# Liste de départ, à faire valider par les vétérinaires (docs/a_faire_valider.md)
LISTES = {'maladies_suspectees': ['Newcastle', 'Gumboro', 'Bronchite infectieuse', 'Influenza aviaire',
                                  'Coccidiose', 'Colibacillose', 'Mycoplasmose', 'Salmonellose', 'Variole aviaire',
                                  'Autre']}


def upgrade():
    op.create_table('diagnostic',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('alerte_id', sa.Integer(), nullable=False),
    sa.Column('maladie', sa.String(length=150), nullable=False),
    sa.Column('prelevement', sa.Boolean(), nullable=False),
    sa.Column('observations', sa.String(length=1000), nullable=True),
    sa.Column('veto_id', sa.Uuid(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['alerte_id'], ['alerte_sanitaire.id'], name=op.f('fk_diagnostic_alerte_id_alerte_sanitaire')),
    sa.ForeignKeyConstraint(['veto_id'], ['utilisateur.id'], name=op.f('fk_diagnostic_veto_id_utilisateur')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_diagnostic'))
    )
    with op.batch_alter_table('diagnostic', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_diagnostic_alerte_id'), ['alerte_id'], unique=False)

    op.create_table('blocage_sorties',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('bande_id', sa.Uuid(), nullable=False),
    sa.Column('ferme_id', sa.Uuid(), nullable=False),
    sa.Column('alerte_id', sa.Integer(), nullable=True),
    sa.Column('motif', sa.String(length=300), nullable=False),
    sa.Column('pose_par', sa.Uuid(), nullable=False),
    sa.Column('leve_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('leve_par', sa.Uuid(), nullable=True),
    sa.Column('motif_levee', sa.String(length=300), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['alerte_id'], ['alerte_sanitaire.id'], name=op.f('fk_blocage_sorties_alerte_id_alerte_sanitaire')),
    sa.ForeignKeyConstraint(['bande_id'], ['bande.id'], name=op.f('fk_blocage_sorties_bande_id_bande')),
    sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_blocage_sorties_ferme_id_ferme')),
    sa.ForeignKeyConstraint(['leve_par'], ['utilisateur.id'], name=op.f('fk_blocage_sorties_leve_par_utilisateur')),
    sa.ForeignKeyConstraint(['pose_par'], ['utilisateur.id'], name=op.f('fk_blocage_sorties_pose_par_utilisateur')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_blocage_sorties'))
    )
    with op.batch_alter_table('blocage_sorties', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_blocage_sorties_bande_id'), ['bande_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_blocage_sorties_ferme_id'), ['ferme_id'], unique=False)

    with op.batch_alter_table('sortie', schema=None) as batch_op:
        batch_op.add_column(sa.Column('blocage_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_sortie_blocage_id_blocage_sorties'), 'blocage_sorties',
                                    ['blocage_id'], ['id'])

    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])


def downgrade():
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'maladies_suspectees'")
    with op.batch_alter_table('sortie', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_sortie_blocage_id_blocage_sorties'), type_='foreignkey')
        batch_op.drop_column('blocage_id')
    with op.batch_alter_table('blocage_sorties', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_blocage_sorties_ferme_id'))
        batch_op.drop_index(batch_op.f('ix_blocage_sorties_bande_id'))
    op.drop_table('blocage_sorties')
    with op.batch_alter_table('diagnostic', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_diagnostic_alerte_id'))
    op.drop_table('diagnostic')
