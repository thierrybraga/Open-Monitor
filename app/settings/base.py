import os, json, logging
from logging import handlers
from pathlib import Path
from urllib.parse import urlparse

class ConfigError(Exception):
    pass

def getenv_typed(name, cast, default=None):
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return cast(raw)
    except Exception as e:
        raise ConfigError(f"Env var {name} invalid: {e}")

class BaseConfig:
    SECRET_KEY = '1234'
    DEBUG = False

    # Se existir DATABASE_URL, usa; senão usa o SQLite em instance/vulnerabilities.db
    _db_url = os.getenv('DATABASE_URL')
    if _db_url:
        SQLALCHEMY_DATABASE_URI = _db_url
    else:
        # assume este arquivo está em settings/, então instance/ fica dois níveis acima
        INSTANCE_PATH = Path(__file__).parent.parent / 'instance'
        INSTANCE_PATH.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{INSTANCE_PATH / 'vulnerabilities.db'}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_FILE = Path(os.getenv('LOG_FILE', 'logs/app.log'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    # PDF Export Configuration
    # Default engine favors 'reportlab' to avoid native dependencies in dev
    PDF_ENGINE = os.getenv('PDF_ENGINE', 'reportlab')
    # Optional wkhtmltopdf path for pdfkit engine (Windows example path)
    WKHTMLTOPDF_PATH = os.getenv('WKHTMLTOPDF_PATH')
    # Base URL used by HTML-to-PDF generators to resolve assets
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')
    CSP = {
        'default-src': ["'self'"],
        'script-src':  [
            "'self'", 
            "'nonce-{{ csp_nonce }}'", 
            "https://cdn.jsdelivr.net",
            "https://maps.googleapis.com",
            "https://maps.gstatic.com",
            "https://api.mapbox.com",
            "'unsafe-eval'"  # Necessário para Chart.js e alguns componentes dinâmicos
        ],
        'style-src':   [
            "'self'", 
            "'unsafe-inline'", 
            "https://cdn.jsdelivr.net", 
            "https://fonts.googleapis.com",
            "https://maps.googleapis.com",
            "https://maps.gstatic.com",
            "https://api.mapbox.com"
        ],
        'font-src':    [
            "'self'", 
            "https://fonts.gstatic.com", 
            "https://cdn.jsdelivr.net",
            "data:"  # Para ícones SVG inline
        ],
        'img-src':     [
            "'self'", 
            "data:", 
            "https:",
            "https://maps.googleapis.com",
            "https://maps.gstatic.com",
            "https://cdn.jsdelivr.net",
            "https://api.mapbox.com"
        ],
        'connect-src': [
            "'self'",
            "https://maps.googleapis.com",
            "https://cdn.jsdelivr.net",
            "https://api.mapbox.com"
        ],
        'frame-src': [
            "'self'",
            "https://maps.google.com",  # Para embeds do Google Maps
            "https://api.mapbox.com"
        ],
        'object-src': ["'none'"],  # Segurança adicional
        'base-uri': ["'self'"],    # Previne ataques de base tag
        'form-action': ["'self'"]  # Restringe envio de formulários
    }
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS = getenv_typed('OPENAI_MAX_TOKENS', int, 1000)
    OPENAI_TEMPERATURE = getenv_typed('OPENAI_TEMPERATURE', float, 0.7)
    
    # Email Configuration
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'localhost')
    MAIL_PORT = getenv_typed('MAIL_PORT', int, 587)
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_USE_TLS = getenv_typed('MAIL_USE_TLS', lambda x: x.lower() == 'true', True)
    MAIL_USE_SSL = getenv_typed('MAIL_USE_SSL', lambda x: x.lower() == 'true', False)
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@opencvereport.com')
    
    # NVD API Configuration - loaded dynamically to ensure .env is loaded first
    @property
    def NVD_API_BASE(self):
        return os.getenv('NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0')
    
    @property
    def NVD_API_KEY(self):
        return os.getenv('NVD_API_KEY')
    
    @property
    def NVD_PAGE_SIZE(self):
        return getenv_typed('NVD_PAGE_SIZE', int, 2000)
    
    @property
    def NVD_MAX_RETRIES(self):
        return getenv_typed('NVD_MAX_RETRIES', int, 5)
    
    @property
    def NVD_CACHE_DIR(self):
        return os.getenv('NVD_CACHE_DIR', 'cache')
    
    @property
    def NVD_REQUEST_TIMEOUT(self):
        return getenv_typed('NVD_REQUEST_TIMEOUT', int, 30)
    
    @property
    def NVD_USER_AGENT(self):
        return os.getenv('NVD_USER_AGENT', 'Open-Monitor NVD Fetcher')
    
    @property
    def NVD_RATE_LIMIT(self):
        return (2, 1)  # 2 requests per 1 second for free API key

    @classmethod
    def init_app(cls, app):
        # logs
        cls.LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        fh = handlers.RotatingFileHandler(str(cls.LOG_FILE), maxBytes=10_000_000, backupCount=5)
        fh.setLevel(getattr(logging, cls.LOG_LEVEL))
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s [%(name)s] %(message)s'))
        app.logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(getattr(logging, cls.LOG_LEVEL))
        ch.setFormatter(fh.formatter)
        app.logger.addHandler(ch)
        app.logger.setLevel(getattr(logging, cls.LOG_LEVEL))

    @classmethod
    def validate(cls):
        if not cls.SECRET_KEY:
            raise ConfigError("SECRET_KEY must be set")
        scheme = urlparse(cls.SQLALCHEMY_DATABASE_URI).scheme
        if scheme and scheme not in ('sqlite','postgresql','mysql','oracle','mssql'):
            raise ConfigError(f"Unsupported DB scheme {scheme}")
