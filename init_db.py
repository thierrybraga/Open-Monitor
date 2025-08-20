#!/usr/bin/env python3
"""
Script de inicialização do banco de dados para o Open-Monitor.

Este script:
1. Cria as tabelas do banco de dados
2. Executa migrações se necessário
3. Cria dados iniciais (usuário admin, etc.)
"""

import os
import sys
from getpass import getpass

# Adiciona o diretório raiz ao path para importações
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from extensions import db
from werkzeug.security import generate_password_hash


def init_database():
    """Inicializa o banco de dados criando todas as tabelas."""
    print("Criando tabelas do banco de dados...")
    db.create_all()
    print("✓ Tabelas criadas com sucesso!")


def create_admin_user():
    """Cria um usuário administrador inicial."""
    from models.user import User
    
    print("\nCriando usuário administrador...")
    
    # Verifica se já existe um usuário admin
    admin_user = User.query.filter_by(username='admin').first()
    if admin_user:
        print("✓ Usuário admin já existe!")
        return
    
    # Solicita dados do admin
    username = input("Nome de usuário do admin [admin]: ").strip() or 'admin'
    email = input("Email do admin: ").strip()
    
    while not email:
        email = input("Email é obrigatório. Digite o email do admin: ").strip()
    
    password = getpass("Senha do admin: ")
    while len(password) < 6:
        password = getpass("Senha deve ter pelo menos 6 caracteres. Digite novamente: ")
    
    # Cria o usuário admin
    try:
        admin_user = User(
            username=username,
            email=email,
            password=password
        )
        
        # Define como ativo e administrador
        admin_user.is_active = True
        admin_user.is_admin = True
        
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"✓ Usuário admin '{username}' criado com sucesso!")
        
    except Exception as e:
        print(f"✗ Erro ao criar usuário admin: {e}")
        db.session.rollback()


def create_default_roles():
    """Cria roles padrão no sistema."""
    from models.role import Role
    
    print("\nCriando roles padrão...")
    
    default_roles = [
        {'name': 'admin', 'description': 'Administrador do sistema'},
        {'name': 'user', 'description': 'Usuário padrão'},
        {'name': 'analyst', 'description': 'Analista de segurança'},
    ]
    
    for role_data in default_roles:
        existing_role = Role.query.filter_by(name=role_data['name']).first()
        if not existing_role:
            try:
                role = Role(
                    name=role_data['name'],
                    description=role_data['description']
                )
                db.session.add(role)
                print(f"✓ Role '{role_data['name']}' criada")
            except Exception as e:
                print(f"✗ Erro ao criar role '{role_data['name']}': {e}")
        else:
            print(f"✓ Role '{role_data['name']}' já existe")
    
    try:
        db.session.commit()
        print("✓ Roles criadas com sucesso!")
    except Exception as e:
        print(f"✗ Erro ao salvar roles: {e}")
        db.session.rollback()


def main():
    """Função principal do script de inicialização."""
    print("=== Inicialização do Banco de Dados - Open Monitor ===")
    print("Este script irá configurar o banco de dados inicial.\n")
    
    # Cria a aplicação Flask
    app = create_app('development')
    
    with app.app_context():
        try:
            # Inicializa o banco de dados
            init_database()
            
            # Cria roles padrão
            create_default_roles()
            
            # Cria usuário admin
            create_admin_user()
            
            print("\n=== Inicialização concluída com sucesso! ===")
            print("\nPróximos passos:")
            print("1. Configure o arquivo .env com suas variáveis")
            print("2. Execute: flask run")
            print("3. Acesse: http://localhost:5000")
            
        except Exception as e:
            print(f"\n✗ Erro durante a inicialização: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()