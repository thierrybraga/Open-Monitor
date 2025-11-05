#!/usr/bin/env python3
"""
Script to run the Flask application in development mode.
Inclui inicialização automática do banco de dados e sincronização NVD.
"""

import sys
import os
import asyncio
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))
# Garantir que o site-packages do ambiente atual esteja no path
import site
for site_path in site.getsitepackages():
    if site_path not in sys.path:
        sys.path.append(site_path)

from app import create_app
from app.main_startup import (
    initialize_database,
    perform_initial_nvd_sync,
    setup_nvd_scheduler,
)
from app.utils.enhanced_logging import get_app_logger

if __name__ == '__main__':
    # Inicialização com uma única instância de app
    print("🚀 Iniciando Open-Monitor...")

    try:
        app = create_app('development')
    except Exception as e:
        print(f"❌ Falha ao criar a aplicação Flask: {e}")
        sys.exit(1)

    # Executar passos de startup usando a mesma app
    try:
        print("🗄️ Inicializando banco de dados...")
        with app.app_context():
            if not initialize_database(app):
                print("❌ Falha na inicialização do banco de dados")
                sys.exit(1)

        print("🔄 Verificando sincronização inicial do NVD...")
        try:
            asyncio.run(perform_initial_nvd_sync(app))
        except Exception as e:
            # Não bloquear o start do servidor por falha de sync inicial
            print(f"⚠️ Sincronização inicial NVD falhou: {e}")

        print("⏰ Configurando scheduler de sincronização NVD...")
        setup_nvd_scheduler(app)

        # Iniciar servidor
        print("🌐 Iniciando servidor web...")
        port = int(os.getenv('PORT', os.getenv('FLASK_RUN_PORT', '8000')))
        app.run(
            host='0.0.0.0',
            port=port,
            debug=app.config.get('DEBUG', True),
            use_reloader=False
        )
    except KeyboardInterrupt:
        print("\n🛑 Servidor interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro ao iniciar servidor: {e}")
        sys.exit(1)