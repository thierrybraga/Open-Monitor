"""
Flask extensions package.
Defines global extension instances and centralized initialization.
"""

import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from .db import db, init_db
from .migrate import migrate, init_migrate
from .login import login_manager, init_login
from .csrf import csrf, init_csrf
from .middleware import session_middleware

logger = logging.getLogger(__name__)

__all__ = ['db', 'migrate', 'login_manager', 'csrf', 'session_middleware', 'init_extensions']

db: SQLAlchemy = db
migrate: Migrate = migrate
login_manager: LoginManager = login_manager
csrf: CSRFProtect = csrf


def init_extensions(app: Flask) -> None:
    """Initializes all registered Flask extensions."""
    logger.debug("Initializing all extensions...")
    init_db(app)
    init_migrate(app, db)
    init_login(app)
    init_csrf(app)
    session_middleware.init_app(app)
    logger.debug("All extensions initialized.")