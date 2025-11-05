"""
Flask application factory to create and configure the application instance.
"""

import os
from pathlib import Path
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
    Blueprint,
    session
)

from dotenv import load_dotenv
from markupsafe import Markup
import mimetypes
# Garantir MIME type correto para .webmanifest
mimetypes.add_type('application/manifest+json', '.webmanifest')
from flask_wtf.csrf import generate_csrf

# Carregar variáveis de ambiente o mais cedo possível, antes de importar settings
try:
    early_env = Path('.env')
    early_example = Path('.env.example')
    if early_env.exists():
        load_dotenv(dotenv_path=str(early_env))
        logger = logging.getLogger(__name__)
        logger.debug("Early env load: .env")
    elif early_example.exists():
        load_dotenv(dotenv_path=str(early_example))
        logger = logging.getLogger(__name__)
        logger.info("Early env load: .env.example (fallback)")
    else:
        load_dotenv()
        logger = logging.getLogger(__name__)
        logger.debug("Early env load: default locations")
except Exception as _e:
    # Não impedir import por falha de env; será tentado novamente em configure_app
    pass

# Importações do projeto
from app.settings import config_map
from app.extensions import init_extensions, db
from app.extensions.csrf import exempt_api_blueprints
from app.controllers import BLUEPRINTS
from app.utils.security import cleanup_session_data
from app.utils.api_rate_limiter import FlaskRateLimiter

