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

    # Exibe as queries SQL no console
    SQLALCHEMY_ECHO: bool = True

    # Define nível de log para detalhamento máximo
    LOG_LEVEL: str = 'DEBUG'