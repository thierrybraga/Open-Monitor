# models/chat_session.py

from datetime import datetime
from typing import TYPE_CHECKING, List
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.extensions import db
from app.models.base_model import BaseModel

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.chat_message import ChatMessage


class ChatSession(BaseModel):
    """
    Modelo para sessões de chat.
    
    Representa uma sessão de conversa entre um usuário e o sistema de chat.
    Cada sessão pode conter múltiplas mensagens.
    """
    
    __tablename__ = 'chat_sessions'
    
    # Campos principais
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Nova Conversa")
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    
    # Relacionamento com usuário
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey('users.id'), nullable=False, index=True)
    
    # Status da sessão
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Metadados da sessão
    context_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string para contexto
    last_activity: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Colunas de auditoria (explícitas para garantir que sejam reconhecidas)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relacionamentos
    user: Mapped["User"] = relationship("User", back_populates="chat_sessions")
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", 
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at"
    )
    
    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title='{self.title}', user_id={self.user_id})>"
    
    def to_dict(self) -> dict:
        """Converte a sessão para dicionário."""
        # Obter prévia da última mensagem
        preview = "Sem mensagens ainda"
        if self.messages:
            last_message = self.messages[-1]
            if last_message.content:
                preview = last_message.content[:100] + "..." if len(last_message.content) > 100 else last_message.content
        
        return {
            'id': self.id,
            'title': self.title,
            'session_token': self.session_token,
            'user_id': self.user_id,
            'is_active': self.is_active,
            'is_archived': self.is_archived,
            'context_data': self.context_data,
            'last_activity': self.last_activity.isoformat() if self.last_activity else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'message_count': len(self.messages) if self.messages else 0,
            'preview': preview
        }
    
    def update_activity(self):
        """Atualiza o timestamp da última atividade."""
        self.last_activity = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def deactivate(self):
        """Desativa a sessão."""
        self.is_active = False
        self.updated_at = datetime.utcnow()
    
    def archive(self):
        """Arquiva a sessão."""
        self.is_archived = True
        self.updated_at = datetime.utcnow()
    
    def unarchive(self):
        """Desarquiva a sessão."""
        self.is_archived = False
        self.updated_at = datetime.utcnow()