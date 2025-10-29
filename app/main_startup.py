#!/usr/bin/env python3
"""
Script principal de inicialização do Open-Monitor.
Gerencia inicialização do banco de dados, verificações de saúde e sincronização automática.
"""

import os
import sys
import asyncio
import threading
import time
from pathlib import Path
from typing import Optional
from datetime import datetime

# Adicionar o diretório raiz ao path
# sys.path.insert(0, str(Path(__file__).parent))

from flask import Flask
from app.extensions import init_extensions, db
from app.settings.base import BaseConfig
from app.settings.development import DevelopmentConfig
from app.utils.enhanced_logging import get_app_logger, setup_logging
from app.utils.terminal_feedback import terminal_feedback, timed_operation
from app.utils.visual_indicators import status_indicator
from app.jobs.nvd_fetcher import NVDFetcher
from app.services.vulnerability_service import VulnerabilityService
from app.models.sync_metadata import SyncMetadata

def create_app(config_class=None) -> Flask:
    """
    Factory para criar a aplicação Flask.
    """
    try:
        app = Flask(__name__)
        
        # Configuração
        if config_class is None:
            env = os.getenv('FLASK_ENV', 'development')
            config_class = DevelopmentConfig if env == 'development' else BaseConfig
        
        app.config.from_object(config_class)
        
        # Validar configurações críticas
        required_configs = ['SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']
        for config_key in required_configs:
            if not app.config.get(config_key):
                raise ValueError(f"Configuração obrigatória '{config_key}' não encontrada")
        
        # Inicializar extensões
        init_extensions(app)
        
        return app
    except Exception as e:
        logger = get_app_logger()
        logger.error(f"Erro ao criar aplicação Flask: {e}")
        raise

def initialize_database(app: Flask) -> bool:
    """
    Inicializa o banco de dados se necessário.
    """
    app_logger = get_app_logger()
    
    try:
        with app.app_context():
            # Verificar conexão com o banco
            try:
                db.engine.connect()
                app_logger.info("✅ Conexão com banco de dados estabelecida")
            except Exception as conn_error:
                app_logger.error(f"❌ Falha na conexão com banco de dados: {conn_error}")
                return False
            
            # Importar todos os modelos para garantir que estejam registrados
            try:
                import app.models as models
                app_logger.info("📦 Modelos importados com sucesso")
            except Exception as import_error:
                app_logger.error(f"❌ Erro ao importar modelos: {import_error}")
                return False
            
            # Verificar se as tabelas existem
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            if not tables:
                app_logger.info("🗄️ Criando tabelas do banco de dados...")
                try:
                    db.create_all()
                    app_logger.info("✅ Comando create_all() executado")
                except Exception as create_error:
                    app_logger.error(f"❌ Erro durante create_all(): {create_error}")
                    return False
                
                # Verificar se as tabelas foram criadas
                # Criar um novo inspector após create_all()
                inspector = inspect(db.engine)
                new_tables = inspector.get_table_names()
                if new_tables:
                    app_logger.success(f"✅ {len(new_tables)} tabelas criadas com sucesso")
                    return True
                else:
                    app_logger.error("❌ Falha ao criar tabelas do banco de dados")
                    return False
            else:
                app_logger.info(f"✅ Banco de dados já existe com {len(tables)} tabelas")
                return True
                
    except Exception as e:
        app_logger.error(f"❌ Erro ao inicializar banco de dados: {e}")
        return False

