"""Lot G / K4 — Mon argent sur 12 mois, mini bilan PDF et fiscalité estimée : seuils réglables (quatre yeux) et date du
rappel de déclaration.

Revision ID: 0030
Revises: 0029
Create Date: 2026-11-10 12:30:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0030'
down_revision = '0029'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('fiscalite.seuil_isl_fcfa', '30000000', 'ENTIER', "Chiffre d'affaires annuel (FCFA) en dessous duquel l'éleveur relève de l'impôt synthétique libératoire (estimation indicative, à valider avec la DGI)."),
    ('fiscalite.seuil_rsi_fcfa', '60000000', 'ENTIER', "Chiffre d'affaires annuel (FCFA) en dessous duquel l'éleveur relève du régime simplifié ; au-delà, régime réel (estimation indicative)."),
    ('fiscalite.rappel_declaration', '30/04', 'TEXTE', 'Date limite (JJ/MM) rappelée à l’éleveur pour sa déclaration annuelle.'),
]


def upgrade():
    bind = op.get_bind()
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
