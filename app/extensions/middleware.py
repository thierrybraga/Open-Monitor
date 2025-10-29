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
            'user_id': None,
            'is_authenticated': False,
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', ''),
            'endpoint': request.endpoint
        }
        
        # Log da sessão para auditoria
        logger.debug(f"Accessing {request.endpoint} from {request.remote_addr}")
    
    def after_request(self, response):
        """Executado após cada requisição."""
        # Log de resposta para auditoria
        if hasattr(g, 'user_session'):
            logger.debug(f"Response {response.status_code} on {g.user_session['endpoint']}")
        
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
            resource_id = kwargs.get(id_param)
            if not resource_id:
                abort(400, description="ID do recurso não fornecido")
            
            # Exigir autenticação
            if not current_user.is_authenticated:
                abort(401, description="Autenticação necessária")
            
            try:
                resource = model_class.query.get_or_404(resource_id)
                owner_id = getattr(resource, owner_field, None)
                is_owner = (owner_id == current_user.id)
                
                # Permitir acesso apenas ao dono ou administradores
                if not (getattr(current_user, 'is_admin', False) or is_owner):
                    abort(403, description="Acesso negado: recurso não pertence ao usuário")
                
                # Adicionar o recurso ao contexto para uso na função
                g.current_resource = resource
                
                return f(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Error accessing resource: {e}")
                abort(500, description="Erro interno do servidor")
        
        return decorated_function
    return decorator

def require_asset_ownership(f: Callable) -> Callable:
    """
    Decorator específico para verificar propriedade de assets.
    """
    from app.models.asset import Asset
    return require_user_ownership(Asset, 'asset_id', 'owner_id')(f)

def filter_by_user_assets(query, user_id=None):
    """
    Filtra uma query para incluir apenas ativos do usuário autenticado.
    
    Args:
        query: Query SQLAlchemy (espera-se que seja baseada em Asset)
        user_id: ID do usuário-alvo (opcional). Se não informado, usa o usuário atual.
    
    Returns:
        Query filtrada por owner_id do usuário, ou vazia se não autenticado.
    """
    from app.models.asset import Asset
    
    # Determinar usuário alvo
    uid = user_id if user_id is not None else (current_user.id if current_user.is_authenticated else None)
    
    if uid is None:
        # Usuário não autenticado: não retornar ativos
        return query.filter(Asset.owner_id == -1)
    
    # Administradores enxergam todos quando user_id não foi explicitado
    if getattr(current_user, 'is_admin', False) and user_id is None:
        return query
    
    # Filtrar por ativos do usuário
    return query.filter(Asset.owner_id == uid)

def audit_log(action: str, resource_type: str = None, resource_id: str = None, details: dict = None):
    """
    Registra ações do usuário para auditoria.
    
    Args:
        action: Ação realizada (create, read, update, delete)
        resource_type: Tipo do recurso (asset, vulnerability, etc.)
        resource_id: ID do recurso
        details: Detalhes adicionais da ação
    """
    log_data = {
        'user_id': None,
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