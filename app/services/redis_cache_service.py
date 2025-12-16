#!/usr/bin/env python3
"""
Serviço de cache Redis para otimização de consultas de vulnerabilidades.
Implementa cache inteligente com TTL dinâmico e invalidação automática.
"""

import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Callable
from functools import wraps
from dataclasses import dataclass
import hashlib

try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    RedisError = Exception
    RedisConnectionError = Exception

logger = logging.getLogger(__name__)

@dataclass
class CacheStats:
    """Estatísticas do cache"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    errors: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0
    
    @property
    def total_operations(self) -> int:
        return self.hits + self.misses + self.sets + self.deletes

class RedisCacheService:
    """
    Serviço de cache Redis otimizado para consultas de vulnerabilidades.
    
    Características:
    - Cache inteligente com TTL dinâmico
    - Serialização otimizada (JSON/Pickle)
    - Invalidação automática baseada em padrões
    - Estatísticas de performance
    - Fallback gracioso quando Redis não disponível
    - Compressão automática para objetos grandes
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Inicializa o serviço de cache Redis.
        
        Args:
            config: Configurações do Redis e cache
        """
        self.config = config
        self.enabled = config.get('REDIS_CACHE_ENABLED', True) and REDIS_AVAILABLE
        
        # Configurações do Redis
        self.redis_url = config.get('REDIS_URL', 'redis://localhost:6379/0')
        self.redis_host = config.get('REDIS_HOST', 'localhost')
        self.redis_port = config.get('REDIS_PORT', 6379)
        self.redis_db = config.get('REDIS_DB', 0)
        self.redis_password = config.get('REDIS_PASSWORD')
        
        # Configurações de cache
        self.default_ttl = config.get('CACHE_DEFAULT_TTL', 3600)  # 1 hora
        self.max_ttl = config.get('CACHE_MAX_TTL', 86400)  # 24 horas
        self.key_prefix = config.get('CACHE_KEY_PREFIX', 'nvd_cache:')
        
        # Configurações de serialização
        self.use_compression = config.get('CACHE_USE_COMPRESSION', True)
        self.compression_threshold = config.get('CACHE_COMPRESSION_THRESHOLD', 1024)  # bytes
        
        # Cliente Redis
        self.redis_client = None
        self.stats = CacheStats()
        
        # Inicializar conexão
        self._initialize_redis()
    
    def _initialize_redis(self):
        """Inicializa a conexão com Redis."""
        if not self.enabled:
            logger.warning("Cache Redis desabilitado ou redis-py não disponível")
            return
        
        try:
            if self.redis_url:
                self.redis_client = redis.from_url(
                    self.redis_url,
                    decode_responses=False,  # Manter bytes para pickle
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
            else:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    retry_on_timeout=True
                )
            
            # Testar conexão
            self.redis_client.ping()
            logger.info(f"Cache Redis conectado: {self.redis_url or f'{self.redis_host}:{self.redis_port}'}")
            
        except Exception as e:
            logger.error(f"Erro ao conectar Redis: {e}")
            self.enabled = False
            self.redis_client = None
    
    def _generate_cache_key(self, key: str, namespace: str = 'default') -> str:
        """Gera chave de cache com namespace e prefix."""
        return f"{self.key_prefix}{namespace}:{key}"
    
    def _serialize_data(self, data: Any) -> bytes:
        """Serializa dados para armazenamento."""
        try:
            # Tentar JSON primeiro (mais rápido e legível)
            json_data = json.dumps(data, default=str, ensure_ascii=False)
            serialized = json_data.encode('utf-8')
            
            # Se muito grande, usar pickle com compressão
            if len(serialized) > self.compression_threshold and self.use_compression:
                import gzip
                pickled = pickle.dumps(data)
                compressed = gzip.compress(pickled)
                return b'GZIP_PICKLE:' + compressed
            
            return b'JSON:' + serialized
            
        except (TypeError, ValueError):
            # Fallback para pickle
            pickled = pickle.dumps(data)
            if len(pickled) > self.compression_threshold and self.use_compression:
                import gzip
                compressed = gzip.compress(pickled)
                return b'GZIP_PICKLE:' + compressed
            return b'PICKLE:' + pickled
    
    def _deserialize_data(self, data: bytes) -> Any:
        """Deserializa dados do cache."""
        try:
            if data.startswith(b'JSON:'):
                json_str = data[5:].decode('utf-8')
                return json.loads(json_str)
            
            elif data.startswith(b'PICKLE:'):
                return pickle.loads(data[7:])
            
            elif data.startswith(b'GZIP_PICKLE:'):
                import gzip
                compressed_data = data[12:]
                decompressed = gzip.decompress(compressed_data)
                return pickle.loads(decompressed)
            
            else:
                # Tentar deserializar como JSON legacy
                return json.loads(data.decode('utf-8'))
                
        except Exception as e:
            logger.error(f"Erro ao deserializar dados do cache: {e}")
            raise
    
    def _calculate_ttl(self, data_size: int, access_frequency: float = 1.0) -> int:
        """Calcula TTL dinâmico baseado no tamanho e frequência de acesso."""
        base_ttl = self.default_ttl
        
        # Ajustar baseado no tamanho (dados maiores = TTL maior)
        if data_size > 10000:  # > 10KB
            base_ttl *= 2
        elif data_size > 100000:  # > 100KB
            base_ttl *= 3
        
        # Ajustar baseado na frequência de acesso
        base_ttl = int(base_ttl * access_frequency)
        
        # Limitar ao máximo
        return min(base_ttl, self.max_ttl)
    
    def get(self, key: str, namespace: str = 'default') -> Optional[Any]:
        """Recupera valor do cache."""
        if not self.enabled or not self.redis_client:
            return None
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            data = self.redis_client.get(cache_key)
            if data is None:
                self.stats.misses += 1
                return None
            
            result = self._deserialize_data(data)
            self.stats.hits += 1
            
            # Atualizar estatísticas de acesso
            access_key = f"{cache_key}:access_count"
            self.redis_client.incr(access_key)
            self.redis_client.expire(access_key, self.max_ttl)
            
            return result
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao recuperar {cache_key}: {e}")
            self.stats.errors += 1
            return None
        except Exception as e:
            logger.error(f"Erro ao recuperar do cache {cache_key}: {e}")
            self.stats.errors += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None, 
           namespace: str = 'default') -> bool:
        """Armazena valor no cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            serialized_data = self._serialize_data(value)
            data_size = len(serialized_data)
            
            # Calcular TTL dinâmico se não especificado
            if ttl is None:
                access_key = f"{cache_key}:access_count"
                access_count = self.redis_client.get(access_key)
                access_frequency = float(access_count or 1) / 10.0  # Normalizar
                ttl = self._calculate_ttl(data_size, access_frequency)
            
            # Armazenar dados
            success = self.redis_client.setex(cache_key, ttl, serialized_data)
            
            if success:
                self.stats.sets += 1
                
                # Armazenar metadados
                metadata = {
                    'size': data_size,
                    'created_at': time.time(),
                    'ttl': ttl
                }
                metadata_key = f"{cache_key}:metadata"
                self.redis_client.setex(
                    metadata_key, 
                    ttl, 
                    json.dumps(metadata)
                )
            
            return bool(success)
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao armazenar {cache_key}: {e}")
            self.stats.errors += 1
            return False
        except Exception as e:
            logger.error(f"Erro ao armazenar no cache {cache_key}: {e}")
            self.stats.errors += 1
            return False
    
    def delete(self, key: str, namespace: str = 'default') -> bool:
        """Remove valor do cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            # Remover dados principais e metadados
            keys_to_delete = [
                cache_key,
                f"{cache_key}:metadata",
                f"{cache_key}:access_count"
            ]
            
            deleted = self.redis_client.delete(*keys_to_delete)
            
            if deleted > 0:
                self.stats.deletes += 1
                return True
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao deletar {cache_key}: {e}")
            self.stats.errors += 1
            return False
        except Exception as e:
            logger.error(f"Erro ao deletar do cache {cache_key}: {e}")
            self.stats.errors += 1
            return False
        
        return False

    async def get_cached_vulnerabilities(self, key: str, return_count_only: bool = False):
        if not self.enabled or not self.redis_client:
            return None
        payload = self.get(key, namespace='nvd_sync')
        if payload is None:
            return None
        if return_count_only:
            try:
                if isinstance(payload, dict) and 'count' in payload:
                    return int(payload.get('count') or 0)
                if isinstance(payload, list):
                    return len(payload)
            except Exception:
                return None
        return payload

    async def cache_vulnerabilities(self, key: str, vulnerabilities, ttl: int = 3600):
        if not self.enabled or not self.redis_client:
            return False
        try:
            if isinstance(vulnerabilities, dict) and 'count' in vulnerabilities:
                payload = vulnerabilities
            elif isinstance(vulnerabilities, list):
                payload = {'count': len(vulnerabilities)}
            else:
                payload = {'count': 0}
            return self.set(key, payload, ttl=ttl, namespace='nvd_sync')
        except Exception:
            self.stats.errors += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            'enabled': self.enabled,
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'sets': self.stats.sets,
            'deletes': self.stats.deletes,
            'errors': self.stats.errors,
            'hit_rate': self.stats.hit_rate
        }
    
    def delete_pattern(self, pattern: str, namespace: str = 'default') -> int:
        """Remove múltiplas chaves baseado em padrão."""
        if not self.enabled or not self.redis_client:
            return 0
        
        cache_pattern = self._generate_cache_key(pattern, namespace)
        
        try:
            keys = self.redis_client.keys(cache_pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                self.stats.deletes += deleted
                return deleted
            return 0
            
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao deletar padrão {cache_pattern}: {e}")
            self.stats.errors += 1
            return 0
        except Exception as e:
            logger.error(f"Erro ao deletar padrão do cache {cache_pattern}: {e}")
            self.stats.errors += 1
            return 0
    
    def exists(self, key: str, namespace: str = 'default') -> bool:
        """Verifica se chave existe no cache."""
        if not self.enabled or not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            return bool(self.redis_client.exists(cache_key))
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao verificar existência {cache_key}: {e}")
            self.stats.errors += 1
            return False
    
    def get_ttl(self, key: str, namespace: str = 'default') -> int:
        """Retorna TTL restante da chave."""
        if not self.enabled or not self.redis_client:
            return -1
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            return self.redis_client.ttl(cache_key)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao obter TTL {cache_key}: {e}")
            return -1
    
    def extend_ttl(self, key: str, additional_seconds: int, 
                  namespace: str = 'default') -> bool:
        """Estende TTL de uma chave."""
        if not self.enabled or not self.redis_client:
            return False
        
        cache_key = self._generate_cache_key(key, namespace)
        
        try:
            current_ttl = self.redis_client.ttl(cache_key)
            if current_ttl > 0:
                new_ttl = min(current_ttl + additional_seconds, self.max_ttl)
                return bool(self.redis_client.expire(cache_key, new_ttl))
            return False
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Erro Redis ao estender TTL {cache_key}: {e}")
            return False
    
    def get_cache_info(self, namespace: str = 'default') -> Dict[str, Any]:
        """Retorna informações sobre o cache."""
        if not self.enabled or not self.redis_client:
            return {'enabled': False, 'error': 'Redis não disponível'}
        
        try:
            # Informações gerais do Redis
            info = self.redis_client.info()
            
            # Contar chaves do namespace
            pattern = self._generate_cache_key('*', namespace)
            keys = self.redis_client.keys(pattern)
            
            # Calcular tamanho total
            total_size = 0
            for key in keys[:100]:  # Limitar para performance
                try:
                    size = self.redis_client.memory_usage(key)
                    if size:
                        total_size += size
                except:
                    pass
            
            return {
                'enabled': True,
                'namespace': namespace,
                'total_keys': len(keys),
                'estimated_size_bytes': total_size,
                'redis_memory_used': info.get('used_memory', 0),
                'redis_memory_human': info.get('used_memory_human', 'N/A'),
                'redis_connected_clients': info.get('connected_clients', 0),
                'stats': {
                    'hits': self.stats.hits,
                    'misses': self.stats.misses,
                    'hit_rate_percent': round(self.stats.hit_rate, 2),
                    'sets': self.stats.sets,
                    'deletes': self.stats.deletes,
                    'errors': self.stats.errors,
                    'total_operations': self.stats.total_operations
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter informações do cache: {e}")
            return {'enabled': False, 'error': str(e)}
    
    def clear_namespace(self, namespace: str = 'default') -> int:
        """Limpa todas as chaves de um namespace."""
        return self.delete_pattern('*', namespace)
    
    def clear_all(self) -> bool:
        """Limpa todo o cache (CUIDADO!)."""
        if not self.enabled or not self.redis_client:
            return False
        
        try:
            pattern = f"{self.key_prefix}*"
            keys = self.redis_client.keys(pattern)
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.warning(f"Cache limpo: {deleted} chaves removidas")
                return True
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return False

def cache_result(ttl: Optional[int] = None, namespace: str = 'default', 
                key_func: Optional[Callable] = None):
    """
    Decorator para cache automático de resultados de funções.
    
    Args:
        ttl: Tempo de vida do cache
        namespace: Namespace do cache
        key_func: Função para gerar chave personalizada
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Obter instância do cache (assumindo que está disponível globalmente)
            cache_service = getattr(wrapper, '_cache_service', None)
            if not cache_service:
                # Executar função sem cache
                return func(*args, **kwargs)
            
            # Gerar chave do cache
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # Gerar chave baseada na função e argumentos
                func_name = f"{func.__module__}.{func.__name__}"
                args_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func_name}:{hashlib.md5(args_str.encode()).hexdigest()}"
            
            # Tentar recuperar do cache
            result = cache_service.get(cache_key, namespace)
            if result is not None:
                return result
            
            # Executar função e armazenar resultado
            result = func(*args, **kwargs)
            cache_service.set(cache_key, result, ttl, namespace)
            
            return result
        
        return wrapper
    return decorator
