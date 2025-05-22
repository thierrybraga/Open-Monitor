import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

logger = logging.getLogger(__name__)

db: SQLAlchemy = SQLAlchemy()

def init_db(app: Flask) -> None:
    """Initializes SQLAlchemy."""
    try:
        db.init_app(app)
        logger.debug("SQLAlchemy initialized")
    except Exception as e:
        logger.error("SQLAlchemy initialization failed", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}") from e