# Configuração básica de logging - pode ser expandida para setups mais complexos
# Configura o formato e o handler básico para o root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s [%(name)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def _sanitize_logging_configuration() -> None:
    """Sanitiza configuração de logging para evitar duplicações no console.

    - Garante apenas um StreamHandler no root logger
    - Remove handlers do logger 'app' (criado por EnhancedLogger) para evitar captura
      de mensagens dos loggers filhos como 'app.app'
    - Ajusta níveis de log de bibliotecas ruidosas
    """
    try:
        root_logger = logging.getLogger()
        # Padronizar formatter do console
        console_formatter = logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s')

        # Manter apenas um StreamHandler no root
        stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
        if stream_handlers:
            # Aplicar formatter padrão
            for h in stream_handlers:
                h.setFormatter(console_formatter)
            # Remover duplicatas além do primeiro
            for h in stream_handlers[1:]:
                root_logger.removeHandler(h)

        # Evitar que o logger 'app' (pai de 'app.app') capture logs dos filhos
        app_parent_logger = logging.getLogger('app')
        if app_parent_logger.handlers:
            for h in list(app_parent_logger.handlers):
                app_parent_logger.removeHandler(h)
        # Permitir propagação ao root para que apenas o root trate
        app_parent_logger.propagate = True

        # Reduzir verbosidade de loggers comuns
        logging.getLogger('werkzeug').setLevel(logging.WARNING)
        logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
        logging.getLogger('alembic').setLevel(logging.INFO)

        # Log de diagnóstico dos handlers
        def _handler_repr(h: logging.Handler) -> str:
            return f"{h.__class__.__name__}(level={logging.getLevelName(h.level)})"
        logger.debug(f"Root handlers after sanitize: {[ _handler_repr(h) for h in root_logger.handlers ]}")
        logger.debug(f"'app' logger handlers after sanitize: {[ _handler_repr(h) for h in app_parent_logger.handlers ]}")

        # Handler único e local para 'app.app' para evitar duplicação via propagação
        app_module_logger = logging.getLogger('app.app')
        for h in list(app_module_logger.handlers):
            app_module_logger.removeHandler(h)
        local_stream = logging.StreamHandler()
        local_stream.setFormatter(console_formatter)
        app_module_logger.addHandler(local_stream)
        app_module_logger.setLevel(logging.DEBUG)
        # Desabilitar propagação para que apenas o handler local trate
        app_module_logger.propagate = False
    except Exception as e:
        # Não falhar inicialização por causa de ajustes de logging
        logger.debug(f"Falha ao sanitizar configuração de logging: {e}")


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
    # Load environment variables, preferring .env and falling back to .env.example
    try:
        env_path = Path('.env')
        example_path = Path('.env.example')
        if env_path.exists():
            load_dotenv(dotenv_path=str(env_path))
            logger.debug("Loaded environment from .env")
        elif example_path.exists():
            load_dotenv(dotenv_path=str(example_path))
            logger.info(".env not found; loaded environment from .env.example (fallback)")
        else:
            load_dotenv()
            logger.debug("Loaded environment from default locations")
    except Exception as e:
        logger.error(f"Failed to load environment variables: {e}")

    # Determine the environment, defaulting to 'development'
    env = env_name or os.getenv('FLASK_ENV') or 'development'

    # Get the configuration class based on the environment
    config_cls = config_map.get(env, config_map['default'])
    cfg = config_cls()

    # Load configuration from the object
    app.config.from_object(cfg)

    # Overlay dynamic environment variables that may have been loaded after class definition
    try:
        # OpenAI configuration overrides
        env_openai_key = os.getenv('OPENAI_API_KEY')
        env_openai_model = os.getenv('OPENAI_MODEL')
        env_openai_max_tokens = os.getenv('OPENAI_MAX_TOKENS')
        env_openai_temperature = os.getenv('OPENAI_TEMPERATURE')
        env_openai_timeout = os.getenv('OPENAI_TIMEOUT')
        env_openai_max_retries = os.getenv('OPENAI_MAX_RETRIES')
        env_openai_retry_backoff = os.getenv('OPENAI_RETRY_BACKOFF')
        env_openai_streaming = os.getenv('OPENAI_STREAMING')
        env_openai_fallback = os.getenv('OPENAI_FALLBACK_TO_DEMO_ON_ERROR')

        if env_openai_key:
            app.config['OPENAI_API_KEY'] = env_openai_key
        if env_openai_model:
            app.config['OPENAI_MODEL'] = env_openai_model
        if env_openai_max_tokens:
            try:
                app.config['OPENAI_MAX_TOKENS'] = int(env_openai_max_tokens)
            except Exception:
                pass
        if env_openai_temperature:
            try:
                app.config['OPENAI_TEMPERATURE'] = float(env_openai_temperature)
            except Exception:
                pass
        if env_openai_timeout:
            try:
                app.config['OPENAI_TIMEOUT'] = int(env_openai_timeout)
            except Exception:
                pass
        if env_openai_max_retries:
            try:
                app.config['OPENAI_MAX_RETRIES'] = int(env_openai_max_retries)
            except Exception:
                pass
        if env_openai_retry_backoff:
            try:
                app.config['OPENAI_RETRY_BACKOFF'] = float(env_openai_retry_backoff)
            except Exception:
                pass
        if env_openai_streaming is not None:
            try:
                app.config['OPENAI_STREAMING'] = int(env_openai_streaming) == 1
            except Exception:
                pass
        if env_openai_fallback is not None:
            try:
                app.config['OPENAI_FALLBACK_TO_DEMO_ON_ERROR'] = int(env_openai_fallback) == 1
            except Exception:
                pass
        try:
            logger.info(f"Config overlay: OPENAI_API_KEY present={bool(app.config.get('OPENAI_API_KEY'))}, model={app.config.get('OPENAI_MODEL')}")
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Failed to overlay OpenAI env config: {e}")

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

    # Cache estático padrão para reduzir revalidação 304
    app.config.setdefault('SEND_FILE_MAX_AGE_DEFAULT', 86400)  # 24h

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
        elif request.path.startswith('/@vite/'):
             # Suppress Vite development client logs in production
             logger.debug(f"Vite development client request ignored: {request.path}")
        else:
             # Log application route 404s with more detail if needed
             logger.warning(f"Page not found: {request.path}", exc_info=False) # exc_info=False here, as NotFound traceback is often not needed unless debugging Werkzeug itself

        if wants_json():
            return jsonify(error="Resource not found", path=request.path), 404
        try:
            # Assume you have an errors/404.html template
            return render_template('error/404.html', path=request.path), 404
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
            return render_template('error/500.html'), 500
        except Exception:
            # Fallback if template rendering fails
            return "Internal server error", 500

from app.csp import setup_csp


def setup_security_cleanup(app: Flask) -> None:
    """Setup periodic cleanup for security session data."""
    import threading
    import time
    
    def cleanup_worker():
        """Background worker to periodically clean up session data."""
        while True:
            try:
                with app.app_context():
                    cleanup_session_data()
                # Cleanup every 6 hours
                time.sleep(6 * 60 * 60)
            except Exception as e:
                logger.error(f"Erro na limpeza de dados de sessão: {e}")
                # Wait 1 hour before retrying on error
                time.sleep(60 * 60)
    
    # Start cleanup thread only in production or when not in debug mode
    if not app.config.get('DEBUG', False):
        cleanup_thread = threading.Thread(target=cleanup_worker, daemon=True)
        cleanup_thread.start()
        logger.info("Thread de limpeza de dados de segurança iniciada")
    else:
        logger.debug("Limpeza automática de dados de segurança desabilitada em modo debug")


