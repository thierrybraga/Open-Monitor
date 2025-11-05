# controllers/__init__.py

"""
Pacote de controllers da aplicação.
Importa e lista todos os Blueprints a serem registrados na aplicação Flask.
"""

from flask import Blueprint
from typing import List

# Importações relativas dos Blueprints dos módulos de controller individuais
from app.controllers.main_controller import main_bp
from app.controllers.auth_controller import auth_bp
from app.controllers.asset_controller import asset_bp
from app.controllers.monitoring_controller import monitoring_bp

from app.controllers.api_controller import api_v1_bp

# Importação dos objetos Blueprint do vulnerability_controller
from app.controllers.vulnerability_controller import vuln_ui_bp, vuln_api_bp, vuln_api_legacy_bp

# Importação do Blueprint do analytics_controller
from app.controllers.analytics_controller import analytics_api_bp
from app.controllers.insights_controller import insights_api_bp

# Importação do Blueprint do newsletter_admin_controller
from app.controllers.newsletter_admin_controller import newsletter_admin_bp

# Importação do Blueprint do chat_controller
from app.controllers.chat_controller import chat_bp

# Importação do Blueprint do report_controller
from app.controllers.report_controller import report_bp

# Lista de todos os Blueprints a serem registrados pela aplicação
BLUEPRINTS: List[Blueprint] = [
    main_bp,
    auth_bp,
    asset_bp,
    monitoring_bp,

    vuln_ui_bp,
    vuln_api_bp,
    vuln_api_legacy_bp,
    api_v1_bp,
    analytics_api_bp,
    insights_api_bp,
    newsletter_admin_bp,
    chat_bp,
    report_bp,
]

# Opcional: Você pode listar explicitamente os Blueprints em __all__
# __all__ = [bp.name for bp in BLUEPRINTS]
