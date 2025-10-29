# settings/testing.py

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
    SQLALCHEMY_DATABASE_URI = 'sqlite:///instance/vulnerabilities.db' # Usa o mesmo banco da configuração principal
    WTF_CSRF_ENABLED = False # Comum desativar CSRF em testes de API ou formulário
    LOG_LEVEL = 'ERROR' # Reduz o output de log durante a execução dos testes