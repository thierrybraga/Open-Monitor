#!/usr/bin/env python3
"""
Sistema avançado de rate limiting para APIs externas
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import random
import os

logger = logging.getLogger(__name__)

class RateLimitType(Enum):
    """Tipos de rate limiting"""
    REQUESTS_PER_SECOND = "requests_per_second"
    REQUESTS_PER_MINUTE = "requests_per_minute"
    REQUESTS_PER_HOUR = "requests_per_hour"
    REQUESTS_PER_DAY = "requests_per_day"

@dataclass
class RateLimitConfig:
    """Configuração de rate limiting"""
    requests: int
    window_seconds: int
    burst_allowance: int = 0  # Permite rajadas ocasionais
    backoff_factor: float = 2.0  # Fator de backoff exponencial
    max_backoff: float = 300.0  # Máximo de 5 minutos de espera
    jitter: bool = True  # Adiciona aleatoriedade para evitar thundering herd

class AdvancedRateLimiter:
    """
    Rate limiter avançado com múltiplas estratégias de controle
    """
    
    def __init__(self, config: RateLimitConfig, api_name: str = "API"):
        self.config = config
        self.api_name = api_name
        self.request_times: List[float] = []
        self.consecutive_rate_limits = 0
        self.last_rate_limit_time = 0
        self.current_backoff = 1.0
        
        # Estatísticas
        self.stats = {
            'total_requests': 0,
            'rate_limited_requests': 0,
            'total_wait_time': 0,
            'max_wait_time': 0,
            'avg_wait_time': 0
        }
        
    async def acquire(self) -> None:
        """
        Adquire permissão para fazer uma requisição
        """
        now = time.time()
        
        # Remove requisições antigas da janela
        self._cleanup_old_requests(now)
        
        # Verifica se precisa esperar
        wait_time = self._calculate_wait_time(now)
        
        if wait_time > 0:
            self.stats['rate_limited_requests'] += 1
            self.stats['total_wait_time'] += wait_time
            self.stats['max_wait_time'] = max(self.stats['max_wait_time'], wait_time)
            
            logger.warning(
                f"[{self.api_name}] Rate limit atingido. "
                f"Aguardando {wait_time:.2f}s (tentativa {self.consecutive_rate_limits + 1})"
            )
            
            await self._smart_wait(wait_time)
            self.consecutive_rate_limits += 1
            self.last_rate_limit_time = now
        else:
            # Reset do backoff se não houve rate limit
            if now - self.last_rate_limit_time > self.config.window_seconds * 2:
                self.consecutive_rate_limits = 0
                self.current_backoff = 1.0
        
        # Registra a requisição
        self.request_times.append(time.time())
        self.stats['total_requests'] += 1
        
        # Atualiza estatísticas
        if self.stats['rate_limited_requests'] > 0:
            self.stats['avg_wait_time'] = (
                self.stats['total_wait_time'] / self.stats['rate_limited_requests']
            )
    
    def _cleanup_old_requests(self, now: float) -> None:
        """
        Remove requisições antigas da janela de tempo
        """
        cutoff_time = now - self.config.window_seconds
        self.request_times = [t for t in self.request_times if t > cutoff_time]
    
    def _calculate_wait_time(self, now: float) -> float:
        """
        Calcula o tempo de espera necessário
        """
        # Verifica limite básico
        if len(self.request_times) < self.config.requests:
            return 0
        
        # Calcula tempo até a próxima janela disponível
        oldest_request = self.request_times[0]
        basic_wait = self.config.window_seconds - (now - oldest_request)
        
        # Aplica backoff exponencial se houve rate limits consecutivos
        if self.consecutive_rate_limits > 0:
            backoff_multiplier = min(
                self.config.backoff_factor ** self.consecutive_rate_limits,
                self.config.max_backoff
            )
            basic_wait *= backoff_multiplier
            self.current_backoff = backoff_multiplier
        
        return max(basic_wait, 0)
    
    async def _smart_wait(self, wait_time: float) -> None:
        """
        Espera inteligente com jitter e possibilidade de interrupção
        """
        if self.config.jitter:
            # Adiciona até 10% de jitter para evitar thundering herd
            jitter_amount = wait_time * 0.1 * random.random()
            wait_time += jitter_amount
        
        # Espera em chunks menores para permitir cancelamento
        chunk_size = min(1.0, wait_time / 10)
        remaining = wait_time
        
        while remaining > 0:
            sleep_time = min(chunk_size, remaining)
            await asyncio.sleep(sleep_time)
            remaining -= sleep_time
    
    def get_stats(self) -> Dict:
        """
        Retorna estatísticas do rate limiter
        """
        return {
            **self.stats,
            'current_backoff': self.current_backoff,
            'consecutive_rate_limits': self.consecutive_rate_limits,
            'requests_in_window': len(self.request_times),
            'window_utilization': len(self.request_times) / self.config.requests * 100
        }
    
    def reset_stats(self) -> None:
        """
        Reseta as estatísticas
        """
        self.stats = {
            'total_requests': 0,
            'rate_limited_requests': 0,
            'total_wait_time': 0,
            'max_wait_time': 0,
            'avg_wait_time': 0
        }

class NVDRateLimiter(AdvancedRateLimiter):
    """
    Rate limiter específico para a API do NVD
    """
    
    @classmethod
    def create_for_nvd(cls, has_api_key: bool = False) -> 'NVDRateLimiter':
        """
        Cria um rate limiter otimizado para a API do NVD
        
        Args:
            has_api_key: Se True, usa limites para usuários com API key
        """
        if has_api_key:
            req = int(os.getenv('NVD_RL_KEY_REQUESTS', '50'))
            win = int(os.getenv('NVD_RL_KEY_WINDOW', '30'))
            bfactor = float(os.getenv('NVD_RL_KEY_BACKOFF', '1.8'))
            mback = float(os.getenv('NVD_RL_KEY_MAX_BACKOFF', '180'))
            config = RateLimitConfig(
                requests=req,
                window_seconds=win,
                burst_allowance=5,
                backoff_factor=bfactor,
                max_backoff=mback,
                jitter=True
            )
        else:
            req = int(os.getenv('NVD_RL_PUBLIC_REQUESTS', '5'))
            win = int(os.getenv('NVD_RL_PUBLIC_WINDOW', '30'))
            bfactor = float(os.getenv('NVD_RL_PUBLIC_BACKOFF', '2.5'))
            mback = float(os.getenv('NVD_RL_PUBLIC_MAX_BACKOFF', '600'))
            config = RateLimitConfig(
                requests=req,
                window_seconds=win,
                burst_allowance=1,
                backoff_factor=bfactor,
                max_backoff=mback,
                jitter=True
            )
        
        return cls(config, "NVD API")
    
    async def handle_http_error(self, status_code: int, response_headers: Dict = None) -> bool:
        """
        Trata erros HTTP específicos da API NVD
        
        Args:
            status_code: Código de status HTTP
            response_headers: Headers da resposta (opcional)
            
        Returns:
            True se deve tentar novamente, False caso contrário
        """
        if status_code == 429:  # Too Many Requests
            # Verifica se há header Retry-After
            retry_after = None
            if response_headers:
                retry_after = response_headers.get('Retry-After')
            
            if retry_after:
                try:
                    wait_time = float(retry_after)
                    logger.warning(
                        f"[{self.api_name}] Recebido 429 com Retry-After: {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    return True
                except ValueError:
                    pass
            
            # Fallback para backoff exponencial
            wait_time = min(60 * (2 ** self.consecutive_rate_limits), 300)
            logger.warning(
                f"[{self.api_name}] Recebido 429. Aguardando {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            self.consecutive_rate_limits += 1
            return True
            
        elif status_code == 503:  # Service Unavailable
            wait_time = min(30 * (2 ** self.consecutive_rate_limits), 180)
            logger.warning(
                f"[{self.api_name}] Serviço indisponível (503). Aguardando {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            self.consecutive_rate_limits += 1
            return True
        elif status_code == 403:
            wait_time = min(20 * (2 ** self.consecutive_rate_limits), 180)
            logger.warning(
                f"[{self.api_name}] Acesso limitado (403). Aguardando {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            self.consecutive_rate_limits += 1
            return True
            
        elif status_code >= 500:  # Outros erros de servidor
            wait_time = min(10 * (2 ** self.consecutive_rate_limits), 60)
            logger.warning(
                f"[{self.api_name}] Erro de servidor ({status_code}). Aguardando {wait_time}s"
            )
            await asyncio.sleep(wait_time)
            self.consecutive_rate_limits += 1
            return True
        
        return False

class MultiAPIRateLimiter:
    """
    Gerenciador de rate limiters para múltiplas APIs
    """
    
    def __init__(self):
        self.limiters: Dict[str, AdvancedRateLimiter] = {}
    
    def add_api(self, name: str, config: RateLimitConfig) -> None:
        """
        Adiciona uma API ao gerenciador
        """
        self.limiters[name] = AdvancedRateLimiter(config, name)
    
    async def acquire(self, api_name: str) -> None:
        """
        Adquire permissão para uma API específica
        """
        if api_name not in self.limiters:
            raise ValueError(f"API '{api_name}' não configurada")
        
        await self.limiters[api_name].acquire()
    
    def get_all_stats(self) -> Dict[str, Dict]:
        """
        Retorna estatísticas de todas as APIs
        """
        return {name: limiter.get_stats() for name, limiter in self.limiters.items()}
    
    def reset_all_stats(self) -> None:
        """
        Reseta estatísticas de todas as APIs
        """
        for limiter in self.limiters.values():
            limiter.reset_stats()
