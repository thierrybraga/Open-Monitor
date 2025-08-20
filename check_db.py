import os
os.environ['FLASK_ENV'] = 'production'

from extensions.db import db
from app import create_app
from sqlalchemy import text
from models.user import User
from models.vulnerability import Vulnerability
from models.asset import Asset

app = create_app()
with app.app_context():
    # Verificar tabelas
    result = db.session.execute(text('SELECT name FROM sqlite_master WHERE type="table"'))
    tables = [row[0] for row in result]
    print('=== TABELAS NO BANCO ===')
    for table in tables:
        print(f'- {table}')
    
    print('\n=== CONTAGEM DE DADOS ===')
    try:
        user_count = User.query.count()
        print(f'Usuários: {user_count}')
    except Exception as e:
        print(f'Erro ao contar usuários: {e}')
    
    try:
        vuln_count = Vulnerability.query.count()
        print(f'Vulnerabilidades: {vuln_count}')
    except Exception as e:
        print(f'Erro ao contar vulnerabilidades: {e}')
    
    try:
        asset_count = Asset.query.count()
        print(f'Assets: {asset_count}')
    except Exception as e:
        print(f'Erro ao contar assets: {e}')
    
    print('\n=== STATUS DO BANCO ===')
    if user_count == 0 and vuln_count == 0 and asset_count == 0:
        print('BANCO VAZIO - Nenhum dado encontrado!')
    else:
        print('BANCO COM DADOS - Dados encontrados!')
        
        if user_count > 0:
            print('\nPrimeiros usuários:')
            users = User.query.limit(3).all()
            for user in users:
                print(f'- {user.username} ({user.email})')
        
        if vuln_count > 0:
            print('\nPrimeiras vulnerabilidades:')
            vulns = Vulnerability.query.limit(3).all()
            for vuln in vulns:
                print(f'- {vuln.title} (Severidade: {vuln.severity})')
        
        if asset_count > 0:
            print('\nPrimeiros assets:')
            assets = Asset.query.limit(3).all()
            for asset in assets:
                print(f'- {asset.name} ({asset.asset_type})')