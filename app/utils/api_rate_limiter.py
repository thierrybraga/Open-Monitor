#!/usr/bin/env python3
"""
Middleware de rate limiting para Flask API
"""

import time
import logging
from functools import wraps
from typing import Dict, Optional, Callable, Any
from flask import request, jsonify, g
from werkzeug.exceptions import TooManyRequests
from app.utils.rate_limiter import RateLimitConfig, AdvancedRateLimiter
from app.config.rate_limiter_config import get_rate_limiter_config

logger = logging.getLogger(__name__)

class FlaskRateLimiter:
    """
    Rate limiter para aplicações Flask
    """
    
    def __init__(self, app=None, config=None):
        self.app = app
        self.limiters: Dict[str, AdvancedRateLimiter] = {}
        self.config = config or get_rate_limiter_config()
        self.default_config = RateLimitConfig(
            requests=100,
            window_seconds=60,
            burst_allowance=10,
            backoff_factor=1.5,
            max_backoff=300.0,
            jitter=True
        )
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """
        Inicializa o rate limiter com a aplicação Flask
        """
        self.app = app
        
        # Configurações padrão
        app.config.setdefault('RATE_LIMIT_ENABLED', True)
        app.config.setdefault('RATE_LIMIT_STORAGE', 'memory')  # memory, redis, etc.
        app.config.setdefault('RATE_LIMIT_STRATEGY', 'ip')  # ip, user, endpoint
        
        # Registrar middleware
        app.before_request(self._before_request)
        app.after_request(self._after_request)
    
    def _get_client_id(self) -> str:
        """
        Obtém identificador único do cliente
        """
        strategy = self.config.RATE_LIMIT_STRATEGY
        
        if strategy == 'ip':
            # Considera proxy headers
            return (
                request.headers.get('X-Forwarded-For', '')
                .split(',')[0].strip() or
                request.headers.get('X-Real-IP', '') or
                request.remote_addr or
                'unknown'
            )
        elif strategy == 'user':
            # Baseado no usuário autenticado
            user_id = getattr(g, 'user_id', None)
            if user_id:
                return f"user_{user_id}"
            # Fallback para IP se não autenticado
            return self._get_client_id_by_ip()
        elif strategy == 'endpoint':
            # Baseado no path da requisição para categorizar corretamente
            path = getattr(request, 'path', None) or 'unknown'
            return f"endpoint_{path}"
        else:
            return request.remote_addr or 'unknown'
    
    def _get_client_id_by_ip(self) -> str:
        """
        Obtém ID do cliente baseado no IP
        """
        return (
            request.headers.get('X-Forwarded-For', '')
            .split(',')[0].strip() or
            request.headers.get('X-Real-IP', '') or
            request.remote_addr or
            'unknown'
        )
    
    def _get_limiter(self, client_id: str, config: Optional[RateLimitConfig] = None, endpoint: str = None) -> AdvancedRateLimiter:
        """
        Obtém ou cria um rate limiter para o cliente
        """
        if client_id not in self.limiters:
            if config is None:
                # Get endpoint-specific configuration
                endpoint_config = self.config.get_rate_limit_for_endpoint(endpoint or '')
                limiter_config = RateLimitConfig(
                    requests=endpoint_config['requests'],
                    window_seconds=endpoint_config['window'],
                    burst_allowance=10,
                    backoff_factor=1.5,
                    max_backoff=300.0,
                    jitter=True
                )
            else:
                limiter_config = config
            
            self.limiters[client_id] = AdvancedRateLimiter(
                limiter_config, 
                f"Flask API ({client_id})"
            )
        
        return self.limiters[client_id]
    
    def _before_request(self):
        """
        Middleware executado antes de cada requisição
        """
        logger.info(f"Rate limiter _before_request called for {request.path}")
        
        if not self.app.config.get('RATE_LIMIT_ENABLED', True):
            logger.info("Rate limiting disabled in config")
            return
        
        # Pular rate limiting para rotas específicas
        if self._should_skip_rate_limiting():
            logger.info(f"Skipping rate limiting for {request.path}")
            return
        
        logger.info(f"Applying rate limiting to {request.path}")
        
        client_id = self._get_client_id()
        # Use request.path para obter configuração específica por categoria (/api, /auth, etc.)
        limiter = self._get_limiter(client_id, endpoint=request.path)
        
        # Verificar se pode fazer a requisição
        now = time.time()
        limiter._cleanup_old_requests(now)
        wait_time = limiter._calculate_wait_time(now)
        
        if wait_time > 0:
            # Rate limit excedido
            stats = limiter.get_stats()
            
            logger.warning(
                f"Rate limit excedido para {client_id}. "
                f"Endpoint: {request.endpoint}, "
                f"Aguardando: {wait_time:.2f}s"
            )
            
            # Retornar erro 429
            response = jsonify({
                'error': 'Rate limit exceeded',
                'message': f'Too many requests. Try again in {wait_time:.0f} seconds.',
                'retry_after': int(wait_time) + 1,
                'stats': {
                    'requests_in_window': stats['requests_in_window'],
                    'window_utilization': f"{stats['window_utilization']:.1f}%"
                }
            })
            response.status_code = 429
            response.headers['Retry-After'] = str(int(wait_time) + 1)
            response.headers['X-RateLimit-Limit'] = str(limiter.config.requests)
            response.headers['X-RateLimit-Remaining'] = str(
                max(0, limiter.config.requests - len(limiter.request_times))
            )
            response.headers['X-RateLimit-Reset'] = str(
                int(now + limiter.config.window_seconds)
            )
            
            raise TooManyRequests(response=response)
        
        # Registrar a requisição
        limiter.request_times.append(now)
        limiter.stats['total_requests'] += 1
        
        # Armazenar limiter no contexto da requisição
        g.rate_limiter = limiter
        g.rate_limiter_endpoint_path = request.path
    
    def _after_request(self, response):
        """
        Middleware executado após cada requisição
        """
        if not self.app.config.get('RATE_LIMIT_ENABLED', True):
            return response
        
        # Adicionar headers de rate limiting
        if hasattr(g, 'rate_limiter') and self.config.INCLUDE_HEADERS:
            limiter = g.rate_limiter
            now = time.time()
            # Utilize o path para determinar a categoria de rate limit
            endpoint_path = getattr(g, 'rate_limiter_endpoint_path', '')
            endpoint_config = self.config.get_rate_limit_for_endpoint(endpoint_path or '')
            
            response.headers['X-RateLimit-Limit'] = str(endpoint_config['requests'])
            response.headers['X-RateLimit-Remaining'] = str(
                max(0, limiter.config.requests - len(limiter.request_times))
            )
            response.headers['X-RateLimit-Reset'] = str(
                int(now + limiter.config.window_seconds)
            )
            response.headers['X-RateLimit-Window'] = str(endpoint_config['window'])
        
        return response
    
    def _should_skip_rate_limiting(self) -> bool:
        """
        Determina se deve pular o rate limiting para a requisição atual
        """
        # Check if rate limiting is enabled
        if not self.config.RATE_LIMITING_ENABLED:
            logger.info(f"Rate limiting disabled in config: {self.config.RATE_LIMITING_ENABLED}")
            return True
        
        # Skip for configured routes
        if self.config.should_skip_route(request.path):
            logger.info(f"Skipping route {request.path} - in skip list")
            return True
        
        # Skip for whitelisted IPs
        client_ip = self._get_client_id_by_ip()
        if self.config.is_whitelisted_ip(client_ip):
            logger.info(f"Skipping IP {client_ip} - whitelisted")
            return True
        
        logger.info(f"Rate limiting should be applied to {request.path} from {client_ip}")
        return False
    
    def limit(self, requests: int, window: int = 60, **kwargs):
        """
        Decorator para aplicar rate limiting específico a uma rota
        
        Args:
            requests: Número de requisições permitidas
            window: Janela de tempo em segundos
            **kwargs: Argumentos adicionais para RateLimitConfig
        """
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if not self.app.config.get('RATE_LIMIT_ENABLED', True):
                    return f(*args, **kwargs)
                
                client_id = self._get_client_id()
                
                # Criar configuração específica para esta rota
                config = RateLimitConfig(
                    requests=requests,
                    window_seconds=window,
                    **kwargs
                )
                
                # Usar limiter específico para esta rota
                route_key = f"{client_id}_{request.endpoint}"
                limiter = self._get_limiter(route_key, config)
                
                # Verificar rate limit
                now = time.time()
                limiter._cleanup_old_requests(now)
                wait_time = limiter._calculate_wait_time(now)
                
                if wait_time > 0:
                    logger.warning(
                        f"Rate limit específico excedido para {client_id} "
                        f"na rota {request.endpoint}"
                    )
                    
                    return jsonify({
                        'error': 'Rate limit exceeded',
                        'message': f'Too many requests for this endpoint. Try again in {wait_time:.0f} seconds.',
                        'retry_after': int(wait_time) + 1
                    }), 429
                
                # Registrar requisição
                limiter.request_times.append(now)
                limiter.stats['total_requests'] += 1
                
                return f(*args, **kwargs)
            
            return decorated_function
        return decorator
    
    def get_stats(self, client_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtém estatísticas de rate limiting
        
        Args:
            client_id: ID específico do cliente (opcional)
            
        Returns:
            Dicionário com estatísticas
        """
        if client_id and client_id in self.limiters:
            return self.limiters[client_id].get_stats()
        
        # Retornar estatísticas agregadas
        total_stats = {
            'total_clients': len(self.limiters),
            'total_requests': 0,
            'total_rate_limited': 0,
            'clients': {}
        }
        
        for cid, limiter in self.limiters.items():
            stats = limiter.get_stats()
            total_stats['total_requests'] += stats['total_requests']
            total_stats['total_rate_limited'] += stats['rate_limited_requests']
            total_stats['clients'][cid] = stats
        
        return total_stats
    
    def reset_stats(self, client_id: Optional[str] = None) -> None:
        """
        Reseta estatísticas de rate limiting
        
        Args:
            client_id: ID específico do cliente (opcional)
        """
        if client_id and client_id in self.limiters:
            self.limiters[client_id].reset_stats()
        else:
            for limiter in self.limiters.values():
                limiter.reset_stats()
    
    def cleanup_old_limiters(self, max_age: int = 3600) -> int:
        """
        Remove limiters antigos para economizar memória
        
        Args:
            max_age: Idade máxima em segundos
            
        Returns:
            Número de limiters removidos
        """
        now = time.time()
        removed = 0
        
        # Identificar limiters para remoção
        to_remove = []
        for client_id, limiter in self.limiters.items():
            if limiter.request_times:
                last_request = max(limiter.request_times)
                if now - last_request > max_age:
                    to_remove.append(client_id)
            elif now - limiter.stats.get('created_at', now) > max_age:
                to_remove.append(client_id)
        
        # Remover limiters antigos
        for client_id in to_remove:
            del self.limiters[client_id]
            removed += 1
        
        if removed > 0:
            logger.info(f"Removidos {removed} rate limiters antigos")
        
        return removed

# Instância global para uso fácil
rate_limiter = FlaskRateLimiter()
