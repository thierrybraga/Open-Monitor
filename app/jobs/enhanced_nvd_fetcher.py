#!/usr/bin/env python3
"""
NVD Fetcher aprimorado com processamento paralelo e otimizações de performance.
Integra todos os serviços criados para máxima eficiência.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.extensions import db
from services.vulnerability_service import VulnerabilityService
from services.parallel_nvd_service import ParallelNVDService, ProcessingMetrics
from services.redis_cache_service import RedisCacheService
from services.bulk_database_service import BulkDatabaseService
from services.retry_service import RetryService, ErrorCategory, RetryConfig
from services.performance_monitor import PerformanceMonitor
from app.jobs.nvd_fetcher import NVDFetcher  # Importar o fetcher original
from app.utils.enhanced_logging import get_app_logger, get_db_logger, get_nvd_logger, progress_context, timed_operation

# Configurar loggers
app_logger = get_app_logger()
db_logger = get_db_logger()
nvd_logger = get_nvd_logger()
logger = logging.getLogger(__name__)

class EnhancedNVDFetcher:
    """
    NVD Fetcher aprimorado com processamento paralelo e otimizações.
    
    Características:
    - Processamento paralelo de requisições à API NVD
    - Cache Redis inteligente
    - Operações de banco em lote otimizadas
    - Sistema de retry robusto
    - Monitoramento de performance em tempo real
    - Fallback para o fetcher original
    """
    
    def __init__(self, app: Flask, max_workers: int = 10, enable_cache: bool = True,
                 enable_monitoring: bool = True, batch_size: int = 1000):
        """
        Inicializa o fetcher aprimorado.
        
        Args:
            app: Instância da aplicação Flask
            max_workers: Número máximo de workers paralelos
            enable_cache: Habilitar cache Redis
            enable_monitoring: Habilitar monitoramento de performance
            batch_size: Tamanho do lote para operações de banco
        """
        self.app = app
        self.max_workers = max_workers
        self.enable_cache = enable_cache
        self.enable_monitoring = enable_monitoring
        self.batch_size = batch_size
        
        # Inicializar serviços
        with app.app_context():
            # Criar sessão do banco de dados
            from app.extensions import db
            self.db_session = db.session
            
            self.vulnerability_service = VulnerabilityService(self.db_session)
            
            # Configuração para ParallelNVDService
            nvd_config = {
                "NVD_API_BASE": getattr(app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                "NVD_API_KEY": getattr(app.config, 'NVD_API_KEY', None),
                "NVD_PAGE_SIZE": getattr(app.config, 'NVD_PAGE_SIZE', 2000),
                "NVD_REQUEST_TIMEOUT": getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
                "NVD_USER_AGENT": getattr(app.config, 'NVD_USER_AGENT', "Sec4all.co Enhanced NVD Fetcher"),
                "BATCH_SIZE": batch_size,
                "DB_BATCH_SIZE": getattr(app.config, 'DB_BATCH_SIZE', 500)
            }
            
            self.parallel_service = ParallelNVDService(nvd_config, max_concurrent_requests=max_workers)
            self.bulk_db_service = BulkDatabaseService(batch_size=batch_size)
            self.retry_service = RetryService()
            
            # Cache Redis (opcional)
            self.cache_service = None
            if enable_cache:
                try:
                    self.cache_service = RedisCacheService()
                    logger.info("Cache Redis habilitado")
                except Exception as e:
                    logger.warning(f"Falha ao inicializar cache Redis: {e}")
            
            # Monitor de performance (opcional)
            self.performance_monitor = None
            if enable_monitoring:
                try:
                    self.performance_monitor = PerformanceMonitor()
                    self.performance_monitor.start_monitoring()
                    logger.info("Monitoramento de performance habilitado")
                except Exception as e:
                    logger.warning(f"Falha ao inicializar monitor: {e}")
            
            # Fetcher original como fallback
            import aiohttp
            self.original_session = aiohttp.ClientSession()
            self.original_fetcher = NVDFetcher(self.original_session, nvd_config)
        
        # Estatísticas
        self.stats = {
            'total_processed': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'parallel_batches': 0,
            'fallback_used': False,
            'start_time': None,
            'end_time': None
        }
        
        logger.info(f"Enhanced NVD Fetcher inicializado com {max_workers} workers")
    
    async def sync_nvd(self, full: bool = False, max_pages: Optional[int] = None,
                      use_parallel: bool = True) -> int:
        """
        Sincroniza dados NVD com processamento paralelo otimizado.
        
        Args:
            full: Sincronização completa ou incremental
            max_pages: Máximo de páginas a processar (para testes)
            use_parallel: Usar processamento paralelo
            
        Returns:
            Número total de vulnerabilidades processadas
        """
        self.stats['start_time'] = datetime.utcnow()
        
        with self.app.app_context():
            logger.info(f"Iniciando sincronização NVD (full={full}, parallel={use_parallel})")
            
            # Monitorar operação
            if self.performance_monitor:
                with self.performance_monitor.track_operation('nvd_sync', {'full': str(full)}) as operation:
                    try:
                        if use_parallel:
                            result = await self._sync_parallel(full, max_pages, operation)
                        else:
                            result = await self._sync_sequential(full, max_pages, operation)
                        
                        operation.metrics['total_processed'] = result
                        return result
                        
                    except Exception as e:
                        logger.error(f"Erro na sincronização: {e}")
                        operation.metrics['error'] = str(e)
                        raise
            else:
                if use_parallel:
                    return await self._sync_parallel(full, max_pages)
                else:
                    return await self._sync_sequential(full, max_pages)
    
    async def _sync_parallel(self, full: bool, max_pages: Optional[int],
                           operation=None) -> int:
        """
        Executa sincronização com processamento paralelo.
        
        Args:
            full: Sincronização completa
            max_pages: Máximo de páginas
            operation: Operação de monitoramento
            
        Returns:
            Número de vulnerabilidades processadas
        """
        try:
            sync_type = "COMPLETA" if full else "INCREMENTAL"
            nvd_logger.sync_started(full_sync=full)
            
            # Determinar range de sincronização
            last_synced_time = None
            if not full:
                last_synced_time = self.vulnerability_service.get_last_sync_time()
                if last_synced_time:
                    last_synced_time_str = last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                    nvd_logger.info(f"Última sincronização: {last_synced_time_str}")
            
            # Verificar cache primeiro
            cache_key = None
            if self.cache_service and not full:
                cache_key = f"nvd_sync_{last_synced_time.isoformat() if last_synced_time else 'full'}"
                cached_result = await self.cache_service.get_cached_vulnerabilities(
                    cache_key, return_count_only=True
                )
                if cached_result:
                    self.stats['cache_hits'] += 1
                    nvd_logger.cache_hit(cache_key)
                    nvd_logger.info(f"Dados encontrados no cache: {cached_result} vulnerabilidades")
                    return cached_result
                else:
                    self.stats['cache_misses'] += 1
                    nvd_logger.cache_miss(cache_key)
            
            # Buscar primeira página para determinar total
            nvd_logger.progress("Buscando primeira página para determinar total de vulnerabilidades")
            
            with timed_operation(nvd_logger, "Busca da primeira página"):
                first_page_data = await self.retry_service.retry_async(
                    self.original_fetcher.fetch_page,
                    0,
                    last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z') if last_synced_time else None,
                    category=ErrorCategory.NETWORK
                )
            
            if not first_page_data:
                nvd_logger.error("Falha ao buscar primeira página")
                return 0
            
            total_results = first_page_data.get('totalResults', 0)
            page_size = len(first_page_data.get('vulnerabilities', []))
            
            nvd_logger.api_call("NVD API", page=0, status_code=200)
            
            if total_results == 0:
                nvd_logger.info("Nenhuma vulnerabilidade nova encontrada")
                return 0
            
            # Calcular número de páginas
            total_pages = (total_results + self.original_fetcher.page_size - 1) // self.original_fetcher.page_size
            if max_pages:
                total_pages = min(total_pages, max_pages)
            
            nvd_logger.info(f"📊 Total de {total_results} vulnerabilidades em {total_pages} páginas")
            nvd_logger.performance_metric("Vulnerabilidades por página", page_size)
            
            # Processar primeira página
            all_vulnerabilities = []
            first_page_vulns = first_page_data.get('vulnerabilities', [])
            if first_page_vulns:
                nvd_logger.progress(f"Processando primeira página ({len(first_page_vulns)} vulnerabilidades)")
                processed_first_page = await self._process_vulnerabilities_batch(first_page_vulns)
                all_vulnerabilities.extend(processed_first_page)
                nvd_logger.batch_processed(len(processed_first_page), total_results)
            
            # Processar páginas restantes em paralelo
            if total_pages > 1:
                remaining_pages = list(range(1, total_pages))
                nvd_logger.info(f"🔄 Processando {len(remaining_pages)} páginas restantes em paralelo")
                
                # Usar barra de progresso para páginas
                with progress_context(len(remaining_pages), "Processando páginas") as progress:
                    # Dividir em lotes para processamento paralelo
                    batch_size = min(self.max_workers, len(remaining_pages))
                    
                    for i in range(0, len(remaining_pages), batch_size):
                        batch_pages = remaining_pages[i:i + batch_size]
                        
                        # Buscar páginas em paralelo
                        nvd_logger.progress(f"Buscando lote de {len(batch_pages)} páginas (páginas {batch_pages[0]}-{batch_pages[-1]})")
                        
                        with timed_operation(nvd_logger, f"Busca de lote {i//batch_size + 1}"):
                            page_data_batch = await self.parallel_service.fetch_pages_concurrent(
                                batch_pages,
                                last_synced_time.isoformat(timespec='milliseconds').replace('+00:00', 'Z') if last_synced_time else None
                            )
                        
                        # Processar dados das páginas
                        batch_vulnerabilities = 0
                        for page_idx, page_data in enumerate(page_data_batch):
                            if page_data and page_data.get('vulnerabilities'):
                                page_vulns = page_data['vulnerabilities']
                                processed_vulns = await self._process_vulnerabilities_batch(page_vulns)
                                all_vulnerabilities.extend(processed_vulns)
                                batch_vulnerabilities += len(processed_vulns)
                                
                                # Log individual da página
                                page_num = batch_pages[page_idx]
                                nvd_logger.vulnerability_processed(f"Página {page_num}", f"processada ({len(processed_vulns)} vulns)")
                        
                        # Atualizar progresso
                        progress.update(len(batch_pages), f"Lote {i//batch_size + 1}: {batch_vulnerabilities} vulnerabilidades")
                        
                        self.stats['parallel_batches'] += 1
                        nvd_logger.batch_processed(batch_vulnerabilities)
                        
                        if operation:
                            operation.metrics['processed_pages'] = i + len(batch_pages)
            
            # Salvar em lote no banco de dados
            if all_vulnerabilities:
                db_logger.info(f"💾 Iniciando salvamento de {len(all_vulnerabilities)} vulnerabilidades no banco")
                
                with timed_operation(db_logger, "Salvamento em lote no banco"):
                    with progress_context(len(all_vulnerabilities), "Salvando no banco") as progress:
                        bulk_stats = self.bulk_db_service.bulk_upsert_vulnerabilities(
                            all_vulnerabilities
                        )
                        progress.update(len(all_vulnerabilities), "Concluído")
                
                self.stats['total_processed'] = bulk_stats.inserted_records + bulk_stats.updated_records
                
                # Log detalhado dos resultados
                db_logger.database_operation(
                    "bulk_upsert",
                    f"✅ Operação concluída: {bulk_stats.inserted_records} inseridas, "
                    f"{bulk_stats.updated_records} atualizadas em {bulk_stats.duration:.2f}s"
                )
                
                db_logger.performance_metric("bulk_insert_rate", 
                                           f"{len(all_vulnerabilities)/bulk_stats.duration:.1f} vulns/s")
                
                # Atualizar cache
                if self.cache_service and cache_key:
                    nvd_logger.progress("Atualizando cache")
                    await self.cache_service.cache_vulnerabilities(
                        cache_key, all_vulnerabilities, ttl=3600
                    )
                    nvd_logger.cache_updated(cache_key, len(all_vulnerabilities))
                
                # Atualizar última sincronização
                sync_time = datetime.utcnow()
                self.vulnerability_service.update_last_sync_time(sync_time)
                db_logger.sync_completed(sync_time, self.stats['total_processed'])
                
                return self.stats['total_processed']
            else:
                nvd_logger.warning("⚠️ Nenhuma vulnerabilidade encontrada para processar")
                return 0
            
        except Exception as e:
            nvd_logger.error(f"❌ Erro no processamento paralelo: {e}")
            app_logger.error(f"Detalhes do erro: {str(e)}", exc_info=True)
            
            # Fallback para processamento sequencial
            nvd_logger.warning("🔄 Tentando fallback para processamento sequencial")
            self.stats['fallback_used'] = True
            return await self._sync_sequential(full, max_pages, operation)
    
    async def _sync_sequential(self, full: bool, max_pages: Optional[int],
                             operation=None) -> int:
        """
        Executa sincronização sequencial (fallback).
        
        Args:
            full: Sincronização completa
            max_pages: Máximo de páginas
            operation: Operação de monitoramento
            
        Returns:
            Número de vulnerabilidades processadas
        """
        nvd_logger.warning("⚠️ Executando sincronização sequencial (modo fallback)")
        app_logger.info("Iniciando processamento sequencial como fallback")
        
        try:
            with timed_operation(nvd_logger, "Sincronização sequencial"):
                # Usar o fetcher original com retry
                nvd_logger.progress("Executando fetcher original com retry")
                
                result = await self.retry_service.retry_async(
                    self.original_fetcher.update,
                    self.vulnerability_service,
                    full,
                    category=ErrorCategory.NETWORK,
                    config=RetryConfig(
                        max_attempts=3,
                        base_delay=2.0,
                        max_delay=30.0
                    )
                )
                
                self.stats['total_processed'] = result
                
                if result > 0:
                    nvd_logger.sync_completed(datetime.utcnow(), result)
                    app_logger.info(f"✅ Sincronização sequencial concluída: {result} vulnerabilidades processadas")
                else:
                    nvd_logger.warning("⚠️ Sincronização sequencial não processou nenhuma vulnerabilidade")
                
                return result
            
        except Exception as e:
            nvd_logger.error(f"❌ Erro na sincronização sequencial: {e}")
            app_logger.error(f"Falha crítica no fallback sequencial: {str(e)}", exc_info=True)
            raise
    
    async def _process_vulnerabilities_batch(self, vulnerabilities_raw: List[Dict]) -> List[Dict]:
        """
        Processa um lote de vulnerabilidades brutas.
        
        Args:
            vulnerabilities_raw: Lista de dados brutos de vulnerabilidades
            
        Returns:
            Lista de vulnerabilidades processadas
        """
        processed = []
        errors = 0
        
        nvd_logger.progress(f"Processando lote de {len(vulnerabilities_raw)} vulnerabilidades")
        
        for idx, vuln_data in enumerate(vulnerabilities_raw):
            try:
                cve_data = vuln_data.get('cve')
                if cve_data:
                    cve_id = cve_data.get('id', f'unknown_{idx}')
                    
                    # Usar o método de processamento do fetcher original
                    extracted_data = await self.original_fetcher.process_cve_data(cve_data)
                    if extracted_data:
                        processed.append(extracted_data)
                        nvd_logger.vulnerability_processed(cve_id, "processada com sucesso")
                    else:
                        nvd_logger.warning(f"⚠️ CVE {cve_id}: dados extraídos vazios")
                else:
                    nvd_logger.warning(f"⚠️ Vulnerabilidade {idx}: dados CVE ausentes")
                        
            except Exception as e:
                errors += 1
                cve_id = vuln_data.get('cve', {}).get('id', f'unknown_{idx}')
                nvd_logger.error(f"❌ Erro ao processar CVE {cve_id}: {e}")
                app_logger.warning(f"Falha no processamento da vulnerabilidade {idx}: {str(e)}")
                continue
        
        # Log do resultado do lote
        success_rate = ((len(processed) / len(vulnerabilities_raw)) * 100) if vulnerabilities_raw else 0
        nvd_logger.batch_processed(
            len(processed), 
            len(vulnerabilities_raw),
            f"Taxa de sucesso: {success_rate:.1f}% ({errors} erros)"
        )
        
        return processed
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de performance.
        
        Returns:
            Dicionário com estatísticas detalhadas
        """
        self.stats['end_time'] = datetime.utcnow()
        
        stats = {
            'enhanced_fetcher_stats': self.stats.copy(),
            'bulk_database_stats': self.bulk_db_service.get_performance_stats(),
            'parallel_service_stats': self.parallel_service.get_metrics().to_dict() if hasattr(self.parallel_service, 'get_metrics') else {},
            'retry_stats': {name: {
                'total_attempts': stat.total_attempts,
                'successful_attempts': stat.successful_attempts,
                'success_rate': stat.success_rate,
                'total_duration': stat.total_duration
            } for name, stat in self.retry_service.get_stats().items()}
        }
        
        if self.cache_service:
            stats['cache_stats'] = self.cache_service.get_stats()
        
        if self.performance_monitor:
            stats['system_performance'] = self.performance_monitor.get_performance_report(hours=1)
        
        # Calcular duração total
        if self.stats['start_time'] and self.stats['end_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            stats['enhanced_fetcher_stats']['total_duration_seconds'] = duration
            
            if self.stats['total_processed'] > 0:
                stats['enhanced_fetcher_stats']['vulnerabilities_per_second'] = \
                    self.stats['total_processed'] / duration
        
        return stats
    
    def optimize_database(self) -> Dict[str, Any]:
        """
        Executa otimizações no banco de dados.
        
        Returns:
            Relatório das otimizações
        """
        with self.app.app_context():
            # Criar índices otimizados
            created_indexes = self.bulk_db_service.create_optimized_indexes()
            
            # Executar otimizações
            optimization_report = self.bulk_db_service.optimize_database()
            optimization_report['created_indexes'] = created_indexes
            
            return optimization_report
    
    def cleanup(self):
        """Limpa recursos e para serviços."""
        if self.performance_monitor:
            self.performance_monitor.stop_monitoring()
        
        if self.cache_service:
            # Cache service cleanup se necessário
            pass
        
        # Fechar sessão aiohttp
        if hasattr(self, 'original_session') and self.original_session:
            asyncio.create_task(self.original_session.close())
        
        logger.info("Enhanced NVD Fetcher finalizado")

def setup_logging(level: str = 'INFO'):
    """Configura logging para o script."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('enhanced_nvd_fetcher.log')
        ]
    )

def create_app_context(env_name: str = None) -> Flask:
    """Cria contexto da aplicação Flask."""
    from app import create_app
    return create_app(env_name=env_name)

async def main():
    """Função principal para execução standalone."""
    parser = argparse.ArgumentParser(description='Enhanced NVD Fetcher')
    parser.add_argument('--full', action='store_true', help='Sincronização completa')
    parser.add_argument('--max-pages', type=int, help='Máximo de páginas para processar')
    parser.add_argument('--max-workers', type=int, default=10, help='Número de workers paralelos')
    parser.add_argument('--batch-size', type=int, default=1000, help='Tamanho do lote para DB')
    parser.add_argument('--no-cache', action='store_true', help='Desabilitar cache Redis')
    parser.add_argument('--no-monitoring', action='store_true', help='Desabilitar monitoramento')
    parser.add_argument('--no-parallel', action='store_true', help='Usar apenas processamento sequencial')
    parser.add_argument('--log-level', default='INFO', help='Nível de log')
    parser.add_argument('--optimize-db', action='store_true', help='Executar otimizações do banco')
    parser.add_argument('--stats-only', action='store_true', help='Mostrar apenas estatísticas')
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging(args.log_level)
    
    # Criar aplicação
    app = create_app_context()
    
    with app.app_context():
        # Inicializar fetcher aprimorado
        fetcher = EnhancedNVDFetcher(
            app=app,
            max_workers=args.max_workers,
            enable_cache=not args.no_cache,
            enable_monitoring=not args.no_monitoring,
            batch_size=args.batch_size
        )
        
        try:
            if args.optimize_db:
                logger.info("Executando otimizações do banco de dados...")
                optimization_report = fetcher.optimize_database()
                print("\n=== Relatório de Otimização ===")
                print(f"Dialeto: {optimization_report['dialect']}")
                print(f"Otimizações aplicadas: {len(optimization_report['optimizations_applied'])}")
                for opt in optimization_report['optimizations_applied']:
                    print(f"  - {opt}")
                if optimization_report['errors']:
                    print(f"Erros: {optimization_report['errors']}")
                print(f"Índices criados: {len(optimization_report.get('created_indexes', []))}")
                return
            
            if args.stats_only:
                stats = fetcher.get_performance_stats()
                print("\n=== Estatísticas de Performance ===")
                print(json.dumps(stats, indent=2, default=str))
                return
            
            # Executar sincronização
            start_time = time.time()
            
            total_processed = await fetcher.sync_nvd(
                full=args.full,
                max_pages=args.max_pages,
                use_parallel=not args.no_parallel
            )
            
            duration = time.time() - start_time
            
            # Mostrar resultados
            print("\n=== Resultados da Sincronização ===")
            print(f"Vulnerabilidades processadas: {total_processed}")
            print(f"Duração: {duration:.2f} segundos")
            if total_processed > 0:
                print(f"Taxa: {total_processed / duration:.2f} vulnerabilidades/segundo")
            
            # Mostrar estatísticas detalhadas
            stats = fetcher.get_performance_stats()
            print("\n=== Estatísticas Detalhadas ===")
            
            enhanced_stats = stats['enhanced_fetcher_stats']
            print(f"Cache hits: {enhanced_stats['cache_hits']}")
            print(f"Cache misses: {enhanced_stats['cache_misses']}")
            print(f"Lotes paralelos: {enhanced_stats['parallel_batches']}")
            print(f"Fallback usado: {enhanced_stats['fallback_used']}")
            
            if 'bulk_database_stats' in stats:
                db_stats = stats['bulk_database_stats']
                print(f"\nBanco de dados:")
                print(f"  Dialeto: {db_stats['database_dialect']}")
                print(f"  Tamanho do lote: {db_stats['batch_size']}")
                print(f"  Suporte a upsert: {db_stats['supports_upsert']}")
            
        except KeyboardInterrupt:
            logger.info("Sincronização interrompida pelo usuário")
        except Exception as e:
            logger.error(f"Erro durante execução: {e}", exc_info=True)
            return 1
        finally:
            fetcher.cleanup()
    
    return 0

if __name__ == '__main__':
    import json
    exit_code = asyncio.run(main())
    sys.exit(exit_code)