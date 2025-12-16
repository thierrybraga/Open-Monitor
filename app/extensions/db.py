import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event, text

logger = logging.getLogger(__name__)

db: SQLAlchemy = SQLAlchemy()

def init_db(app: Flask) -> None:
    """Initializes SQLAlchemy."""
    try:
        db.init_app(app)
        logger.debug("SQLAlchemy initialized")

        # Apply SQLite PRAGMA optimizations and ensure helpful indexes
        with app.app_context():
            try:
                # Configurar PRAGMAs para o engine principal
                core_engine = db.engine
                if 'sqlite' in core_engine.name:
                    logger.debug("Configuring SQLite PRAGMAs for core engine...")

                    @event.listens_for(core_engine, "connect")
                    def set_sqlite_pragmas_core(dbapi_connection, connection_record):
                        try:
                            cursor = dbapi_connection.cursor()
                            cursor.execute("PRAGMA journal_mode=WAL")
                            cursor.execute("PRAGMA busy_timeout=5000")
                            cursor.execute("PRAGMA synchronous=NORMAL")
                            cursor.execute("PRAGMA temp_store=MEMORY")
                            cursor.execute("PRAGMA cache_size=-10000")
                            cursor.execute("PRAGMA foreign_keys=ON")
                            cursor.close()
                        except Exception:
                            logger.warning("Failed to apply SQLite PRAGMAs on core connect.")

                # Configurar PRAGMAs para o bind 'public' (se existir)
                try:
                    public_engine = db.get_engine(app, bind='public')
                except Exception:
                    public_engine = None

                if public_engine and 'sqlite' in public_engine.name:
                    logger.debug("Configuring SQLite PRAGMAs for public engine...")

                    @event.listens_for(public_engine, "connect")
                    def set_sqlite_pragmas_public(dbapi_connection, connection_record):
                        try:
                            cursor = dbapi_connection.cursor()
                            cursor.execute("PRAGMA journal_mode=WAL")
                            cursor.execute("PRAGMA busy_timeout=5000")
                            cursor.execute("PRAGMA synchronous=NORMAL")
                            cursor.execute("PRAGMA temp_store=MEMORY")
                            cursor.execute("PRAGMA cache_size=-10000")
                            cursor.execute("PRAGMA foreign_keys=ON")
                            cursor.close()
                        except Exception:
                            logger.warning("Failed to apply SQLite PRAGMAs on public connect.")

                # Index management moved to Alembic migrations for consistency
                logger.debug("Skipping runtime index creation; handled by migrations.")
            except Exception as e:
                logger.warning(f"DB engine not available for PRAGMA/index setup: {e}")
    except Exception as e:
        logger.error("SQLAlchemy initialization failed", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}") from e
