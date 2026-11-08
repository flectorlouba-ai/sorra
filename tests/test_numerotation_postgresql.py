"""Numérotation sous accès simultanés : ne s'exécute que sur PostgreSQL
(TEST_DATABASE_URL=postgresql+psycopg2://…), ignoré sous SQLite."""
import threading

import pytest

from app import db
from app.services.numerotation import generer_numero


def test_numeros_uniques_en_parallele(app):
    if db.engine.dialect.name != 'postgresql':
        pytest.skip('test réservé à PostgreSQL')
    resultats, erreurs = [], []

    def travailleur():
        with app.app_context():
            try:
                for _ in range(25):
                    resultats.append(generer_numero('ESSAI', 'PAR'))
                    db.session.commit()
            except Exception as e:  # pragma: no cover
                erreurs.append(e)
            finally:
                db.session.remove()

    fils = [threading.Thread(target=travailleur) for _ in range(4)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    assert erreurs == []
    assert len(resultats) == 100 and len(set(resultats)) == 100
    assert sorted(resultats)[-1] == 'PAR-000100'
