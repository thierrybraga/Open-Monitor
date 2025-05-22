import logging
from flask import Flask
from flask_login import LoginManager

logger = logging.getLogger(__name__)

login_manager: LoginManager = LoginManager()

def init_login(app: Flask) -> None:
    """
    Initializes the Flask-Login extension.

    Configures login view, session protection, and login message category.
    """
    try:
        login_manager.login_view = 'auth.login'
        login_manager.session_protection = 'strong'
        login_manager.login_message_category = 'warning'
        login_manager.init_app(app)

        logger.debug("Flask-Login initialized successfully.")
    except Exception as e:
        logger.error("Flask-Login initialization failed.", exc_info=True)
        raise RuntimeError(f"LoginManager initialization failed: {e}") from e