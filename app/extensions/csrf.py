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
    try:
        logger.debug(f"Available blueprints: {list(app.blueprints.keys())}")
        api_blueprints = {'chatbot', 'chat'}
        for blueprint_name, blueprint in app.blueprints.items():
            bp_prefix = getattr(blueprint, 'url_prefix', '') or ''
            is_api = ('api' in blueprint_name.lower()) or bp_prefix.startswith('/api') or (blueprint_name in api_blueprints)
            if is_api:
                csrf.exempt(blueprint)
                for endpoint, view_func in app.view_functions.items():
                    if endpoint.startswith(f"{blueprint_name}."):
                        csrf.exempt(view_func)
            else:
                logger.debug(f"Blueprint '{blueprint_name}' not exempted")
        specific_endpoints = {'auth.check_availability', 'asset.delete_asset'}
        for endpoint, view_func in app.view_functions.items():
            if endpoint in specific_endpoints:
                csrf.exempt(view_func)
    except Exception as e:
        logger.error("Failed to exempt API blueprints from CSRF protection.", exc_info=True)
        raise RuntimeError(f"CSRF exemption failed: {e}") from e
