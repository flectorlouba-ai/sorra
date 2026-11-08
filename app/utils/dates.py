"""Dates : stockées en UTC, affichées à l'heure du Gabon (UTC+1, sans heure d'été)."""
from datetime import datetime, time, timedelta, timezone

HEURE_GABON = timezone(timedelta(hours=1), 'WAT')


def en_utc(d):
    """SQLite rend des dates sans fuseau : elles sont en UTC."""
    if d is None:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def date_locale(d, format='%d/%m/%Y %H:%M'):
    if d is None:
        return ''
    return en_utc(d).astimezone(HEURE_GABON).strftime(format)


def debut_jour_utc(jour):
    """Minuit (heure du Gabon) du jour donné, exprimé en UTC."""
    return datetime.combine(jour, time.min, HEURE_GABON).astimezone(timezone.utc)
