# settings/__init__.py

# Importações relativas para módulos dentro do mesmo pacote 'settings'
from .base import BaseConfig
from .development import DevelopmentConfig
from .testing import TestingConfig
from .production import ProductionConfig
from .default import DefaultConfig

config_map = {
    'development': DevelopmentConfig,
    'testing':     TestingConfig,
    'production':  ProductionConfig,
    'default':     DefaultConfig # Default fallback configuration
}