# asset.py
# Refatorado para definir o modelo SQLAlchemy de Asset com campos, relacionamentos e mixins

from datetime import datetime
from ..extensions.db import db
from .base_model import BaseModel

class Asset(BaseModel):
    """
    Representa um ativo monitorado (servidor, IP, serviço, etc.).
    """
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='unknown')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relacionamento com AssetVulnerability
    vulnerabilities = db.relationship(
        'AssetVulnerability',
        back_populates='asset',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Asset id={self.id} name={self.name} ip={self.ip_address} status={self.status}>"
