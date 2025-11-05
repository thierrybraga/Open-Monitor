# settings/production.py

import os
from .base import BaseConfig, ConfigError

class ProductionConfig(BaseConfig):
    """
    Configurações específicas para o ambiente de Produção.
    DEBUG é desativado.
    Requer que SECRET_KEY seja explicitamente definido no ambiente.
    """
    DEBUG = False

    # Em produção, habilitar cache Redis por padrão (pode ser sobrescrito via env)
    REDIS_CACHE_ENABLED = os.getenv('REDIS_CACHE_ENABLED', 'true').lower() == 'true'

    @classmethod
    def validate(cls) -> None:
        # Chama a validação da classe base primeiro
        super().validate()
        # Adiciona validação específica para produção
        if not os.getenv('SECRET_KEY'):
            raise ConfigError("SECRET_KEY must be set in production environment variables")