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
    CSP = {
        'default-src': ["'self'"],
        'script-src':  ["'self'", "'nonce-{{ csp_nonce }}'"],
        'style-src':   ["'self'"],
    }

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
