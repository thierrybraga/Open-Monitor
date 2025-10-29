#!/usr/bin/env python3
"""
Sistema de retry com backoff exponencial para operações robustas.
Implementa estratégias inteligentes de retry para APIs e banco de dados.
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps

import aiohttp
from sqlalchemy.exc import SQLAlchemyError, OperationalError, IntegrityError

logger = logging.getLogger(__name__)

class RetryStrategy(Enum):
    """Estratégias de retry disponíveis"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    FIBONACCI = "fibonacci"
    CUSTOM = "custom"

class ErrorCategory(Enum):
    """Categorias de erro para diferentes estratégias"""
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    DATABASE = "database"
    AUTHENTICATION = "authentication"
    CLIENT_ERROR = "client_error"
    UNKNOWN = "unknown"

@dataclass
class RetryConfig:
    """Configuração de retry"""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    jitter_range: float = 0.1
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retryable_exceptions: Tuple[type, ...] = (Exception,)
    non_retryable_exceptions: Tuple[type, ...] = ()
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
    non_retryable_status_codes: Tuple[int, ...] = (400, 401, 403, 404)
    custom_delay_func: Optional[Callable[[int], float]] = None
    
@dataclass
class RetryAttempt:
    """Informações sobre uma tentativa de retry"""
    attempt_number: int
    delay: float
    exception: Optional[Exception] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    duration: Optional[float] = None
    
