#!/usr/bin/env python3
"""
Script de integração para jobs paralelos NVD.
Atualiza jobs existentes para usar o sistema aprimorado.
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any, List
import argparse
import shutil

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

class JobIntegrationManager:
    """
    Gerenciador de integração para jobs paralelos.
    """
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.backup_dir = os.path.join(project_root, 'backups', f'job_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}')
        self.integration_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'backups_created': [],
            'files_modified': [],
            'jobs_updated': [],
            'schedulers_updated': [],
            'status': 'pending'
        }
    
    def create_backup(self, file_path: str) -> str:
        """
        Cria backup de um arquivo antes da modificação.
        
        Args:
            file_path: Caminho do arquivo para backup
            
        Returns:
            Caminho do arquivo de backup
        """
        if not os.path.exists(self.backup_dir):
            os.makedirs(self.backup_dir)
        
        rel_path = os.path.relpath(file_path, self.project_root)
        backup_path = os.path.join(self.backup_dir, rel_path)
        
        # Criar diretórios necessários
        backup_dir = os.path.dirname(backup_path)
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Copiar arquivo
        shutil.copy2(file_path, backup_path)
        
        self.integration_report['backups_created'].append({
            'original': file_path,
            'backup': backup_path,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Backup criado: {file_path} -> {backup_path}")
        return backup_path
    
    def update_job_scheduler(self) -> bool:
        """
        Atualiza o scheduler principal para usar jobs paralelos.
        
        Returns:
            True se atualização foi bem-sucedida
        """
        scheduler_file = os.path.join(self.project_root, 'jobs', 'scheduler.py')
        
        if not os.path.exists(scheduler_file):
            logger.warning(f"Arquivo scheduler não encontrado: {scheduler_file}")
            return False
        
        try:
            # Criar backup
            self.create_backup(scheduler_file)
            
            # Ler arquivo atual
            with open(scheduler_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Modificações necessárias
            modifications = [
                {
                    'search': 'from jobs.nvd_fetcher import NVDFetcher',
                    'replace': 'from jobs.nvd_fetcher import NVDFetcher\nfrom app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher'
                },
                {
                    'search': 'def schedule_nvd_sync',
                    'replace': 'def schedule_nvd_sync_legacy'
                }
            ]
            
            # Aplicar modificações
            modified_content = content
            for mod in modifications:
                if mod['search'] in modified_content:
                    modified_content = modified_content.replace(mod['search'], mod['replace'])
            
            # Adicionar nova função de agendamento
            new_scheduler_function = '''

def schedule_nvd_sync(app, use_enhanced=True, **kwargs):
    """
    Agenda sincronização NVD com opção de usar sistema aprimorado.
    
    Args:
        app: Instância Flask
        use_enhanced: Se True, usa EnhancedNVDFetcher
        **kwargs: Argumentos adicionais para configuração
    """
    if use_enhanced:
        return schedule_enhanced_nvd_sync(app, **kwargs)
    else:
        return schedule_nvd_sync_legacy(app, **kwargs)

def schedule_enhanced_nvd_sync(app, max_workers=None, enable_cache=True, 
                              enable_monitoring=True, batch_size=None):
    """
    Agenda sincronização NVD usando sistema aprimorado.
    
    Args:
        app: Instância Flask
        max_workers: Número máximo de workers paralelos
        enable_cache: Habilitar cache Redis
        enable_monitoring: Habilitar monitoramento de performance
        batch_size: Tamanho do batch para processamento
    """
    from flask_apscheduler import APScheduler
    
    # Configurações padrão
    config = {
        'max_workers': max_workers or app.config.get('NVD_MAX_WORKERS', 10),
        'enable_cache': enable_cache and app.config.get('REDIS_URL') is not None,
        'enable_monitoring': enable_monitoring,
        'batch_size': batch_size or app.config.get('NVD_BATCH_SIZE', 1000)
    }
    
    def run_enhanced_nvd_sync():
        with app.app_context():
            try:
                logger.info("Iniciando sincronização NVD aprimorada")
                
                fetcher = EnhancedNVDFetcher(
                    app=app,
                    max_workers=config['max_workers'],
                    enable_cache=config['enable_cache'],
                    enable_monitoring=config['enable_monitoring'],
                    batch_size=config['batch_size']
                )
                
                try:
                    # Executar sincronização
                    import asyncio
                    result = asyncio.run(fetcher.sync_nvd(full=False, use_parallel=True))
                    
                    # Log estatísticas
                    stats = fetcher.get_performance_stats()
                    logger.info(f"Sincronização concluída: {result} vulnerabilidades processadas")
                    logger.info(f"Estatísticas: {stats}")
                    
                    return result
                    
                finally:
                    fetcher.cleanup()
                    
            except Exception as e:
                logger.error(f"Erro na sincronização NVD aprimorada: {e}", exc_info=True)
                
                # Fallback para sistema original se configurado
                if app.config.get('NVD_FALLBACK_ON_ERROR', True):
                    logger.info("Tentando fallback para sistema original")
                    return schedule_nvd_sync_legacy(app)
                else:
                    raise
    
    # Agendar job
    scheduler = APScheduler()
    
    # Job diário às 2:00 AM
    scheduler.add_job(
        func=run_enhanced_nvd_sync,
        trigger='cron',
        hour=2,
        minute=0,
        id='enhanced_nvd_sync_daily',
        name='Enhanced NVD Sync Daily',
        replace_existing=True
    )
    
    # Job incremental a cada 6 horas
    scheduler.add_job(
        func=lambda: run_enhanced_nvd_sync(),
        trigger='interval',
        hours=6,
        id='enhanced_nvd_sync_incremental',
        name='Enhanced NVD Sync Incremental',
        replace_existing=True
    )
    
    logger.info("Jobs de sincronização NVD aprimorada agendados")
    return scheduler
'''
            
            # Adicionar nova função ao final
            modified_content += new_scheduler_function
            
            # Salvar arquivo modificado
            with open(scheduler_file, 'w', encoding='utf-8') as f:
                f.write(modified_content)
            
            self.integration_report['schedulers_updated'].append({
                'file': scheduler_file,
                'modifications': len(modifications),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Scheduler atualizado: {scheduler_file}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar scheduler: {e}")
            return False
    
    def create_job_wrapper(self) -> bool:
        """
        Cria wrapper para facilitar uso dos jobs paralelos.
        
        Returns:
            True se criação foi bem-sucedida
        """
        wrapper_file = os.path.join(self.project_root, 'jobs', 'parallel_job_wrapper.py')
        
        wrapper_content = '''
#!/usr/bin/env python3
"""
Wrapper para jobs paralelos NVD.
Facilita a execução e configuração de jobs aprimorados.
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from flask import Flask

