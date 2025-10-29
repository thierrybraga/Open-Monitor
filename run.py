#!/usr/bin/env python3
"""
Script to run the Flask application in development mode.
Inclui inicialização automática do banco de dados e sincronização NVD.
"""

import sys
from pathlib import Path

# Adicionar o diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent))

from app import create_app
from app.main_startup import main as initialize_system
from app.utils.enhanced_logging import get_app_logger

if __name__ == '__main__':
    # Executar inicialização completa do sistema
    print("🚀 Iniciando Open-Monitor...")
    
    if initialize_system():
        print("✅ Sistema inicializado com sucesso!")
        print("🌐 Iniciando servidor web...")
         
        # Criar aplicação e iniciar servidor
        app = create_app('development')
        
        try:
            app.run(host='0.0.0.0', port=5000, debug=True)
        except KeyboardInterrupt:
            print("\n🛑 Servidor interrompido pelo usuário")
        except Exception as e:
            print(f"\n❌ Erro ao iniciar servidor: {e}")
            sys.exit(1)
    else:
        print("❌ Falha na inicialização do sistema!")
        sys.exit(1)