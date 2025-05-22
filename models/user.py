# project/models/user.py

import logging # Importar logging
from datetime import datetime
# Adicionado 'List', 'Optional', 'TYPE_CHECKING' à importação do typing
from typing import Dict, Any, Optional, TYPE_CHECKING, List # CORRIGIDO: Adicionado List, Optional, TYPE_CHECKING
import re
import bcrypt # Certifique-se que bcrypt está instalado (pip install bcrypt)
from flask_login import UserMixin
# Importar Colunas, Tipos SQLAlchemy, e ForeignKey se usado (ex: em user_role)
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey # Importar ForeignKey (mesmo se usado em outro modelo relacionado)
# Importar relationship, Mapped e mapped_column
from sqlalchemy.orm import relationship, Mapped, mapped_column # CORRIGIDO: Importado Mapped e mapped_column
from sqlalchemy.exc import SQLAlchemyError # Importar SQLAlchemyError
# Importar current_app de flask se necessário (geralmente dentro de funções)
from flask import current_app # Importar current_app (opcional, descomente se usar)


# Use importação relativa CORRETA para as instâncias das extensões
# Assumindo que db e login_manager são exportados por project/extensions/__init__.py
from ..extensions import db, login_manager # CORRIGIDO: Caminho de importação


# Importar BaseModel para herdar campos auditáveis (criado_em, atualizado_em)
# Assumindo que BaseModel está em project/models/base_model.py
from .base_model import BaseModel


# Importe modelos relacionados para type hinting, mas apenas em tempo de checagem de tipo
# Isso evita ciclos de importação. Use o nome string do modelo nos relacionamentos SQLAlchemy.
if TYPE_CHECKING:
    from .asset import Asset
    from .monitoring_rule import MonitoringRule
    # TODO: Adicionar outros modelos relacionados se necessário para type hinting
    # from .chat_log import ChatLog
    # from .user_role import UserRole # Importar UserRole para o relacionamento
    # from .role import Role # Importar Role para o relacionamento


logger = logging.getLogger(__name__) # Adicionar logger


class User(BaseModel, UserMixin, db.Model): # Herda de BaseModel, UserMixin e db.Model
    """
    Modelo do banco de dados para usuários.

    Contém informações de autenticação, perfil básico e relacionamentos
    com outros dados do usuário (ativos, regras de monitoramento, etc.).
    """
    __tablename__ = 'users'  # Nome da tabela (plural por convenção)

    # Colunas da tabela usando Mapped[] e mapped_column
    # Use mapped_column para definir as colunas do DB e Mapped[] para a anotação de tipo
    id: Mapped[int] = mapped_column(Integer, primary_key=True) # CORRIGIDO
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True) # CORRIGIDO
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True) # CORRIGIDO
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False) # CORRIGIDO
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False) # CORRIGIDO

    # Campos auditáveis (herdados de BaseModel) - Se BaseModel usa Mapped[] e mapped_column, user também deve herdar corretamente
    # Se BaseModel define estes campos diretamente sem Mapped[], você pode precisar anotá-los aqui ou garantir que BaseModel use Mapped[]
    # Assumindo que BaseModel SERÁ atualizado para usar Mapped[] e mapped_column para seus campos:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False) # Assumindo default em BaseModel ou aqui
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False) # Assumindo default em BaseModel ou aqui


    # Relacionamentos usando Mapped[List[...]]
    # A anotação de tipo agora usa Mapped[] envolvendo a lista
    # Use o nome string do modelo ('Asset', 'MonitoringRule') no relationship
    assets: Mapped[List['Asset']] = relationship('Asset', back_populates='owner', lazy='dynamic') # CORRIGIDO
    monitoring_rules: Mapped[List['MonitoringRule']] = relationship('MonitoringRule', back_populates='user', lazy='dynamic') # CORRIGIDO

    # TODO: Adicionar outros relacionamentos usando Mapped[List['Modelo']] ou Mapped['Modelo']
    # chat_logs: Mapped[List['ChatLog']] = relationship('ChatLog', back_populates='user', lazy='dynamic') # CORRIGIDO
    # Exemplo de relacionamento para UserRole (tabela de associação para Many-to-Many com Role)
    # user_roles: Mapped[List['UserRole']] = relationship('UserRole', back_populates='user', lazy='dynamic')


    # ---------- Construtor (Opcional se SQLAlchemy usa default __init__) ----------
    # SQLAlchemy pode gerar um __init__ automaticamente, mas você pode definir um personalizado
    # se precisar de lógica adicional na inicialização (como validação).
    # Se BaseModel tem um __init__ que precisa ser chamado, adicione a chamada aqui.
    def __init__(self, username: str, email: str, password: Optional[str] = None): # Senha opcional para alguns casos
        self.username = username
        self.email = self._validate_email(email) # Valida e normaliza e-mail
        if password:
            self.set_password(password)
        # TODO: Se BaseModel tem __init__, chamar: super().__init__() # ou BaseModel.__init__(self)


    # ---------- Validações ----------
    @staticmethod
    def _validate_email(email: str) -> str:
        """Valida o formato do e-mail e retorna em lowercase."""
        # Regex básica para validação de e-mail (ajuste conforme sua necessidade)
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not isinstance(email, str):
             logger.warning(f"Invalid email type: {type(email)}")
             raise ValueError("Email deve ser uma string.")
        if not re.match(pattern, email):
            logger.warning(f"Invalid email format: {email}") # Logar e-mails inválvidos
            raise ValueError("Formato de e-mail inválido.")
        return email.lower() # Retorna e-mail em minúsculas

    # TODO: Adicionar validação de username (caracteres permitidos, comprimento, etc.)


    # ---------- Senha segura com bcrypt ----------
    def set_password(self, password: str) -> None:
        """Define a senha, hasheando-a com bcrypt."""
        # Validar força da senha antes de hashear
        if not isinstance(password, str) or not password or len(password) < 8: # Exemplo: mínimo 8 caracteres
            logger.warning(f"Attempted to set password invalid or shorter than 8 characters.")
            raise ValueError("Senha inválida ou deve ter ao menos 8 caracteres.")

        # Hashear a senha
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), # Converter para bytes
            bcrypt.gensalt() # Gerar um salt aleatório
        ).decode('utf-8') # Converter o hash resultante de volta para string

    def check_password(self, password: str) -> bool:
        """Verifica se a senha fornecida corresponde ao hash armazenado."""
        if not isinstance(password, str) or not self.password_hash: # Se não houver hash armazenado ou senha não é string
             return False
        try:
            # Comparar a senha fornecida (hasheada) com o hash armazenado
            return bcrypt.checkpw(
                password.encode('utf-8'), # Converter senha de entrada para bytes
                self.password_hash.encode('utf-8') # Converter hash armazenado para bytes
            )
        except ValueError:
             # Lidar com hashes inválidos (ex: formato incorreto no DB)
             logger.error("Invalid password hash format detected for user ID %s.", self.id, exc_info=True) # Usar %s para log
             return False
        except Exception as e:
             logger.error("An unexpected error occurred during password check for user ID %s: %s", self.id, e, exc_info=True) # Usar %s para log
             return False


    # ---------- Serialização ----------
    def to_dict(self) -> Dict[str, Any]:
        """Serializa o objeto User para um dicionário (uso básico)."""
        # TODO: Usar um Marshmallow Schema (em schemas/user_schema.py) para serialização mais complexa/API
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            # Convertar objetos datetime para ISO 8601 strings, lidando com None
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            # TODO: Incluir outros campos ou relacionamentos serializados (ex: roles)
        }

    def __repr__(self) -> str:
        """Representação string do objeto User para debug."""
        return f"<User id={self.id} username='{self.username}'>" # Usar aspas simples para username


