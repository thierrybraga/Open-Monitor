# asset.py
# Refatorado para definir o modelo SQLAlchemy de Asset com campos, relacionamentos e mixins

from datetime import datetime
from app.extensions import db
from app.models.base_model import BaseModel

class Asset(BaseModel):
    """
    Representa um ativo monitorado (servidor, IP, serviço, etc.).
    """
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), unique=True, nullable=False)
    status = db.Column(db.String(50), nullable=False, default='active')
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=True)
    # BIA-related fields collected at registration
    rto_hours = db.Column(db.Integer, nullable=True)
    rpo_hours = db.Column(db.Integer, nullable=True)
    uptime_text = db.Column(db.String(100), nullable=True)
    operational_cost_per_hour = db.Column(db.Float, nullable=True)
    # created_at/updated_at são fornecidos por BaseModel

    # Relacionamento com AssetVulnerability
# Relacionamentos
    owner = db.relationship('User', back_populates='assets')
    vulnerabilities = db.relationship(
        'AssetVulnerability',
        back_populates='asset',
        cascade='all, delete-orphan'
    )
    risk_assessments = db.relationship(
        'RiskAssessment',
        back_populates='asset',
        cascade='all, delete-orphan'
    )
    # Vendor relationship
    vendor = db.relationship('Vendor', backref='assets')

    def __repr__(self):
        return f"<Asset id={self.id} name={self.name} ip={self.ip_address} status={self.status}>"

    def to_dict(self):
        data = super().to_dict(False)
        # Include vendor info
        data['vendor_id'] = self.vendor_id
        if self.vendor:
            data['vendor'] = {'id': self.vendor.id, 'name': self.vendor.name}
            data['vendor_name'] = self.vendor.name
        else:
            data['vendor'] = None
            data['vendor_name'] = None
        # Include BIA-related fields
        data['rto_hours'] = self.rto_hours
        data['rpo_hours'] = self.rpo_hours
        data['uptime_text'] = self.uptime_text
        data['operational_cost_per_hour'] = self.operational_cost_per_hour
        return data
