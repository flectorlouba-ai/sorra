"""Lot 19 ter — espace terrain de l'agent et de l'opérateur : données seulement (aucune table modifiée).
Liste des motifs de vérification, téléphone de contact de la DGE, aides « Comment faire ? » de l'agent et de
l'opérateur (textes à faire valider, docs/a_faire_valider.md).

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-09 21:00:00

"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None

LISTES = {'motifs_verification': ['Recompté ensemble', 'Erreur de saisie', 'Autre']}
NOUVEAUX = [
    ('contact.telephone_dge', '', 'TEXTE',
     "Téléphone de contact de la DGE affiché aux agents (« 📞 Appeler la DGE »). Vide : celui du premier compte DGE "
     'actif qui a un téléphone ; aucun : rien ne s\'affiche.'),
]
# (clé, groupe, titre, [(texte, capture)]) — l'agent : ag_…, l'opérateur : op_… (3 étapes au plus)
AIDES = [
    ('ag_tournee', 'Agent : ma journée', 'Préparer ma tournée', [
        ('Ouvrez « Ma tournée » le matin, avec du réseau : elle reste lisible sans réseau.', ''),
        ('Les fermes sont dans l\'ordre : la plus urgente d\'abord, avec la raison.', ''),
        ('Touchez « 🧭 Y aller » pour avoir la route.', '')]),
    ('ag_saisir', 'Agent : ma journée', 'Saisir pour un éleveur', [
        ('Choisissez la ferme, puis le bâtiment.', ''),
        ('Touchez Jour, Pesée, Vaccin ou Sortie : ce sont les écrans de l\'éleveur.', ''),
        ('Envoyez : c\'est marqué « saisi par vous ».', 'envoyer')]),
    ('ag_visite', 'Agent : ma journée', 'Faire une visite', [
        ('Choisissez la ferme en haut de l\'écran.', ''),
        ('Dites pourquoi vous venez, ce que vous avez vu, et touchez vos conseils.', ''),
        ('Touchez « Envoyer le compte rendu » : l\'éleveur voit vos conseils.', '')]),
    ('ag_verifier', 'Agent : ma journée', 'Vérifier deux versions', [
        ('Comparez les deux chiffres : celui de l\'éleveur compte en attendant.', ''),
        ('Touchez la version à garder, puis la raison.', ''),
        ('Touchez « Valider » : c\'est inscrit au journal.', '')]),
    ('ag_stock', 'Agent : les fermes', 'Compter le stock', [
        ('Choisissez la ferme.', ''),
        ('Touchez « Compter » sur un produit et tapez ce qui reste.', ''),
        ('« Enregistrer » : SORRA dit s\'il manque des sacs.', 'enregistrer')]),
    ('ag_nouvel', 'Agent : les fermes', 'Inscrire un nouvel éleveur', [
        ('Choisissez sa ferme (une nouvelle ferme : avec du réseau seulement).', ''),
        ('La personne, la ferme, le compte : touchez « Suivant ».', ''),
        ('Notez l\'identifiant et le mot de passe provisoire : ils ne s\'affichent qu\'une fois.', '')]),
    ('op_recevoir', 'Recevoir les poulets', 'Recevoir un lot', [
        ('Touchez « Recevoir un lot » et mettez le QR dans le cadre jaune.', ''),
        ('Tapez les vivants, les morts (« 0 » s\'il n\'y en a pas) et le poids total.', ''),
        ('Touchez « Valider la réception ».', '')]),
    ('op_ecart', 'Recevoir les poulets', 'Il manque des poulets', [
        ('Tapez ce que vous avez vraiment compté.', ''),
        ('Touchez la raison : erreur de comptage, morts au transport, poulets échappés…', ''),
        ('« Valider avec cet écart » : l\'agent de la ferme est prévenu.', '')]),
    ('op_arrivent', 'Recevoir les poulets', 'Les lots qui arrivent', [
        ('La liste montre les lots envoyés chez vous par les fermes.', ''),
        ('Elle reste sur le téléphone, même sans réseau.', ''),
        ('Quand le camion arrive, touchez « Recevoir ».', '')]),
]


def upgrade():
    bind = op.get_bind()
    liste = sa.table('liste_deroulante', sa.column('categorie', sa.String), sa.column('valeur', sa.String),
                     sa.column('ordre', sa.Integer), sa.column('actif', sa.Boolean))
    op.bulk_insert(liste, [dict(categorie=c, valeur=v, ordre=i, actif=True)
                           for c, valeurs in LISTES.items() for i, v in enumerate(valeurs)])
    parametre = sa.table('parametre', sa.column('cle', sa.String), sa.column('valeur', sa.Text),
                         sa.column('type', sa.String), sa.column('description', sa.Text))
    existants = {r[0] for r in bind.execute(sa.text('SELECT cle FROM parametre'))}
    op.bulk_insert(parametre, [dict(cle=c, valeur=v, type=t, description=d) for c, v, t, d in NOUVEAUX
                               if c not in existants])
    aide = sa.table('aide', sa.column('cle', sa.String), sa.column('groupe', sa.String), sa.column('titre', sa.String),
                    sa.column('etapes', sa.JSON), sa.column('actif', sa.Boolean), sa.column('ordre', sa.Integer),
                    sa.column('cree_le', sa.DateTime), sa.column('modifie_le', sa.DateTime))
    maintenant = datetime.now(timezone.utc)
    deja = {r[0] for r in bind.execute(sa.text('SELECT cle FROM aide'))}
    op.bulk_insert(aide, [dict(cle=c, groupe=g, titre=t, etapes=[{'texte': x, 'capture': k} for x, k in e],
                               actif=True, ordre=100 + i, cree_le=maintenant, modifie_le=maintenant)
                          for i, (c, g, t, e) in enumerate(AIDES) if c not in deja])


def downgrade():
    for cle, *_ in AIDES:
        op.execute(sa.text('DELETE FROM aide WHERE cle = :c').bindparams(c=cle))
    for cle, *_ in NOUVEAUX:
        op.execute(sa.text('DELETE FROM parametre WHERE cle = :c').bindparams(c=cle))
    op.execute("DELETE FROM liste_deroulante WHERE categorie = 'motifs_verification'")
