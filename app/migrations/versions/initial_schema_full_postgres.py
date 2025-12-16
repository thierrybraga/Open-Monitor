"""Initial full schema for Postgres (core and public)

Revision ID: initial_schema_full_postgres
Revises: initial_postgres
Create Date: 2025-12-04 01:05:00

"""
from alembic import op
import sqlalchemy as sa

# Optional imports to access Flask application context and binds
from flask import current_app
# Ensure models are imported and registered so metadata includes all tables
try:
    from app import models as _models  # noqa: F401
except Exception:
    _models = None
try:
    from app.extensions import db as _db
except Exception:
    _db = None


# revision identifiers, used by Alembic.
revision = 'initial_schema_full_postgres'
down_revision = 'initial_postgres'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Create all core tables from SQLAlchemy metadata
    try:
        target_db = current_app.extensions['migrate'].db
        if hasattr(target_db, 'metadatas'):
            core_meta = target_db.metadatas.get(None)
            if core_meta is not None:
                core_meta.create_all(bind=bind)
        else:
            core_metadata = getattr(target_db, 'metadata', None)
            if core_metadata:
                core_metadata.create_all(bind=bind)
    except Exception:
        pass

    # Create 'public' bind tables using its metadata and engine
    try:
        target_db = current_app.extensions['migrate'].db
        public_metadata = None
        if hasattr(target_db, 'metadatas'):
            public_metadata = target_db.metadatas.get('public')
        if public_metadata and _db is not None:
            try:
                public_engine = _db.get_engine(current_app, bind='public')
            except Exception:
                public_engine = None
            if public_engine is not None:
                # Ensure enum types required by Postgres exist before table creation
                try:
                    if public_engine.dialect.name == 'postgresql':
                        public_engine.execute(sa.text("""
                        DO $$
                        BEGIN
                            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'messagetype') THEN
                                CREATE TYPE messagetype AS ENUM ('USER', 'ASSISTANT', 'SYSTEM', 'ERROR');
                            END IF;
                        END $$;
                        """))
                except Exception:
                    pass
                public_metadata.create_all(bind=public_engine)
    except Exception:
        pass


def downgrade():
    # No automatic downgrade for initial schema bootstrap
    pass
