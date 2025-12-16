# settings/development.py

from .base import BaseConfig

class DevelopmentConfig(BaseConfig):
    """
    Configurações específicas para o ambiente de Desenvolvimento.

    - Ativa DEBUG e SQLAlchemy Echo.
    - Define nível de log para DEBUG.
    """

    # Ativa o modo debug do Flask
    DEBUG: bool = True

    # Disable SQL query logging for cleaner output
    SQLALCHEMY_ECHO: bool = False

    DB_FILE = str(BaseConfig.INSTANCE_PATH / 'om_dev_core.sqlite')
    PUBLIC_DB_FILE = str(BaseConfig.INSTANCE_PATH / 'om_dev_public.sqlite')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_FILE}"
    SQLALCHEMY_BINDS = {'public': f"sqlite:///{PUBLIC_DB_FILE}"}

    # Engine options para estabilidade em dev (evita conexões zumbis)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_size': 5,
        'max_overflow': 5,
        'pool_timeout': 15,
        'pool_recycle': 1800,
    }

    # Define nível de log para detalhamento máximo
    LOG_LEVEL: str = 'DEBUG'
