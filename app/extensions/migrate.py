import logging
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from .db import db

logger = logging.getLogger(__name__)

migrate: Migrate = Migrate()

def init_migrate(app: Flask, db: SQLAlchemy) -> None:
    """Initializes Flask-Migrate.

    Ensure the migrations directory points to the project's 'app/migrations'.
    This fixes 'Path doesn't exist: migrations' when using flask CLI.
    """
    try:
        # Explicitly set directory to match repository structure
        migrate.init_app(app, db, directory='app/migrations')
        logger.debug("Flask-Migrate initialized (directory='app/migrations')")
    except Exception as e:
        logger.error("Flask-Migrate initialization failed", exc_info=True)
        raise RuntimeError(f"Migrate initialization failed: {e}") from e