"""
Flask application factory to create and configure the application instance.
"""

import os
import secrets
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    g,
    Blueprint
)

from dotenv import load_dotenv
from markupsafe import Markup

# Importações do projeto
from settings import config_map
from extensions import init_extensions, db
from extensions.csrf import exempt_api_blueprints
from controllers import BLUEPRINTS

# Configuração básica de logging - pode ser expandida para setups mais complexos
# Configura o formato e o handler básico para o root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def format_datetime(value: Optional[datetime], format: str = '%Y-%m-%d') -> str:
    """
    Formats a datetime object into a string.
    Useful as a Jinja2 filter.
    """
    if value is None:
        return "N/A"
    if not isinstance(value, datetime):
        # Handle cases where the value might be a string or other type unexpectedly
        logger.warning(f"datetimeformat filter received non-datetime value: {value} (type: {type(value)})")
        return str(value)

    try:
        return value.strftime(format)
    except Exception as e:
        # Log the specific error during formatting
        logger.error(f"Error formatting datetime value '{value}' with format '{format}': {e}", exc_info=False) # exc_info=False here to avoid flooding logs for potentially many formatting errors
        return str(value)


def markdown_filter(text: str) -> Markup:
    """
    Converts Markdown text to HTML.
    Useful as a Jinja2 filter.
    """
    if not text:
        return Markup("")
    
    try:
        import markdown
        html = markdown.markdown(text, extensions=['tables', 'fenced_code', 'nl2br'])
        return Markup(html)
    except ImportError:
        logger.warning("Biblioteca markdown não encontrada, retornando texto simples")
        # Fallback: converter quebras de linha simples para HTML
        html = text.replace('\n', '<br>')
        return Markup(f"<pre>{html}</pre>")
    except Exception as e:
        logger.error(f"Erro ao processar markdown: {e}")
        return Markup(f"<pre>{text}</pre>")


def configure_app(app: Flask, env_name: str = None) -> None:
    """Loads and applies configuration to the Flask app object."""
    load_dotenv()

    # Determine the environment, defaulting to 'development'
    env = env_name or os.getenv('FLASK_ENV') or 'development'

    # Get the configuration class based on the environment
    config_cls = config_map.get(env, config_map['default'])
    cfg = config_cls()

    # Load configuration from the object
    app.config.from_object(cfg)

    # Initialize configuration if it has an init_app method
    if hasattr(cfg, 'init_app'):
        try:
            cfg.init_app(app)
            logger.debug("Configuration class init_app executed.")
        except Exception as e:
            logger.error(f"Error during configuration init_app: {e}", exc_info=True)

    # Validate configuration if it has a validate method
    if hasattr(cfg, 'validate'):
        try:
            logger.info("Attempting to validate configuration...")
            cfg.validate()
            logger.info("Configuration validated successfully.")
        except Exception as e:
            # Log validation failure with traceback
            logger.error(f"Configuration validation failed: {e}", exc_info=True)
            # Depending on severity, you might want to exit here in a production environment
            # import sys
            # sys.exit(1)
    else:
        logger.debug("Configuration class has no 'validate' method.")

    logger.info(f"Starting Flask app in '{env}' environment with config: {config_cls.__name__}")


def wants_json() -> bool:
    """Determines if the client prefers JSON response."""
    # Check if the request contains 'application/json' or explicitly asks for JSON
    return request.is_json or 'application/json' in request.accept_mimetypes.values()


def register_error_handlers(app: Flask) -> None:
    """Registers standard error handlers."""

    @app.errorhandler(404)
    def page_not_found(e):
        # Log 404 errors, but avoid full traceback for static file errors
        # Werkzeug's NotFound includes the path, which is useful.
        if request.path.startswith('/static/'):
             logger.warning(f"Static file not found: {request.path}")
        else:
             # Log application route 404s with more detail if needed
             logger.warning(f"Page not found: {request.path}", exc_info=False) # exc_info=False here, as NotFound traceback is often not needed unless debugging Werkzeug itself

        if wants_json():
            return jsonify(error="Resource not found", path=request.path), 404
        try:
            # Assume you have an errors/404.html template
            return render_template('errors/404.html', path=request.path), 404
        except Exception:
            # Fallback if template rendering fails
            return "Resource not found", 404


    @app.errorhandler(500)
    def internal_server_error(e):
        # Log internal server errors with traceback for debugging
        logger.error("Internal server error", exc_info=True)

        if wants_json():
            return jsonify(error="Internal server error"), 500
        try:
            # Assume you have an errors/500.html template
            return render_template('errors/500.html'), 500
        except Exception:
            # Fallback if template rendering fails
            return "Internal server error", 500

# TODO: Import and call setup_csp if you have it
# from .csp import setup_csp


