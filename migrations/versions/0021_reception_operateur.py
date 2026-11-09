"""Lot 19 — opérateur (abattoir, marché) et traçabilité aval : comptes OPÉRATEUR rattachés à une fiche du
registre, réceptions (annoncé et reçu gardés tous les deux), scans, contrôles et seuils (quatre yeux),
motifs d'écart au quai, type d'opérateur « Marché ».

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-09 18:00:00

"""
from alembic import op
import sqlalchemy as sa


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None

NOUVEAUX = [
    ('reception.controle_delai_attente', 'TOUS', 'TEXTE',
     "Réception : aucun traitement en délai d'attente. TOUS, ABATTOIR, INFO ou NON. Quatre yeux."),
    ('reception.controle_vaccins', 'ABATTOIR', 'TEXTE',
     'Réception : vaccins obligatoires faits. TOUS, ABATTOIR, INFO ou NON. Quatre yeux.'),
    ('reception.controle_pesee', 'ABATTOIR', 'TEXTE',
     'Réception : pesée récente. TOUS, ABATTOIR, INFO ou NON. Quatre yeux.'),
    ('reception.pesee_max_jours', '7', 'JOURS',
     'Réception : la dernière pesée doit dater de moins de ce nombre de jours avant la sortie. Quatre yeux.'),
    ('reception.vaccin_tolerance_jours', '2', 'JOURS',
     'Réception : un vaccin en retard de moins de ce nombre de jours ne met pas le lot en réserve. Quatre yeux.'),
    ('reception.seuil_morts_pct', '2', 'DECIMAL',
     "Réception : morts à l'arrivée (% de l'annoncé) au-delà desquels le vétérinaire de la zone est alerté. "
     'Quatre yeux.'),
    ('reception.refus_alerte_nombre', '3', 'ENTIER',
     'Réception : nombre de refus du même QR (tous opérateurs) qui alerte la DGE. Quatre yeux.'),
    ('reception.refus_alerte_heures', '24', 'ENTIER',
     'Réception : période (heures) sur laquelle les refus du même QR sont comptés. Quatre yeux.'),
]
LISTES = {'motifs_ecart_quai': ['Erreur de comptage', 'Morts au transport', 'Poulets échappés', 'Autre']}
TYPE_MARCHE = 'Marché'


