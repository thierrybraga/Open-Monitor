"""
Testes para o utilitário ORM de SyncMetadata.

Valida cenários de insert, update e sanitização de valores
usando a função upsert_sync_metadata e o helper get_last_sync_info.
"""

from datetime import datetime

import pytest

from flask import Flask
from app.extensions import db, init_extensions
from app.utils.sync_metadata_orm import upsert_sync_metadata, get_last_sync_info
from app.models.sync_metadata import SyncMetadata


@pytest.fixture(scope="module")
def app():
    """Cria uma aplicação Flask mínima com DB em memória."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    init_extensions(app)
    return app


@pytest.fixture(autouse=True)
def setup_db(app):
    """Garante um banco limpo por teste."""
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        try:
            db.session.rollback()
        except Exception:
            pass


def _fetch_by_key(key: str):
    return db.session.query(SyncMetadata).filter_by(key=key).first()


def test_upsert_insert_creates_row(app):
    key = 'nvd_last_sync'
    value = datetime.utcnow().isoformat(timespec='milliseconds')

    with app.app_context():
        ok, instance = upsert_sync_metadata(
            session=None,
            key=key,
            value=value,
            status='completed',
            sync_type='daily',
        )
        assert ok is True
        assert isinstance(instance, SyncMetadata)
        db.session.commit()

        found = _fetch_by_key(key)
        assert found is not None
        assert found.value == value
        assert found.status == 'completed'
        assert found.sync_type == 'daily'


def test_upsert_update_existing_row(app):
    key = 'nvd_last_sync'
    initial_value = 'initial'
    with app.app_context():
        # cria inicial
        ok, _ = upsert_sync_metadata(
            session=None,
            key=key,
            value=initial_value,
            status='pending',
            sync_type='hourly',
        )
        assert ok
        db.session.commit()

        # atualiza
        ok, instance = upsert_sync_metadata(
            session=None,
            key=key,
            value='sync-error',
            status='error',
            sync_type='daily',
            last_modified=datetime.utcnow(),
        )
        assert ok
        assert isinstance(instance, SyncMetadata)
        db.session.commit()

        found = _fetch_by_key(key)
        assert found is not None
        assert found.value == 'sync-error'
        assert found.status == 'error'
        assert found.sync_type == 'daily'


def test_upsert_value_trimming_to_255(app):
    key = 'nvd_last_sync'
    long_value = 'a' * 300
    with app.app_context():
        ok, _ = upsert_sync_metadata(
            session=None,
            key=key,
            value=long_value,
            status='completed',
            sync_type='daily',
        )
        assert ok
        db.session.commit()

        found = _fetch_by_key(key)
        assert found is not None
        assert isinstance(found.value, str)
        assert len(found.value) <= 255
        assert found.value.endswith('...')


def test_get_last_sync_info_helper(app):
    with app.app_context():
        info = get_last_sync_info()
        # Pode ser None se não existir; garanta existência inserindo um valor
        if info is None:
            ok, _ = upsert_sync_metadata(
                session=None,
                key='nvd_last_sync',
                value=datetime.utcnow().isoformat(timespec='milliseconds'),
                status='completed',
                sync_type='daily',
            )
            assert ok
            db.session.commit()
            info = get_last_sync_info()

        assert info is not None
        assert info.key == 'nvd_last_sync'