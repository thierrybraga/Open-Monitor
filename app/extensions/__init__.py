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
from .babel import init_babel

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
    
    # Initialize Flask-Login unless explicitly disabled by PUBLIC_MODE
    # and no override is set. When LOGIN_ENABLED_IN_PUBLIC_MODE=True,
    # authentication remains available even in public mode.
    public_mode = app.config.get('PUBLIC_MODE', False)
    allow_login_public = app.config.get('LOGIN_ENABLED_IN_PUBLIC_MODE', False)
    if not public_mode or allow_login_public:
        init_login(app)
        logger.debug("Flask-Login initialized (authentication enabled)")
    else:
        logger.info("Flask-Login skipped (PUBLIC_MODE enabled without login override)")
    
    init_csrf(app)
    # Initialize Flask-Babel (safe fallback if not installed)
    try:
        init_babel(app)
        logger.debug("Flask-Babel initialized (i18n enabled)")
    except Exception as e:
        logger.warning(f"Flask-Babel initialization skipped or failed: {e}")
    session_middleware.init_app(app)
    logger.debug("All extensions initialized.")