from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
from app.jobs.nvd_fetcher import NVDFetcher
import aiohttp

logger = logging.getLogger(__name__)

class ParallelJobWrapper:
    """
    Wrapper para execução de jobs paralelos NVD.
    """
    
    def __init__(self, app: Flask, config: Optional[Dict[str, Any]] = None):
        self.app = app
        self.config = config or self._get_default_config()
        self.fetcher = None
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Obtém configuração padrão do app."""
        return {
            'max_workers': self.app.config.get('NVD_MAX_WORKERS', 10),
            'enable_cache': bool(self.app.config.get('REDIS_URL')),
            'enable_monitoring': self.app.config.get('NVD_ENABLE_MONITORING', True),
            'batch_size': self.app.config.get('NVD_BATCH_SIZE', 1000),
            'use_enhanced': self.app.config.get('NVD_USE_ENHANCED', True),
            'fallback_on_error': self.app.config.get('NVD_FALLBACK_ON_ERROR', True)
        }
    
    async def run_sync(self, full: bool = False, max_pages: Optional[int] = None, 
                      use_parallel: Optional[bool] = None) -> int:
        """
        Executa sincronização NVD.
        
        Args:
            full: Se True, executa sincronização completa
            max_pages: Número máximo de páginas para processar
            use_parallel: Forçar uso de processamento paralelo
            
        Returns:
            Número de vulnerabilidades processadas
        """
        if self.config['use_enhanced']:
            return await self._run_enhanced_sync(full, max_pages, use_parallel)
        else:
            return await self._run_legacy_sync(full, max_pages)
    
    async def _run_enhanced_sync(self, full: bool, max_pages: Optional[int], 
                               use_parallel: Optional[bool]) -> int:
        """Executa sincronização usando sistema aprimorado."""
        try:
            self.fetcher = EnhancedNVDFetcher(
                app=self.app,
                max_workers=self.config['max_workers'],
                enable_cache=self.config['enable_cache'],
                enable_monitoring=self.config['enable_monitoring'],
                batch_size=self.config['batch_size']
            )
            
            # Determinar se usar processamento paralelo
            if use_parallel is None:
                use_parallel = self.config['max_workers'] > 1
            
            result = await self.fetcher.sync_nvd(
                full=full, 
                max_pages=max_pages, 
                use_parallel=use_parallel
            )
            
            # Log estatísticas
            stats = self.fetcher.get_performance_stats()
            logger.info(f"Sincronização aprimorada concluída: {result} vulnerabilidades")
            logger.info(f"Estatísticas: {stats}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erro na sincronização aprimorada: {e}")
            
            if self.config['fallback_on_error']:
                logger.info("Tentando fallback para sistema original")
                return await self._run_legacy_sync(full, max_pages)
            else:
                raise
        
        finally:
            if self.fetcher:
                self.fetcher.cleanup()
    
    async def _run_legacy_sync(self, full: bool, max_pages: Optional[int]) -> int:
        """Executa sincronização usando sistema original."""
        from services.vulnerability_service import VulnerabilityService
        from app.extensions import db
        
        async with aiohttp.ClientSession() as session:
            nvd_config = {
                "NVD_API_BASE": self.app.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                "NVD_API_KEY": self.app.config.get("NVD_API_KEY"),
                "NVD_PAGE_SIZE": self.app.config.get("NVD_PAGE_SIZE", 2000),
                "NVD_REQUEST_TIMEOUT": self.app.config.get("NVD_REQUEST_TIMEOUT", 30),
                "NVD_USER_AGENT": self.app.config.get("NVD_USER_AGENT", "Open-Monitor/1.0")
            }
            
            fetcher = NVDFetcher(session, nvd_config)
            vulnerability_service = VulnerabilityService(db.session)
            
            result = await fetcher.update(vulnerability_service, full)
            
            logger.info(f"Sincronização original concluída: {result} vulnerabilidades")
            return result
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do último job executado."""
        if self.fetcher and hasattr(self.fetcher, 'get_performance_stats'):
            return self.fetcher.get_performance_stats()
        return {}

