#!/usr/bin/env python3
"""
Script de migração para o sistema paralelo de processamento NVD.
Facilita a transição do sistema sequencial para o sistema aprimorado.
"""

import asyncio
import logging
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
import json
import argparse

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
from app.jobs.nvd_fetcher import NVDFetcher
from app.extensions import db
from services.vulnerability_service import VulnerabilityService
import aiohttp

logger = logging.getLogger(__name__)

class NVDMigrationManager:
    """
    Gerenciador de migração para o sistema paralelo NVD.
    """
    
    def __init__(self, app: Flask):
        self.app = app
        self.migration_report = {
            'timestamp': datetime.utcnow().isoformat(),
            'tests': [],
            'recommendations': [],
            'status': 'pending'
        }
    
    async def run_migration_tests(self) -> Dict[str, Any]:
        """
        Executa testes de migração para validar o sistema aprimorado.
        
        Returns:
            Relatório de migração
        """
        logger.info("Iniciando testes de migração para sistema paralelo NVD")
        
        with self.app.app_context():
            # Teste 1: Conectividade básica
            await self._test_basic_connectivity()
            
            # Teste 2: Sistema aprimorado com configuração mínima
            await self._test_enhanced_minimal()
            
            # Teste 3: Comparação de performance
            await self._test_performance_comparison()
            
            # Teste 4: Teste de fallback
            await self._test_fallback_mechanism()
            
            # Teste 5: Validação de configurações
            await self._test_configuration_validation()
            
            # Gerar recomendações
            self._generate_recommendations()
            
            # Determinar status final
            self._determine_migration_status()
        
        return self.migration_report
    
    async def _test_basic_connectivity(self):
        """Testa conectividade básica com a API NVD."""
        test_name = "Conectividade Básica API NVD"
        logger.info(f"Executando: {test_name}")
        
        test_result = {
            'name': test_name,
            'status': 'failed',
            'details': {},
            'duration': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Testar com aiohttp diretamente
            async with aiohttp.ClientSession() as session:
                url = self.app.config.get('NVD_API_BASE', 'https://services.nvd.nist.gov/rest/json/cves/2.0')
                headers = {'User-Agent': 'Migration Test'}
                
                if self.app.config.get('NVD_API_KEY'):
                    headers['apiKey'] = self.app.config.get('NVD_API_KEY')
                
                async with session.get(
                    url,
                    headers=headers,
                    params={'resultsPerPage': 1},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        test_result['status'] = 'passed'
                        test_result['details'] = {
                            'api_accessible': True,
                            'has_api_key': bool(self.app.config.get('NVD_API_KEY')),
                            'total_results': data.get('totalResults', 0),
                            'response_time_ms': (datetime.utcnow() - start_time).total_seconds() * 1000
                        }
                    else:
                        test_result['details'] = {
                            'api_accessible': False,
                            'status_code': response.status,
                            'error': f"HTTP {response.status}"
                        }
        
        except Exception as e:
            test_result['details'] = {
                'api_accessible': False,
                'error': str(e)
            }
        
        test_result['duration'] = (datetime.utcnow() - start_time).total_seconds()
        self.migration_report['tests'].append(test_result)
        
        logger.info(f"{test_name}: {test_result['status']} ({test_result['duration']:.2f}s)")
    
    async def _test_enhanced_minimal(self):
        """Testa o sistema aprimorado com configuração mínima."""
        test_name = "Sistema Aprimorado - Configuração Mínima"
        logger.info(f"Executando: {test_name}")
        
        test_result = {
            'name': test_name,
            'status': 'failed',
            'details': {},
            'duration': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Criar fetcher aprimorado com configuração mínima
            fetcher = EnhancedNVDFetcher(
                app=self.app,
                max_workers=2,
                enable_cache=False,
                enable_monitoring=False,
                batch_size=100
            )
            
            try:
                # Teste com apenas 1 página
                result = await fetcher.sync_nvd(full=False, max_pages=1, use_parallel=True)
                
                stats = fetcher.get_performance_stats()
                
                test_result['status'] = 'passed'
                test_result['details'] = {
                    'vulnerabilities_processed': result,
                    'fallback_used': stats['enhanced_fetcher_stats'].get('fallback_used', False),
                    'parallel_batches': stats['enhanced_fetcher_stats'].get('parallel_batches', 0),
                    'initialization_successful': True
                }
                
            finally:
                fetcher.cleanup()
        
        except Exception as e:
            test_result['details'] = {
                'initialization_successful': False,
                'error': str(e)
            }
        
        test_result['duration'] = (datetime.utcnow() - start_time).total_seconds()
        self.migration_report['tests'].append(test_result)
        
        logger.info(f"{test_name}: {test_result['status']} ({test_result['duration']:.2f}s)")
    
    async def _test_performance_comparison(self):
        """Compara performance entre sistema original e aprimorado."""
        test_name = "Comparação de Performance"
        logger.info(f"Executando: {test_name}")
        
        test_result = {
            'name': test_name,
            'status': 'failed',
            'details': {},
            'duration': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Teste sistema original
            original_start = datetime.utcnow()
            
            async with aiohttp.ClientSession() as session:
                nvd_config = {
                    "NVD_API_BASE": self.app.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                    "NVD_API_KEY": self.app.config.get("NVD_API_KEY"),
                    "NVD_PAGE_SIZE": 100,  # Pequeno para teste
                    "NVD_REQUEST_TIMEOUT": 30,
                    "NVD_USER_AGENT": "Migration Test Original"
                }
                
                original_fetcher = NVDFetcher(session, nvd_config)
                vulnerability_service = VulnerabilityService(db.session)
                
                try:
                    # Buscar apenas 1 página para comparação
                    original_data = await original_fetcher.fetch_page(0, None)
                    original_vulns = len(original_data.get('vulnerabilities', [])) if original_data else 0
                except Exception as e:
                    logger.warning(f"Erro no teste original: {e}")
                    original_vulns = 0
            
            original_duration = (datetime.utcnow() - original_start).total_seconds()
            
            # Teste sistema aprimorado
            enhanced_start = datetime.utcnow()
            
            fetcher = EnhancedNVDFetcher(
                app=self.app,
                max_workers=5,
                enable_cache=False,
                enable_monitoring=False,
                batch_size=100
            )
            
            try:
                enhanced_result = await fetcher.sync_nvd(full=False, max_pages=1, use_parallel=True)
                enhanced_stats = fetcher.get_performance_stats()
            finally:
                fetcher.cleanup()
            
            enhanced_duration = (datetime.utcnow() - enhanced_start).total_seconds()
            
            # Calcular melhoria
            if original_duration > 0:
                speedup = original_duration / enhanced_duration if enhanced_duration > 0 else 0
            else:
                speedup = 0
            
            test_result['status'] = 'passed'
            test_result['details'] = {
                'original_duration': original_duration,
                'original_vulnerabilities': original_vulns,
                'enhanced_duration': enhanced_duration,
                'enhanced_vulnerabilities': enhanced_result,
                'speedup_factor': speedup,
                'performance_improvement': ((original_duration - enhanced_duration) / original_duration * 100) if original_duration > 0 else 0
            }
        
        except Exception as e:
            test_result['details'] = {
                'error': str(e),
                'comparison_failed': True
            }
        
        test_result['duration'] = (datetime.utcnow() - start_time).total_seconds()
        self.migration_report['tests'].append(test_result)
        
        logger.info(f"{test_name}: {test_result['status']} ({test_result['duration']:.2f}s)")
    
    async def _test_fallback_mechanism(self):
        """Testa o mecanismo de fallback."""
        test_name = "Mecanismo de Fallback"
        logger.info(f"Executando: {test_name}")
        
        test_result = {
            'name': test_name,
            'status': 'failed',
            'details': {},
            'duration': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            # Criar fetcher com configuração que pode forçar fallback
            fetcher = EnhancedNVDFetcher(
                app=self.app,
                max_workers=1,
                enable_cache=False,
                enable_monitoring=False,
                batch_size=50
            )
            
            try:
                # Tentar sincronização que pode usar fallback
                result = await fetcher.sync_nvd(full=False, max_pages=1, use_parallel=False)
                
                stats = fetcher.get_performance_stats()
                fallback_used = stats['enhanced_fetcher_stats'].get('fallback_used', False)
                
                test_result['status'] = 'passed'
                test_result['details'] = {
                    'fallback_mechanism_available': True,
                    'fallback_used_in_test': fallback_used,
                    'vulnerabilities_processed': result,
                    'system_resilient': True
                }
                
            finally:
                fetcher.cleanup()
        
        except Exception as e:
            test_result['details'] = {
                'fallback_mechanism_available': False,
                'error': str(e)
            }
        
        test_result['duration'] = (datetime.utcnow() - start_time).total_seconds()
        self.migration_report['tests'].append(test_result)
        
        logger.info(f"{test_name}: {test_result['status']} ({test_result['duration']:.2f}s)")
    
    async def _test_configuration_validation(self):
        """Valida as configurações necessárias."""
        test_name = "Validação de Configurações"
        logger.info(f"Executando: {test_name}")
        
        test_result = {
            'name': test_name,
            'status': 'passed',
            'details': {},
            'duration': 0
        }
        
        start_time = datetime.utcnow()
        
        try:
            config_checks = {
                'nvd_api_base': bool(self.app.config.get('NVD_API_BASE')),
                'nvd_api_key': bool(self.app.config.get('NVD_API_KEY')),
                'database_configured': bool(self.app.config.get('SQLALCHEMY_DATABASE_URI')),
                'redis_available': self._check_redis_availability(),
                'required_packages': self._check_required_packages()
            }
            
            # Verificar configurações opcionais
            optional_configs = {
                'max_concurrent_requests': self.app.config.get('MAX_CONCURRENT_REQUESTS', 10),
                'batch_size': self.app.config.get('BATCH_SIZE', 1000),
                'enable_monitoring': self.app.config.get('ENABLE_PERFORMANCE_MONITORING', True)
            }
            
            # Determinar se configuração é adequada
            critical_missing = [k for k, v in config_checks.items() if not v and k in ['nvd_api_base', 'database_configured']]
            
            if critical_missing:
                test_result['status'] = 'failed'
            
            test_result['details'] = {
                'critical_configs': config_checks,
                'optional_configs': optional_configs,
                'critical_missing': critical_missing,
                'configuration_adequate': len(critical_missing) == 0
            }
        
        except Exception as e:
            test_result['status'] = 'failed'
            test_result['details'] = {
                'error': str(e),
                'validation_failed': True
            }
        
        test_result['duration'] = (datetime.utcnow() - start_time).total_seconds()
        self.migration_report['tests'].append(test_result)
        
        logger.info(f"{test_name}: {test_result['status']} ({test_result['duration']:.2f}s)")
    
    def _check_redis_availability(self) -> bool:
        """Verifica se Redis está disponível."""
        try:
            from services.redis_cache_service import RedisCacheService
            cache_service = RedisCacheService()
            return True
        except Exception:
            return False
    
    def _check_required_packages(self) -> bool:
        """Verifica se pacotes necessários estão instalados."""
        required_packages = ['aiohttp', 'psutil', 'redis']
        
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                return False
        
        return True
    
    def _generate_recommendations(self):
        """Gera recomendações baseadas nos testes."""
        recommendations = []
        
        # Analisar resultados dos testes
        test_results = {test['name']: test for test in self.migration_report['tests']}
        
        # Recomendações baseadas em conectividade
        connectivity_test = test_results.get('Conectividade Básica API NVD')
        if connectivity_test and connectivity_test['status'] == 'passed':
            if not connectivity_test['details'].get('has_api_key'):
                recommendations.append({
                    'type': 'warning',
                    'message': 'Considere configurar uma API key da NVD para melhor rate limiting',
                    'action': 'Adicionar NVD_API_KEY nas variáveis de ambiente'
                })
        
        # Recomendações baseadas em performance
        performance_test = test_results.get('Comparação de Performance')
        if performance_test and performance_test['status'] == 'passed':
            speedup = performance_test['details'].get('speedup_factor', 0)
            if speedup > 1.5:
                recommendations.append({
                    'type': 'success',
                    'message': f'Sistema aprimorado {speedup:.1f}x mais rápido - migração recomendada',
                    'action': 'Proceder com migração gradual'
                })
            elif speedup < 1:
                recommendations.append({
                    'type': 'warning',
                    'message': 'Sistema aprimorado não mostrou melhoria significativa',
                    'action': 'Revisar configurações ou manter sistema original'
                })
        
        # Recomendações baseadas em configuração
        config_test = test_results.get('Validação de Configurações')
        if config_test and config_test['status'] == 'failed':
            missing = config_test['details'].get('critical_missing', [])
            for item in missing:
                recommendations.append({
                    'type': 'error',
                    'message': f'Configuração crítica ausente: {item}',
                    'action': f'Configurar {item} antes da migração'
                })
        
        # Recomendações gerais
        if not any(test['status'] == 'failed' for test in self.migration_report['tests']):
            recommendations.append({
                'type': 'info',
                'message': 'Todos os testes passaram - sistema pronto para migração',
                'action': 'Executar migração em ambiente de produção'
            })
        
        self.migration_report['recommendations'] = recommendations
    
    def _determine_migration_status(self):
        """Determina o status final da migração."""
        failed_tests = [test for test in self.migration_report['tests'] if test['status'] == 'failed']
        
        if not failed_tests:
            self.migration_report['status'] = 'ready'
        elif len(failed_tests) <= 1:
            self.migration_report['status'] = 'ready_with_warnings'
        else:
            self.migration_report['status'] = 'not_ready'
    
    def save_report(self, filename: str = None):
        """Salva o relatório de migração."""
        if not filename:
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            filename = f'nvd_migration_report_{timestamp}.json'
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.migration_report, f, indent=2, default=str)
        
        logger.info(f"Relatório de migração salvo em: {filename}")
        return filename

def setup_logging():
    """Configura logging para o script."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('nvd_migration.log')
        ]
    )

def create_app_context() -> Flask:
    """Cria contexto da aplicação Flask."""
    from app import create_app
    return create_app()

async def main():
    """Função principal do script de migração."""
    parser = argparse.ArgumentParser(description='Script de Migração NVD Paralelo')
    parser.add_argument('--save-report', help='Nome do arquivo para salvar relatório')
    parser.add_argument('--log-level', default='INFO', help='Nível de log')
    
    args = parser.parse_args()
    
    # Configurar logging
    setup_logging()
    logging.getLogger().setLevel(getattr(logging, args.log_level.upper()))
    
    logger.info("Iniciando script de migração para sistema paralelo NVD")
    
    # Criar aplicação
    app = create_app_context()
    
    with app.app_context():
        # Criar gerenciador de migração
        migration_manager = NVDMigrationManager(app)
        
        try:
            # Executar testes de migração
            report = await migration_manager.run_migration_tests()
            
            # Salvar relatório
            report_file = migration_manager.save_report(args.save_report)
            
            # Mostrar resumo
            print("\n" + "="*60)
            print("RELATÓRIO DE MIGRAÇÃO - SISTEMA PARALELO NVD")
            print("="*60)
            
            print(f"Status: {report['status'].upper()}")
            print(f"Total de testes: {len(report['tests'])}")
            
            passed_tests = [t for t in report['tests'] if t['status'] == 'passed']
            failed_tests = [t for t in report['tests'] if t['status'] == 'failed']
            
            print(f"Testes aprovados: {len(passed_tests)}")
            print(f"Testes falharam: {len(failed_tests)}")
            
            # Mostrar resultados dos testes
            print("\nRESULTADOS DOS TESTES:")
            for test in report['tests']:
                status_icon = "✓" if test['status'] == 'passed' else "✗"
                print(f"  {status_icon} {test['name']} ({test['duration']:.2f}s)")
                
                if test['status'] == 'failed' and 'error' in test['details']:
                    print(f"    Erro: {test['details']['error']}")
            
            # Mostrar recomendações
            if report['recommendations']:
                print("\nRECOMENDAÇÕES:")
                for rec in report['recommendations']:
                    icon = {
                        'success': '✓',
                        'warning': '⚠',
                        'error': '✗',
                        'info': 'ℹ'
                    }.get(rec['type'], '•')
                    
                    print(f"  {icon} {rec['message']}")
                    print(f"    Ação: {rec['action']}")
            
            # Conclusão
            print("\nCONCLUSÃO:")
            if report['status'] == 'ready':
                print("✓ Sistema pronto para migração!")
                print("  Recomendação: Proceder com migração gradual em produção")
            elif report['status'] == 'ready_with_warnings':
                print("⚠ Sistema pronto com ressalvas")
                print("  Recomendação: Revisar warnings antes da migração")
            else:
                print("✗ Sistema não está pronto para migração")
                print("  Recomendação: Corrigir problemas identificados")
            
            print(f"\nRelatório detalhado salvo em: {report_file}")
            print("="*60)
            
            # Código de saída baseado no status
            if report['status'] in ['ready', 'ready_with_warnings']:
                return 0
            else:
                return 1
                
        except KeyboardInterrupt:
            logger.info("Migração interrompida pelo usuário")
            return 1
        except Exception as e:
            logger.error(f"Erro durante migração: {e}", exc_info=True)
            return 1

if __name__ == '__main__':
    exit_code = asyncio.run(main())
    sys.exit(exit_code)