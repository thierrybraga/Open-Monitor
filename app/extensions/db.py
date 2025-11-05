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
                engine = db.engine
                if 'sqlite' in engine.name:
                    logger.debug("Configuring SQLite PRAGMAs...")

                    # Apply PRAGMA settings on each new DB-API connection
                    @event.listens_for(engine, "connect")
                    def set_sqlite_pragmas(dbapi_connection, connection_record):
                        try:
                            cursor = dbapi_connection.cursor()
                            cursor.execute("PRAGMA journal_mode=WAL")
                            cursor.execute("PRAGMA synchronous=NORMAL")
                            cursor.execute("PRAGMA temp_store=MEMORY")
                            # Negative cache_size sets size in KB; -10000 ~= 10MB
                            cursor.execute("PRAGMA cache_size=-10000")
                            cursor.execute("PRAGMA foreign_keys=ON")
                            cursor.close()
                        except Exception:
                            # Don't hard-fail if PRAGMAs cannot be applied; log and continue
                            logger.warning("Failed to apply SQLite PRAGMAs on connect.")

                    # Index management moved to Alembic migrations for consistency
                    logger.debug("Skipping runtime index creation; handled by migrations.")
                else:
                    logger.debug("Non-SQLite engine detected; skipping PRAGMAs.")
            except Exception as e:
                logger.warning(f"DB engine not available for PRAGMA/index setup: {e}")
    except Exception as e:
        logger.error("SQLAlchemy initialization failed", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}") from e