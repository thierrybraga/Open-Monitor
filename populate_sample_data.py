#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para popular o banco de dados com dados de exemplo.
Este script cria assets de exemplo e associa vulnerabilidades a eles.
"""

import sys
import logging
from datetime import datetime
from app import create_app
from extensions import db
from models.user import User
from models.asset import Asset
from models.vulnerability import Vulnerability
from models.asset_vulnerability import AssetVulnerability

logger = logging.getLogger(__name__)

def create_sample_assets():
    """Cria assets de exemplo para o usuário admin."""
    print("Criando assets de exemplo...")
    
    # Buscar usuário admin
    admin_user = User.query.filter_by(username='admin').first()
    if not admin_user:
        print("❌ Usuário admin não encontrado. Execute init_db.py primeiro.")
        return False
    
    # Verificar se já existem assets
    existing_assets_list = Asset.query.filter_by(owner_id=admin_user.id).all()
    if existing_assets_list:
        print(f"✓ Já existem {len(existing_assets_list)} assets para o usuário admin.")
        return existing_assets_list
    
    # Criar assets de exemplo
    sample_assets = [
        {
            'name': 'Servidor Web Principal',
            'ip_address': '192.168.1.10',
            'status': 'active',
            'description': 'Servidor web principal da aplicação'
        },
        {
            'name': 'Banco de Dados MySQL',
            'ip_address': '192.168.1.20',
            'status': 'active',
            'description': 'Servidor de banco de dados MySQL'
        },
        {
            'name': 'Servidor de Aplicação',
            'ip_address': '192.168.1.30',
            'status': 'active',
            'description': 'Servidor de aplicação backend'
        },
        {
            'name': 'Load Balancer',
            'ip_address': '192.168.1.5',
            'status': 'active',
            'description': 'Balanceador de carga nginx'
        },
        {
            'name': 'Servidor de Cache Redis',
            'ip_address': '192.168.1.40',
            'status': 'maintenance',
            'description': 'Servidor Redis para cache'
        }
    ]
    
    created_assets = []
    for asset_data in sample_assets:
        asset = Asset(
            name=asset_data['name'],
            ip_address=asset_data['ip_address'],
            status=asset_data['status'],
            owner_id=admin_user.id
        )
        db.session.add(asset)
        created_assets.append(asset)
        print(f"  ✓ Criado asset: {asset_data['name']}")
    
    try:
        db.session.commit()
        print(f"✓ {len(created_assets)} assets criados com sucesso!")
        return created_assets
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao criar assets: {e}")
        return False

def associate_vulnerabilities_to_assets(assets):
    """Associa vulnerabilidades existentes aos assets criados."""
    print("Associando vulnerabilidades aos assets...")
    
    if not assets:
        print("❌ Nenhum asset fornecido para associação.")
        return False
    
    # Buscar algumas vulnerabilidades existentes
    vulnerabilities = Vulnerability.query.limit(20).all()
    if not vulnerabilities:
        print("❌ Nenhuma vulnerabilidade encontrada no banco de dados.")
        return False
    
    print(f"Encontradas {len(vulnerabilities)} vulnerabilidades para associar.")
    
    associations_created = 0
    
    # Associar vulnerabilidades aos assets de forma distribuída
    for i, vulnerability in enumerate(vulnerabilities):
        # Distribuir vulnerabilidades entre os assets
        asset = assets[i % len(assets)]
        
        # Verificar se a associação já existe
        existing = AssetVulnerability.query.filter_by(
            asset_id=asset.id,
            vulnerability_id=vulnerability.cve_id
        ).first()
        
        if not existing:
            association = AssetVulnerability(
                asset_id=asset.id,
                vulnerability_id=vulnerability.cve_id,
                status='OPEN'
            )
            db.session.add(association)
            associations_created += 1
            print(f"  ✓ Associado {vulnerability.cve_id} ao asset {asset.name}")
    
    try:
        db.session.commit()
        print(f"✓ {associations_created} associações criadas com sucesso!")
        return True
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao criar associações: {e}")
        return False

def main():
    """Função principal do script."""
    print("=== Populando Banco de Dados com Dados de Exemplo ===\n")
    
    # Criar aplicação Flask
    app = create_app('development')
    
    with app.app_context():
        try:
            # Criar assets de exemplo
            assets = create_sample_assets()
            if not assets:
                sys.exit(1)
            
            # Associar vulnerabilidades aos assets
            if not associate_vulnerabilities_to_assets(assets):
                sys.exit(1)
            
            print("\n=== Dados de exemplo criados com sucesso! ===\n")
            print("Agora você pode:")
            print("1. Fazer login com usuário 'admin' e senha 'admin123'")
            print("2. Visualizar o dashboard com dados reais")
            print("3. Explorar as funcionalidades de assets e vulnerabilidades")
            
        except Exception as e:
            print(f"\n❌ Erro durante a população de dados: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()