@dataclass
class RetryStats:
    """Estatísticas de retry"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_delay: float = 0.0
    attempts_history: List[RetryAttempt] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return (self.successful_attempts / self.total_attempts) * 100
    
    @property
    def total_duration(self) -> float:
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

class RetryService:
    """
    Serviço de retry com backoff exponencial e estratégias inteligentes.
    
    Características:
    - Múltiplas estratégias de backoff
    - Jitter para evitar thundering herd
    - Categorização inteligente de erros
    - Configurações específicas por tipo de operação
    - Estatísticas detalhadas
    - Suporte para operações síncronas e assíncronas
    """
    
    def __init__(self):
        self.configs = self._get_default_configs()
        self.stats = {}
        
    def _get_default_configs(self) -> Dict[ErrorCategory, RetryConfig]:
        """Retorna configurações padrão por categoria de erro."""
        return {
            ErrorCategory.NETWORK: RetryConfig(
                max_attempts=5,
                base_delay=1.0,
                max_delay=30.0,
                backoff_multiplier=2.0,
                retryable_exceptions=(aiohttp.ClientError, ConnectionError, TimeoutError),
                non_retryable_exceptions=(aiohttp.ClientResponseError,)
            ),
            
            ErrorCategory.RATE_LIMIT: RetryConfig(
                max_attempts=10,
                base_delay=5.0,
                max_delay=300.0,
                backoff_multiplier=1.5,
                strategy=RetryStrategy.LINEAR,
                retryable_status_codes=(429,),
                jitter_range=0.2
            ),
            
            ErrorCategory.SERVER_ERROR: RetryConfig(
                max_attempts=3,
                base_delay=2.0,
                max_delay=60.0,
                backoff_multiplier=2.5,
                retryable_status_codes=(500, 502, 503, 504)
            ),
            
            ErrorCategory.DATABASE: RetryConfig(
                max_attempts=3,
                base_delay=0.5,
                max_delay=10.0,
                backoff_multiplier=2.0,
                retryable_exceptions=(OperationalError, SQLAlchemyError),
                non_retryable_exceptions=(IntegrityError,)
            ),
            
            ErrorCategory.AUTHENTICATION: RetryConfig(
                max_attempts=2,
                base_delay=1.0,
                max_delay=5.0,
                retryable_status_codes=(401,),
                non_retryable_status_codes=(403,)
            )
        }
    
    def categorize_error(self, exception: Exception, 
                        status_code: Optional[int] = None) -> ErrorCategory:
        """
        Categoriza um erro para aplicar a estratégia apropriada.
        
        Args:
            exception: Exceção ocorrida
            status_code: Código de status HTTP (se aplicável)
            
        Returns:
            Categoria do erro
        """
        # Verificar código de status primeiro
        if status_code:
            if status_code == 429:
                return ErrorCategory.RATE_LIMIT
            elif status_code in (500, 502, 503, 504):
                return ErrorCategory.SERVER_ERROR
            elif status_code in (401, 403):
                return ErrorCategory.AUTHENTICATION
            elif 400 <= status_code < 500:
                return ErrorCategory.CLIENT_ERROR
        
        # Verificar tipo de exceção
        if isinstance(exception, (ConnectionError, TimeoutError, aiohttp.ClientError)):
            return ErrorCategory.NETWORK
        elif isinstance(exception, (OperationalError, SQLAlchemyError)):
            return ErrorCategory.DATABASE
        
        return ErrorCategory.UNKNOWN
    
    def calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """
        Calcula o delay para uma tentativa específica.
        
        Args:
            attempt: Número da tentativa (começando em 1)
            config: Configuração de retry
            
        Returns:
            Delay em segundos
        """
        if config.custom_delay_func:
            delay = config.custom_delay_func(attempt)
        elif config.strategy == RetryStrategy.EXPONENTIAL:
            delay = config.base_delay * (config.backoff_multiplier ** (attempt - 1))
        elif config.strategy == RetryStrategy.LINEAR:
            delay = config.base_delay * attempt
        elif config.strategy == RetryStrategy.FIXED:
            delay = config.base_delay
        elif config.strategy == RetryStrategy.FIBONACCI:
            delay = config.base_delay * self._fibonacci(attempt)
        else:
            delay = config.base_delay
        
        # Aplicar limite máximo
        delay = min(delay, config.max_delay)
        
        # Aplicar jitter se habilitado
        if config.jitter:
            jitter_amount = delay * config.jitter_range
            jitter = random.uniform(-jitter_amount, jitter_amount)
            delay = max(0, delay + jitter)
        
        return delay
    
    def _fibonacci(self, n: int) -> int:
        """Calcula o n-ésimo número de Fibonacci."""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
    
    def should_retry(self, exception: Exception, attempt: int, 
                   config: RetryConfig, status_code: Optional[int] = None) -> bool:
        """
        Determina se uma operação deve ser repetida.
        
        Args:
            exception: Exceção ocorrida
            attempt: Número da tentativa atual
            config: Configuração de retry
            status_code: Código de status HTTP (se aplicável)
            
        Returns:
            True se deve tentar novamente
        """
        # Verificar limite de tentativas
        if attempt >= config.max_attempts:
            return False
        
        # Verificar exceções não retryáveis
        if config.non_retryable_exceptions and isinstance(exception, config.non_retryable_exceptions):
            return False
        
        # Verificar códigos de status não retryáveis
        if status_code and config.non_retryable_status_codes and status_code in config.non_retryable_status_codes:
            return False
        
        # Verificar exceções retryáveis
        if config.retryable_exceptions and isinstance(exception, config.retryable_exceptions):
            return True
        
        # Verificar códigos de status retryáveis
        if status_code and config.retryable_status_codes and status_code in config.retryable_status_codes:
            return True
        
        # Padrão: não retry para exceções não categorizadas
        return False
    
    def retry_sync(self, func: Callable, *args, 
                  category: Optional[ErrorCategory] = None,
                  config: Optional[RetryConfig] = None,
                  **kwargs) -> Any:
        """
        Executa uma função com retry síncrono.
        
        Args:
            func: Função a ser executada
            *args: Argumentos posicionais
            category: Categoria do erro (opcional)
            config: Configuração customizada (opcional)
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
        """
        stats = RetryStats(start_time=datetime.utcnow())
        
        for attempt in range(1, (config or self.configs.get(category or ErrorCategory.UNKNOWN, RetryConfig())).max_attempts + 1):
            try:
                stats.total_attempts += 1
                start_time = time.time()
                
                result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                stats.successful_attempts += 1
                stats.end_time = datetime.utcnow()
                
                # Registrar tentativa bem-sucedida
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    delay=0.0,
                    duration=duration
                )
                stats.attempts_history.append(retry_attempt)
                
                # Salvar estatísticas
                func_name = getattr(func, '__name__', str(func))
                self.stats[func_name] = stats
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                stats.failed_attempts += 1
                
                # Determinar categoria se não fornecida
                if category is None:
                    status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                    category = self.categorize_error(e, status_code)
                
                # Obter configuração
                retry_config = config or self.configs.get(category, RetryConfig())
                
                # Verificar se deve tentar novamente
                status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                if not self.should_retry(e, attempt, retry_config, status_code):
                    stats.end_time = datetime.utcnow()
                    
                    # Registrar tentativa final falhada
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        delay=0.0,
                        exception=e,
                        duration=duration
                    )
                    stats.attempts_history.append(retry_attempt)
                    
                    # Salvar estatísticas
                    func_name = getattr(func, '__name__', str(func))
                    self.stats[func_name] = stats
                    
                    raise e
                
                # Calcular delay
                delay = self.calculate_delay(attempt, retry_config)
                stats.total_delay += delay
                
                # Registrar tentativa falhada
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    delay=delay,
                    exception=e,
                    duration=duration
                )
                stats.attempts_history.append(retry_attempt)
                
                logger.warning(f"Tentativa {attempt} falhou para {func.__name__}: {e}. "
                             f"Tentando novamente em {delay:.2f}s")
                
                # Aguardar antes da próxima tentativa
                if attempt < retry_config.max_attempts:
                    time.sleep(delay)
        
        # Se chegou aqui, todas as tentativas falharam
        stats.end_time = datetime.utcnow()
        func_name = getattr(func, '__name__', str(func))
        self.stats[func_name] = stats
        
        raise Exception(f"Todas as {retry_config.max_attempts} tentativas falharam")
    
    async def retry_async(self, func: Callable, *args,
                         category: Optional[ErrorCategory] = None,
                         config: Optional[RetryConfig] = None,
                         **kwargs) -> Any:
        """
        Executa uma função com retry assíncrono.
        
        Args:
            func: Função assíncrona a ser executada
            *args: Argumentos posicionais
            category: Categoria do erro (opcional)
            config: Configuração customizada (opcional)
            **kwargs: Argumentos nomeados
            
        Returns:
            Resultado da função
        """
        stats = RetryStats(start_time=datetime.utcnow())
        
        for attempt in range(1, (config or self.configs.get(category or ErrorCategory.UNKNOWN, RetryConfig())).max_attempts + 1):
            try:
                stats.total_attempts += 1
                start_time = time.time()
                
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                duration = time.time() - start_time
                stats.successful_attempts += 1
                stats.end_time = datetime.utcnow()
                
                # Registrar tentativa bem-sucedida
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    delay=0.0,
                    duration=duration
                )
                stats.attempts_history.append(retry_attempt)
                
                # Salvar estatísticas
                func_name = getattr(func, '__name__', str(func))
                self.stats[func_name] = stats
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                stats.failed_attempts += 1
                
                # Determinar categoria se não fornecida
                if category is None:
                    status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                    category = self.categorize_error(e, status_code)
                
                # Obter configuração
                retry_config = config or self.configs.get(category, RetryConfig())
                
                # Verificar se deve tentar novamente
                status_code = getattr(e, 'status', None) or getattr(e, 'status_code', None)
                if not self.should_retry(e, attempt, retry_config, status_code):
                    stats.end_time = datetime.utcnow()
                    
                    # Registrar tentativa final falhada
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        delay=0.0,
                        exception=e,
                        duration=duration
                    )
                    stats.attempts_history.append(retry_attempt)
                    
                    # Salvar estatísticas
                    func_name = getattr(func, '__name__', str(func))
                    self.stats[func_name] = stats
                    
                    raise e
                
                # Calcular delay
                delay = self.calculate_delay(attempt, retry_config)
                stats.total_delay += delay
                
                # Registrar tentativa falhada
                retry_attempt = RetryAttempt(
                    attempt_number=attempt,
                    delay=delay,
                    exception=e,
                    duration=duration
                )
                stats.attempts_history.append(retry_attempt)
                
                logger.warning(f"Tentativa {attempt} falhou para {func.__name__}: {e}. "
                             f"Tentando novamente em {delay:.2f}s")
                
                # Aguardar antes da próxima tentativa
                if attempt < retry_config.max_attempts:
                    await asyncio.sleep(delay)
        
        # Se chegou aqui, todas as tentativas falharam
        stats.end_time = datetime.utcnow()
        func_name = getattr(func, '__name__', str(func))
        self.stats[func_name] = stats
        
        raise Exception(f"Todas as {retry_config.max_attempts} tentativas falharam")
    
    def get_stats(self, func_name: Optional[str] = None) -> Union[Dict[str, RetryStats], RetryStats]:
        """
        Retorna estatísticas de retry.
        
        Args:
            func_name: Nome da função (opcional, retorna todas se None)
            
        Returns:
            Estatísticas da função ou todas as estatísticas
        """
        if func_name:
            return self.stats.get(func_name, RetryStats())
        return self.stats
    
    def clear_stats(self, func_name: Optional[str] = None):
        """
        Limpa estatísticas de retry.
        
        Args:
            func_name: Nome da função (opcional, limpa todas se None)
        """
        if func_name:
            self.stats.pop(func_name, None)
        else:
            self.stats.clear()

# Decoradores para facilitar o uso
def retry(category: Optional[ErrorCategory] = None,
         config: Optional[RetryConfig] = None,
         service: Optional[RetryService] = None):
    """
    Decorador para adicionar retry automático a funções síncronas.
    
    Args:
        category: Categoria do erro
        config: Configuração customizada
        service: Instância do serviço de retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retry_service = service or RetryService()
            return retry_service.retry_sync(func, *args, category=category, config=config, **kwargs)
        return wrapper
    return decorator

def async_retry(category: Optional[ErrorCategory] = None,
               config: Optional[RetryConfig] = None,
               service: Optional[RetryService] = None):
    """
    Decorador para adicionar retry automático a funções assíncronas.
    
    Args:
        category: Categoria do erro
        config: Configuração customizada
        service: Instância do serviço de retry
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_service = service or RetryService()
            return await retry_service.retry_async(func, *args, category=category, config=config, **kwargs)
        return wrapper
    return decorator

# Instância global para uso conveniente
default_retry_service = RetryService()