def cleanup_legacy_sync_metadata(app: Flask) -> None:
    """Normalize legacy SyncMetadata rows where value='in_progress' but status!='in_progress'."""
    with app.app_context():
        try:
            # Ensure table exists before querying to avoid OperationalError on fresh databases
            from sqlalchemy import inspect
            from app.extensions import db
            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            if 'sync_metadata' not in tables:
                logger.debug("SyncMetadata cleanup skipped: table 'sync_metadata' not found.")
                return

            from app.models.sync_metadata import SyncMetadata
            legacy_rows = SyncMetadata.query.filter(
                SyncMetadata.value == 'in_progress',
                SyncMetadata.status != 'in_progress'
            ).all()
            if not legacy_rows:
                logger.debug("SyncMetadata cleanup: no legacy rows found.")
                return
            for row in legacy_rows:
                # Normalize to correct state and avoid isoformat parsing issues
                # Preserve existing status; only clear invalid 'value'
                row.value = None
                row.last_modified = datetime.utcnow()
            db.session.commit()
            logger.info(f"SyncMetadata cleanup: normalized {len(legacy_rows)} legacy rows (value='in_progress').")
        except Exception as e:
            logger.error(f"SyncMetadata cleanup failed: {e}", exc_info=True)


def run_startup_health_check(app: Flask) -> None:
    """Run a one-time startup health check and log concise results."""
    with app.app_context():
        try:
            from sqlalchemy import inspect, select, text
            from app.extensions import db
            logger.info("Performing startup health check...")

            # Basic DB connectivity
            try:
                db.session.execute(select(1))
                logger.info("DB connection OK")
            except Exception as e:
                logger.error(f"DB connection failed: {e}", exc_info=True)
                return

            inspector = inspect(db.engine)
            tables = set(inspector.get_table_names())
            logger.info(f"Database has {len(tables)} tables")

            # Vulnerabilities count (if table present)
            try:
                if 'vulnerabilities' in tables:
                    res = db.session.execute(text('SELECT COUNT(*) as c FROM vulnerabilities')).mappings().first()
                    total_vulns = int(res['c']) if res and 'c' in res else 0
                    logger.info(f"Vulnerabilities count: {total_vulns}")
            except Exception as e:
                logger.warning(f"Could not count vulnerabilities: {e}")

            # Last NVD sync metadata (if table present)
            try:
                if 'sync_metadata' in tables:
                    from app.models.sync_metadata import SyncMetadata
                    last_sync = (
                        db.session.query(SyncMetadata)
                        .filter_by(key='nvd_last_sync')
                        .order_by(SyncMetadata.last_modified.desc())
                        .first()
                    )
                    if last_sync and last_sync.last_modified:
                        from datetime import datetime
                        now = datetime.utcnow()
                        delta_days = (now - last_sync.last_modified).days
                        logger.info(f"Last NVD sync: {delta_days} day(s) ago; status={getattr(last_sync, 'status', 'unknown')}")
                        if delta_days > 7:
                            logger.warning("Last NVD sync older than 7 days; consider a full refresh")
                    else:
                        logger.info("No NVD sync metadata found; initial sync may be needed")
            except Exception as e:
                logger.warning(f"Startup sync metadata check failed: {e}")

        except Exception as e:
            logger.error(f"Startup health check failed: {e}", exc_info=True)


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

    # Sanitizar configuração de logging para evitar duplicação no console
    _sanitize_logging_configuration()

    # Initialize Flask extensions
    init_extensions(app) # Make sure init_extensions properly initializes extensions like db, LoginManager, etc.

    # Cleanup legacy SyncMetadata inconsistencies
    cleanup_legacy_sync_metadata(app)
    
    # Startup health check
    run_startup_health_check(app)
    
    # Initialize rate limiter
    try:
        from app.config.rate_limiter_config import get_rate_limiter_config
        config = get_rate_limiter_config()
        rate_limiter = FlaskRateLimiter(app, config)
        app.logger.info(f"Rate limiter initialized successfully with config: {config.__class__.__name__}")
    except Exception as e:
        app.logger.error(f"Failed to initialize rate limiter: {e}")
        import traceback
        app.logger.error(traceback.format_exc())
    
    # Setup periodic cleanup for security session data
    setup_security_cleanup(app)

    # Register custom Jinja2 filters
    app.jinja_env.filters['datetimeformat'] = format_datetime
    app.jinja_env.filters['markdown'] = markdown_filter
    logger.debug("Custom Jinja2 filters 'datetimeformat' and 'markdown' registered.")

    # Create a moment-like utility class for templates
    class MomentUtil:
        """Utility class to provide moment-like functionality in templates."""
        
        def __init__(self):
            self._datetime = datetime.now()
        
        @property
        def year(self):
            """Get current year."""
            return self._datetime.year
        
        def format(self, format_string):
            """Format datetime using moment.js-like format strings."""
            # Convert moment.js format to Python strftime format
            format_mapping = {
                'YYYY-MM-DD': '%Y-%m-%d',
                'DD/MM/YYYY HH:mm': '%d/%m/%Y %H:%M',
                'YYYY': '%Y',
                'MM': '%m',
                'DD': '%d',
                'HH': '%H',
                'mm': '%M',
                'ss': '%S'
            }
            
            python_format = format_mapping.get(format_string, format_string)
            return self._datetime.strftime(python_format)

    # Inject common variables into all templates
    @app.context_processor
    def inject_base_variables():
        """Injects common variables like social links into all templates."""
        social_links_data = {
            "twitter": "https://twitter.com/seu_perfil", # Consider making these configurable
            "linkedin": "https://linkedin.com/sua_pagina", # Consider making these configurable
        }
        
        # Generate CSP nonce for each request
        nonce = secrets.token_urlsafe(16)
        # Ensure CSP header uses the same nonce
        g.csp_nonce = nonce
        
        # Create moment utility instance
        moment_util = MomentUtil()

        # Determine current_user for templates: inject Flask-Login proxy when available,
        # otherwise provide a safe anonymous user in PUBLIC_MODE to avoid template errors.
        try:
            from flask import current_app
            login_mgr = getattr(current_app, 'login_manager', None)
            if login_mgr is not None:
                # Flask-Login initialized: use its current_user proxy
                from flask_login import current_user as flask_current_user
                injected_user = flask_current_user
            else:
                # PUBLIC_MODE or LoginManager not initialized: provide a safe anonymous user
                class AnonymousUser:
                    is_authenticated = False
                    is_admin = False
                    username = 'Visitante'
                    first_name = None
                    id = None
                    def get_id(self):
                        return None
                injected_user = AnonymousUser()
        except Exception:
            # Fallback in case import or attribute access fails
            class AnonymousUserFallback:
                is_authenticated = False
                is_admin = False
                username = 'Visitante'
                first_name = None
                id = None
                def get_id(self):
                    return None
            injected_user = AnonymousUserFallback()

        # Read UI settings from session (language/theme)
        try:
            settings_state = session.get('settings') or {}
            general_settings = settings_state.get('general') or {}
            ui_settings = {
                'language': general_settings.get('language') or app.config.get('HTML_LANG', 'pt-BR'),
                'theme': general_settings.get('theme') or 'auto',
            }
        except Exception:
            ui_settings = {
                'language': app.config.get('HTML_LANG', 'pt-BR'),
                'theme': 'auto',
            }

        return {
            'social_links': social_links_data,
            'nonce': nonce,
            'csp_nonce': nonce,
            'moment': moment_util,
            'current_user': injected_user,
            'MAPBOX_ACCESS_TOKEN': app.config.get('MAPBOX_ACCESS_TOKEN'),
            'ui_settings': ui_settings,
            'csrf_token': generate_csrf
        }


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


    # Setup CSP
    try:
        setup_csp(app)
        logger.debug("CSP setup complete.")
    except Exception as e:
        logger.error(f"CSP setup failed: {e}", exc_info=True)


    # Register error handlers
    register_error_handlers(app)
    logger.debug("Error handlers registered.")

    # Headers de cache para respostas estáticas
    @app.after_request
    def _static_cache_headers(response):
        try:
            path = request.path or ''
            if path.startswith('/static/'):
                if path.endswith('.webmanifest'):
                    response.headers['Content-Type'] = 'application/manifest+json'
                    response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
                elif path.endswith(('.css', '.js', '.woff', '.woff2', '.ttf', '.eot', '.svg', '.png', '.jpg', '.jpeg', '.gif', '.ico')):
                    response.headers['Cache-Control'] = 'public, max-age=86400, immutable'
                else:
                    response.headers.setdefault('Cache-Control', 'public, max-age=86400')
        except Exception:
            pass
        return response

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

# Default app instance for `flask run`
# This allows `flask --app app run` or FLASK_APP=app to work without specifying the factory
app = create_app(os.getenv('FLASK_ENV') or 'development')