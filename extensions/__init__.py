"""
Flask extensions package.
Defines global extension instances and centralized initialization.
"""

import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager

from .db import db, init_db
from .migrate import migrate, init_migrate
from .login import login_manager, init_login

logger = logging.getLogger(__name__)

__all__ = ['db', 'migrate', 'login_manager', 'init_extensions']

db: SQLAlchemy = db
migrate: Migrate = migrate
login_manager: LoginManager = login_manager


def init_extensions(app: Flask) -> None:
    """Initializes all registered Flask extensions."""
    logger.debug("Initializing all extensions...")
    init_db(app)
    init_migrate(app, db)
    init_login(app)
    logger.debug("All extensions initialized.")