# Funções de conveniência para uso direto

async def run_parallel_nvd_sync(app: Flask, **kwargs) -> int:
    """
    Função de conveniência para executar sincronização paralela.
    
    Args:
        app: Instância Flask
        **kwargs: Argumentos para configuração
        
    Returns:
        Número de vulnerabilidades processadas
    """
    wrapper = ParallelJobWrapper(app)
    return await wrapper.run_sync(**kwargs)

def run_sync_job(app: Flask, **kwargs) -> int:
    """
    Função síncrona para executar job de sincronização.
    
    Args:
        app: Instância Flask
        **kwargs: Argumentos para configuração
        
    Returns:
        Número de vulnerabilidades processadas
    """
    return asyncio.run(run_parallel_nvd_sync(app, **kwargs))

# Exemplo de uso em CLI
if __name__ == '__main__':
    import sys
    import os
    
    # Adicionar diretório raiz ao path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    from app import create_app
    
    app = create_app()
    
    with app.app_context():
        result = run_sync_job(app, full=False, max_pages=1)
        print(f"Sincronização concluída: {result} vulnerabilidades processadas")
'''
        
        try:
            with open(wrapper_file, 'w', encoding='utf-8') as f:
                f.write(wrapper_content)
            
            self.integration_report['files_modified'].append({
                'file': wrapper_file,
                'action': 'created',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Wrapper criado: {wrapper_file}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar wrapper: {e}")
            return False
    
    def update_app_config(self) -> bool:
        """
        Atualiza configurações da aplicação para suportar jobs paralelos.
        
        Returns:
            True se atualização foi bem-sucedida
        """
        config_file = os.path.join(self.project_root, 'config.py')
        
        if not os.path.exists(config_file):
            logger.warning(f"Arquivo de configuração não encontrado: {config_file}")
            return False
        
        try:
            # Criar backup
            self.create_backup(config_file)
            
            # Ler arquivo atual
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Configurações adicionais para sistema paralelo
            additional_configs = '''

