"""Lot A1 — ARCHIVER remplace SUPPRIMER : archive_le et archive_par sur les saisies et les fiches.
Reprise sans perte : les éléments déjà annulés (vaccination, dépense, entretien fait) ou désactivés (produit,
opérateur, bâtiment) sont recopiés comme archivés ; les anciennes colonnes restent.

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-10 08:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None

TABLES = ['bande', 'saisie_jour', 'pesee', 'sortie', 'declaration', 'vaccination', 'traitement', 'depense',
          'entretien_fait', 'panne', 'visite', 'produit', 'livraison', 'ferme', 'batiment', 'operateur']
# Reprise : (table, condition « déjà annulé ou désactivé », date à reprendre)
REPRISE = [('vaccination', 'annule', 'modifie_le'), ('depense', 'annule', 'modifie_le'),
           ('entretien_fait', 'annule', 'modifie_le'), ('produit', 'NOT actif', 'modifie_le'),
           ('operateur', 'NOT actif', 'modifie_le'), ('batiment', 'NOT actif', 'CURRENT_TIMESTAMP')]


def upgrade():
    for t in TABLES:
        with op.batch_alter_table(t, schema=None) as batch_op:
            batch_op.add_column(sa.Column('archive_le', sa.DateTime(timezone=True), nullable=True))
            batch_op.add_column(sa.Column('archive_par', sa.Uuid(), nullable=True))
            batch_op.create_foreign_key(batch_op.f(f'fk_{t}_archive_par_utilisateur'), 'utilisateur',
                                        ['archive_par'], ['id'])
    for t, condition, quand in REPRISE:
        op.execute(f'UPDATE {t} SET archive_le = {quand} WHERE {condition} AND archive_le IS NULL')


def downgrade():
    for t in reversed(TABLES):
        with op.batch_alter_table(t, schema=None) as batch_op:
            batch_op.drop_constraint(batch_op.f(f'fk_{t}_archive_par_utilisateur'), type_='foreignkey')
            batch_op.drop_column('archive_par')
            batch_op.drop_column('archive_le')
