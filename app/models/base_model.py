# base_model.py

import logging
from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar, List

from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from app.extensions.db import db

logger = logging.getLogger(__name__)
T = TypeVar('T', bound='BaseModel')

class BaseModel(db.Model):
    """
    Modelo base abstrato para SQLAlchemy (Flask-SQLAlchemy).
    Fornece colunas de auditoria e métodos utilitários leves.
    """
    __abstract__ = True
    __allow_unmapped__ = True  # <--- ADICIONE ESTA LINHA AQUI

    id = db.Column(
        db.Integer,
        primary_key=True,
        autoincrement=True,
        doc='Chave primária'
    )
    created_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        nullable=False,
        doc='Data de criação'
    )
    updated_at = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
        doc='Data da última atualização'
    )

    def save(self) -> 'BaseModel':
        """
        Adiciona a instância à sessão, mas não faz commit.
        Retorna self para encadeamento.
        """
        db.session.add(self)
        return self

    def delete(self) -> None:
        """
        Marca a instância para remoção na sessão, mas não comita.
        """
        db.session.delete(self)

    def update(self, **kwargs: Any) -> 'BaseModel':
        """
        Atualiza atributos da instância. Não faz commit.
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"{self.__class__.__name__} sem atributo '{key}'")
        return self

    def to_dict(self, include_relationships: bool = False) -> Dict[str, Any]:
        """
        Converte colunas em dict de forma resiliente a colunas ausentes.
        Relacionamentos só se include_relationships=True.
        """
        data: Dict[str, Any] = {}
        try:
            from sqlalchemy import inspect as sa_inspect
            from app.extensions.db import db as _db
            inspector = sa_inspect(_db.engine)
            existing = { (c.get('name') or '') for c in inspector.get_columns(self.__table__.name) }
        except Exception:
            existing = { c.name for c in self.__table__.columns }

        for col in self.__table__.columns:
            # Se a coluna não existir fisicamente na tabela, retornar None sem tentar carregar
            if col.name not in existing:
                data[col.name] = None
                continue
            try:
                # Evitar carregamento preguiçoso desnecessário: tentar pegar valor já carregado
                if col.name in self.__dict__:
                    v = self.__dict__.get(col.name)
                else:
                    v = getattr(self, col.name)
                data[col.name] = v.isoformat() if isinstance(v, datetime) else v
            except Exception:
                # Em caso de erro ao acessar atributo (coluna ausente/deferred), retornar None
                data[col.name] = None

        if include_relationships:
            for rel in self.__mapper__.relationships:
                val = getattr(self, rel.key)
                if val is None:
                    data[rel.key] = None
                elif isinstance(val, BaseModel):
                    data[rel.key] = val.to_dict(False)
                else:
                    # assume iterable of BaseModel
                    data[rel.key] = [o.to_dict(False) for o in val]
        return data

    @classmethod
    def find_by_id(cls: Type[T], obj_id: Any) -> Optional[T]:
        """
        Retorna instância pelo ID, ou None.
        """
        try:
            return cls.query.get(obj_id)
        except SQLAlchemyError as e:
            logger.error(f"find_by_id error on {cls.__name__}({obj_id}): {e}")
            return None

    @classmethod
    def find_all(cls: Type[T]) -> List[T]:
        """
        Retorna todos registros (lista vazia em erro).
        """
        try:
            return cls.query.all()
        except SQLAlchemyError as e:
            logger.error(f"find_all error on {cls.__name__}: {e}")
            return []

    @classmethod
    def find_by_filter(cls: Type[T], **filters: Any) -> List[T]:
        """
        Retorna lista filtrada por filters (ou lista vazia em erro).
        """
        try:
            return cls.query.filter_by(**filters).all()
        except SQLAlchemyError as e:
            logger.error(f"find_by_filter error on {cls.__name__} with {filters}: {e}")
            return []
