#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
from dotenv import load_dotenv

# Força o recarregamento do .env
load_dotenv(override=True)

# Remove módulos de configuração do cache se existirem
modules_to_remove = []
for module_name in sys.modules.keys():
    if 'settings' in module_name or 'config' in module_name or 'app' in module_name:
        modules_to_remove.append(module_name)

for module_name in modules_to_remove:
    if module_name in sys.modules:
        del sys.modules[module_name]

from app import create_app
from app.services.email_service import EmailService

# Cria a aplicação Flask
app = create_app()

with app.app_context():
    # Cria uma instância do EmailService
    email_service = EmailService()
    
    print(f"SMTP Server: {email_service.smtp_server}")
    print(f"SMTP Port: {email_service.smtp_port}")
    print(f"SMTP Username: {email_service.smtp_username}")
    print(f"SMTP Password: {email_service.smtp_password}")
    print(f"Use TLS: {email_service.use_tls}")
    print(f"Use SSL: {email_service.use_ssl}")
    print(f"Default Sender: {email_service.default_sender}")
