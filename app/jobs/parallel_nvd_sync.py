#!/usr/bin/env python3
"""
Script de sincronização NVD com processamento paralelo.
Integra o ParallelNVDService com o sistema existente.
"""

import sys
import os
import asyncio
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Adicionar o diretório pai ao path para importações
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from app.extensions import db
from app.models.sync_metadata import SyncMetadata
from services.parallel_nvd_service import ParallelNVDService
from services.redis_cache_service import RedisCacheService
from services.vulnerability_service import VulnerabilityService
from app.config.scheduler_config import SchedulerConfig

logger = logging.getLogger(__name__)

def setup_logging(debug: bool = False):
    """Configura logging para o script."""
    level = logging.DEBUG if debug else logging.INFO
    
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('logs/parallel_nvd_sync.log', mode='a')
        ]
    )
    
    # Reduzir verbosidade de bibliotecas externas
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

def create_app():
    """Cria instância da aplicação Flask para contexto de banco."""
    app = Flask(__name__)
    
    # Carregar configurações
    from settings.development import DevelopmentConfig
    app.config.from_object(DevelopmentConfig)
    
    # Inicializar extensões
    db.init_app(app)
    
    return app

def get_nvd_config(app):
    """Extrai configurações NVD da aplicação."""
    return {
        'NVD_API_BASE': getattr(app.config, 'NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0'),
        'NVD_API_KEY': getattr(app.config, 'NVD_API_KEY', None),
        'NVD_PAGE_SIZE': getattr(app.config, 'NVD_PAGE_SIZE', 2000),
        'NVD_REQUEST_TIMEOUT': getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
        'NVD_USER_AGENT': getattr(app.config, 'NVD_USER_AGENT', 'Sec4all.co Parallel NVD Fetcher'),
        'NVD_MAX_RETRIES': getattr(app.config, 'NVD_MAX_RETRIES', 3),
        'BATCH_SIZE': getattr(app.config, 'NVD_BATCH_SIZE', 100),
        'DB_BATCH_SIZE': getattr(app.config, 'NVD_DB_BATCH_SIZE', 500),
        'MAX_CONCURRENT_REQUESTS': getattr(app.config, 'NVD_MAX_CONCURRENT_REQUESTS', 5)
    }

def get_redis_config(app):
    """Extrai configurações Redis da aplicação."""
    return {
        'REDIS_CACHE_ENABLED': app.config.get('REDIS_CACHE_ENABLED', True),
        'REDIS_URL': app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
        'REDIS_HOST': app.config.get('REDIS_HOST', 'localhost'),
        'REDIS_PORT': app.config.get('REDIS_PORT', 6379),
        'REDIS_DB': app.config.get('REDIS_DB', 0),
        'REDIS_PASSWORD': app.config.get('REDIS_PASSWORD'),
        'CACHE_DEFAULT_TTL': app.config.get('CACHE_DEFAULT_TTL', 3600),
        'CACHE_MAX_TTL': app.config.get('CACHE_MAX_TTL', 86400),
        'CACHE_KEY_PREFIX': app.config.get('CACHE_KEY_PREFIX', 'nvd_cache:'),
        'CACHE_USE_COMPRESSION': app.config.get('CACHE_USE_COMPRESSION', True),
        'CACHE_COMPRESSION_THRESHOLD': app.config.get('CACHE_COMPRESSION_THRESHOLD', 1024)
    }

