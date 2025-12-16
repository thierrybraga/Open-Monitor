#!/usr/bin/env python3
"""
Configuração para o scheduler NVD.
Centraliza todas as configurações relacionadas ao agendamento.
"""

import os
from datetime import timedelta

class SchedulerConfig:
    """
    Configurações do scheduler NVD.
    """
    
    # Configurações de intervalo
    INCREMENTAL_SYNC_INTERVAL = timedelta(hours=1)  # Sincronização incremental a cada hora
    FULL_SYNC_SCHEDULE = {
        'day_of_week': 'sun',  # Domingo
        'hour': 2,             # 2h da manhã
        'minute': 0
    }
    
    # Configurações de execução
    MAX_INSTANCES = 1  # Evita execuções simultâneas
    JOB_TIMEOUT = timedelta(hours=2)  # Timeout para jobs
    
    # Configurações de retry
    MAX_RETRIES = 3
    RETRY_DELAY = timedelta(minutes=5)
    
    # Configurações de logging
    LOG_LEVEL = os.getenv('SCHEDULER_LOG_LEVEL', 'INFO')
    LOG_DIR = os.getenv('SCHEDULER_LOG_DIR', 'logs')
    
    # Configurações do NVD API
    NVD_CONFIG = {
        'NVD_API_BASE': os.getenv('NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0'),
        'NVD_API_KEY': os.getenv('NVD_API_KEY'),
        'NVD_RATE_LIMIT': (2, 1),  # 2 requests per second
        'NVD_CACHE_DIR': os.getenv('NVD_CACHE_DIR', 'cache'),
        'NVD_REQUEST_TIMEOUT': int(os.getenv('NVD_REQUEST_TIMEOUT', '30')),
        'NVD_USER_AGENT': os.getenv('NVD_USER_AGENT', 'Sec4all.co NVD Fetcher')
    }
    
    # Configurações de monitoramento
    ENABLE_HEALTH_CHECK = True
    HEALTH_CHECK_INTERVAL = timedelta(minutes=30)
    
    # Configurações de notificação (para futuras implementações)
    ENABLE_NOTIFICATIONS = False
    NOTIFICATION_CHANNELS = {
        'email': {
            'enabled': False,
            'recipients': [],
            'smtp_server': os.getenv('SMTP_SERVER'),
            'smtp_port': int(os.getenv('SMTP_PORT', '587')),
            'smtp_user': os.getenv('SMTP_USER'),
            'smtp_password': os.getenv('SMTP_PASSWORD')
        },
        'webhook': {
            'enabled': False,
            'url': os.getenv('WEBHOOK_URL'),
            'secret': os.getenv('WEBHOOK_SECRET')
        }
    }
    
    # Configurações de performance
    BATCH_SIZE = int(os.getenv('NVD_BATCH_SIZE', '100'))
    CONCURRENT_REQUESTS = int(os.getenv('NVD_MAX_CONCURRENT_REQUESTS', '5'))
    
    @classmethod
    def validate_config(cls):
        """
        Valida as configurações essenciais.
        
        Returns:
            tuple: (is_valid, error_messages)
        """
        errors = []
        
        # Validar configurações do NVD
        if not cls.NVD_CONFIG.get('NVD_API_BASE'):
            errors.append("NVD_API_BASE is required")
        
        # Validar intervalos
        if cls.INCREMENTAL_SYNC_INTERVAL.total_seconds() < 300:  # Mínimo 5 minutos
            errors.append("INCREMENTAL_SYNC_INTERVAL must be at least 5 minutes")
        
        # Validar configurações de retry
        if cls.MAX_RETRIES < 0:
            errors.append("MAX_RETRIES must be non-negative")
        
        if cls.RETRY_DELAY.total_seconds() < 60:  # Mínimo 1 minuto
            errors.append("RETRY_DELAY must be at least 1 minute")
        
        # Validar configurações de performance
        if cls.BATCH_SIZE <= 0:
            errors.append("BATCH_SIZE must be positive")
        
        if cls.CONCURRENT_REQUESTS <= 0:
            errors.append("CONCURRENT_REQUESTS must be positive")
        
        return len(errors) == 0, errors
    
    @classmethod
    def get_job_configs(cls):
        """
        Retorna configurações dos jobs do scheduler.
        
        Returns:
            dict: Configurações dos jobs
        """
        return {
            'incremental_sync': {
                'id': 'nvd_incremental_sync',
                'name': 'NVD Incremental Sync',
                'trigger': 'interval',
                'interval': cls.INCREMENTAL_SYNC_INTERVAL,
                'max_instances': cls.MAX_INSTANCES,
                'replace_existing': True
            },
            'full_sync': {
                'id': 'nvd_full_sync',
                'name': 'NVD Full Sync (Weekly)',
                'trigger': 'cron',
                'trigger_args': cls.FULL_SYNC_SCHEDULE,
                'max_instances': cls.MAX_INSTANCES,
                'replace_existing': True
            },
            'health_check': {
                'id': 'scheduler_health_check',
                'name': 'Scheduler Health Check',
                'trigger': 'interval',
                'interval': cls.HEALTH_CHECK_INTERVAL,
                'max_instances': 1,
                'replace_existing': True,
                'enabled': cls.ENABLE_HEALTH_CHECK
            }
        }
    
    @classmethod
    def load_from_env(cls):
        """
        Carrega configurações de variáveis de ambiente.
        """
        # Atualizar intervalo de sincronização incremental
        interval_hours = float(os.getenv('NVD_SYNC_INTERVAL_HOURS', '1'))
        cls.INCREMENTAL_SYNC_INTERVAL = timedelta(hours=interval_hours)
        
        # Atualizar configurações de retry
        cls.MAX_RETRIES = int(os.getenv('NVD_MAX_RETRIES', '3'))
        retry_minutes = int(os.getenv('NVD_RETRY_DELAY_MINUTES', '5'))
        cls.RETRY_DELAY = timedelta(minutes=retry_minutes)
        
        # Atualizar configurações de performance
        cls.BATCH_SIZE = int(os.getenv('NVD_BATCH_SIZE', '100'))
        cls.CONCURRENT_REQUESTS = int(os.getenv('NVD_MAX_CONCURRENT_REQUESTS', '5'))
        
        # Manter compatibilidade com variável antiga, se presente
        try:
            legacy = os.getenv('NVD_CONCURRENT_REQUESTS')
            if legacy is not None:
                cls.CONCURRENT_REQUESTS = int(legacy)
        except Exception:
            pass

    @classmethod
    def to_dict(cls) -> dict:
        return {
            'INCREMENTAL_SYNC_INTERVAL_SECONDS': int(cls.INCREMENTAL_SYNC_INTERVAL.total_seconds()),
            'FULL_SYNC_SCHEDULE': dict(cls.FULL_SYNC_SCHEDULE),
            'MAX_INSTANCES': cls.MAX_INSTANCES,
            'JOB_TIMEOUT_SECONDS': int(cls.JOB_TIMEOUT.total_seconds()),
            'MAX_RETRIES': cls.MAX_RETRIES,
            'RETRY_DELAY_SECONDS': int(cls.RETRY_DELAY.total_seconds()),
            'LOG_LEVEL': cls.LOG_LEVEL,
            'LOG_DIR': cls.LOG_DIR,
            'NVD_CONFIG': dict(cls.NVD_CONFIG),
            'ENABLE_HEALTH_CHECK': cls.ENABLE_HEALTH_CHECK,
            'HEALTH_CHECK_INTERVAL_SECONDS': int(cls.HEALTH_CHECK_INTERVAL.total_seconds()),
            'BATCH_SIZE': cls.BATCH_SIZE,
            'CONCURRENT_REQUESTS': cls.CONCURRENT_REQUESTS,
        }
        
        # Atualizar configurações de monitoramento
        cls.ENABLE_HEALTH_CHECK = os.getenv('ENABLE_HEALTH_CHECK', 'true').lower() == 'true'
        health_check_minutes = int(os.getenv('HEALTH_CHECK_INTERVAL_MINUTES', '30'))
        cls.HEALTH_CHECK_INTERVAL = timedelta(minutes=health_check_minutes)

# Carregar configurações de variáveis de ambiente na importação
SchedulerConfig.load_from_env()
