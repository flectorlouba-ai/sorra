"""Lot E (partie a) — positions des fermes et contrôle des visites.
- position_ferme : historique de toutes les positions (aucune n'est écrasée), avec leur origine ;
- ferme.position_a_verifier ; visite : précision, distance à la ferme (serveur), motif d'une visite éloignée ;
- reprise : chaque position déjà connue devient une ligne d'historique d'origine REPRISE ;
- paramètres : précision exigée, distance d'une visite, correction à la main sous quatre yeux.

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-11 01:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None

LISTES = {'motifs_position': ['Bâtiment loin de la route', 'Province mal notée sur la fiche', 'GPS du téléphone imprécis',
                              'Ferme à la limite de deux provinces', 'Autre'],
          'motifs_visite_eloignee': ['Rencontre au village', 'Route coupée', 'Éleveur absent, appel téléphonique',
                                     'Position de la ferme à corriger', 'Autre']}
NOUVEAUX = [
    ('gps.precision_max_m', '30', 'ENTIER', 'Précision exigée pour garder une position relevée (mètres).'),
    ('gps.distance_visite_km', '1', 'DECIMAL', "Au-delà de cette distance de la ferme, la visite demande une explication (km)."),
    ('gps.correction_quatre_yeux_km', '1', 'DECIMAL',
     'Une position corrigée à la main de plus de cette distance passe par les quatre yeux (km).'),
]


def upgrade():
    bind = op.get_bind()
    op.create_table(
        'position_ferme',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ferme_id', sa.Uuid(), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('precision_m', sa.Integer(), nullable=True),
        sa.Column('releve_le', sa.DateTime(timezone=True), nullable=False),
        sa.Column('auteur_id', sa.Uuid(), nullable=True),
        sa.Column('appareil', sa.String(length=64), nullable=True),
        sa.Column('hors_ligne', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('origine', sa.String(length=10), nullable=False),
        sa.Column('motif', sa.String(length=300), nullable=True),
        sa.Column('province_trouvee', sa.String(length=5), nullable=True),
        sa.Column('distance_province_km', sa.Integer(), nullable=True),
        sa.Column('a_verifier', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('en_vigueur', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_position_ferme_ferme_id_ferme')),
        sa.ForeignKeyConstraint(['auteur_id'], ['utilisateur.id'], name=op.f('fk_position_ferme_auteur_id_utilisateur')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_position_ferme')),
    )
    with op.batch_alter_table('position_ferme', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_position_ferme_ferme_id'), ['ferme_id'], unique=False)
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position_a_verifier', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.add_column(sa.Column('precision_m', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('distance_m', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('motif_distance', sa.String(length=300), nullable=True))
    op.execute("INSERT INTO position_ferme (ferme_id, latitude, longitude, precision_m, releve_le, origine, hors_ligne, "
               "a_verifier, en_vigueur) SELECT id, latitude, longitude, gps_precision_m, "
               "COALESCE(gps_date, modifie_le), 'REPRISE', false, false, true FROM ferme "
               "WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])


def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    op.execute("DELETE FROM liste_deroulante WHERE categorie IN ('motifs_position', 'motifs_visite_eloignee')")
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.drop_column('motif_distance')
        batch_op.drop_column('distance_m')
        batch_op.drop_column('precision_m')
    with op.batch_alter_table('ferme', schema=None) as batch_op:
        batch_op.drop_column('position_a_verifier')
    with op.batch_alter_table('position_ferme', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_position_ferme_ferme_id'))
    op.drop_table('position_ferme')
