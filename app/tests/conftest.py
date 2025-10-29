# tests/conftest.py

import pytest
import sys
import os
from unittest.mock import Mock, patch

# Adicionar o diretório raiz ao path (raiz do projeto)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Configurações globais para testes
@pytest.fixture(scope="session")
def app():
    """Fixture para criar aplicação Flask de teste."""
    from flask import Flask
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    return app

@pytest.fixture
def client(app):
    """Fixture para cliente de teste."""
    return app.test_client()

@pytest.fixture
def mock_user():
    """Fixture para usuário mock."""
    user = Mock()
    user.id = 1
    user.email = 'test@example.com'
    user.name = 'Test User'
    return user

@pytest.fixture
def mock_report():
    """Fixture para relatório mock."""
    report = Mock()
    report.id = 1
    report.title = 'Test Report'
    report.user_id = 1
    report.content = {
        'assets': {'total_assets': 10},
        'vulnerabilities': {'total_vulnerabilities': 5}
    }
    report.ai_analysis = {}
    report.charts_data = {}
    return report

@pytest.fixture(autouse=True)
def mock_database():
    """Mock automático para operações de banco de dados."""
    with patch('app.controllers.report_controller.db') as mock_db:
        mock_db.session.add = Mock()
        mock_db.session.commit = Mock()
        mock_db.session.rollback = Mock()
        yield mock_db

# Removido mock de current_user e login_required, não utilizados no report_controller

# Configurações para pytest
def pytest_configure(config):
    """Configuração do pytest."""
    import warnings
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=PendingDeprecationWarning)

# Marcadores personalizados
# Removido pytest_plugins para compatibilidade com versões recentes do pytest