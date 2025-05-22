# settings/default.py

import os
from .base import BaseConfig

class DefaultConfig(BaseConfig):
    """
    Configuração padrão (fallback).
    Por padrão, trata-se de um build de desenvolvimento.
    """
    DEBUG = True
    TESTING = False
    SQLALCHEMY_ECHO = True           # log all SQL queries
    LOG_LEVEL = 'DEBUG'              # verbose logging level

    # Você pode sobrescrever outros atributos de BaseConfig aqui, se necessário.
    # SECRET_KEY = os.getenv('SECRET_KEY', 'you-should-override-this-in-env')
    # SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///default.db')

# Este arquivo pode opcionalmente exportar a própria classe para uso direto se necessário
# config = DefaultConfig # Esta linha não é estritamente necessária se apenas config_map em __init__.py for usado