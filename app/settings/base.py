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
    
    # Modo público - permite acesso às vulnerabilidades sem autenticação
    # Usa parsing explícito de string para evitar bool('false') == True
    PUBLIC_MODE = getenv_typed('PUBLIC_MODE', lambda x: x.lower() == 'true', True)

    # Permitir login mesmo quando PUBLIC_MODE estiver habilitado
    LOGIN_ENABLED_IN_PUBLIC_MODE = getenv_typed('LOGIN_ENABLED_IN_PUBLIC_MODE', lambda x: x.lower() == 'true', True)

    # Caminho da pasta 'instance' na raiz do projeto (sempre disponível)
    INSTANCE_PATH = Path(__file__).parent.parent.parent / 'instance'
    INSTANCE_PATH.mkdir(parents=True, exist_ok=True)

    # Configuração do banco principal
    _db_url = os.getenv('DATABASE_URL')
    if _db_url and _db_url.startswith('postgres://'):
        _db_url = 'postgresql://' + _db_url[len('postgres://'):]
    if not _db_url:
        _db_url = (
            f"postgresql://{os.getenv('POSTGRES_CORE_USER','postgres')}:"
            f"{os.getenv('POSTGRES_CORE_PASSWORD','Passw0rdCore')}@"
            f"{os.getenv('POSTGRES_CORE_HOST','postgres_core')}:5432/"
            f"{os.getenv('POSTGRES_CORE_DB','om_core')}"
        )
    SQLALCHEMY_DATABASE_URI = _db_url

    # Bind adicional 'public' — sempre definido com fallback seguro
    # Sobrescreve via PUBLIC_DATABASE_URL; caso contrário, usa PostgreSQL padrão
    _pub_db_url = os.getenv('PUBLIC_DATABASE_URL')
    if _pub_db_url and _pub_db_url.startswith('postgres://'):
        _pub_db_url = 'postgresql://' + _pub_db_url[len('postgres://'):]
    if not _pub_db_url:
        _pub_db_url = (
            f"postgresql://{os.getenv('POSTGRES_PUBLIC_USER','postgres')}:"
            f"{os.getenv('POSTGRES_PUBLIC_PASSWORD','Passw0rdPublic')}@"
            f"{os.getenv('POSTGRES_PUBLIC_HOST','postgres_public')}:5432/"
            f"{os.getenv('POSTGRES_PUBLIC_DB','om_public')}"
        )
    SQLALCHEMY_BINDS = {'public': _pub_db_url}

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    LOG_FILE = Path(os.getenv('LOG_FILE', 'logs/app.log'))
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

    # Internationalization / Localization defaults
    HTML_LANG = os.getenv('HTML_LANG', 'pt-BR')  # BCP 47 for HTML/JS
    LANGUAGE = os.getenv('LANGUAGE', 'pt-BR')    # Used in templates/SEO
    LOCALE = os.getenv('LOCALE', 'pt_BR')        # Underscore for OG/locale

    # -----------------------------
    # Sessão e Cookies (Segurança)
    # -----------------------------
    # Em ambientes locais (http://localhost), cookies "secure" não são enviados.
    # Por isso, habilite via env quando deploy em produção (HTTPS).
    SESSION_COOKIE_NAME = os.getenv('SESSION_COOKIE_NAME', 'om_session')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE

    # Duração padrão da sessão (pode ser ajustada por preferências do usuário)
    from datetime import timedelta
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int(os.getenv('SESSION_LIFETIME_MINUTES', '30')))

    # -----------------------------
    # Cache Analytics
    # -----------------------------
    # TTL padrão para respostas de Analytics e intervalo de atualização periódica
    ANALYTICS_CACHE_TTL = int(os.getenv('ANALYTICS_CACHE_TTL', '900'))  # 15 minutos
    ANALYTICS_CACHE_REFRESH_INTERVAL_MINUTES = int(os.getenv('ANALYTICS_CACHE_REFRESH_INTERVAL_MINUTES', '15'))
    MULTILINGUAL = getenv_typed('MULTILINGUAL', lambda x: x.lower() == 'true', True)
    SUPPORTED_LOCALES = ['en_US', 'pt_BR']
    BABEL_DEFAULT_LOCALE = LOCALE
    BABEL_DEFAULT_TIMEZONE = os.getenv('BABEL_DEFAULT_TIMEZONE', 'UTC')

    NEWS_REFRESH_INTERVAL_MINUTES = int(os.getenv('NEWS_REFRESH_INTERVAL_MINUTES', '1440'))
    NEWS_FEED_SOURCES_JSON = os.getenv('NEWS_FEED_SOURCES_JSON') or (
        '{"rss_feeds":[{"url":"https://feeds.feedburner.com/TheHackersNews","tag":"rss"},'
        '{"url":"https://krebsonsecurity.com/feed/","tag":"rss"},'
        '{"url":"https://www.bleepingcomputer.com/feed/","tag":"rss"},'
        '{"url":"https://www.darkreading.com/rss.xml","tag":"rss"}],'
        '"cybernews_categories":["general","security","malware","cyberAttack","dataBreach","vulnerability"]}'
    )

    # PDF Export Configuration
    # Default engine favors 'reportlab' to avoid native dependencies in dev
    PDF_ENGINE = os.getenv('PDF_ENGINE', 'reportlab')
    # Optional wkhtmltopdf path for pdfkit engine (Windows example path)
    WKHTMLTOPDF_PATH = os.getenv('WKHTMLTOPDF_PATH')
    # Base URL used by HTML-to-PDF generators to resolve assets
    BASE_URL = os.getenv('BASE_URL', 'http://localhost:4443')
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
    
    # -----------------------------
    # Redis Cache (Opcional)
    # -----------------------------
    # Desabilitado por padrão em desenvolvimento para evitar erros quando
    # não há serviço Redis local. Pode ser habilitado via variável de ambiente.
    REDIS_CACHE_ENABLED = getenv_typed('REDIS_CACHE_ENABLED', lambda x: x.lower() == 'true', False)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
    REDIS_PORT = getenv_typed('REDIS_PORT', int, 6379)
    REDIS_DB = getenv_typed('REDIS_DB', int, 0)
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    
    # OpenAI Configuration
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    OPENAI_MAX_TOKENS = getenv_typed('OPENAI_MAX_TOKENS', int, 1000)
    OPENAI_TEMPERATURE = getenv_typed('OPENAI_TEMPERATURE', float, 0.7)
    OPENAI_TIMEOUT = getenv_typed('OPENAI_TIMEOUT', int, 30)
    OPENAI_MAX_RETRIES = getenv_typed('OPENAI_MAX_RETRIES', int, 2)
    OPENAI_RETRY_BACKOFF = getenv_typed('OPENAI_RETRY_BACKOFF', float, 1.5)
    OPENAI_STREAMING = getenv_typed('OPENAI_STREAMING', int, 0) == 1
    
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
