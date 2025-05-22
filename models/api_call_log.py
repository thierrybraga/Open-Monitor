# project/models/api_call_log.py

# Importação relativa para as extensões dentro do seu pacote project
# Sobe 2 níveis (de models para project) e desce para extensions.extensions
from ..extensions.db import db
from datetime import datetime
# Assume que o modelo SyncMetadata existe em project/models/sync_metadata.py
# from .sync_metadata import SyncMetadata # Você pode precisar desta importação aqui se for usar SyncMetadata diretamente no modelo

class ApiCallLog(db.Model):
    """Modelo para registrar chamadas à API."""
    __tablename__ = 'api_call_logs'

    id            = db.Column(db.Integer, primary_key=True)
    endpoint      = db.Column(db.String(255), nullable=False)
    status_code   = db.Column(db.Integer, nullable=False)
    response_time = db.Column(db.Float, nullable=False)
    timestamp     = db.Column(db.DateTime, default=datetime.utcnow)
    # Garante que a FK referencia a tabela correta, mesmo se o modelo SyncMetadata não for importado aqui
    sync_id       = db.Column(db.Integer, db.ForeignKey('sync_metadata.id'))
    # Define o relacionamento com SyncMetadata (SyncMetadata precisa ser importado onde o relacionamento é usado,
    # por exemplo, em um arquivo de schemas ou no próprio SyncMetadata se a FK for definida lá com backref)
    # sync_metadata = db.relationship('SyncMetadata', back_populates='api_call_logs') # Esta linha pode precisar do modelo SyncMetadata importado

    def __repr__(self):
        return f"<ApiCallLog(endpoint='{self.endpoint}', status_code={self.status_code})>"