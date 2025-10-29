#!/usr/bin/env python3
"""
Script para iniciar o scheduler NVD como um serviço.
Pode ser usado para executar o scheduler em background.
"""

import os
import sys
import signal
import time
from pathlib import Path

# Adicionar o diretório raiz ao path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.jobs.nvd_scheduler import NVDScheduler
from app.utils.logging_config import setup_logging

# Configurar logging para o serviço
logger = setup_logging('nvd_scheduler_service', log_level='INFO')

class NVDSchedulerService:
    """
    Serviço para gerenciar o scheduler NVD.
    """
    
    def __init__(self):
        self.scheduler = None
        self.running = False
        self.setup_signal_handlers()
    
    def setup_signal_handlers(self):
        """
        Configura handlers para sinais do sistema.
        """
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """
        Handler para sinais de parada.
        """
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.stop()
    
    def start(self):
        """
        Inicia o serviço do scheduler.
        """
        logger.info("Starting NVD Scheduler Service...")
        
        try:
            # Verificar se já está rodando
            if self.running:
                logger.warning("Scheduler service is already running")
                return
            
            # Criar e iniciar o scheduler
            self.scheduler = NVDScheduler()
            self.running = True
            
            logger.info("NVD Scheduler Service started successfully")
            
            # Iniciar o scheduler (blocking)
            self.scheduler.start()
            
        except KeyboardInterrupt:
            logger.info("Service interrupted by user")
            self.stop()
        except Exception as e:
            logger.error(f"Failed to start scheduler service: {e}", exc_info=True)
            self.stop()
            sys.exit(1)
    
    def stop(self):
        """
        Para o serviço do scheduler.
        """
        if not self.running:
            return
        
        logger.info("Stopping NVD Scheduler Service...")
        
        try:
            if self.scheduler:
                self.scheduler.stop()
            
            self.running = False
            logger.info("NVD Scheduler Service stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping scheduler service: {e}", exc_info=True)
    
    def status(self):
        """
        Retorna o status do serviço.
        """
        if self.running and self.scheduler:
            jobs = self.scheduler.scheduler.get_jobs()
            return {
                'status': 'running',
                'jobs_count': len(jobs),
                'jobs': [{
                    'id': job.id,
                    'name': job.name,
                    'next_run': str(job.next_run_time)
                } for job in jobs]
            }
        else:
            return {'status': 'stopped'}

def main():
    """
    Função principal do serviço.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='NVD Scheduler Service')
    parser.add_argument('action', choices=['start', 'stop', 'status', 'restart'],
                       help='Action to perform')
    parser.add_argument('--daemon', action='store_true',
                       help='Run as daemon (background process)')
    
    args = parser.parse_args()
    
    service = NVDSchedulerService()
    
    if args.action == 'start':
        if args.daemon:
            logger.info("Starting service in daemon mode...")
            # Para Windows, usar subprocess para executar em background
            import subprocess
            import sys
            
            # Executar o script sem a flag --daemon
            cmd = [sys.executable, __file__, 'start']
            
            # No Windows, usar CREATE_NEW_PROCESS_GROUP
            if os.name == 'nt':
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen(cmd, start_new_session=True)
            
            logger.info("Service started in background")
        else:
            service.start()
    
    elif args.action == 'stop':
        # Para parar o serviço, enviar sinal SIGTERM
        logger.info("Stopping service...")
        # Implementar lógica para parar o serviço
        print("Stop functionality not fully implemented for this demo")
    
    elif args.action == 'status':
        status = service.status()
        print(f"Service Status: {status['status']}")
        if status['status'] == 'running':
            print(f"Active Jobs: {status['jobs_count']}")
            for job in status['jobs']:
                print(f"  - {job['name']} (Next: {job['next_run']})")
    
    elif args.action == 'restart':
        logger.info("Restarting service...")
        service.stop()
        time.sleep(2)
        service.start()

if __name__ == "__main__":
    main()