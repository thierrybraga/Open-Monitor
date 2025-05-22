import logging
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from .db import db

logger = logging.getLogger(__name__)

migrate: Migrate = Migrate()

def init_migrate(app: Flask, db: SQLAlchemy) -> None:
    """Initializes Flask-Migrate."""
    try:
        migrate.init_app(app, db)
        logger.debug("Flask-Migrate initialized")
    except Exception as e:
        logger.error("Flask-Migrate initialization failed", exc_info=True)
        raise RuntimeError(f"Migrate initialization failed: {e}") from e