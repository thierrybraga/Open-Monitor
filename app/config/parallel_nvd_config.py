#!/usr/bin/env python3
"""
Configurações específicas para o sistema paralelo NVD.
Centraliza todas as configurações relacionadas ao processamento paralelo.
"""

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ParallelNVDConfig:
    """
    Classe de configuração para sistema paralelo NVD.
    """
    
    # Configurações básicas
    use_enhanced: bool = True
    max_workers: int = 10
    batch_size: int = 1000
    max_concurrent_requests: int = 10
    
    # Configurações de cache
    enable_cache: bool = True
    cache_ttl: int = 3600  # 1 hora
    cache_prefix: str = "nvd_cache:"
    
    # Configurações de monitoramento
    enable_monitoring: bool = True
    monitoring_interval: int = 30  # segundos
    performance_log_level: str = "INFO"
    
    # Configurações de fallback
    fallback_on_error: bool = True
    fallback_timeout: int = 300  # 5 minutos
    
    # Configurações de API NVD
    api_base: str = "https://services.nvd.nist.gov/rest/json/cves/2.0"
    api_key: Optional[str] = None
    page_size: int = 2000
    request_timeout: int = 30
    user_agent: str = "Open-Monitor/1.0"
    
    # Configurações de retry
    max_retries: int = 3
    retry_delay: float = 1.0
    backoff_factor: float = 2.0
    
    # Configurações de logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> 'ParallelNVDConfig':
        """
        Cria configuração a partir de variáveis de ambiente.
        
        Returns:
            Instância de ParallelNVDConfig
        """
        return cls(
            # Configurações básicas
            use_enhanced=os.environ.get('NVD_USE_ENHANCED', 'true').lower() == 'true',
            max_workers=int(os.environ.get('NVD_MAX_WORKERS', '10')),
            batch_size=int(os.environ.get('NVD_BATCH_SIZE', '1000')),
            max_concurrent_requests=int(os.environ.get('MAX_CONCURRENT_REQUESTS', '10')),
            
            # Configurações de cache
            enable_cache=bool(os.environ.get('REDIS_URL')) and 
                        os.environ.get('NVD_ENABLE_CACHE', 'true').lower() == 'true',
            cache_ttl=int(os.environ.get('REDIS_CACHE_TTL', '3600')),
            cache_prefix=os.environ.get('REDIS_CACHE_PREFIX', 'nvd_cache:'),
            
            # Configurações de monitoramento
            enable_monitoring=os.environ.get('NVD_ENABLE_MONITORING', 'true').lower() == 'true',
            monitoring_interval=int(os.environ.get('PERFORMANCE_MONITORING_INTERVAL', '30')),
            performance_log_level=os.environ.get('PERFORMANCE_LOG_LEVEL', 'INFO'),
            
            # Configurações de fallback
            fallback_on_error=os.environ.get('NVD_FALLBACK_ON_ERROR', 'true').lower() == 'true',
            fallback_timeout=int(os.environ.get('NVD_FALLBACK_TIMEOUT', '300')),
            
            # Configurações de API NVD
            api_base=os.environ.get('NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0'),
            api_key=os.environ.get('NVD_API_KEY'),
            page_size=int(os.environ.get('NVD_PAGE_SIZE', '2000')),
            request_timeout=int(os.environ.get('NVD_REQUEST_TIMEOUT', '30')),
            user_agent=os.environ.get('NVD_USER_AGENT', 'Open-Monitor/1.0'),
            
            # Configurações de retry
            max_retries=int(os.environ.get('NVD_MAX_RETRIES', '3')),
            retry_delay=float(os.environ.get('NVD_RETRY_DELAY', '1.0')),
            backoff_factor=float(os.environ.get('NVD_BACKOFF_FACTOR', '2.0')),
            
            # Configurações de logging
            log_level=os.environ.get('LOG_LEVEL', 'INFO'),
            log_file=os.environ.get('PARALLEL_JOBS_LOG_FILE')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Converte configuração para dicionário.
        
        Returns:
            Dicionário com configurações
        """
        return {
            'use_enhanced': self.use_enhanced,
            'max_workers': self.max_workers,
            'batch_size': self.batch_size,
            'max_concurrent_requests': self.max_concurrent_requests,
            'enable_cache': self.enable_cache,
            'cache_ttl': self.cache_ttl,
            'cache_prefix': self.cache_prefix,
            'enable_monitoring': self.enable_monitoring,
            'monitoring_interval': self.monitoring_interval,
            'performance_log_level': self.performance_log_level,
            'fallback_on_error': self.fallback_on_error,
            'fallback_timeout': self.fallback_timeout,
            'api_base': self.api_base,
            'api_key': self.api_key,
            'page_size': self.page_size,
            'request_timeout': self.request_timeout,
            'user_agent': self.user_agent,
            'max_retries': self.max_retries,
            'retry_delay': self.retry_delay,
            'backoff_factor': self.backoff_factor,
            'log_level': self.log_level,
            'log_file': self.log_file
        }
    
    def get_nvd_config(self) -> Dict[str, Any]:
        """
        Obtém configuração específica para NVDFetcher.
        
        Returns:
            Dicionário com configurações NVD
        """
        return {
            'NVD_API_BASE': self.api_base,
            'NVD_API_KEY': self.api_key,
            'NVD_PAGE_SIZE': self.page_size,
            'NVD_REQUEST_TIMEOUT': self.request_timeout,
            'NVD_USER_AGENT': self.user_agent,
            'NVD_MAX_RETRIES': self.max_retries,
            'NVD_RETRY_DELAY': self.retry_delay
        }
    
    def validate(self) -> Dict[str, str]:
        """
        Valida configurações e retorna erros encontrados.
        
        Returns:
            Dicionário com erros de validação
        """
        errors = {}
        
        # Validar valores numéricos
        if self.max_workers <= 0:
            errors['max_workers'] = 'Deve ser maior que 0'
        
        if self.batch_size <= 0:
            errors['batch_size'] = 'Deve ser maior que 0'
        
        if self.max_concurrent_requests <= 0:
            errors['max_concurrent_requests'] = 'Deve ser maior que 0'
        
        if self.cache_ttl <= 0:
            errors['cache_ttl'] = 'Deve ser maior que 0'
        
        if self.monitoring_interval <= 0:
            errors['monitoring_interval'] = 'Deve ser maior que 0'
        
        if self.page_size <= 0 or self.page_size > 2000:
            errors['page_size'] = 'Deve estar entre 1 e 2000'
        
        if self.request_timeout <= 0:
            errors['request_timeout'] = 'Deve ser maior que 0'
        
        if self.max_retries < 0:
            errors['max_retries'] = 'Deve ser maior ou igual a 0'
        
        if self.retry_delay < 0:
            errors['retry_delay'] = 'Deve ser maior ou igual a 0'
        
        if self.backoff_factor < 1:
            errors['backoff_factor'] = 'Deve ser maior ou igual a 1'
        
        # Validar URLs
        if not self.api_base.startswith(('http://', 'https://')):
            errors['api_base'] = 'Deve ser uma URL válida'
        
        # Validar níveis de log
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if self.log_level.upper() not in valid_log_levels:
            errors['log_level'] = f'Deve ser um dos: {valid_log_levels}'
        
        if self.performance_log_level.upper() not in valid_log_levels:
            errors['performance_log_level'] = f'Deve ser um dos: {valid_log_levels}'
        
        return errors
    
    def optimize_for_environment(self, environment: str = 'production') -> 'ParallelNVDConfig':
        """
        Otimiza configurações para ambiente específico.
        
        Args:
            environment: Tipo de ambiente (development, testing, production)
            
        Returns:
            Nova instância otimizada
        """
        config = ParallelNVDConfig(**self.to_dict())
        
        if environment == 'development':
            config.max_workers = min(5, self.max_workers)
            config.batch_size = min(500, self.batch_size)
            config.enable_monitoring = True
            config.log_level = 'DEBUG'
            config.performance_log_level = 'DEBUG'
            
        elif environment == 'testing':
            config.max_workers = min(3, self.max_workers)
            config.batch_size = min(100, self.batch_size)
            config.enable_cache = False
            config.enable_monitoring = False
            config.fallback_on_error = False
            
        elif environment == 'production':
            config.max_workers = max(10, self.max_workers)
            config.batch_size = max(1000, self.batch_size)
            config.enable_monitoring = True
            config.log_level = 'INFO'
            config.performance_log_level = 'INFO'
            config.fallback_on_error = True
        
        return config

class ConfigurationManager:
    """
    Gerenciador de configurações para sistema paralelo.
    """
    
    def __init__(self, config: Optional[ParallelNVDConfig] = None):
        self.config = config or ParallelNVDConfig.from_env()
    
    def get_config(self) -> ParallelNVDConfig:
        """Obtém configuração atual."""
        return self.config
    
    def update_config(self, **kwargs) -> None:
        """
        Atualiza configuração com novos valores.
        
        Args:
            **kwargs: Novos valores de configuração
        """
        current_dict = self.config.to_dict()
        current_dict.update(kwargs)
        self.config = ParallelNVDConfig(**current_dict)
    
    def validate_config(self) -> bool:
        """
        Valida configuração atual.
        
        Returns:
            True se configuração é válida
        """
        errors = self.config.validate()
        if errors:
            for field, error in errors.items():
                print(f"Erro em {field}: {error}")
            return False
        return True
    
    def get_flask_config(self) -> Dict[str, Any]:
        """
        Obtém configurações no formato Flask.
        
        Returns:
            Dicionário com configurações Flask
        """
        config_dict = self.config.to_dict()
        
        flask_config = {
            # Configurações NVD
            'NVD_USE_ENHANCED': config_dict['use_enhanced'],
            'NVD_MAX_WORKERS': config_dict['max_workers'],
            'NVD_BATCH_SIZE': config_dict['batch_size'],
            'MAX_CONCURRENT_REQUESTS': config_dict['max_concurrent_requests'],
            
            # Configurações de cache
            'NVD_ENABLE_CACHE': config_dict['enable_cache'],
            'REDIS_CACHE_TTL': config_dict['cache_ttl'],
            'REDIS_CACHE_PREFIX': config_dict['cache_prefix'],
            
            # Configurações de monitoramento
            'NVD_ENABLE_MONITORING': config_dict['enable_monitoring'],
            'PERFORMANCE_MONITORING_INTERVAL': config_dict['monitoring_interval'],
            'PERFORMANCE_LOG_LEVEL': config_dict['performance_log_level'],
            
            # Configurações de fallback
            'NVD_FALLBACK_ON_ERROR': config_dict['fallback_on_error'],
            'NVD_FALLBACK_TIMEOUT': config_dict['fallback_timeout'],
            
            # Configurações de API
            'NVD_API_BASE': config_dict['api_base'],
            'NVD_API_KEY': config_dict['api_key'],
            'NVD_PAGE_SIZE': config_dict['page_size'],
            'NVD_REQUEST_TIMEOUT': config_dict['request_timeout'],
            'NVD_USER_AGENT': config_dict['user_agent'],
            
            # Configurações de retry
            'NVD_MAX_RETRIES': config_dict['max_retries'],
            'NVD_RETRY_DELAY': config_dict['retry_delay'],
            'NVD_BACKOFF_FACTOR': config_dict['backoff_factor']
        }
        
        return flask_config
    
    def save_to_file(self, filename: str) -> None:
        """
        Salva configuração em arquivo.
        
        Args:
            filename: Nome do arquivo
        """
        import json
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.config.to_dict(), f, indent=2, default=str)
    
    def load_from_file(self, filename: str) -> None:
        """
        Carrega configuração de arquivo.
        
        Args:
            filename: Nome do arquivo
        """
        import json
        
        with open(filename, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        self.config = ParallelNVDConfig(**config_dict)

# Instância global do gerenciador
_config_manager = None

def get_config_manager() -> ConfigurationManager:
    """
    Obtém instância global do gerenciador de configurações.
    
    Returns:
        Instância do ConfigurationManager
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager

def get_parallel_config() -> ParallelNVDConfig:
    """
    Função de conveniência para obter configuração paralela.
    
    Returns:
        Configuração paralela atual
    """
    return get_config_manager().get_config()

def update_parallel_config(**kwargs) -> None:
    """
    Função de conveniência para atualizar configuração paralela.
    
    Args:
        **kwargs: Novos valores de configuração
    """
    get_config_manager().update_config(**kwargs)

# Configurações predefinidas para diferentes ambientes
DEVELOPMENT_CONFIG = ParallelNVDConfig(
    max_workers=5,
    batch_size=500,
    enable_monitoring=True,
    log_level='DEBUG',
    performance_log_level='DEBUG'
)

TESTING_CONFIG = ParallelNVDConfig(
    max_workers=3,
    batch_size=100,
    enable_cache=False,
    enable_monitoring=False,
    fallback_on_error=False,
    log_level='WARNING'
)

PRODUCTION_CONFIG = ParallelNVDConfig(
    max_workers=15,
    batch_size=2000,
    enable_monitoring=True,
    log_level='INFO',
    performance_log_level='INFO',
    fallback_on_error=True
)

# Exemplo de uso
if __name__ == '__main__':
    # Criar configuração a partir do ambiente
    config = ParallelNVDConfig.from_env()
    
    # Validar configuração
    errors = config.validate()
    if errors:
        print("Erros de configuração encontrados:")
        for field, error in errors.items():
            print(f"  {field}: {error}")
    else:
        print("Configuração válida!")
    
    # Mostrar configuração atual
    print("\nConfiguração atual:")
    import json
    print(json.dumps(config.to_dict(), indent=2, default=str))
    
    # Otimizar para produção
    prod_config = config.optimize_for_environment('production')
    print("\nConfiguração otimizada para produção:")
    print(json.dumps(prod_config.to_dict(), indent=2, default=str))