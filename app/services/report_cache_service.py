# services/report_cache_service.py

"""
Serviço de cache e otimizações de performance para relatórios.
Implementa cache em memória, Redis e otimizações de consultas.
"""

import json
import hashlib
import logging
import pickle
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from functools import wraps
import threading
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entrada do cache."""
    key: str
    value: Any
    created_at: datetime
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: datetime = None
    size_bytes: int = 0

    def is_expired(self) -> bool:
        """Verifica se a entrada expirou."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    def touch(self):
        """Atualiza último acesso."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1


class LRUCache:
    """Cache LRU (Least Recently Used) em memória."""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache = OrderedDict()
        self.lock = threading.RLock()

    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache."""
        with self.lock:
            if key not in self.cache:
                return None
            
            entry = self.cache[key]
            
            # Verificar expiração
            if entry.is_expired():
                del self.cache[key]
                return None
            
            # Mover para o final (mais recente)
            self.cache.move_to_end(key)
            entry.touch()
            
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Define valor no cache."""
        with self.lock:
            try:
                # Calcular TTL
                expires_at = None
                if ttl or self.default_ttl:
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl or self.default_ttl)
                
                # Calcular tamanho aproximado
                size_bytes = len(pickle.dumps(value))
                
                # Criar entrada
                entry = CacheEntry(
                    key=key,
                    value=value,
                    created_at=datetime.now(timezone.utc),
                    expires_at=expires_at,
                    size_bytes=size_bytes,
                    last_accessed=datetime.now(timezone.utc)
                )
                
                # Remover entrada existente se houver
                if key in self.cache:
                    del self.cache[key]
                
                # Verificar limite de tamanho
                while len(self.cache) >= self.max_size:
                    # Remover o menos recentemente usado
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]
                
                # Adicionar nova entrada
                self.cache[key] = entry
                
                return True
                
            except Exception as e:
                logger.error(f"Erro ao definir cache para {key}: {e}")
                return False

    def delete(self, key: str) -> bool:
        """Remove entrada do cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self):
        """Limpa todo o cache."""
        with self.lock:
            self.cache.clear()

    def cleanup_expired(self):
        """Remove entradas expiradas."""
        with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do cache."""
        with self.lock:
            total_size = sum(entry.size_bytes for entry in self.cache.values())
            total_accesses = sum(entry.access_count for entry in self.cache.values())
            
            return {
                'entries': len(self.cache),
                'max_size': self.max_size,
                'total_size_bytes': total_size,
                'total_accesses': total_accesses,
                'hit_ratio': 0.0  # Seria calculado com métricas de hit/miss
            }


class ReportCacheService:
    """Serviço de cache para relatórios."""

    def __init__(self, redis_client=None):
        self.memory_cache = LRUCache(max_size=500, default_ttl=1800)  # 30 min
        self.redis_client = redis_client
        self.query_cache = LRUCache(max_size=1000, default_ttl=600)   # 10 min
        self.chart_cache = LRUCache(max_size=200, default_ttl=3600)   # 1 hora
        
        # Configurações de cache
        self.cache_config = {
            'report_data': {'ttl': 1800, 'enabled': True},      # 30 min
            'charts_data': {'ttl': 3600, 'enabled': True},       # 1 hora
            'ai_analysis': {'ttl': 7200, 'enabled': True},      # 2 horas
            'query_results': {'ttl': 600, 'enabled': True},     # 10 min
            'export_files': {'ttl': 1800, 'enabled': True},     # 30 min
        }

    def get_report_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Obtém dados de relatório do cache."""
        if not self.cache_config['report_data']['enabled']:
            return None
        
        try:
            # Tentar cache em memória primeiro
            data = self.memory_cache.get(cache_key)
            if data is not None:
                return data
            
            # Tentar Redis se disponível
            if self.redis_client:
                cached = self.redis_client.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    # Armazenar em memória para próximos acessos
                    self.memory_cache.set(cache_key, data, ttl=300)  # 5 min em memória
                    return data
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do cache {cache_key}: {e}")
            return None

    def set_report_data(self, cache_key: str, data: Dict[str, Any]) -> bool:
        """Armazena dados de relatório no cache."""
        if not self.cache_config['report_data']['enabled']:
            return False
        
        try:
            ttl = self.cache_config['report_data']['ttl']
            
            # Armazenar em memória
            self.memory_cache.set(cache_key, data, ttl=ttl)
            
            # Armazenar no Redis se disponível
            if self.redis_client:
                self.redis_client.setex(
                    cache_key,
                    ttl,
                    json.dumps(data, default=str)
                )
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao armazenar dados no cache {cache_key}: {e}")
            return False

    def get_chart_data(self, chart_key: str) -> Optional[Dict[str, Any]]:
        """Obtém dados de gráfico do cache."""
        if not self.cache_config['charts_data']['enabled']:
            return None
        
        return self.chart_cache.get(chart_key)

    def set_chart_data(self, chart_key: str, data: Dict[str, Any]) -> bool:
        """Armazena dados de gráfico no cache."""
        if not self.cache_config['charts_data']['enabled']:
            return False
        
        # Corrigir chave de configuração: usar 'charts_data' em vez de 'chart_data'
        ttl = self.cache_config['charts_data']['ttl']
        return self.chart_cache.set(chart_key, data, ttl=ttl)

    def get_query_result(self, query_hash: str) -> Optional[List[Dict[str, Any]]]:
        """Obtém resultado de consulta do cache."""
        if not self.cache_config['query_results']['enabled']:
            return None
        
        return self.query_cache.get(query_hash)

    def set_query_result(self, query_hash: str, result: List[Dict[str, Any]]) -> bool:
        """Armazena resultado de consulta no cache."""
        if not self.cache_config['query_results']['enabled']:
            return False
        
        ttl = self.cache_config['query_results']['ttl']
        return self.query_cache.set(query_hash, result, ttl=ttl)

    def invalidate_report_cache(self, report_id: int):
        """Invalida cache relacionado a um relatório específico."""
        try:
            # Padrões de chave para invalidar
            patterns = [
                f"report_{report_id}_*",
                f"chart_{report_id}_*",
                f"ai_analysis_{report_id}_*",
                f"export_{report_id}_*"
            ]
            
            # Invalidar cache em memória
            for cache in [self.memory_cache, self.chart_cache, self.query_cache]:
                keys_to_delete = []
                with cache.lock:
                    for key in cache.cache.keys():
                        for pattern in patterns:
                            if self._match_pattern(key, pattern):
                                keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    cache.delete(key)
            
            # Invalidar Redis se disponível
            if self.redis_client:
                for pattern in patterns:
                    keys = self.redis_client.keys(pattern)
                    if keys:
                        self.redis_client.delete(*keys)
            
            logger.info(f"Cache invalidado para relatório {report_id}")
            
        except Exception as e:
            logger.error(f"Erro ao invalidar cache do relatório {report_id}: {e}")

    def generate_cache_key(self, prefix: str, **kwargs) -> str:
        """Gera chave de cache baseada em parâmetros."""
        # Ordenar parâmetros para consistência
        sorted_params = sorted(kwargs.items())
        param_str = "_".join(f"{k}={v}" for k, v in sorted_params)
        
        # Gerar hash para chaves longas
        if len(param_str) > 100:
            param_hash = hashlib.md5(param_str.encode()).hexdigest()
            return f"{prefix}_{param_hash}"
        
        return f"{prefix}_{param_str}"

    def cache_query(self, ttl: int = None):
        """Decorator para cache de consultas."""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                if not self.cache_config['query_results']['enabled']:
                    return func(*args, **kwargs)
                
                # Gerar hash da consulta
                query_data = {
                    'function': func.__name__,
                    'args': str(args),
                    'kwargs': str(sorted(kwargs.items()))
                }
                query_hash = hashlib.md5(str(query_data).encode()).hexdigest()
                
                # Tentar obter do cache
                cached_result = self.get_query_result(query_hash)
                if cached_result is not None:
                    return cached_result
                
                # Executar consulta e armazenar resultado
                result = func(*args, **kwargs)
                self.set_query_result(query_hash, result)
                
                return result
            
            return wrapper
        return decorator

    def preload_report_data(self, report_ids: List[int]):
        """Pré-carrega dados de relatórios em background."""
        try:
            from services.report_data_service import ReportDataService
            data_service = ReportDataService()
            
            for report_id in report_ids:
                try:
                    # Verificar se já está em cache
                    cache_key = f"report_{report_id}_data"
                    if self.get_report_data(cache_key) is not None:
                        continue
                    
                    # Carregar dados (implementação simplificada)
                    # Em uma implementação real, isso seria feito em background
                    logger.info(f"Pré-carregando dados do relatório {report_id}")
                    
                except Exception as e:
                    logger.error(f"Erro ao pré-carregar relatório {report_id}: {e}")
            
        except Exception as e:
            logger.error(f"Erro no pré-carregamento: {e}")

    def optimize_query_performance(self, query_func):
        """Otimiza performance de consultas com cache e batching."""
        @wraps(query_func)
        def wrapper(*args, **kwargs):
            # Implementar batching se aplicável
            batch_size = kwargs.pop('batch_size', None)
            if batch_size and 'ids' in kwargs:
                ids = kwargs['ids']
                if len(ids) > batch_size:
                    # Dividir em lotes
                    results = []
                    for i in range(0, len(ids), batch_size):
                        batch_ids = ids[i:i + batch_size]
                        batch_kwargs = kwargs.copy()
                        batch_kwargs['ids'] = batch_ids
                        batch_result = query_func(*args, **batch_kwargs)
                        results.extend(batch_result if isinstance(batch_result, list) else [batch_result])
                    return results
            
            return query_func(*args, **kwargs)
        
        return wrapper

    def get_cache_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas de todos os caches."""
        stats = {
            'memory_cache': self.memory_cache.get_stats(),
            'chart_cache': self.chart_cache.get_stats(),
            'query_cache': self.query_cache.get_stats(),
            'config': self.cache_config
        }
        
        # Estatísticas do Redis se disponível
        if self.redis_client:
            try:
                redis_info = self.redis_client.info('memory')
                stats['redis'] = {
                    'used_memory': redis_info.get('used_memory', 0),
                    'used_memory_human': redis_info.get('used_memory_human', '0B'),
                    'connected_clients': self.redis_client.info('clients').get('connected_clients', 0)
                }
            except Exception as e:
                logger.error(f"Erro ao obter estatísticas do Redis: {e}")
                stats['redis'] = {'error': str(e)}
        
        return stats

    def cleanup_all_caches(self):
        """Limpa entradas expiradas de todos os caches."""
        try:
            expired_counts = {
                'memory_cache': self.memory_cache.cleanup_expired(),
                'chart_cache': self.chart_cache.cleanup_expired(),
                'query_cache': self.query_cache.cleanup_expired()
            }
            
            logger.info(f"Limpeza de cache concluída: {expired_counts}")
            return expired_counts
            
        except Exception as e:
            logger.error(f"Erro na limpeza de cache: {e}")
            return {}

    def configure_cache(self, cache_type: str, config: Dict[str, Any]) -> bool:
        """Configura parâmetros de cache."""
        try:
            if cache_type in self.cache_config:
                self.cache_config[cache_type].update(config)
                logger.info(f"Configuração de cache {cache_type} atualizada")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Erro ao configurar cache {cache_type}: {e}")
            return False

    def _match_pattern(self, text: str, pattern: str) -> bool:
        """Verifica se texto corresponde ao padrão (suporte básico a wildcards)."""
        if '*' not in pattern:
            return text == pattern
        
        # Implementação simples de wildcard
        parts = pattern.split('*')
        if len(parts) == 2:
            prefix, suffix = parts
            return text.startswith(prefix) and text.endswith(suffix)
        
        return False