# Configurações do Sistema Paralelo NVD
NVD_USE_ENHANCED = os.environ.get('NVD_USE_ENHANCED', 'true').lower() == 'true'
NVD_MAX_WORKERS = int(os.environ.get('NVD_MAX_WORKERS', '10'))
NVD_BATCH_SIZE = int(os.environ.get('NVD_BATCH_SIZE', '1000'))
NVD_ENABLE_MONITORING = os.environ.get('NVD_ENABLE_MONITORING', 'true').lower() == 'true'
NVD_FALLBACK_ON_ERROR = os.environ.get('NVD_FALLBACK_ON_ERROR', 'true').lower() == 'true'
MAX_CONCURRENT_REQUESTS = int(os.environ.get('MAX_CONCURRENT_REQUESTS', '10'))

# Cache Redis para sistema paralelo
REDIS_CACHE_TTL = int(os.environ.get('REDIS_CACHE_TTL', '3600'))  # 1 hora
REDIS_CACHE_PREFIX = os.environ.get('REDIS_CACHE_PREFIX', 'nvd_cache:')

# Monitoramento de performance
PERFORMANCE_MONITORING_INTERVAL = int(os.environ.get('PERFORMANCE_MONITORING_INTERVAL', '30'))  # segundos
PERFORMANCE_LOG_LEVEL = os.environ.get('PERFORMANCE_LOG_LEVEL', 'INFO')
'''
            
            # Verificar se configurações já existem
            if 'NVD_USE_ENHANCED' not in content:
                content += additional_configs
                
                # Salvar arquivo modificado
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                self.integration_report['files_modified'].append({
                    'file': config_file,
                    'action': 'updated_config',
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                logger.info(f"Configurações adicionadas: {config_file}")
            else:
                logger.info("Configurações paralelas já existem")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar configurações: {e}")
            return False
    
    def create_env_template(self) -> bool:
        """
        Cria template de variáveis de ambiente para sistema paralelo.
        
        Returns:
            True se criação foi bem-sucedida
        """
        env_template_file = os.path.join(self.project_root, '.env.parallel.template')
        
        env_template_content = '''
# Template de Variáveis de Ambiente - Sistema Paralelo NVD
# Copie este arquivo para .env e ajuste os valores conforme necessário

# === CONFIGURAÇÕES BÁSICAS NVD ===
NVD_API_KEY=your_nvd_api_key_here
NVD_API_BASE=https://services.nvd.nist.gov/rest/json/cves/2.0
NVD_PAGE_SIZE=2000
NVD_REQUEST_TIMEOUT=30
NVD_USER_AGENT=Open-Monitor/1.0

# === CONFIGURAÇÕES SISTEMA PARALELO ===
# Habilitar sistema aprimorado (true/false)
NVD_USE_ENHANCED=true

# Número de workers paralelos (recomendado: 5-15)
NVD_MAX_WORKERS=10

# Tamanho do batch para processamento (recomendado: 500-2000)
NVD_BATCH_SIZE=1000

# Número máximo de requisições simultâneas
MAX_CONCURRENT_REQUESTS=10

# === CONFIGURAÇÕES DE CACHE ===
# URL do Redis para cache (opcional)
REDIS_URL=redis://localhost:6379/0

# TTL do cache em segundos (3600 = 1 hora)
REDIS_CACHE_TTL=3600

# Prefixo para chaves do cache
REDIS_CACHE_PREFIX=nvd_cache:

# === CONFIGURAÇÕES DE MONITORAMENTO ===
# Habilitar monitoramento de performance (true/false)
NVD_ENABLE_MONITORING=true

# Intervalo de monitoramento em segundos
PERFORMANCE_MONITORING_INTERVAL=30

# Nível de log para performance (DEBUG/INFO/WARNING/ERROR)
PERFORMANCE_LOG_LEVEL=INFO

# === CONFIGURAÇÕES DE FALLBACK ===
# Usar sistema original em caso de erro (true/false)
NVD_FALLBACK_ON_ERROR=true

# === CONFIGURAÇÕES DE BANCO DE DADOS ===
# Manter configurações existentes do banco
# SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost/dbname

# === CONFIGURAÇÕES DE LOGGING ===
# Nível de log geral
LOG_LEVEL=INFO

