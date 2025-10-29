#!/usr/bin/env python3
"""
Scheduler para sincronização automática do NVD.
Executa a sincronização de vulnerabilidades a cada hora.
"""

import logging
import sys
import os
import asyncio
import aiohttp
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Adicionar o diretório raiz ao path para importações
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.jobs.nvd_fetcher import NVDFetcher
from services.vulnerability_service import VulnerabilityService
from app.utils.logging_config import setup_logging

# Configurar logging específico para o scheduler
logger = setup_logging('nvd_scheduler', log_level='INFO')

class NVDScheduler:
    """
    Classe responsável pelo agendamento automático da sincronização NVD.
    """
    
    def __init__(self):
        self.scheduler = BlockingScheduler()
        self.app = None
        self.setup_scheduler()
    
    def setup_scheduler(self):
        """
        Configura o scheduler com os jobs necessários.
        """
        # Job para sincronização incremental a cada hora
        self.scheduler.add_job(
            func=self.run_incremental_sync,
            trigger=IntervalTrigger(hours=1),
            id='nvd_incremental_sync',
            name='NVD Incremental Sync',
            replace_existing=True,
            max_instances=1  # Evita execuções simultâneas
        )
        
        # Job para sincronização completa uma vez por semana (domingo às 2h)
        self.scheduler.add_job(
            func=self.run_full_sync,
            trigger='cron',
            day_of_week='sun',
            hour=2,
            minute=0,
            id='nvd_full_sync',
            name='NVD Full Sync (Weekly)',
            replace_existing=True,
            max_instances=1
        )
        
        # Adicionar listeners para eventos do scheduler
        self.scheduler.add_listener(self.job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
    
    def job_listener(self, event):
        """
        Listener para eventos dos jobs.
        """
        if event.exception:
            logger.error(
                f"Job {event.job_id} failed with exception: {event.exception}",
                exc_info=True
            )
        else:
            logger.info(f"Job {event.job_id} executed successfully")
    
    def run_incremental_sync(self):
        """
        Executa sincronização incremental do NVD.
        """
        logger.info("Starting scheduled incremental NVD synchronization")
        
        try:
            # Criar contexto da aplicação Flask
            if not self.app:
                self.app = create_app()
            
            with self.app.app_context():
                # Executar sincronização assíncrona
                result = asyncio.run(self._run_sync(full=False))
                logger.info(f"Incremental sync completed. Processed {result} CVEs")
                
        except Exception as e:
            logger.error(f"Error during incremental sync: {e}", exc_info=True)
            raise
    
    def run_full_sync(self):
        """
        Executa sincronização completa do NVD.
        """
        logger.info("Starting scheduled full NVD synchronization")
        
        try:
            # Criar contexto da aplicação Flask
            if not self.app:
                self.app = create_app()
            
            with self.app.app_context():
                # Executar sincronização assíncrona
                result = asyncio.run(self._run_sync(full=True))
                logger.info(f"Full sync completed. Processed {result} CVEs")
                
        except Exception as e:
            logger.error(f"Error during full sync: {e}", exc_info=True)
            raise
    
    async def _run_sync(self, full=False):
        """
        Executa a sincronização NVD de forma assíncrona.
        
        Args:
            full (bool): Se True, executa sincronização completa
        
        Returns:
            int: Número de CVEs processados
        """
        # Configurações do NVD
        nvd_config = {
            "NVD_API_BASE": getattr(self.app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
            "NVD_API_KEY": getattr(self.app.config, 'NVD_API_KEY', None),
            "NVD_RATE_LIMIT": getattr(self.app.config, 'NVD_RATE_LIMIT', (2, 1)),
            "NVD_CACHE_DIR": getattr(self.app.config, 'NVD_CACHE_DIR', "cache"),
            "NVD_REQUEST_TIMEOUT": getattr(self.app.config, 'NVD_REQUEST_TIMEOUT', 30),
            "NVD_USER_AGENT": getattr(self.app.config, 'NVD_USER_AGENT', "Sec4all.co NVD Fetcher")
        }
        
        # Validar configurações essenciais
        if not nvd_config.get("NVD_API_BASE"):
            raise ValueError("NVD_API_BASE configuration is missing")
        
        # Usar aiohttp.ClientSession
        async with aiohttp.ClientSession() as http_session:
            # Instanciar o fetcher
            fetcher = NVDFetcher(http_session, nvd_config)
            
            # Criar instância do VulnerabilityService
            vulnerability_service = VulnerabilityService(db.session)
            
            # Executar sincronização
            processed_count = await fetcher.update(
                vulnerability_service=vulnerability_service,
                full=full
            )
            
            return processed_count
    
    def start(self):
        """
        Inicia o scheduler.
        """
        logger.info("Starting NVD Scheduler...")
        
        try:
            # Iniciar o scheduler primeiro
            self.scheduler.start()
            
            # Agora listar os jobs com next_run_time disponível
            logger.info("Scheduled jobs:")
            for job in self.scheduler.get_jobs():
                next_run = getattr(job, 'next_run_time', 'Not scheduled')
                logger.info(f"  - {job.name} (ID: {job.id}) - Next run: {next_run}")
                
        except KeyboardInterrupt:
            logger.info("Scheduler interrupted by user")
            self.stop()
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            raise
    
    def stop(self):
        """
        Para o scheduler.
        """
        logger.info("Stopping NVD Scheduler...")
        self.scheduler.shutdown()
        logger.info("NVD Scheduler stopped")

def main():
    """
    Função principal para execução do scheduler.
    """
    logger.info("NVD Scheduler starting up...")
    
    try:
        scheduler = NVDScheduler()
        scheduler.start()
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()