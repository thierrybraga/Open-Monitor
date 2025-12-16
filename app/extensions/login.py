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
        # Mensagem unificada exibida ao acessar páginas protegidas sem estar logado
        login_manager.login_message = 'Faça login para continuar.'
        login_manager.init_app(app)

        # Configure user_loader callback
        @login_manager.user_loader
        def load_user(user_id):
            """Load user by ID for Flask-Login."""
            try:
                from app.models.user import User
                return User.query.get(int(user_id))
            except Exception as e:
                logger.error(f"Error loading user {user_id}: {e}")
                return None

        logger.debug("Flask-Login initialized successfully.")
    except Exception as e:
        logger.error("Flask-Login initialization failed.", exc_info=True)
        raise RuntimeError(f"LoginManager initialization failed: {e}") from e

    @login_manager.unauthorized_handler
    def _unauthorized():
        try:
            from flask import request, jsonify, redirect, url_for
            wants_json = False
            try:
                wants_json = (
                    'application/json' in ((request.headers.get('Accept', '') or '').lower())
                ) or (
                    request.headers.get('X-Requested-With', '') == 'XMLHttpRequest'
                )
            except Exception:
                wants_json = False

            if wants_json:
                return jsonify({'success': False, 'error': 'Autenticação necessária'}), 401
            return redirect(url_for(login_manager.login_view))
        except Exception:
            return ("Autenticação necessária", 401)
