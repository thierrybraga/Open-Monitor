from datetime import datetime
from app.extensions import db
from app.models.base_model import BaseModel

class MonitoringRule(BaseModel):
    """
    Representa uma regra de monitoramento configurada por um usuário.
    """
    __tablename__ = 'monitoring_rules'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    rule_type = db.Column(db.String(50), nullable=False)
    conditions = db.Column(db.JSON)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relacionamentos
    user = db.relationship('User', back_populates='monitoring_rules')

    def __repr__(self):
        return f'<MonitoringRule {self.name}>'