def create_app(env_name: str = None) -> Flask:
    """
    Flask application factory function.

    Initializes the application, loads configuration, initializes extensions,
    registers Blueprints, and sets up error handlers.
    """

    # Explicitly define static and template folders
    app = Flask(__name__, static_folder='static', template_folder='templates')

    # Configure the application
    configure_app(app, env_name)

    # Initialize Flask extensions
    init_extensions(app) # Make sure init_extensions properly initializes extensions like db, LoginManager, etc.

    # Register custom Jinja2 filters
    app.jinja_env.filters['datetimeformat'] = format_datetime
    app.jinja_env.filters['markdown'] = markdown_filter
    logger.debug("Custom Jinja2 filters 'datetimeformat' and 'markdown' registered.")

    # Inject common variables into all templates
    @app.context_processor
    def inject_base_variables():
        """Injects common variables like social links into all templates."""
        social_links_data = {
            "twitter": "https://twitter.com/seu_perfil", # Consider making these configurable
            "linkedin": "https://linkedin.com/sua_pagina", # Consider making these configurable
        }
        # TODO: Add other common variables here if needed (e.g., logged-in user, dynamic nav links)
        # from flask_login import current_user # Import current_user at the top if used
        # Ensure flask_login is initialized in init_extensions
        # try:
        #      from flask_login import current_user
        #      return {'social_links': social_links_data, 'current_user': current_user}
        # except ImportError:
        #      logger.warning("Flask-Login not available or not initialized. 'current_user' not injected into context.")
        #      return {'social_links': social_links_data}

        # Basic injection if flask_login is not used or initialized yet
        return {'social_links': social_links_data}


    # Register Blueprints
    # Ensure BLUEPRINTS is correctly defined in controllers/__init__.py
    if not isinstance(BLUEPRINTS, (list, tuple)):
        logger.error("controllers.BLUEPRINTS must be a list or tuple of Blueprint instances. No blueprints will be registered.")
        blueprints_to_register = []
    else:
        # Filter out any items in BLUEPRINTS that are not Blueprint instances
        blueprints_to_register = [bp for bp in BLUEPRINTS if isinstance(bp, Blueprint)]
        if len(blueprints_to_register) < len(BLUEPRINTS):
             logger.warning(f"Skipped invalid items in BLUEPRINTS list. Registered {len(blueprints_to_register)} out of {len(BLUEPRINTS)} total items.")


    seen_prefixes: Dict[str, str] = {}
    logger.debug(f"Attempting to register {len(blueprints_to_register)} blueprints.")

    for bp in blueprints_to_register:
        # Use the blueprint name as the key if url_prefix is None, otherwise use the prefix
        prefix_key = bp.url_prefix if bp.url_prefix is not None else bp.name # Use bp.name for root blueprints

        if prefix_key in seen_prefixes:
            logger.warning(f"Prefix or name conflict: '{prefix_key}' used by existing blueprint '{seen_prefixes[prefix_key]}' and new blueprint '{bp.name}'. Skipping '{bp.name}'.")
            continue

        seen_prefixes[prefix_key] = bp.name

        # url_prefix parameter should be None for blueprints mounted at the root
        register_prefix = bp.url_prefix if bp.url_prefix is not None and bp.url_prefix != '/' else None

        try:
            app.register_blueprint(bp, url_prefix=register_prefix)
            logger.debug(f"Blueprint '{bp.name}' registered with prefix '{register_prefix or '/'}'.")
        except Exception as e:
             logger.error(f"Error registering blueprint '{bp.name}': {e}", exc_info=True)


    # Log all successfully registered blueprint names and their prefixes
    registered_blueprints_info = {name: bp.url_prefix if bp.url_prefix is not None else '/' for bp in blueprints_to_register if bp.name in seen_prefixes for name in [bp.name]}
    logger.debug(f"Finished blueprint registration. Registered: {registered_blueprints_info}")

    # Exempt API blueprints from CSRF protection
    try:
        exempt_api_blueprints(app)
        logger.debug("API blueprints exempted from CSRF protection.")
    except Exception as e:
        logger.error(f"Failed to exempt API blueprints from CSRF protection: {e}", exc_info=True)


    # TODO: Setup CSP - Uncomment and implement if needed
    # try:
    #     setup_csp(app)
    #     logger.debug("CSP setup complete.")
    # except Exception as e:
    #     logger.error(f"CSP setup failed: {e}", exc_info=True)


    # Register error handlers
    register_error_handlers(app)
    logger.debug("Error handlers registered.")


    # Health check endpoint
    @app.route('/health')
    def health():
        """Endpoint for health check."""
        try:
            # Check database connection by executing a simple query
            with app.app_context():
                 # Assuming 'db' is your SQLAlchemy instance
                 from sqlalchemy import select
                 # db.session.execute(select(1)) is a good way to check connection
                 # Alternatively, depending on your ORM, you might use a different check
                 db.session.execute(select(1)) # Executa uma query simples
            logger.debug("Health check successful (DB connection OK).")
            # Include git commit or version info if available in config
            return jsonify(status='healthy', env=app.config.get('FLASK_ENV', 'unknown'), version=app.config.get('APP_VERSION', 'N/A')), 200
        except Exception as e:
            # Log the database connection error for debugging health issues
            logger.error("Health check failed (DB connection error).", exc_info=True)
            return jsonify(status='unhealthy', error="Database connection failed"), 500 # Provide a generic error message to the client

    logger.info("Flask app factory finished configuration.")

    return app

# Note: The factory function itself should not call app.run().
# To run the app, you typically use 'flask run' with FLASK_APP pointing to the factory,
# or have a separate run.py file that imports and runs the factory.