"""
Pacote principal da aplicação Flask.
"""

def create_app(env_name=None, config_class=None):
    from .main_startup import create_app as _create_app
    return _create_app(env_name, config_class)

__all__ = ['create_app']
