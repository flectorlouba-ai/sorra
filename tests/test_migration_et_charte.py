"""La migration crée bien la base (et ses protections) ; la charte reste celle de YL.1."""
import os
import re
import sqlite3
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
GABARITS = RACINE / 'app' / 'templates'
CSS = RACINE / 'app' / 'static' / 'css' / 'perform.css'


def test_migration_sur_base_vide(tmp_path, monkeypatch):
    from alembic.config import Config
    from alembic import command
    from app import create_app

    base = tmp_path / 'essai.db'
    monkeypatch.setenv('TEST_DATABASE_URL', f'sqlite:///{base}')
    import config as module_config
    monkeypatch.setattr(module_config.TestingConfig, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{base}')
    app = create_app('testing')
    with app.app_context():
        from flask_migrate import upgrade
        upgrade(directory=str(RACINE / 'migrations'))
    c = sqlite3.connect(base)
    codes = [r[0] for r in c.execute('select code from province order by ordre')]
    assert codes == ['EST', 'HOG', 'MOG', 'NGO', 'NYA', 'OGI', 'OGL', 'OGM', 'WNT']
    assert c.execute('select count(*) from parametre').fetchone()[0] == 4
    c.execute("insert into journal_audit (horodatage, action) values ('2026-01-01', 'EXPORT')")
    c.commit()
    for ordre in ("update journal_audit set action='X'", 'delete from journal_audit'):
        with pytest.raises(sqlite3.DatabaseError, match='lecture seule'):
            c.execute(ordre)
    c.close()


def test_modeles_et_migration_concordent(tmp_path, monkeypatch):
    """Aucune différence entre les modèles et la migration (hors table d'essai des tests)."""
    from alembic.migration import MigrationContext
    from alembic.autogenerate import compare_metadata
    from app import create_app, db
    import config as module_config

    base = tmp_path / 'compare.db'
    monkeypatch.setattr(module_config.TestingConfig, 'SQLALCHEMY_DATABASE_URI', f'sqlite:///{base}')
    app = create_app('testing')
    with app.app_context():
        from flask_migrate import upgrade
        upgrade(directory=str(RACINE / 'migrations'))
        with db.engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
    diff = [d for d in diff if 'essai_saisie' not in str(d)]
    assert diff == []


def test_aucun_cdn():
    for f in list(GABARITS.rglob('*.html')) + [CSS]:
        texte = f.read_text(encoding='utf-8')
        assert not re.search(r'(src|href)="https?://', texte), f
        assert '@import url(http' not in texte, f


def test_couleurs_uniquement_dans_root():
    texte = CSS.read_text(encoding='utf-8')
    debut = texte.index(':root{')
    fin = texte.index('}', debut)
    hors_root = texte[:debut] + texte[fin:]
    assert re.findall(r'#[0-9a-fA-F]{3,6}\b', hors_root) == []
    for f in GABARITS.rglob('*.html'):
        assert re.findall(r'#[0-9a-fA-F]{3,6}\b', f.read_text(encoding='utf-8')) == [], f


def test_valeurs_couleurs_de_yl1():
    """Chaque couleur de :root existait dans YL.1 (relevé de l'étape 1)."""
    yl1 = {'#0c2461', '#0d2d7a', '#1241a8', '#333', '#555', '#888', '#bbb', '#eee', '#f0f5ff',
           '#fff', '#15803d', '#b91c1c', '#d97706', '#ddd', '#ccc', '#0d3ecf', '#1a56db', '#2563eb',
           '#3b82f6', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff', '#6b93c8', '#071640', '#1e40af',
           '#f59e0b', '#1a1100', '#dc2626', '#fca5a5', '#fef2f2', '#94a3b8', '#f0f0f0', '#f9f0f0',
           '#8b0000', '#faf8f0', '#5a4000', '#a07800', '#f0f4f8', '#fde8e8', '#d8a0a0', '#e8f5e8',
           '#2a6a2a', '#b0d8b0', '#fff3e0', '#7a4800', '#f0c080', '#e0eaff', '#1a3a8a', '#a0bce8',
           '#c0392b', '#e8b0a8', '#a00', '#d0daf0', '#c0c8e0', '#1a5a1a', '#90c890'}
    texte = CSS.read_text(encoding='utf-8')
    racine = texte[texte.index(':root{'):texte.index('}', texte.index(':root{'))]
    couleurs = {c.lower() for c in re.findall(r'#[0-9a-fA-F]{3,6}\b', racine)}
    assert couleurs <= yl1, couleurs - yl1


def test_nom_affiche_kimba():
    for f in GABARITS.rglob('*.html'):
        affiche = re.sub(r'\{#.*?#\}', '', f.read_text(encoding='utf-8'), flags=re.S)
        assert 'PERFORM' not in affiche, f