def upgrade():
    with op.batch_alter_table('utilisateur', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operateur_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(batch_op.f('fk_utilisateur_operateur_id_operateur'), 'operateur',
                                    ['operateur_id'], ['id'])
    op.create_table('reception',
    sa.Column('lot_id', sa.Integer(), nullable=True),
    sa.Column('ferme_id', sa.Uuid(), nullable=True),
    sa.Column('operateur_id', sa.Integer(), nullable=False),
    sa.Column('recu_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('lot_saisi', sa.String(length=60), nullable=True),
    sa.Column('annonce', sa.Integer(), nullable=True),
    sa.Column('annonce_kg', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=True),
    sa.Column('vivants', sa.Integer(), nullable=True),
    sa.Column('morts', sa.Integer(), nullable=True),
    sa.Column('poids_kg', sa.Numeric(precision=12, scale=2, asdecimal=False), nullable=True),
    sa.Column('etat', sa.String(length=14), nullable=False),
    sa.Column('motif_refus', sa.Text(), nullable=True),
    sa.Column('controles', sa.JSON(), nullable=True),
    sa.Column('motif_ecart', sa.String(length=150), nullable=True),
    sa.Column('explication', sa.Text(), nullable=True),
    sa.Column('hors_ligne', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('vu_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_par', sa.Uuid(), nullable=True),
    sa.Column('decision_le', sa.DateTime(timezone=True), nullable=True),
    sa.Column('decision_motif', sa.Text(), nullable=True),
    sa.Column('cree_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modifie_le', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('numero_metier', sa.String(length=40), nullable=True),
    sa.Column('numero_provisoire', sa.Boolean(), nullable=False),
    sa.Column('appareil_id', sa.String(length=64), nullable=True),
    sa.Column('statut_synchro', sa.Enum('LOCAL', 'SYNCHRONISE', 'CONFLIT', name='statutsynchro', native_enum=False, length=12), nullable=False),
    sa.Column('cree_par', sa.Uuid(), nullable=True),
    sa.Column('modifie_par', sa.Uuid(), nullable=True),
    sa.ForeignKeyConstraint(['cree_par'], ['utilisateur.id'], name=op.f('fk_reception_cree_par_utilisateur')),
    sa.ForeignKeyConstraint(['decision_par'], ['utilisateur.id'], name=op.f('fk_reception_decision_par_utilisateur')),
    sa.ForeignKeyConstraint(['ferme_id'], ['ferme.id'], name=op.f('fk_reception_ferme_id_ferme')),
    sa.ForeignKeyConstraint(['lot_id'], ['lot_trace.id'], name=op.f('fk_reception_lot_id_lot_trace')),
    sa.ForeignKeyConstraint(['modifie_par'], ['utilisateur.id'], name=op.f('fk_reception_modifie_par_utilisateur')),
    sa.ForeignKeyConstraint(['operateur_id'], ['operateur.id'], name=op.f('fk_reception_operateur_id_operateur')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reception')),
    sa.UniqueConstraint('numero_metier', name=op.f('uq_reception_numero_metier'))
    )
    with op.batch_alter_table('reception', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_reception_etat'), ['etat'], unique=False)
        batch_op.create_index(batch_op.f('ix_reception_ferme_id'), ['ferme_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reception_lot_id'), ['lot_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_reception_operateur_id'), ['operateur_id'], unique=False)

    op.create_table('scan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('horodatage', sa.DateTime(timezone=True), nullable=False),
    sa.Column('utilisateur_id', sa.Uuid(), nullable=True),
    sa.Column('operateur_id', sa.Integer(), nullable=True),
    sa.Column('lot_id', sa.Integer(), nullable=True),
    sa.Column('empreinte', sa.String(length=16), nullable=False),
    sa.Column('saisie', sa.String(length=60), nullable=True),
    sa.Column('source', sa.String(length=12), nullable=False),
    sa.Column('resultat', sa.String(length=6), nullable=False),
    sa.Column('motif', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['lot_id'], ['lot_trace.id'], name=op.f('fk_scan_lot_id_lot_trace')),
    sa.ForeignKeyConstraint(['operateur_id'], ['operateur.id'], name=op.f('fk_scan_operateur_id_operateur')),
    sa.ForeignKeyConstraint(['utilisateur_id'], ['utilisateur.id'], name=op.f('fk_scan_utilisateur_id_utilisateur')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_scan'))
    )
    with op.batch_alter_table('scan', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_scan_empreinte'), ['empreinte'], unique=False)
        batch_op.create_index(batch_op.f('ix_scan_horodatage'), ['horodatage'], unique=False)
        batch_op.create_index(batch_op.f('ix_scan_lot_id'), ['lot_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_scan_operateur_id'), ['operateur_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_scan_resultat'), ['resultat'], unique=False)

    bind = op.get_bind()
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])
    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])
    deja = bind.execute(sa.text("SELECT count(*) FROM liste_deroulante WHERE categorie = 'types_operateurs' "
                                "AND valeur = :v").bindparams(v=TYPE_MARCHE)).scalar()
    if not deja:
        ordre = bind.execute(sa.text("SELECT coalesce(max(ordre), -1) + 1 FROM liste_deroulante "
                                     "WHERE categorie = 'types_operateurs'")).scalar()
        op.bulk_insert(liste, [dict(categorie='types_operateurs', valeur=TYPE_MARCHE, ordre=ordre, actif=True)])


def downgrade():
    op.execute(sa.text("DELETE FROM liste_deroulante WHERE categorie = 'types_operateurs' AND valeur = :v")
               .bindparams(v=TYPE_MARCHE))
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'motifs_ecart_quai'")
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    with op.batch_alter_table('scan', schema=None) as batch_op:
        for ix in ('resultat', 'operateur_id', 'lot_id', 'horodatage', 'empreinte'):
            batch_op.drop_index(batch_op.f(f'ix_scan_{ix}'))
    op.drop_table('scan')
    with op.batch_alter_table('reception', schema=None) as batch_op:
        for ix in ('operateur_id', 'lot_id', 'ferme_id', 'etat'):
            batch_op.drop_index(batch_op.f(f'ix_reception_{ix}'))
    op.drop_table('reception')
    with op.batch_alter_table('utilisateur', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_utilisateur_operateur_id_operateur'), type_='foreignkey')
        batch_op.drop_column('operateur_id')
