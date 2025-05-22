from sqlalchemy import String, Integer, Column, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserRole(Base):
    __tablename__ = "user_role"

    # Campos
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("user.id"), primary_key=True)
    role_id: Mapped[int] = mapped_column(Integer, ForeignKey("role.id"), primary_key=True)

    # Relações
    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", back_populates="users")


class Role(Base):
    __tablename__ = "role"

    # Campos
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=True)

    # Relações
    users: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")

    def __init__(self, name: str, description: str = None):
        """Inicializa um novo papel com nome e descrição opcional."""
        self.name = self._validate_name(name)
        self.description = description

    def _validate_name(self, name: str) -> str:
        """Valida o nome do papel."""
        if not name or len(name) < 3:
            raise ValueError("O nome do papel deve ter pelo menos 3 caracteres.")
        if not name.isalnum() and "_" not in name:
            raise ValueError("O nome do papel deve conter apenas caracteres alfanuméricos ou '_'.")
        return name

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name})>"