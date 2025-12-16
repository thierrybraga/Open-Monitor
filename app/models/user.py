# project/models/user.py

import logging # Importar logging
from datetime import datetime, timedelta, timezone
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
from app.extensions import db, login_manager


# Importar BaseModel para herdar campos auditáveis (criado_em, atualizado_em)
from app.models.base_model import BaseModel


# Importe modelos relacionados para type hinting, mas apenas em tempo de checagem de tipo
# Isso evita ciclos de importação. Use o nome string do modelo nos relacionamentos SQLAlchemy.
if TYPE_CHECKING:
    from app.models.asset import Asset
    from app.models.monitoring_rule import MonitoringRule
    from app.models.chat_session import ChatSession
    from app.models.chat_message import ChatMessage
    # TODO: Adicionar outros modelos relacionados se necessário para type hinting
    # from utils.user_role import UserRole # Importar UserRole para o relacionamento
    # from utils.role import Role # Importar Role para o relacionamento


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
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False) # Campo para identificar administradores
    
    # Campos para confirmação de email
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_confirmation_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_confirmation_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Campos para recuperação de senha
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password_reset_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Campos de perfil
    first_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # Caminho para a imagem
    tacacs_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tacacs_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tacacs_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tacacs_server: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tacacs_port: Mapped[int] = mapped_column(Integer, default=49, nullable=False)
    tacacs_timeout: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    root_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    approved_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey('users.id'), nullable=True, index=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    trial_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Campos de auditoria (timestamps) - definidos explicitamente para compatibilidade
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


    # Relacionamentos usando Mapped[List[...]]
    # A anotação de tipo agora usa Mapped[] envolvendo a lista
    # Use o nome string do modelo ('Asset', 'MonitoringRule') no relationship
# Relacionamentos
    assets: Mapped[List['Asset']] = relationship('Asset', back_populates='owner', lazy='dynamic') # CORRIGIDO
    monitoring_rules: Mapped[List['MonitoringRule']] = relationship('MonitoringRule', back_populates='user', lazy='dynamic') # CORRIGIDO

    risk_assessments: Mapped[List['RiskAssessment']] = relationship('RiskAssessment', back_populates='user', lazy='dynamic')

    # Relacionamentos de chat
    chat_sessions: Mapped[List['ChatSession']] = relationship('ChatSession', back_populates='user', lazy='dynamic')
    chat_messages: Mapped[List['ChatMessage']] = relationship('ChatMessage', back_populates='user', lazy='dynamic')
    
    # Relacionamento de relatórios
    reports: Mapped[List['Report']] = relationship('Report', back_populates='generated_by', lazy='dynamic')
    
    # TODO: Adicionar outros relacionamentos usando Mapped[List['Modelo']] ou Mapped['Modelo']
    # Exemplo de relacionamento para UserRole (tabela de associação para Many-to-Many com Role)
    # user_roles: Mapped[List['UserRole']] = relationship('UserRole', back_populates='user', lazy='dynamic')


    # ---------- Construtor (Opcional se SQLAlchemy usa default __init__) ----------
    # SQLAlchemy pode gerar um __init__ automaticamente, mas você pode definir um personalizado
    # se precisar de lógica adicional na inicialização (como validação).
    # Se BaseModel tem um __init__ que precisa ser chamado, adicione a chamada aqui.
    def __init__(self, username: str, email: str, password: Optional[str] = None, **kwargs): # Senha opcional para alguns casos
        super().__init__()  # Chama o construtor do BaseModel
        self.username = username
        self.email = self._validate_email(email) # Valida e normaliza e-mail
        if password:
            self.set_password(password)
        
        # Campos de perfil opcionais
        self.first_name = kwargs.get('first_name')
        self.last_name = kwargs.get('last_name')
        self.phone = kwargs.get('phone')
        self.address = kwargs.get('address')
        self.bio = kwargs.get('bio')
        self.profile_picture = kwargs.get('profile_picture')


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


    # ---------- Confirmação de Email ----------
    def generate_confirmation_token(self) -> str:
        """Gera um token único para confirmação de email."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.email_confirmation_token = token
        self.email_confirmation_sent_at = datetime.now(timezone.utc)
        return token

    def confirm_email(self, token: str) -> bool:
        """Confirma o email se o token for válido e não expirado."""
        if not self.email_confirmation_token or self.email_confirmation_token != token:
            return False
        
        # Verificar se o token não expirou (24 horas)
        if self.email_confirmation_sent_at:
            sent_at = self.email_confirmation_sent_at
            if getattr(sent_at, 'tzinfo', None) is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            else:
                sent_at = sent_at.astimezone(timezone.utc)
            expiration_time = sent_at + timedelta(hours=24)
            if datetime.now(timezone.utc) > expiration_time:
                return False
        
        # Confirmar email
        self.email_confirmed = True
        self.email_confirmation_token = None
        self.email_confirmation_sent_at = None
        return True

    def is_confirmation_token_expired(self) -> bool:
        """Verifica se o token de confirmação expirou."""
        if not self.email_confirmation_sent_at:
            return True
        sent_at = self.email_confirmation_sent_at
        if getattr(sent_at, 'tzinfo', None) is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        else:
            sent_at = sent_at.astimezone(timezone.utc)
        expiration_time = sent_at + timedelta(hours=24)
        return datetime.now(timezone.utc) > expiration_time


    # ---------- Recuperação de Senha ----------
    def generate_password_reset_token(self) -> str:
        """Gera um token único para recuperação de senha."""
        import secrets
        token = secrets.token_urlsafe(32)
        self.password_reset_token = token
        self.password_reset_sent_at = datetime.now(timezone.utc)
        return token

    def reset_password(self, token: str, new_password: str) -> bool:
        """Redefine a senha se o token for válido e não expirado."""
        if not self.password_reset_token or self.password_reset_token != token:
            return False
        
        # Verificar se o token não expirou (1 hora)
        if self.password_reset_sent_at:
            sent_at = self.password_reset_sent_at
            if getattr(sent_at, 'tzinfo', None) is None:
                sent_at = sent_at.replace(tzinfo=timezone.utc)
            else:
                sent_at = sent_at.astimezone(timezone.utc)
            expiration_time = sent_at + timedelta(hours=1)
            if datetime.now(timezone.utc) > expiration_time:
                return False
        
        # Redefinir senha
        self.set_password(new_password)
        self.password_reset_token = None
        self.password_reset_sent_at = None
        return True

    def is_password_reset_token_expired(self) -> bool:
        """Verifica se o token de recuperação de senha expirou."""
        if not self.password_reset_sent_at:
            return True
        sent_at = self.password_reset_sent_at
        if getattr(sent_at, 'tzinfo', None) is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        else:
            sent_at = sent_at.astimezone(timezone.utc)
        expiration_time = sent_at + timedelta(hours=1)
        return datetime.now(timezone.utc) > expiration_time


    # ---------- Serialização ----------
    def to_dict(self) -> Dict[str, Any]:
        """Serializa o objeto User para um dicionário (uso básico)."""
        # TODO: Usar um Marshmallow Schema (em schemas/user_schema.py) para serialização mais complexa/API
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'address': self.address,
            'bio': self.bio,
            'profile_picture': self.profile_picture,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'email_confirmed': self.email_confirmed,
            # Converter objetos datetime para ISO 8601 strings, lidando com None
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'email_confirmation_sent_at': self.email_confirmation_sent_at.isoformat() if self.email_confirmation_sent_at else None,
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
