# project/models/sync_metadata.py

from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from app.extensions import db

class SyncMetadata(db.Model):
    """
    Metadados de sincronização (ex.: 'last_sync_time').
    Usa PK numérica para suportar relacionamentos ORM.
    """
    __tablename__ = 'sync_metadata'

    id            = Column(Integer, primary_key=True)
    key           = Column(String(100), nullable=False, unique=True)
    value         = Column(String(255), nullable=True)
    status        = Column(String(50), nullable=True, default='pending')
    last_modified = Column(DateTime, nullable=True, default=datetime.utcnow)
    sync_type     = Column(String(20), nullable=True)

    # relacionamento com ApiCallLog
    # api_call_logs = db.relationship(
    #     'ApiCallLog',
    #     back_populates='sync_metadata',
    #     cascade='all, delete-orphan'
    # )

    def __repr__(self):
        return f"<SyncMetadata id={self.id} key={self.key} value={self.value}>"
