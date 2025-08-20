# E:\Open-Monitor\models\__init__.py

"""
Centraliza a importação e o registro de modelos SQLAlchemy.
Faz auto-descoberta de todos os módulos em models/ dentro do pacote 'Open-Monitor'
e registra classes que subclassam BaseModel para acesso centralizado.
"""

import logging
import pkgutil
import importlib
import inspect
import sys
from pathlib import Path
from typing import Type, Dict, List, Any
from functools import lru_cache
from sqlalchemy import inspect
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from inflection import underscore

from .base_model import BaseModel
from extensions import db, migrate

logger = logging.getLogger(__name__)

# --- Auto-descoberta e import de todos os módulos em models/ ---
_package_path: Path = Path(__file__).parent
# Usa o nome do pacote raiz ('Open-Monitor') para o prefixo, não 'project'.
# Isso garante que importlib.import_module use o nome correto para os módulos.
# O prefixo é baseado no __package__ do pacote pai do módulo __init__.py
# (e.g., 'Open-Monitor.models').
# Para garantir que o prefixo seja sempre correto (Open-Monitor.models),
# podemos usar o __name__ que é 'Open-Monitor.models' se o app for carregado corretamente.
for finder, module_name, is_pkg in pkgutil.walk_packages([str(_package_path)], prefix=f"{__package__}."): # <-- CORRIGIDO AQUI
    if module_name == __name__:
        continue
    try:
        importlib.import_module(module_name)
        logger.debug(f"Imported model module: {module_name}")
    except Exception as e:
        logger.warning(f"Falha ao importar {module_name}: {e}", exc_info=e)


# --- Código de depuração para verificar o caminho do user.py ---
# Mantenha este bloco de depuração por enquanto, mas ajuste as strings de depuração
try:
    # Tenta acessar o módulo user diretamente via sys.modules, se já foi importado
    # Agora procurando por 'Open-Monitor.models.user'
    if 'Open-Monitor.models.user' in sys.modules: # <-- CORRIGIDO AQUI
         user_module = sys.modules['Open-Monitor.models.user'] # <-- CORRIGIDO AQUI
         if hasattr(user_module, '__file__') and user_module.__file__:
            print(f"DEBUG: Módulo Open-Monitor.models.user encontrado em sys.modules. Carregado de: {user_module.__file__}", file=sys.stderr) # <-- CORRIGIDO AQUI
         else:
            print("DEBUG: Módulo Open-Monitor.models.user encontrado em sys.modules, mas __file__ não disponível.", file=sys.stderr) # <-- CORRIGIDO AQUI
    else:
         # Se não está em sys.modules, tenta encontrá-lo (embora o erro sugira que foi importado)
         spec = importlib.util.find_spec('.user', package=__name__)
         if spec and spec.origin:
             print(f"DEBUG: Módulo Open-Monitor.models.user NÃO encontrado em sys.modules, mas find_spec o localizou em: {spec.origin}", file=sys.stderr) # <-- CORRIGIDO AQUI
         else:
              print("DEBUG: Módulo Open-Monitor.models.user NÃO encontrado em sys.modules e find_spec não o localizou.", file=sys.stderr) # <-- CORRIGIDO AQUI

    # Opcional: Verificar se a classe User específica foi carregada no módulo
    if 'Open-Monitor.models.user' in sys.modules and hasattr(sys.modules['Open-Monitor.models.user'], 'User'): # <-- CORRIGIDO AQUI
         print("DEBUG: Classe Open-Monitor.models.user.User encontrada.", file=sys.stderr) # <-- CORRIGIDO AQUI
    else:
         print("DEBUG: Classe Open-Monitor.models.user.User NÃO encontrada no módulo carregado.", file=sys.stderr) # <-- CORRIGIDO AQUI


except Exception as e:
    print(f"DEBUG: Erro inesperado ao tentar verificar Open-Monitor.models.user: {e}", file=sys.stderr) # <-- CORRIGIDO AQUI
# --- Fim do código de depuração ---


# --- Registry automático de classes BaseModel ---
def _register_models():
   logger.debug("Registering models via SQLAlchemy registry...")
   try:
       for mapper in db.Model.registry.mappers:
            model_class = mapper.class_
            # ...
       logger.debug("Model registration via registry complete.")
   except Exception as e:
        logger.error("Error during SQLAlchemy model registration/inspection.", exc_info=True)
        raise

def validate_models():
    logger.debug("Validating model structures...")
    try:
        for mapper in db.Model.registry.mappers:
            model = mapper.class_
            name = model.__name__
            insp = inspect(model)
            for rel in insp.relationships:
                if not (rel.back_populates or rel.backref):
                    logger.warning(f"Modelo {name}.{rel.key} é um relacionamento sem back_populates/backref. Considere adicioná-lo.")
        logger.debug("Model validation complete.")
    except Exception as e:
        logger.error("Error during model validation.", exc_info=True)

class ModelRegistry:
    _model_cache: Dict[str, Type[db.Model]] = {}

    @classmethod
    @lru_cache(maxsize=None)
    def get_model(cls, model_name: str) -> Type[db.Model]:
        try:
             for mapper in db.Model.registry.mappers:
                  model_class = mapper.class_
                  if model_class.__name__ == model_name:
                       logger.debug(f"Modelo '{model_name}' encontrado no registro SQLAlchemy.")
                       return model_class
        except Exception as e:
             logger.warning(f"Erro ao buscar modelo '{model_name}' no registro SQLAlchemy: {e}", exc_info=True)

        from inflection import underscore
        module_name = underscore(model_name)
        # Caminho completo do módulo esperado (e.g., Open-Monitor.models.user)
        module_path = f"{__package__}.{module_name}" # <-- CORRIGIDO AQUI

        try:
            mod = importlib.import_module(module_path)
            model = getattr(mod, model_name)

            for mapper in db.Model.registry.mappers:
                if mapper.class_ == model:
                     logger.debug(f"Modelo '{model_name}' importado dinamicamente e encontrado no registro SQLAlchemy.")
                     return model

            logger.error(f"Modelo '{model_name}' importado dinamicamente, mas não encontrado no registro SQLAlchemy após importação.")
            raise ValueError(f"Modelo '{model_name}' carregado, mas não registrado pelo SQLAlchemy.")

        except (ImportError, AttributeError, TypeError) as e:
            logger.error(f"Não foi possível carregar modelo '{model_name}' dinamicamente ou ele não é um modelo válido: {e}", exc_info=e)
            raise ValueError(f"Modelo '{model_name}' não encontrado, ou inválido (não é db.Model). Verifique o nome e a importação.") from e
        except Exception as e:
             logger.error(f"Erro inesperado ao carregar modelo '{model_name}': {e}", exc_info=True)
             raise RuntimeError(f"Erro ao carregar modelo '{model_name}'.") from e

try:
    _register_models()
except Exception:
    pass

_exported_models_names: List[str] = []
try:
     for mapper in db.Model.registry.mappers:
          _exported_models_names.append(mapper.class_.__name__)
except Exception as e:
     logger.warning(f"Não foi possível listar nomes de modelos do registro SQLAlchemy para exports: {e}")


__all__: List[str] = [
    'db',
    'migrate',
    'BaseModel',
    'validate_models',
    'ModelRegistry'
] + _exported_models_names