# Open-Monitor/__init__.py

"""
Pacote principal da aplicação Flask.
Define o ponto de entrada para a criação da aplicação.
"""

from .app import create_app

__all__ = ['create_app']