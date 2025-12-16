"""
Adapter de fábrica da aplicação para compatibilidade.

Expõe `create_app` a partir de `app.main_startup` para módulos que importam
`app.app`. Mantém compatibilidade com scripts existentes.
"""

try:
    from .main_startup import create_app
except ImportError:
    from app.main_startup import create_app

__all__ = ["create_app"]
