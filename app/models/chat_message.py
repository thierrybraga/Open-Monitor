# models/chat_message.py

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Enum
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.extensions import db
from app.models.base_model import BaseModel
import enum

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat_session import ChatSession


class MessageType(enum.Enum):
    """Tipos de mensagem no chat."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ERROR = "error"


class ChatMessage(BaseModel):
    """
    Modelo para mensagens de chat.
    
    Representa uma mensagem individual dentro de uma sessão de chat.
    Pode ser do usuário, assistente, sistema ou erro.
    """
    
    __tablename__ = 'chat_messages'
    
    # Campos principais
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessageType] = mapped_column(Enum(MessageType), nullable=False)
    
    # Relacionamentos
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey('chat_sessions.id'), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Metadados da mensagem
    token_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    processing_time: Mapped[Optional[float]] = mapped_column(nullable=True)  # em segundos
    
    # Status da mensagem
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Dados adicionais (JSON string)
    message_metadata: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Colunas de auditoria (explícitas para garantir que sejam reconhecidas)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    session: Mapped["ChatSession"] = relationship("ChatSession", back_populates="messages")
    user: Mapped["User"] = relationship("User", back_populates="chat_messages")
    
    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(id={self.id}, type={self.message_type.value}, content='{content_preview}')>"
    
    def to_dict(self) -> dict:
        """Converte a mensagem para dicionário."""
        return {
            'id': self.id,
            'content': self.content,
            'message_type': self.message_type.value,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'token_count': self.token_count,
            'processing_time': self.processing_time,
            'is_edited': self.is_edited,
            'is_deleted': self.is_deleted,
            'metadata': self.message_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def mark_as_edited(self):
        """Marca a mensagem como editada."""
        self.is_edited = True
        self.updated_at = datetime.utcnow()
    
    def soft_delete(self):
        """Marca a mensagem como deletada (soft delete)."""
        self.is_deleted = True
        self.updated_at = datetime.utcnow()
    
    def restore(self):
        """Restaura uma mensagem deletada."""
        self.is_deleted = False
        self.updated_at = datetime.utcnow()