async def perform_initial_nvd_sync(app: Flask) -> bool:
    """
    Executa sincronização de início em toda execução da aplicação (incremental).
    """
    app_logger = get_app_logger()
    
    try:
        with app.app_context():
            # Verificar se já existe sincronização anterior (apenas para logging)
            last_sync = db.session.query(SyncMetadata).filter_by(key='nvd_last_sync').first()
            if last_sync:
                app_logger.info("🔄 Sincronização de início: sincronização anterior encontrada — executando atualização incremental")
            else:
                app_logger.info("🔄 Sincronização de início: nenhuma sincronização anterior encontrada — executando atualização inicial incremental")
            
            # Configurações do NVD
            nvd_config = {
                "NVD_API_BASE": getattr(app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                "NVD_API_KEY": getattr(app.config, 'NVD_API_KEY', None),
                "NVD_RATE_LIMIT": getattr(app.config, 'NVD_RATE_LIMIT', (2, 1)),
                "NVD_CACHE_DIR": getattr(app.config, 'NVD_CACHE_DIR', "cache"),
                "NVD_REQUEST_TIMEOUT": getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
                "NVD_USER_AGENT": getattr(app.config, 'NVD_USER_AGENT', "Open-Monitor NVD Fetcher")
            }
            
            # Executar sincronização de início (incremental baseada na última sincronização)
            import aiohttp
            async with aiohttp.ClientSession() as session:
                fetcher = NVDFetcher(session, nvd_config)
                vulnerability_service = VulnerabilityService(db.session)
                
                processed_count = await fetcher.update(
                    vulnerability_service=vulnerability_service,
                    full=False
                )
            
            app_logger.success(f"✅ Sincronização de início concluída: {processed_count} vulnerabilidades processadas")
            return True
                
    except Exception as e:
        app_logger.error(f"❌ Erro durante sincronização de início: {e}")
        return False

def setup_nvd_scheduler(app: Flask) -> None:
    """
    Configura scheduler para sincronização automática do NVD a cada 1 hora.
    """
    app_logger = get_app_logger()
    
    def run_hourly_sync():
        """Executa sincronização horária em thread separada."""
        while True:
            try:
                time.sleep(3600)  # Aguardar 1 hora (3600 segundos)
                
                app_logger.info("🔄 Iniciando sincronização horária do NVD...")
                
                with app.app_context():
                    # Executar sincronização assíncrona
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        # Configurações do NVD
                        nvd_config = {
                            "NVD_API_BASE": getattr(app.config, 'NVD_API_BASE', "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                            "NVD_API_KEY": getattr(app.config, 'NVD_API_KEY', None),
                            "NVD_RATE_LIMIT": getattr(app.config, 'NVD_RATE_LIMIT', (2, 1)),
                            "NVD_CACHE_DIR": getattr(app.config, 'NVD_CACHE_DIR', "cache"),
                            "NVD_REQUEST_TIMEOUT": getattr(app.config, 'NVD_REQUEST_TIMEOUT', 30),
                            "NVD_USER_AGENT": getattr(app.config, 'NVD_USER_AGENT', "Open-Monitor NVD Fetcher")
                        }
                        
                        async def sync_task():
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                fetcher = NVDFetcher(session, nvd_config)
                                vulnerability_service = VulnerabilityService(db.session)
                                
                                processed_count = await fetcher.update(
                                    vulnerability_service=vulnerability_service,
                                    full=False
                                )
                                
                                app_logger.info(f"✅ Sincronização horária concluída: {processed_count} vulnerabilidades processadas")
                        
                        loop.run_until_complete(sync_task())
                        
                    finally:
                        loop.close()
                        
            except Exception as e:
                app_logger.error(f"❌ Erro durante sincronização horária: {e}")
    
    # Iniciar thread do scheduler
    scheduler_thread = threading.Thread(target=run_hourly_sync, daemon=True)
    scheduler_thread.start()
    app_logger.info("⏰ Scheduler de sincronização NVD iniciado (execução a cada 1 hora)")

def main():
    """
    Função principal de inicialização com feedback aprimorado.
    """
    # Configurar logging
    setup_logging("INFO", "logs/openmonitor.log")
    app_logger = get_app_logger()
    
    # Iniciar sistema de indicadores visuais
    status_indicator.start_display()
    
    # Usar sistema de feedback aprimorado
    terminal_feedback.info("🚀 Iniciando Open-Monitor")
    terminal_feedback.info(f"⏰ Horário de inicialização: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Criar aplicação Flask com feedback
        with timed_operation("Configuração da aplicação Flask"):
            app = create_app()
        
        # Inicializar banco de dados com feedback visual
        with timed_operation("Inicialização do banco de dados"):
            if not initialize_database(app):
                terminal_feedback.error("❌ Falha na inicialização do banco de dados", 
                                      suggestion="Verifique a configuração do banco e permissões")
                status_indicator.stop_display()
                return False
        
        # Executar sincronização inicial do NVD
        with timed_operation("Verificação de sincronização inicial"):
            initial_sync_success = asyncio.run(perform_initial_nvd_sync(app))
            if not initial_sync_success:
                terminal_feedback.warning("⚠️ Sincronização inicial falhou, mas continuando inicialização")
        
        # Configurar scheduler para sincronização automática
        with timed_operation("Configuração de sincronização automática"):
            setup_nvd_scheduler(app)
        
        # Finalizar com sucesso
        terminal_feedback.success("✅ Open-Monitor inicializado com sucesso!")
        terminal_feedback.info("🌐 Para iniciar o servidor web, execute: flask run", 
                             {"url": "http://localhost:5000", "command": "flask run"})
        terminal_feedback.info("🔄 Sincronização automática configurada para executar a cada 1 hora")
        
        # Parar indicadores visuais
        time.sleep(2)  # Dar tempo para ver as mensagens finais
        status_indicator.stop_display()
        
        return True
        
    except Exception as e:
        # Usar sistema de erro aprimorado
        terminal_feedback.error("❌ Erro durante inicialização", 
                              context={"error_type": type(e).__name__, "error_message": str(e)},
                              suggestion="Verifique as configurações e dependências")
        
        # Parar indicadores visuais em caso de erro
        status_indicator.stop_display()
        
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 Inicialização concluída com sucesso!")
        print("💡 Execute 'flask run' para iniciar o servidor")
        sys.exit(0)
    else:
        print("\n❌ Inicialização falhou!")
        sys.exit(1)