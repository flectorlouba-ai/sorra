"""Empreinte SHA-256 d'une entrée du journal (lot 15). Fonction unique, utilisée par l'application,
par la migration 0016 (chaînage de l'existant) et par l'écran « Intégrité ». Ne pas la modifier :
toute la chaîne existante en dépend."""
import hashlib
import json
from datetime import datetime, timezone

GENESE = '0' * 64
CHAMPS = ('id', 'horodatage', 'utilisateur_id', 'identifiant', 'adresse_ip', 'action', 'table_nom',
          'enregistrement_id', 'avant', 'apres', 'detail')


def _normal(valeur):
    if isinstance(valeur, datetime):
        if valeur.tzinfo is None:
            valeur = valeur.replace(tzinfo=timezone.utc)
        return valeur.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f')
    if isinstance(valeur, str) and valeur[:1] in '[{':
        try:
            return json.loads(valeur)            # JSON relu comme texte (selon la base)
        except ValueError:
            return valeur
    return valeur


def empreinte(precedente, ligne):
    """`ligne` : correspondance des colonnes de journal_audit (objet Row ou dict)."""
    contenu = {c: _normal(ligne[c]) for c in CHAMPS}
    contenu['utilisateur_id'] = str(contenu['utilisateur_id']).replace('-', '') if contenu['utilisateur_id'] else None
    texte = json.dumps(contenu, sort_keys=True, ensure_ascii=False, default=str, separators=(',', ':'))
    return hashlib.sha256((precedente + texte).encode('utf-8')).hexdigest()
