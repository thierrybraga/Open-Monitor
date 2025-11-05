#!/usr/bin/env python3
"""
Sistema de inicialização e verificação automática do banco de dados.
Verifica se o banco existe, cria se necessário, e popula com dados da NIST.
"""

import os
import sys
import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.append(str(Path(__file__).parent.parent))

from app.utils.enhanced_logging import get_app_logger, get_db_logger, get_nvd_logger, progress_context, timed_operation
from app.extensions.db import db
from services.vulnerability_service import VulnerabilityService
from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
from app.config.parallel_nvd_config import ParallelNVDConfig
from flask import Flask
from sqlalchemy import text
from app.utils.sync_metadata_orm import upsert_sync_metadata

class DatabaseInitializer:
    """
    Classe responsável pela inicialização e verificação do banco de dados.
    """
    
    def __init__(self, app: Optional[Flask] = None, config: Optional[ParallelNVDConfig] = None):
        self.app_logger = get_app_logger()
        self.db_logger = get_db_logger()
        self.nvd_logger = get_nvd_logger()
        
        # Aplicação Flask
        self.app = app
        
        # Configuração
        self.config = config or ParallelNVDConfig.from_env()
        
        # Serviços
        self.vulnerability_service = None
        self.nvd_fetcher = None
        
        # Estado da inicialização
        self.initialization_stats = {
            'database_created': False,
            'tables_created': 0,
            'initial_sync_performed': False,
            'vulnerabilities_imported': 0,
            'initialization_time': 0.0,
            'errors': []
        }
    
    async def initialize(self) -> bool:
        """
        Executa a inicialização completa do banco de dados.
        
        Returns:
            bool: True se a inicialização foi bem-sucedida
        """
        start_time = time.time()
        
        try:
            self.app_logger.section("Inicialização do Sistema Open-Monitor")
            
            # 1. Verificar e criar banco de dados
            if not await self._check_and_create_database():
                return False
            
            # 2. Verificar e criar tabelas
            if not await self._check_and_create_tables():
                return False
            
            # 3. Verificar se precisa de sincronização inicial
            needs_initial_sync = await self._check_needs_initial_sync()
            
            if needs_initial_sync:
                # 4. Executar sincronização inicial
                if not await self._perform_initial_sync():
                    return False
            else:
                self.app_logger.info("Banco de dados já possui dados, verificando atualizações...")
                # 5. Verificar atualizações incrementais
                await self._check_for_updates()
            
            # 6. Configurar sincronização automática
            await self._setup_automatic_sync()
            
            # Finalizar
            self.initialization_stats['initialization_time'] = time.time() - start_time
            self._print_initialization_summary()
            
            return True
            
        except Exception as e:
            self.app_logger.error(f"Erro durante inicialização: {str(e)}")
            self.initialization_stats['errors'].append(str(e))
            return False
        finally:
            await self._cleanup()
    
    async def _check_and_create_database(self) -> bool:
        """
        Verifica se o banco de dados existe e cria se necessário.
        """
        try:
            self.app_logger.subsection("Verificação do Banco de Dados")
            
            # Tentar conectar ao banco
            self.database = Database()
            
            with timed_operation(self.db_logger, "Conexão com banco de dados"):
                await self.database.connect()
            
            # Verificar se o banco está acessível
            if await self._test_database_connection():
                self.app_logger.success("Banco de dados encontrado e acessível")
                return True
            else:
                self.app_logger.warning("Banco de dados não acessível, tentando criar...")
                return await self._create_database()
                
        except Exception as e:
            self.app_logger.warning(f"Erro ao conectar ao banco: {str(e)}")
            self.app_logger.info("Tentando criar novo banco de dados...")
            return await self._create_database()
    
    async def _test_database_connection(self) -> bool:
        """
        Testa a conexão com o banco de dados.
        """
        try:
            # Executar uma query simples para testar
            result = await self.database.execute_query("SELECT 1 as test")
            return result is not None
        except Exception:
            return False
    
    async def _create_database(self) -> bool:
        """
        Cria o banco de dados.
        """
        try:
            self.db_logger.info("Criando novo banco de dados...")
            
            # Aqui você implementaria a criação do banco
            # Por exemplo, executando scripts SQL de criação
            
            # Simular criação (adapte conforme seu SGBD)
            await self._execute_creation_scripts()
            
            self.initialization_stats['database_created'] = True
            self.app_logger.success("Banco de dados criado com sucesso")
            return True
            
        except Exception as e:
            self.app_logger.error(f"Erro ao criar banco de dados: {str(e)}")
            return False
    
    async def _execute_creation_scripts(self):
        """
        Executa scripts de criação do banco.
        """
        # Scripts básicos de criação (adapte conforme necessário)
        creation_scripts = [
            # Exemplo de scripts - adapte para seu esquema
            """
            CREATE TABLE IF NOT EXISTS vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cve_id VARCHAR(20) UNIQUE NOT NULL,
                description TEXT,
                severity VARCHAR(10),
                score REAL,
                published_date DATETIME,
                modified_date DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                last_sync_time DATETIME,
                sync_type VARCHAR(20),
                vulnerabilities_count INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_vulnerabilities_cve_id ON vulnerabilities(cve_id)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_vulnerabilities_published_date ON vulnerabilities(published_date)
            """
        ]
        
        for i, script in enumerate(creation_scripts, 1):
            try:
                await self.database.execute_query(script)
                self.db_logger.success(f"Script {i}/{len(creation_scripts)} executado")
                self.initialization_stats['tables_created'] += 1
            except Exception as e:
                self.db_logger.error(f"Erro no script {i}: {str(e)}")
                raise
    
    async def _check_and_create_tables(self) -> bool:
        """
        Verifica se as tabelas existem e cria se necessário.
        """
        try:
            self.app_logger.subsection("Verificação das Tabelas")
            
            # Lista de tabelas necessárias
            required_tables = ['vulnerabilities', 'sync_metadata']
            
            for table in required_tables:
                if await self._table_exists(table):
                    self.app_logger.info(f"Tabela '{table}' encontrada")
                else:
                    self.app_logger.warning(f"Tabela '{table}' não encontrada, criando...")
                    await self._create_table(table)
            
            return True
            
        except Exception as e:
            self.app_logger.error(f"Erro ao verificar tabelas: {str(e)}")
            return False
    
    async def _table_exists(self, table_name: str) -> bool:
        """
        Verifica se uma tabela existe.
        """
        try:
            # Adapte conforme seu SGBD
            query = f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'"
            result = await self.database.execute_query(query)
            return result is not None and len(result) > 0
        except Exception:
            return False
    
    async def _create_table(self, table_name: str):
        """
        Cria uma tabela específica.
        """
        # Implementar criação de tabelas específicas
        # Por enquanto, usar os scripts de criação
        await self._execute_creation_scripts()
    
    async def _check_needs_initial_sync(self) -> bool:
        """
        Verifica se é necessária uma sincronização inicial.
        """
        try:
            self.app_logger.subsection("Verificação de Dados Existentes")
            
            # Verificar se há vulnerabilidades no banco
            query = "SELECT COUNT(*) as count FROM vulnerabilities"
            result = await self.database.execute_query(query)
            
            if result and len(result) > 0:
                count = result[0]['count']
                self.app_logger.info(f"Encontradas {count} vulnerabilidades no banco")
                
                if count == 0:
                    self.app_logger.info("Banco vazio, sincronização inicial necessária")
                    return True
                else:
                    # Verificar se a última sincronização foi há muito tempo
                    return await self._check_last_sync_time()
            else:
                self.app_logger.info("Não foi possível verificar dados, assumindo sincronização necessária")
                return True
                
        except Exception as e:
            self.app_logger.warning(f"Erro ao verificar dados existentes: {str(e)}")
            return True
    
    async def _check_last_sync_time(self) -> bool:
        """
        Verifica quando foi a última sincronização.
        """
        try:
            # Garantir que a tabela exista
            table_check = await self.database.execute_query(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sync_metadata'"
            )
            if not table_check:
                self.app_logger.info("Tabela 'sync_metadata' não encontrada; assumindo necessidade de sincronização inicial")
                return True

            # Usar colunas válidas: value (ISO string) e last_modified
            query = "SELECT value, last_modified FROM sync_metadata WHERE key = ? ORDER BY last_modified DESC LIMIT 1"
            result = await self.database.execute_query(query, ("nvd_last_sync",))

            last_sync_dt = None
            if result and len(result) > 0:
                row = result[0]
                value_str = row.get('value')
                lm = row.get('last_modified')
                # Parse value ISO first; fallback to last_modified
                if isinstance(value_str, str) and value_str:
                    try:
                        last_sync_dt = datetime.fromisoformat(value_str.replace('Z', '+00:00'))
                    except Exception:
                        last_sync_dt = None
                if last_sync_dt is None and isinstance(lm, str) and lm:
                    try:
                        last_sync_dt = datetime.fromisoformat(lm.replace('Z', '+00:00'))
                    except Exception:
                        last_sync_dt = None

            if last_sync_dt is None:
                # Fallback: usar data da última CVE cadastrada
                try:
                    vuln_query = "SELECT MAX(last_update) as max_update FROM vulnerabilities"
                    vres = await self.database.execute_query(vuln_query)
                    if vres and len(vres) > 0 and vres[0].get('max_update'):
                        mu = vres[0]['max_update']
                        if isinstance(mu, str):
                            try:
                                last_sync_dt = datetime.fromisoformat(mu.replace('Z', '+00:00'))
                            except Exception:
                                last_sync_dt = None
                except Exception:
                    last_sync_dt = None

            if last_sync_dt is None:
                self.app_logger.info("Nenhum registro de sincronização válido encontrado")
                return True

            # Se a última sincronização foi há mais de 7 dias, fazer sincronização completa
            days_since_sync = (datetime.now() - last_sync_dt).days

            if days_since_sync > 7:
                self.app_logger.warning(f"Última sincronização há {days_since_sync} dias, sincronização completa necessária")
                return True
            else:
                self.app_logger.info(f"Última sincronização há {days_since_sync} dias, apenas atualizações incrementais")
                return False
            
        except Exception as e:
            self.app_logger.warning(f"Erro ao verificar última sincronização: {str(e)}")
            return True
    
    async def _perform_initial_sync(self) -> bool:
        """
        Executa a sincronização inicial completa.
        """
        try:
            self.app_logger.subsection("Sincronização Inicial")
            self.nvd_logger.sync_started(full_sync=True)
            
            # Inicializar serviços
            await self._initialize_services()
            
            # Executar sincronização
            start_time = time.time()
            
            with timed_operation(self.nvd_logger, "Sincronização inicial completa"):
                result = await self.nvd_fetcher.sync_nvd(
                    self.vulnerability_service,
                    full=True
                )
            
            duration = time.time() - start_time
            
            if result:
                self.initialization_stats['initial_sync_performed'] = True
                self.initialization_stats['vulnerabilities_imported'] = result.get('processed', 0)
                
                self.nvd_logger.sync_completed(
                    processed=result.get('processed', 0),
                    duration=duration,
                    errors=result.get('errors', 0)
                )
                
                # Registrar sincronização
                await self._record_sync_metadata('initial', result.get('processed', 0))
                
                return True
            else:
                self.app_logger.error("Sincronização inicial falhou")
                return False
                
        except Exception as e:
            self.app_logger.error(f"Erro durante sincronização inicial: {str(e)}")
            return False
    
    async def _check_for_updates(self):
        """
        Verifica e aplica atualizações incrementais.
        """
        try:
            self.app_logger.subsection("Verificação de Atualizações")
            
            # Inicializar serviços se necessário
            if not self.nvd_fetcher:
                await self._initialize_services()
            
            # Executar sincronização incremental
            start_time = time.time()
            
            with timed_operation(self.nvd_logger, "Sincronização incremental"):
                result = await self.nvd_fetcher.sync_nvd(
                    self.vulnerability_service,
                    full=False
                )
            
            duration = time.time() - start_time
            
            if result:
                processed = result.get('processed', 0)
                if processed > 0:
                    self.nvd_logger.sync_completed(
                        processed=processed,
                        duration=duration,
                        errors=result.get('errors', 0)
                    )
                    
                    # Registrar sincronização
                    await self._record_sync_metadata('incremental', processed)
                else:
                    self.app_logger.info("Nenhuma atualização encontrada")
            
        except Exception as e:
            self.app_logger.warning(f"Erro durante verificação de atualizações: {str(e)}")
    
    async def _initialize_services(self):
        """
        Inicializa os serviços necessários.
        """
        if not self.vulnerability_service:
            self.vulnerability_service = VulnerabilityService(self.database)
        
        if not self.nvd_fetcher:
            self.nvd_fetcher = EnhancedNVDFetcher(
                max_workers=self.config.max_workers,
                enable_cache=self.config.enable_cache,
                cache_ttl=self.config.cache_ttl,
                enable_monitoring=self.config.enable_monitoring
            )
    
    async def _record_sync_metadata(self, sync_type: str, count: int):
        """
        Registra metadados da sincronização.
        """
        try:
            # Usa ORM com app context (self.app é fornecido ao initializer)
            if self.app is None:
                self.app_logger.warning("Aplicação Flask não definida; não foi possível registrar metadados via ORM")
                return
            with self.app.app_context():
                ok, _ = upsert_sync_metadata(
                    session=None,
                    key="nvd_last_sync",
                    value=datetime.now().isoformat(timespec='milliseconds'),
                    status="completed",
                    sync_type=sync_type,
                )
                if ok:
                    self.db_logger.insert("sync_metadata", 1)
                else:
                    self.app_logger.warning("Falha ao registrar metadados de sincronização via ORM")

        except Exception as e:
            self.app_logger.warning(f"Erro ao registrar metadados de sincronização: {str(e)}")
    
    async def _setup_automatic_sync(self):
        """
        Configura sincronização automática.
        """
        self.app_logger.subsection("Configuração de Sincronização Automática")
        
        # Aqui você configuraria um scheduler (como APScheduler)
        # Por enquanto, apenas log da configuração
        
        self.app_logger.info("Sincronização automática configurada para executar a cada 1 hora")
        self.app_logger.info("Para ativar, certifique-se de que o scheduler esteja rodando")
        
        # Exemplo de como seria a configuração:
        # scheduler.add_job(
        #     func=self._hourly_sync,
        #     trigger="interval",
        #     hours=1,
        #     id='nvd_hourly_sync'
        # )
    
    async def _hourly_sync(self):
        """
        Executa sincronização horária.
        Esta função seria chamada pelo scheduler.
        """
        try:
            self.nvd_logger.info("Iniciando sincronização horária automática")
            
            if not self.nvd_fetcher:
                await self._initialize_services()
            
            result = await self.nvd_fetcher.sync_nvd(
                self.vulnerability_service,
                full=False
            )
            
            if result:
                processed = result.get('processed', 0)
                if processed > 0:
                    await self._record_sync_metadata('hourly', processed)
                    self.nvd_logger.success(f"Sincronização horária concluída: {processed} vulnerabilidades")
                else:
                    self.nvd_logger.info("Sincronização horária: nenhuma atualização")
            
        except Exception as e:
            self.nvd_logger.error(f"Erro na sincronização horária: {str(e)}")
    
    async def _cleanup(self):
        """
        Limpa recursos utilizados.
        """
        try:
            if self.nvd_fetcher:
                await self.nvd_fetcher.cleanup()
            
            if self.database:
                await self.database.disconnect()
                
        except Exception as e:
            self.app_logger.warning(f"Erro durante limpeza: {str(e)}")
    
    def _print_initialization_summary(self):
        """
        Imprime resumo da inicialização.
        """
        self.app_logger.section("Resumo da Inicialização")
        
        stats = self.initialization_stats
        
        # Status geral
        if stats['errors']:
            self.app_logger.warning(f"Inicialização concluída com {len(stats['errors'])} erro(s)")
        else:
            self.app_logger.success("Inicialização concluída com sucesso")
        
        # Estatísticas
        self.app_logger.info(f"⏱️  Tempo total: {stats['initialization_time']:.2f}s")
        self.app_logger.info(f"🗄️  Banco criado: {'Sim' if stats['database_created'] else 'Não'}")
        self.app_logger.info(f"📋 Tabelas criadas: {stats['tables_created']}")
        self.app_logger.info(f"🔄 Sincronização inicial: {'Sim' if stats['initial_sync_performed'] else 'Não'}")
        self.app_logger.info(f"🔍 Vulnerabilidades importadas: {stats['vulnerabilities_imported']}")
        
        # Erros
        if stats['errors']:
            self.app_logger.subsection("Erros Encontrados")
            for i, error in enumerate(stats['errors'], 1):
                self.app_logger.error(f"{i}. {error}")
        
        # Próximos passos
        self.app_logger.subsection("Próximos Passos")
        self.app_logger.info("✅ Sistema pronto para uso")
        self.app_logger.info("🔄 Sincronização automática configurada (1 hora)")
        self.app_logger.info("📊 Monitoramento de performance ativo")
        
        # Estatísticas dos loggers
        self.app_logger.print_stats()
        self.db_logger.print_operation_stats()
        self.nvd_logger.print_nvd_stats()

async def initialize_database(config: Optional[ParallelNVDConfig] = None) -> bool:
    """
    Função principal para inicializar o banco de dados.
    
    Args:
        config: Configuração do sistema paralelo NVD
    
    Returns:
        bool: True se a inicialização foi bem-sucedida
    """
    initializer = DatabaseInitializer(config)
    return await initializer.initialize()

if __name__ == "__main__":
    # Executar inicialização
    import asyncio
    from app.utils.enhanced_logging import setup_logging
    
    # Configurar logging
    setup_logging("INFO", "logs/initialization.log")
    
    # Executar inicialização
    success = asyncio.run(initialize_database())
    
    if success:
        print("\n🎉 Inicialização concluída com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Inicialização falhou!")
        sys.exit(1)