# Função user_loader para Flask-Login
# Este decorador registra a função no LoginManager (importado corretamente de ..extensions)
@login_manager.user_loader # Decorador correto
def load_user(user_id: Optional[str]) -> Optional[User]: # Adicionado type hinting
    """
    Carrega um usuário pelo ID para o Flask-Login.
    Chamado a cada requisição para obter o usuário atual.

    Args:
        user_id: O ID do usuário (como string) armazenado na sessão pelo Flask-Login.
                 Pode ser None se não houver ID na sessão (usuário não logado).

    Returns:
        O objeto User correspondente, ou None se o ID for inválido ou o usuário não for encontrado.
    """
    # Flask-Login passa o user_id como string. Se não houver ID na sessão (não logado), pode ser None.
    if user_id is None:
        logger.debug("user_loader called with None user_id (user not logged in).")
        return None

    try:
        # Tenta converter o user_id string para o tipo da PK do seu modelo User (geralmente int)
        # e busca no banco de dados.
        # Usar query.get() é eficiente para buscar por PK.
        # O logger.debug aqui pode ajudar a depurar se o user_loader está sendo chamado
        # logger.debug("Attempting to load user with ID: %s", user_id) # Usar %s para log
        user = User.query.get(int(user_id))

        # Log para debug se o usuário foi encontrado ou não
        # if user:
        #     # current_app pode não estar disponível aqui se o user_loader for chamado muito cedo.
        #     # Usar o logger normal é mais seguro.
        #     logger.debug("User loaded successfully: %s", user.username) # Usar %s para log
        # else:
        #     logger.debug("User ID %s not found by user_loader.", user_id) # Usar %s para log


        return user

    except (ValueError, TypeError):
        # Se user_id não for um número válido (não pode ser convertido para int), retorna None
        # Isso pode acontecer se a sessão for adulterada ou contiver um ID inválido.
        logger.warning("Invalid user_id format '%s' passed to user_loader. Cannot convert to int.", user_id, exc_info=True) # Usar %s para log
        return None
    except SQLAlchemyError as e:
        # Capturar erros de banco de dados durante a query
        logger.error("DB error loading user ID %s in user_loader.", user_id, exc_info=True) # Usar %s para log
        return None # Retornar None em caso de erro de DB
    except Exception as e:
        # Capturar outros erros inesperados no user_loader
        logger.error("An unexpected error occurred in user_loader for ID %s: %s", user_id, e, exc_info=True) # Usar %s para log
        return None # Retornar None em caso de outros erros