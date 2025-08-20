import logging
from flask import Flask
from flask_wtf.csrf import CSRFProtect

logger = logging.getLogger(__name__)

csrf: CSRFProtect = CSRFProtect()

def init_csrf(app: Flask) -> None:
    """Initializes Flask-WTF CSRF protection."""
    try:
        csrf.init_app(app)
        logger.debug("Flask-WTF CSRF protection initialized successfully.")
    except Exception as e:
        logger.error("Flask-WTF CSRF initialization failed.", exc_info=True)
        raise RuntimeError(f"CSRF initialization failed: {e}") from e

def exempt_api_blueprints(app: Flask) -> None:
    """Exempts API blueprints from CSRF protection."""
    try:
        logger.debug(f"Available blueprints: {list(app.blueprints.keys())}")
        # Exempt API blueprints from CSRF protection
        api_blueprints = ['chatbot']  # Blueprints específicos para exemption
        for blueprint_name, blueprint in app.blueprints.items():
            logger.debug(f"Checking blueprint: {blueprint_name}")
            if 'api' in blueprint_name.lower() or blueprint_name in api_blueprints:
                # Exempt the entire blueprint
                csrf.exempt(blueprint)
                logger.debug(f"Blueprint '{blueprint_name}' exempted from CSRF protection.")
                
                # Also exempt all view functions in the blueprint
                for endpoint, view_func in app.view_functions.items():
                    if endpoint.startswith(f"{blueprint_name}."):
                        csrf.exempt(view_func)
                        logger.debug(f"View function '{endpoint}' exempted from CSRF protection.")
            else:
                logger.debug(f"Blueprint '{blueprint_name}' not exempted (no 'api' in name).")
    except Exception as e:
        logger.error("Failed to exempt API blueprints from CSRF protection.", exc_info=True)
        raise RuntimeError(f"CSRF exemption failed: {e}") from e