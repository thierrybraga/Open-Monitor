# project/models/user_role.py

from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
# Importar db do pacote extensions
from extensions import db
# Importar modelos relacionados (User e Role) para definições de relacionamento
# from .user import User
# from .role import Role

# Usar db.Model em vez de declarative_base() para consistência com Flask-SQLAlchemy
class UserRole(db.Model):
    __tablename__ = "user_role" # Nome da tabela de associação

    # Usar Column em vez de mapped_column para consistência com User model
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True) # Chave estrangeira para a tabela 'users'
    role_id = Column(Integer, ForeignKey("role.id"), primary_key=True) # Chave estrangeira para a tabela 'role'

    # Relações (opcional para association object, dependendo como você o usa)
    # Estas relações aqui permitem acessar User e Role diretamente do objeto UserRole
    # user: Mapped["User"] = relationship("User", back_populates="roles") # Exemplo se user tiver 'roles'
    # role: Mapped["Role"] = relationship("Role", back_populates="users") # Exemplo se role tiver 'users'

    # Remover __init__ se a inicialização padrão do SQLAlchemy for suficiente
    # def __init__(self, user_id: int, role_id: int):
    #     """Inicializa uma associação entre um usuário e um papel."""
    #     self.user_id = user_id
    #     self.role_id = role_id

    def __repr__(self) -> str:
        return f"<UserRole(user_id={self.user_id}, role_id={self.role_id})>"