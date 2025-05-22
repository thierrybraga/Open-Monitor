# controllers/__init__.py

"""
Pacote de controllers da aplicação.
Importa e lista todos os Blueprints a serem registrados na aplicação Flask.
"""

from flask import Blueprint
from typing import List

# Importações relativas dos Blueprints dos módulos de controller individuais
from .main_controller import main_bp
from .auth_controller import auth_bp
from .asset_controller import asset_bp
from .monitoring_controller import monitoring_bp
from .report_controller import report_bp
from .api_controller import api_v1_bp

# Importação dos objetos Blueprint do vulnerability_controller
from .vulnerability_controller import vuln_ui_bp, vuln_api_bp

# Lista de todos os Blueprints a serem registrados pela aplicação
BLUEPRINTS: List[Blueprint] = [
    main_bp,
    auth_bp,
    asset_bp,
    monitoring_bp,
    report_bp,
    vuln_ui_bp,
    vuln_api_bp,
    api_v1_bp,
]

# Opcional: Você pode listar explicitamente os Blueprints em __all__
# __all__ = [bp.name for bp in BLUEPRINTS]