async def run_parallel_sync(full_sync: bool = False, max_concurrent: int = 5, 
                          use_cache: bool = True, debug: bool = False):
    """
    Executa sincronização paralela da API NVD.
    
    Args:
        full_sync: Se True, faz sincronização completa
        max_concurrent: Número máximo de requisições concorrentes
        use_cache: Se True, usa cache Redis
        debug: Se True, ativa logs de debug
    """
    setup_logging(debug)
    
    logger.info("=== Iniciando Sincronização Paralela NVD ===")
    logger.info(f"Modo: {'Completo' if full_sync else 'Incremental'}")
    logger.info(f"Requisições concorrentes: {max_concurrent}")
    logger.info(f"Cache Redis: {'Ativado' if use_cache else 'Desativado'}")
    
    # Criar aplicação Flask
    app = create_app()
    
    with app.app_context():
        try:
            # Obter configurações
            nvd_config = get_nvd_config(app)
            nvd_config['MAX_CONCURRENT_REQUESTS'] = max_concurrent
            
            redis_config = get_redis_config(app)
            redis_config['REDIS_CACHE_ENABLED'] = use_cache
            
            # Inicializar serviços
            logger.info("Inicializando serviços...")
            
            # Cache Redis
            cache_service = RedisCacheService(redis_config)
            cache_info = cache_service.get_cache_info()
            logger.info(f"Cache Redis: {cache_info.get('enabled', False)}")
            
            # Serviço de vulnerabilidades
            from sqlalchemy.orm import sessionmaker
            Session = sessionmaker(bind=db.engine)
            session = Session()
            vulnerability_service = VulnerabilityService(session)
            
            # Serviço de processamento paralelo
            parallel_service = ParallelNVDService(nvd_config, max_concurrent)
            
            # Verificar última sincronização
            if not full_sync:
                last_sync = vulnerability_service.get_last_sync_time()
                if last_sync:
                    logger.info(f"Última sincronização: {last_sync}")
                else:
                    logger.info("Nenhuma sincronização anterior encontrada, executando sync completo")
                    full_sync = True
            
            # Executar sincronização paralela
            logger.info("Iniciando processamento paralelo...")
            start_time = datetime.now()
            
            metrics = await parallel_service.parallel_sync(
                full_sync=full_sync,
                vulnerability_service=vulnerability_service
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Relatório de performance
            logger.info("=== Relatório de Performance ===")
            performance_report = parallel_service.get_performance_report()
            
            for key, value in performance_report.items():
                logger.info(f"{key}: {value}")
            
            # Estatísticas do cache
            if use_cache:
                cache_stats = cache_service.get_cache_info()
                logger.info("=== Estatísticas do Cache ===")
                if 'stats' in cache_stats:
                    for key, value in cache_stats['stats'].items():
                        logger.info(f"Cache {key}: {value}")
            
            # Resumo final
            logger.info("=== Resumo Final ===")
            logger.info(f"Duração total: {duration:.2f} segundos")
            logger.info(f"CVEs processados: {metrics.total_cves_processed}")
            logger.info(f"CVEs salvos: {metrics.total_cves_saved}")
            logger.info(f"Taxa de sucesso: {metrics.success_rate:.1f}%")
            logger.info(f"Performance: {metrics.cves_per_second:.2f} CVEs/segundo")
            
            if metrics.total_cves_saved > 0:
                logger.info("✅ Sincronização concluída com sucesso!")
                return True
            else:
                logger.warning("⚠️ Nenhum CVE foi salvo")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro durante sincronização: {e}", exc_info=True)
            return False

def benchmark_performance(iterations: int = 3):
    """
    Executa benchmark de performance comparando diferentes configurações.
    
    Args:
        iterations: Número de iterações para cada teste
    """
    logger.info("=== Iniciando Benchmark de Performance ===")
    
    # Configurações para testar
    test_configs = [
        {'concurrent': 1, 'cache': False, 'name': 'Sequencial sem cache'},
        {'concurrent': 1, 'cache': True, 'name': 'Sequencial com cache'},
        {'concurrent': 3, 'cache': False, 'name': 'Paralelo (3) sem cache'},
        {'concurrent': 3, 'cache': True, 'name': 'Paralelo (3) com cache'},
        {'concurrent': 5, 'cache': True, 'name': 'Paralelo (5) com cache'},
        {'concurrent': 10, 'cache': True, 'name': 'Paralelo (10) com cache'}
    ]
    
    results = []
    
    for config in test_configs:
        logger.info(f"\n--- Testando: {config['name']} ---")
        
        config_results = []
        
        for i in range(iterations):
            logger.info(f"Iteração {i+1}/{iterations}")
            
            start_time = datetime.now()
            
            # Executar teste (apenas incremental para benchmark)
            success = asyncio.run(run_parallel_sync(
                full_sync=False,
                max_concurrent=config['concurrent'],
                use_cache=config['cache'],
                debug=False
            ))
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            config_results.append({
                'duration': duration,
                'success': success
            })
            
            logger.info(f"Duração: {duration:.2f}s, Sucesso: {success}")
        
        # Calcular estatísticas
        successful_runs = [r for r in config_results if r['success']]
        if successful_runs:
            avg_duration = sum(r['duration'] for r in successful_runs) / len(successful_runs)
            min_duration = min(r['duration'] for r in successful_runs)
            max_duration = max(r['duration'] for r in successful_runs)
            
            results.append({
                'config': config['name'],
                'avg_duration': avg_duration,
                'min_duration': min_duration,
                'max_duration': max_duration,
                'success_rate': len(successful_runs) / len(config_results) * 100
            })
        
    # Relatório final
    logger.info("\n=== Relatório de Benchmark ===")
    logger.info(f"{'Configuração':<25} {'Média (s)':<12} {'Mín (s)':<10} {'Máx (s)':<10} {'Taxa Sucesso':<12}")
    logger.info("-" * 80)
    
    for result in results:
        logger.info(
            f"{result['config']:<25} "
            f"{result['avg_duration']:<12.2f} "
            f"{result['min_duration']:<10.2f} "
            f"{result['max_duration']:<10.2f} "
            f"{result['success_rate']:<12.1f}%"
        )
    
    # Encontrar melhor configuração
    if results:
        best_config = min(results, key=lambda x: x['avg_duration'])
        logger.info(f"\n🏆 Melhor configuração: {best_config['config']}")
        logger.info(f"   Tempo médio: {best_config['avg_duration']:.2f}s")

def main():
    """Função principal do script."""
    parser = argparse.ArgumentParser(
        description='Sincronização paralela da API NVD',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python parallel_nvd_sync.py --full                    # Sincronização completa
  python parallel_nvd_sync.py --incremental             # Sincronização incremental
  python parallel_nvd_sync.py --concurrent 10 --cache   # 10 requisições paralelas com cache
  python parallel_nvd_sync.py --benchmark               # Executar benchmark
  python parallel_nvd_sync.py --debug                   # Modo debug
        """
    )
    
    # Argumentos principais
    sync_group = parser.add_mutually_exclusive_group(required=True)
    sync_group.add_argument(
        '--full', 
        action='store_true',
        help='Executa sincronização completa (todos os CVEs)'
    )
    sync_group.add_argument(
        '--incremental', 
        action='store_true',
        help='Executa sincronização incremental (apenas CVEs modificados)'
    )
    sync_group.add_argument(
        '--benchmark', 
        action='store_true',
        help='Executa benchmark de performance'
    )
    
    # Configurações de performance
    parser.add_argument(
        '--concurrent', 
        type=int, 
        default=5,
        help='Número máximo de requisições concorrentes (padrão: 5)'
    )
    parser.add_argument(
        '--cache', 
        action='store_true',
        help='Ativa cache Redis (padrão: desativado)'
    )
    parser.add_argument(
        '--no-cache', 
        action='store_true',
        help='Desativa cache Redis explicitamente'
    )
    
    # Configurações de debug
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Ativa logs de debug'
    )
    parser.add_argument(
        '--benchmark-iterations', 
        type=int, 
        default=3,
        help='Número de iterações para benchmark (padrão: 3)'
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if args.concurrent < 1 or args.concurrent > 20:
        parser.error("--concurrent deve estar entre 1 e 20")
    
    if args.benchmark_iterations < 1 or args.benchmark_iterations > 10:
        parser.error("--benchmark-iterations deve estar entre 1 e 10")
    
    # Determinar configuração de cache
    use_cache = args.cache and not args.no_cache
    
    try:
        if args.benchmark:
            # Executar benchmark
            benchmark_performance(args.benchmark_iterations)
        else:
            # Executar sincronização
            success = asyncio.run(run_parallel_sync(
                full_sync=args.full,
                max_concurrent=args.concurrent,
                use_cache=use_cache,
                debug=args.debug
            ))
            
            sys.exit(0 if success else 1)
            
    except KeyboardInterrupt:
        logger.info("\n⏹️ Sincronização interrompida pelo usuário")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()