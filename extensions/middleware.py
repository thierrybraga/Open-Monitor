import logging
from functools import wraps
from flask import request, jsonify, abort, current_app, g
from flask_login import current_user
from typing import Callable, Any

logger = logging.getLogger(__name__)

class SessionMiddleware:
    """
    Middleware para controle de sessão e acesso baseado em usuário.
    """
    
    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Inicializa o middleware com a aplicação Flask."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        logger.debug("Session middleware initialized.")
    
    def before_request(self):
        """Executado antes de cada requisição."""
        # Armazenar informações da sessão no contexto global
        g.user_session = {
            'user_id': current_user.id if current_user.is_authenticated else None,
            'is_authenticated': current_user.is_authenticated,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'endpoint': request.endpoint
        }
        
        # Log da sessão para auditoria
        if current_user.is_authenticated:
            logger.debug(f"User {current_user.id} accessing {request.endpoint} from {request.remote_addr}")
    
    def after_request(self, response):
        """Executado após cada requisição."""
        # Log de resposta para auditoria
        if hasattr(g, 'user_session') and g.user_session['is_authenticated']:
            logger.debug(f"Response {response.status_code} for user {g.user_session['user_id']} on {g.user_session['endpoint']}")
        
        return response

def require_user_ownership(model_class, id_param='id', owner_field='owner_id'):
    """
    Decorator para garantir que o usuário só possa acessar recursos que possui.
    
    Args:
        model_class: Classe do modelo a ser verificado
        id_param: Nome do parâmetro que contém o ID do recurso
        owner_field: Nome do campo que contém o ID do proprietário
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            
            resource_id = kwargs.get(id_param)
            if not resource_id:
                abort(400, description="ID do recurso não fornecido")
            
            try:
                resource = model_class.query.get_or_404(resource_id)
                
                # Verificar se o usuário é o proprietário do recurso
                if getattr(resource, owner_field) != current_user.id:
                    logger.warning(f"User {current_user.id} attempted to access resource {resource_id} owned by {getattr(resource, owner_field)}")
                    abort(403, description="Acesso negado: você não tem permissão para acessar este recurso")
                
                # Adicionar o recurso ao contexto para uso na função
                g.current_resource = resource
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error checking resource ownership: {e}")
                abort(500, description="Erro interno do servidor")
        
        return decorated_function
    return decorator

def require_asset_ownership(f: Callable) -> Callable:
    """
    Decorator específico para verificar propriedade de assets.
    """
    from models.asset import Asset
    return require_user_ownership(Asset, 'asset_id', 'owner_id')(f)

def filter_by_user_assets(query, user_id=None):
    """
    Filtra uma query para incluir apenas dados relacionados aos assets do usuário.
    
    Args:
        query: Query SQLAlchemy
        user_id: ID do usuário (usa current_user.id se não fornecido)
    
    Returns:
        Query filtrada
    """
    if user_id is None:
        if not current_user.is_authenticated:
            return query.filter(False)  # Retorna query vazia
        user_id = current_user.id
    
    from models.asset import Asset
    from models.asset_vulnerability import AssetVulnerability
    
    # Assumindo que a query é para vulnerabilidades
    return query.join(
        AssetVulnerability, query.column_descriptions[0]['type'].cve_id == AssetVulnerability.vulnerability_id
    ).join(
        Asset, AssetVulnerability.asset_id == Asset.id
    ).filter(
        Asset.owner_id == user_id
    )

def audit_log(action: str, resource_type: str = None, resource_id: str = None, details: dict = None):
    """
    Registra ações do usuário para auditoria.
    
    Args:
        action: Ação realizada (create, read, update, delete)
        resource_type: Tipo do recurso (asset, vulnerability, etc.)
        resource_id: ID do recurso
        details: Detalhes adicionais da ação
    """
    user_id = current_user.id if current_user.is_authenticated else None
    
    log_data = {
        'user_id': user_id,
        'action': action,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'ip_address': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', ''),
        'endpoint': request.endpoint,
        'details': details or {}
    }
    
    logger.info(f"AUDIT: {log_data}")

# Instância global do middleware
session_middleware = SessionMiddleware()