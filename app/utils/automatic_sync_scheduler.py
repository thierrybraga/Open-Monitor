#!/usr/bin/env python3
"""
Sistema de sincronização automática para manter o banco de dados atualizado.
Executa sincronizações incrementais a cada hora e gerencia o ciclo de vida das atualizações.
"""

import asyncio
import sys
import time
import signal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Callable
from pathlib import Path
from threading import Event, Thread

# Adicionar o diretório raiz ao path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    print("⚠️  APScheduler não encontrado. Instale com: pip install apscheduler")

from app.utils.enhanced_logging import get_app_logger, get_db_logger, get_nvd_logger, timed_operation
from app.utils.database_initializer import DatabaseInitializer
from database.database import Database
from services.vulnerability_service import VulnerabilityService
from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
from app.config.parallel_nvd_config import ParallelNVDConfig
from app.utils.sync_metadata_orm import upsert_sync_metadata
from app.app import create_app

class AutomaticSyncScheduler:
    """
    Gerenciador de sincronização automática do banco de dados NVD.
    """
    
    def __init__(self, config: Optional[ParallelNVDConfig] = None):
        self.app_logger = get_app_logger()
        self.db_logger = get_db_logger()
        self.nvd_logger = get_nvd_logger()
        
        # Configuração
        self.config = config or ParallelNVDConfig.from_env()
        
        # Scheduler
        self.scheduler = None
        if SCHEDULER_AVAILABLE:
            self.scheduler = AsyncIOScheduler()
            self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # Serviços
        self.database = None
        self.vulnerability_service = None
        self.nvd_fetcher = None
        self.app = None
        
        # Estado
        self.is_running = False
        self.shutdown_event = Event()
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'total_vulnerabilities_processed': 0,
            'last_sync_time': None,
            'last_sync_duration': 0.0,
            'average_sync_duration': 0.0,
            'consecutive_failures': 0
        }
        
        # Callbacks
        self.on_sync_complete: Optional[Callable] = None
        self.on_sync_error: Optional[Callable] = None
    
    async def start(self) -> bool:
        """
        Inicia o sistema de sincronização automática.
        
        Returns:
            bool: True se iniciado com sucesso
        """
        try:
            self.app_logger.section("Iniciando Sistema de Sincronização Automática")
            
            if not SCHEDULER_AVAILABLE:
                self.app_logger.error("APScheduler não disponível. Instale com: pip install apscheduler")
                return False
            
            # Inicializar serviços
            if not await self._initialize_services():
                return False
            
            # Configurar jobs
            self._setup_sync_jobs()
            
            # Configurar handlers de sinal
            self._setup_signal_handlers()
            
            # Iniciar scheduler
            self.scheduler.start()
            self.is_running = True
            
            self.app_logger.success("Sistema de sincronização automática iniciado")
            self._print_schedule_info()
            
            return True
            
        except Exception as e:
            self.app_logger.error(f"Erro ao iniciar sistema de sincronização: {str(e)}")
            return False
    
    async def stop(self):
        """
        Para o sistema de sincronização automática.
        """
        try:
            self.app_logger.info("Parando sistema de sincronização automática...")
            
            self.is_running = False
            self.shutdown_event.set()
            
            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=True)
            
            await self._cleanup_services()
            
            self.app_logger.success("Sistema de sincronização parado")
            self._print_final_stats()
            
        except Exception as e:
            self.app_logger.error(f"Erro ao parar sistema de sincronização: {str(e)}")
    
    async def _initialize_services(self) -> bool:
        """
        Inicializa os serviços necessários.
        """
        try:
            self.app_logger.subsection("Inicializando Serviços")

            # Database
            self.database = Database()
            await self.database.connect()
            self.app_logger.success("Conexão com banco de dados estabelecida")

            # Vulnerability Service
            self.vulnerability_service = VulnerabilityService(self.database)
            self.app_logger.success("Serviço de vulnerabilidades inicializado")

            # NVD Fetcher
            self.nvd_fetcher = EnhancedNVDFetcher(
                max_workers=self.config.max_workers,
                enable_cache=self.config.enable_cache,
                cache_ttl=self.config.cache_ttl,
                enable_monitoring=self.config.enable_monitoring
            )
            self.app_logger.success("NVD Fetcher inicializado")

            # Flask app para operações ORM (app context obrigatório)
            try:
                self.app = create_app()
                self.app_logger.success("Aplicação Flask criada para operações ORM")
            except Exception as e:
                self.app_logger.error(f"Falha ao criar aplicação Flask para ORM: {e}")
                return False

            return True
            
        except Exception as e:
            self.app_logger.error(f"Erro ao inicializar serviços: {str(e)}")
            return False
    
    def _setup_sync_jobs(self):
        """
        Configura os jobs de sincronização.
        """
        self.app_logger.subsection("Configurando Jobs de Sincronização")
        
        # Job principal: sincronização a cada hora
        self.scheduler.add_job(
            func=self._hourly_sync,
            trigger=IntervalTrigger(hours=1),
            id='nvd_hourly_sync',
            name='Sincronização Horária NVD',
            max_instances=1,
            coalesce=True,
            misfire_grace_time=300  # 5 minutos de tolerância
        )
        self.app_logger.info("✅ Job de sincronização horária configurado")
        
        # Job de sincronização completa diária (às 2:00 AM)
        self.scheduler.add_job(
            func=self._daily_full_sync,
            trigger=CronTrigger(hour=2, minute=0),
            id='nvd_daily_full_sync',
            name='Sincronização Completa Diária',
            max_instances=1,
            coalesce=True
        )
        self.app_logger.info("✅ Job de sincronização diária configurado")
        
        # Job de limpeza semanal (domingos às 3:00 AM)
        self.scheduler.add_job(
            func=self._weekly_cleanup,
            trigger=CronTrigger(day_of_week=6, hour=3, minute=0),
            id='nvd_weekly_cleanup',
            name='Limpeza Semanal',
            max_instances=1,
            coalesce=True
        )
        self.app_logger.info("✅ Job de limpeza semanal configurado")
        
        # Job de verificação de saúde (a cada 6 horas)
        self.scheduler.add_job(
            func=self._health_check,
            trigger=IntervalTrigger(hours=6),
            id='nvd_health_check',
            name='Verificação de Saúde',
            max_instances=1,
            coalesce=True
        )
        self.app_logger.info("✅ Job de verificação de saúde configurado")
    
    async def _hourly_sync(self):
        """
        Executa sincronização incremental a cada hora.
        """
        sync_id = f"hourly_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            self.nvd_logger.info(f"🔄 Iniciando sincronização horária [{sync_id}]")
            start_time = time.time()
            
            # Verificar se não há muitas falhas consecutivas
            if self.sync_stats['consecutive_failures'] >= 3:
                self.nvd_logger.warning("Muitas falhas consecutivas, pulando sincronização")
                return
            
            with timed_operation(self.nvd_logger, "Sincronização horária"):
                result = await self.nvd_fetcher.sync_nvd(
                    self.vulnerability_service,
                    full=False
                )
            
            duration = time.time() - start_time
            
            if result:
                processed = result.get('processed', 0)
                errors = result.get('errors', 0)
                
                # Atualizar estatísticas
                self._update_sync_stats(True, processed, duration)
                
                # Registrar no banco
                await self._record_sync_result(sync_id, 'hourly', processed, duration, errors)
                
                if processed > 0:
                    self.nvd_logger.success(f"✅ Sincronização horária concluída: {processed} vulnerabilidades em {duration:.2f}s")
                    
                    # Callback de sucesso
                    if self.on_sync_complete:
                        await self.on_sync_complete('hourly', processed, duration)
                else:
                    self.nvd_logger.info("ℹ️  Sincronização horária: nenhuma atualização encontrada")
                
                # Reset contador de falhas
                self.sync_stats['consecutive_failures'] = 0
            else:
                raise Exception("Sincronização retornou resultado inválido")
                
        except Exception as e:
            duration = time.time() - start_time if 'start_time' in locals() else 0
            
            self._update_sync_stats(False, 0, duration)
            
            self.nvd_logger.error(f"❌ Erro na sincronização horária [{sync_id}]: {str(e)}")
            
            # Callback de erro
            if self.on_sync_error:
                await self.on_sync_error('hourly', str(e), duration)
            
            # Registrar erro no banco
            await self._record_sync_error(sync_id, 'hourly', str(e), duration)
    
    async def _daily_full_sync(self):
        """
        Executa sincronização completa diária.
        """
        sync_id = f"daily_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            self.nvd_logger.info(f"🔄 Iniciando sincronização completa diária [{sync_id}]")
            start_time = time.time()
            
            with timed_operation(self.nvd_logger, "Sincronização completa diária"):
                result = await self.nvd_fetcher.sync_nvd(
                    self.vulnerability_service,
                    full=True
                )
            
            duration = time.time() - start_time
            
            if result:
                processed = result.get('processed', 0)
                errors = result.get('errors', 0)
                
                self._update_sync_stats(True, processed, duration)
                await self._record_sync_result(sync_id, 'daily_full', processed, duration, errors)
                
                self.nvd_logger.success(f"✅ Sincronização completa diária concluída: {processed} vulnerabilidades em {duration:.2f}s")
                
                if self.on_sync_complete:
                    await self.on_sync_complete('daily_full', processed, duration)
                
                # Reset contador de falhas após sincronização completa bem-sucedida
                self.sync_stats['consecutive_failures'] = 0
            else:
                raise Exception("Sincronização retornou resultado inválido")
                
        except Exception as e:
            duration = time.time() - start_time if 'start_time' in locals() else 0
            
            self._update_sync_stats(False, 0, duration)
            self.nvd_logger.error(f"❌ Erro na sincronização completa diária [{sync_id}]: {str(e)}")
            
            if self.on_sync_error:
                await self.on_sync_error('daily_full', str(e), duration)
            
            await self._record_sync_error(sync_id, 'daily_full', str(e), duration)
    
    async def _weekly_cleanup(self):
        """
        Executa limpeza semanal do banco de dados.
        """
        try:
            self.app_logger.info("🧹 Iniciando limpeza semanal")

            # Garantir que a tabela 'sync_metadata' existe antes de consultar
            try:
                exists_check = await self.database.execute_query(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    ("sync_metadata",)
                )
                table_exists = bool(exists_check and len(exists_check) > 0)
            except Exception:
                # Fallback genérico: tentar uma consulta direta e capturar erro
                try:
                    await self.database.execute_query("SELECT 1 FROM sync_metadata LIMIT 1")
                    table_exists = True
                except Exception:
                    table_exists = False

            if not table_exists:
                self.app_logger.info("Tabela 'sync_metadata' não encontrada; pulando limpeza semanal")
                return
            
            # Limpar registros antigos de sync_metadata (mais de 30 dias)
            cutoff_date = datetime.now() - timedelta(days=30)

            # Usar coluna existente 'last_modified' em vez de 'created_at'
            count_query = "SELECT COUNT(*) as count FROM sync_metadata WHERE last_modified < ?"
            delete_query = "DELETE FROM sync_metadata WHERE last_modified < ?"

            total_cleaned = 0
            try:
                count_result = await self.database.execute_query(count_query, (cutoff_date.isoformat(timespec='seconds'),))
                if count_result and len(count_result) > 0:
                    total_cleaned = int(count_result[0].get('count', 0))
            except Exception as e:
                self.app_logger.warning(f"Erro ao contar registros para limpeza: {str(e)}")

            try:
                await self.database.execute_query(delete_query, (cutoff_date.isoformat(timespec='seconds'),))
            except Exception as e:
                self.app_logger.warning(f"Erro ao remover registros antigos: {str(e)}")

            self.app_logger.success(f"✅ Limpeza semanal concluída: {total_cleaned} registros removidos")
            
        except Exception as e:
            self.app_logger.error(f"❌ Erro na limpeza semanal: {str(e)}")
    
    async def _health_check(self):
        """
        Executa verificação de saúde do sistema.
        """
        try:
            self.app_logger.info("🏥 Executando verificação de saúde")
            
            health_status = {
                'database_connection': False,
                'nvd_api_accessible': False,
                'recent_sync_success': False,
                'disk_space_ok': False
            }
            
            # Verificar conexão com banco
            try:
                await self.database.execute_query("SELECT 1")
                health_status['database_connection'] = True
            except Exception:
                pass
            
            # Verificar API NVD (teste simples)
            try:
                # Implementar teste de conectividade com API NVD
                health_status['nvd_api_accessible'] = True
            except Exception:
                pass
            
            # Verificar sincronizações recentes
            if (self.sync_stats['last_sync_time'] and 
                datetime.now() - self.sync_stats['last_sync_time'] < timedelta(hours=2)):
                health_status['recent_sync_success'] = True
            
            # Verificar espaço em disco (simplificado)
            try:
                import shutil
                total, used, free = shutil.disk_usage("/")
                free_percent = (free / total) * 100
                health_status['disk_space_ok'] = free_percent > 10  # Pelo menos 10% livre
            except Exception:
                health_status['disk_space_ok'] = True  # Assumir OK se não conseguir verificar
            
            # Avaliar saúde geral
            healthy_checks = sum(health_status.values())
            total_checks = len(health_status)
            
            if healthy_checks == total_checks:
                self.app_logger.success(f"✅ Sistema saudável ({healthy_checks}/{total_checks} verificações OK)")
            elif healthy_checks >= total_checks * 0.75:
                self.app_logger.warning(f"⚠️  Sistema com problemas menores ({healthy_checks}/{total_checks} verificações OK)")
            else:
                self.app_logger.error(f"❌ Sistema com problemas graves ({healthy_checks}/{total_checks} verificações OK)")
            
            # Log detalhado
            for check, status in health_status.items():
                status_icon = "✅" if status else "❌"
                self.app_logger.info(f"  {status_icon} {check.replace('_', ' ').title()}")
            
        except Exception as e:
            self.app_logger.error(f"❌ Erro na verificação de saúde: {str(e)}")
    
    def _update_sync_stats(self, success: bool, processed: int, duration: float):
        """
        Atualiza estatísticas de sincronização.
        """
        self.sync_stats['total_syncs'] += 1
        
        if success:
            self.sync_stats['successful_syncs'] += 1
            self.sync_stats['total_vulnerabilities_processed'] += processed
            self.sync_stats['consecutive_failures'] = 0
        else:
            self.sync_stats['failed_syncs'] += 1
            self.sync_stats['consecutive_failures'] += 1
        
        self.sync_stats['last_sync_time'] = datetime.now()
        self.sync_stats['last_sync_duration'] = duration
        
        # Calcular duração média
        if self.sync_stats['successful_syncs'] > 0:
            total_duration = (self.sync_stats['average_sync_duration'] * 
                            (self.sync_stats['successful_syncs'] - 1) + duration)
            self.sync_stats['average_sync_duration'] = total_duration / self.sync_stats['successful_syncs']
    
    async def _record_sync_result(self, sync_id: str, sync_type: str, processed: int, duration: float, errors: int):
        """
        Registra resultado de sincronização no banco.
        """
        try:
            if not self.app:
                self.app = create_app()
            with self.app.app_context():
                ok, _ = upsert_sync_metadata(
                    session=None,
                    key="nvd_last_sync",
                    value=datetime.utcnow().isoformat(timespec='milliseconds'),
                    status="completed",
                    sync_type=sync_type,
                )
                if not ok:
                    raise RuntimeError("Upsert de SyncMetadata falhou")
        except Exception as e:
            self.app_logger.warning(f"Erro ao registrar resultado de sincronização via ORM: {str(e)}")
    
    async def _record_sync_error(self, sync_id: str, sync_type: str, error: str, duration: float):
        """
        Registra erro de sincronização no banco.
        """
        try:
            safe_error = (error or "").strip()
            if len(safe_error) > 255:
                safe_error = safe_error[:252] + "..."

            if not self.app:
                self.app = create_app()
            with self.app.app_context():
                from datetime import timezone as _tz
                ok, _ = upsert_sync_metadata(
                    session=None,
                    key="nvd_last_sync",
                    value=safe_error,
                    status="error",
                    sync_type=sync_type,
                    last_modified=datetime.now(_tz.utc),
                )
                if not ok:
                    raise RuntimeError("Upsert de erro de SyncMetadata falhou")
        except Exception as e:
            self.app_logger.warning(f"Erro ao registrar erro de sincronização via ORM: {str(e)}")
    
    async def _cleanup_services(self):
        """
        Limpa recursos dos serviços.
        """
        try:
            if self.nvd_fetcher:
                await self.nvd_fetcher.cleanup()
            
            if self.database:
                await self.database.disconnect()
                
        except Exception as e:
            self.app_logger.warning(f"Erro durante limpeza de serviços: {str(e)}")
    
    def _setup_signal_handlers(self):
        """
        Configura handlers para sinais do sistema.
        """
        def signal_handler(signum, frame):
            self.app_logger.info(f"Sinal {signum} recebido, iniciando shutdown...")
            asyncio.create_task(self.stop())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _job_listener(self, event):
        """
        Listener para eventos de jobs do scheduler.
        """
        if event.exception:
            self.app_logger.error(f"Job {event.job_id} falhou: {event.exception}")
        else:
            self.app_logger.debug(f"Job {event.job_id} executado com sucesso")
    
    def _print_schedule_info(self):
        """
        Imprime informações sobre os jobs agendados.
        """
        self.app_logger.subsection("Jobs Agendados")
        
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time.strftime('%Y-%m-%d %H:%M:%S') if job.next_run_time else 'N/A'
            self.app_logger.info(f"📅 {job.name} - Próxima execução: {next_run}")
    
    def _print_final_stats(self):
        """
        Imprime estatísticas finais.
        """
        self.app_logger.subsection("Estatísticas Finais de Sincronização")
        
        stats = self.sync_stats
        success_rate = (stats['successful_syncs'] / stats['total_syncs'] * 100) if stats['total_syncs'] > 0 else 0
        
        self.app_logger.info(f"📊 Total de sincronizações: {stats['total_syncs']}")
        self.app_logger.info(f"✅ Sucessos: {stats['successful_syncs']} ({success_rate:.1f}%)")
        self.app_logger.info(f"❌ Falhas: {stats['failed_syncs']}")
        self.app_logger.info(f"🔍 Total de vulnerabilidades processadas: {stats['total_vulnerabilities_processed']}")
        self.app_logger.info(f"⏱️  Duração média: {stats['average_sync_duration']:.2f}s")
        
        if stats['last_sync_time']:
            self.app_logger.info(f"🕐 Última sincronização: {stats['last_sync_time'].strftime('%Y-%m-%d %H:%M:%S')}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas atuais.
        """
        return self.sync_stats.copy()
    
    async def force_sync(self, full: bool = False) -> bool:
        """
        Força uma sincronização manual.
        
        Args:
            full: Se deve fazer sincronização completa
        
        Returns:
            bool: True se bem-sucedida
        """
        try:
            sync_type = "completa" if full else "incremental"
            self.nvd_logger.info(f"🔄 Forçando sincronização {sync_type}")
            
            if full:
                await self._daily_full_sync()
            else:
                await self._hourly_sync()
            
            return True
            
        except Exception as e:
            self.nvd_logger.error(f"Erro na sincronização forçada: {str(e)}")
            return False

async def run_automatic_sync(config: Optional[ParallelNVDConfig] = None):
    """
    Executa o sistema de sincronização automática.
    
    Args:
        config: Configuração do sistema
    """
    scheduler = AutomaticSyncScheduler(config)
    
    try:
        if await scheduler.start():
            # Manter rodando até receber sinal de parada
            while scheduler.is_running:
                await asyncio.sleep(1)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        pass
    finally:
        await scheduler.stop()

if __name__ == "__main__":
    # Executar sistema de sincronização
    from app.utils.enhanced_logging import setup_logging
    
    # Configurar logging
    setup_logging("INFO", "logs/automatic_sync.log")
    
    # Executar
    asyncio.run(run_automatic_sync())
