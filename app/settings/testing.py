# settings/testing.py

import os
from .base import BaseConfig

class TestingConfig(BaseConfig):
    """
    Configurações específicas para o ambiente de Teste.
    Ativa TESTING.
    Desativa CSRF.
    Define nível de log para ERROR para reduzir ruído em testes.
    Usa um banco de dados SQLite simples.
    """
    DEBUG = False
    TESTING = True
    WTF_CSRF_ENABLED = False # Comum desativar CSRF em testes de API ou formulário
    LOG_LEVEL = 'ERROR' # Reduz o output de log durante a execução dos testes

    # Bancos de teste em SQLite (isolados na pasta instance)
    DB_FILE = str(BaseConfig.INSTANCE_PATH / 'om_test_core.sqlite')
    PUBLIC_DB_FILE = str(BaseConfig.INSTANCE_PATH / 'om_test_public.sqlite')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_FILE}"
    SQLALCHEMY_BINDS = {'public': f"sqlite:///{PUBLIC_DB_FILE}"}

    # Opções de engine para estabilidade em testes (efeito mínimo em SQLite)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('TEST_DB_POOL_SIZE', '5')),
        'max_overflow': int(os.getenv('TEST_DB_MAX_OVERFLOW', '5')),
        'pool_timeout': int(os.getenv('TEST_DB_POOL_TIMEOUT', '15')),
        'pool_recycle': int(os.getenv('TEST_DB_POOL_RECYCLE', '1800')),
        'pool_pre_ping': True,
    }