# Arquivo de log para jobs paralelos
PARALLEL_JOBS_LOG_FILE=logs/parallel_jobs.log
'''
        
        try:
            with open(env_template_file, 'w', encoding='utf-8') as f:
                f.write(env_template_content)
            
            self.integration_report['files_modified'].append({
                'file': env_template_file,
                'action': 'created',
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Template de ambiente criado: {env_template_file}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao criar template de ambiente: {e}")
            return False
    
    def run_integration(self) -> Dict[str, Any]:
        """
        Executa integração completa do sistema paralelo.
        
        Returns:
            Relatório de integração
        """
        logger.info("Iniciando integração do sistema paralelo NVD")
        
        success_count = 0
        total_tasks = 4
        
        # 1. Atualizar scheduler
        if self.update_job_scheduler():
            success_count += 1
            logger.info("✓ Scheduler atualizado")
        else:
            logger.error("✗ Falha ao atualizar scheduler")
        
        # 2. Criar wrapper de jobs
        if self.create_job_wrapper():
            success_count += 1
            logger.info("✓ Wrapper de jobs criado")
        else:
            logger.error("✗ Falha ao criar wrapper")
        
        # 3. Atualizar configurações
        if self.update_app_config():
            success_count += 1
            logger.info("✓ Configurações atualizadas")
        else:
            logger.error("✗ Falha ao atualizar configurações")
        
        # 4. Criar template de ambiente
        if self.create_env_template():
            success_count += 1
            logger.info("✓ Template de ambiente criado")
        else:
            logger.error("✗ Falha ao criar template")
        
        # Determinar status
        if success_count == total_tasks:
            self.integration_report['status'] = 'completed'
        elif success_count >= total_tasks // 2:
            self.integration_report['status'] = 'partial'
        else:
            self.integration_report['status'] = 'failed'
        
        self.integration_report['success_rate'] = success_count / total_tasks
        
        logger.info(f"Integração concluída: {success_count}/{total_tasks} tarefas bem-sucedidas")
        
        return self.integration_report
    
    def save_report(self, filename: str = None) -> str:
        """Salva relatório de integração."""
        if not filename:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'integration_report_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.integration_report, f, indent=2, default=str)
        
        logger.info(f"Relatório de integração salvo em: {filename}")
        return filename

def setup_logging():
    """Configura logging para o script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('job_integration.log')
        ]
    )

def main():
    """Função principal do script de integração."""
    parser = argparse.ArgumentParser(description='Script de Integração Jobs Paralelos')
    parser.add_argument('--project-root', default='.', help='Diretório raiz do projeto')
    parser.add_argument('--save-report', help='Nome do arquivo para salvar relatório')
    parser.add_argument('--log-level', default='INFO', help='Nível de log')
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    # Obter caminho absoluto do projeto
    project_root = os.path.abspath(args.project_root)
    
    logger.info(f"Iniciando integração de jobs paralelos em: {project_root}")
    
    try:
        # Criar gerenciador de integração
        integration_manager = JobIntegrationManager(project_root)
        
        # Executar integração
        report = integration_manager.run_integration()
        
        # Salvar relatório
        report_file = integration_manager.save_report(args.save_report)
        
        # Mostrar resumo
        print("\n" + "="*60)
        print("RELATÓRIO DE INTEGRAÇÃO - JOBS PARALELOS NVD")
        print("="*60)
        
        print(f"Status: {report['status'].upper()}")
        print(f"Taxa de sucesso: {report['success_rate']:.1%}")
        
        # Mostrar backups criados
        if report['backups_created']:
            print(f"\nBackups criados: {len(report['backups_created'])}")
            for backup in report['backups_created']:
                print(f"  • {os.path.basename(backup['original'])} -> {backup['backup']}")
        
        # Mostrar arquivos modificados
        if report['files_modified']:
            print(f"\nArquivos modificados: {len(report['files_modified'])}")
            for file_mod in report['files_modified']:
                print(f"  • {file_mod['file']} ({file_mod['action']})")
        
        # Próximos passos
        print("\nPRÓXIMOS PASSOS:")
        print("1. Revisar e ajustar configurações em .env.parallel.template")
        print("2. Copiar template para .env e configurar variáveis")
        print("3. Executar script de migração para validar sistema")
        print("4. Testar jobs em ambiente de desenvolvimento")
        print("5. Implementar gradualmente em produção")
        
        print(f"\nRelatório detalhado salvo em: {report_file}")
        print("Backups dos arquivos originais criados em:", integration_manager.backup_dir)
        print("="*60)
        
        # Código de saída baseado no status
        if report['status'] == 'completed':
            return 0
        elif report['status'] == 'partial':
            return 1
        else:
            return 2
            
    except KeyboardInterrupt:
        logger.info("Integração interrompida pelo usuário")
        return 1
    except Exception as e:
        logger.error(f"Erro durante integração: {e}", exc_info=True)
        return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)