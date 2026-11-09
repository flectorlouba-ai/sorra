"""Lot 16 — écrans de l'agent : commandes d'intrants, inventaires de stock, biosécurité (grille,
score et mesures correctives dans la visite), seuil d'écart de stock (quatre yeux).

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-09 11:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None

# Grille de départ, à faire valider par les vétérinaires (docs/a_faire_valider.md)
GRILLE = ['Pédiluve à l\'entrée, propre et rempli', 'Clôture fermée, pas d\'animaux errants',
          'Tenue réservée au bâtiment (bottes, blouse)', 'Lavage des mains à l\'entrée',
          'Registre des visiteurs tenu', 'Morts ramassés chaque jour et éliminés (fosse, incinération)',
          'Litière sèche', 'Abreuvoirs et mangeoires propres', 'Aliment stocké au sec, sur palette',
          'Vide sanitaire respecté entre deux bandes']
LISTES = {'grille_biosecurite': GRILLE}
NOUVEAUX = [
    ('intrants.seuil_ecart_stock_pct', '10', 'ENTIER',
     'Écart de stock (livré − utilisé − compté) au-delà duquel la ferme passe en orange chez l\'agent, en % du livré. '
     'Quatre yeux.'),
]


def upgrade():
    op.create_table('commande_intrant',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ferme_id', sa.Uuid(), nullable=False),
    sa.Column('produit_id', sa.Integer(), nullable=False),
    sa.Column('quantite', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=False),
    sa.Column('motif', sa.String(length=300), nullable=True),
    sa.Column('statut', sa.String(length=10), nullable=False),
    sa.Column('demandee_par', sa.Uuid(), nullable=False),
    sa.Column('decidee_par', sa.Uuid(), nullable=True),
    sa.Column('decidee_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('motif_refus', sa.String(length=300), nullable=True),
    sa.Column('refus_lu_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('livraison_id', sa.Uuid(), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['decidee_par'], ['utilisateur.id'], name=op.f('fk_commande_intrant_decidee_par_utilisateur')),
    sa.ForeignKeyConstraint(['demandee_par'], ['utilisateur.id'], name=op.f('fk_commande_intrant_demandee_par_utilisateur')),
    sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_commande_intrant_ferme_id_ferme')),
    sa.ForeignKeyConstraint(['livraison_id'], ['livraison.id'], name=op.f('fk_commande_intrant_livraison_id_livraison')),
    sa.ForeignKeyConstraint(['produit_id'], ['produit.id'], name=op.f('fk_commande_intrant_produit_id_produit')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_commande_intrant'))
    )
    with op.batch_alter_table('commande_intrant', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_commande_intrant_ferme_id'), ['ferme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_commande_intrant_statut'), ['statut'], unique=False)

    op.create_table('inventaire_stock',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('ferme_id', sa.Uuid(), nullable=False),
    sa.Column('produit_id', sa.Integer(), nullable=False),
    sa.Column('jour', sa.Date(), nullable=False),
    sa.Column('livre', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=False),
    sa.Column('utilise', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=False),
    sa.Column('compte', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=False),
    sa.Column('agent_id', sa.Uuid(), nullable=False),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['utilisateur.id'], name=op.f('fk_inventaire_stock_agent_id_utilisateur')),
    sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_inventaire_stock_ferme_id_ferme')),
    sa.ForeignKeyConstraint(['produit_id'], ['produit.id'], name=op.f('fk_inventaire_stock_produit_id_produit')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_inventaire_stock'))
    )
    with op.batch_alter_table('inventaire_stock', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inventaire_stock_ferme_id'), ['ferme_id'], unique=False)

    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.add_column(sa.Column('biosecurite', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('score_biosecurite', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('mesures_correctives', sa.JSON(), nullable=True))

    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in op.get_bind().execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])

def downgrade():
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'grille_biosecurite'")
    with op.batch_alter_table('visite', schema=None) as batch_op:
        batch_op.drop_column('mesures_correctives')
        batch_op.drop_column('score_biosecurite')
        batch_op.drop_column('biosecurite')
    with op.batch_alter_table('inventaire_stock', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inventaire_stock_ferme_id'))
    op.drop_table('inventaire_stock')
    with op.batch_alter_table('commande_intrant', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_commande_intrant_statut'))
        batch_op.drop_index(batch_op.f('ix_commande_intrant_ferme_id'))
    op.drop_table('commande_intrant')
