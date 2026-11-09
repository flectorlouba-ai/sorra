"""Données fictives de la démonstration (sorra.performyl.com) : export depuis une base de démo locale, et
chargement dans la base de la démo, avec les dates décalées à aujourd'hui (les visites « d'aujourd'hui » et
les retards restent vrais). Le journal repart vide : sa chaîne d'empreintes est intacte."""
import json
from datetime import date, datetime, timedelta

import sqlalchemy as sa

# Jamais exportées : journal (repart vide), sessions, envois du téléphone, fichiers joints absents du serveur
EXCLUES = {'alembic_version', 'journal_audit', 'journal_chaine', 'session_utilisateur', 'envoi_hors_ligne',
           'declaration_photo', 'rapport_mensuel'}
# Fichiers joints : non copiés, la colonne est vidée
FICHIERS = {'declaration': ['audio'], 'visite': ['photo'], 'panne': ['photo'], 'livraison': ['photo_recu'],
            'depense': ['photo_recu']}


class RegleDemo(Exception):
    pass


def _tables(metadata):
    return [t for t in metadata.sorted_tables if t.name not in EXCLUES]


def exporter(connexion, metadata, reference=None):
    """{reference, tables: {nom: [lignes]}} — valeurs en texte JSON (dates ISO)."""
    import enum
    import decimal

    def texte(v):
        if isinstance(v, enum.Enum):
            return v.name
        if isinstance(v, decimal.Decimal):
            return float(v)
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        if hasattr(v, 'hex') and not isinstance(v, (bytes, str)):      # UUID
            return str(v)
        return v
    tables = {}
    for t in _tables(metadata):
        lignes = []
        for r in connexion.execute(sa.select(t)).mappings():
            ligne = {k: texte(v) for k, v in r.items()}
            for c in FICHIERS.get(t.name, []):
                ligne[c] = None
            if t.name == 'utilisateur':
                ligne.update(derniere_connexion=None, echecs_connexion=0, bloque_jusqu_a=None)
            lignes.append(ligne)
        tables[t.name] = lignes
    return {'reference': (reference or date.today()).isoformat(), 'tables': tables}


def _valeur(colonne, v, decalage):
    import uuid
    if v is None:
        return None
    type_ = colonne.type
    if isinstance(type_, sa.DateTime):
        d = datetime.fromisoformat(v)
        return d + decalage
    if isinstance(type_, sa.Date):
        return date.fromisoformat(v[:10]) + decalage
    if isinstance(type_, sa.Uuid):
        return uuid.UUID(v)
    return v


def charger(connexion, metadata, donnees, adresse_publique=None, aujourdhui=None):
    """Remplace TOUTES les données (sauf le journal, laissé vide) par les données fictives, dates décalées."""
    if connexion.execute(sa.text('SELECT count(*) FROM journal_audit')).scalar():
        raise RegleDemo('Le journal de cette base n’est pas vide : chargez seulement dans une base neuve '
                        '(remise à zéro de la démo).')
    decalage = (aujourdhui or date.today()) - date.fromisoformat(donnees['reference'])
    tables = _tables(metadata)
    for t in reversed(tables):                       # valeurs de départ posées par les migrations
        connexion.execute(t.delete())
    for t in tables:
        lignes = donnees['tables'].get(t.name, [])
        if lignes:
            connexion.execute(t.insert(), [{k: _valeur(t.c[k], v, decalage) for k, v in l.items() if k in t.c}
                                           for l in lignes])
    if connexion.dialect.name == 'postgresql':       # compteurs automatiques des clés entières
        for t in tables:
            for c in t.primary_key.columns:
                if isinstance(c.type, sa.Integer) and c.autoincrement is not False:
                    connexion.execute(sa.text(
                        f"SELECT setval(pg_get_serial_sequence('{t.name}', '{c.name}'), "
                        f"COALESCE((SELECT max({c.name}) FROM {t.name}), 0) + 1, false)"))
    if adresse_publique:
        connexion.execute(sa.text("UPDATE parametre SET valeur = :v WHERE cle = 'tracabilite.adresse_publique'"),
                          {'v': adresse_publique})
    return {t.name: len(donnees['tables'].get(t.name, [])) for t in tables}


def lire(chemin):
    with open(chemin, encoding='utf-8') as f:
        return json.load(f)
