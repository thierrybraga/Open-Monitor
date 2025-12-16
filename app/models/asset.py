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
    __table_args__ = (
        # Garante unicidade por proprietário + IP, permitindo mesmo IP em donos diferentes
        db.UniqueConstraint('owner_id', 'ip_address', name='uq_assets_owner_ip'),
    )

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    ip_address = db.Column(db.String(45), nullable=False, index=True)
    status = db.Column(db.String(50), nullable=False, default='active')
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey('vendor.id'), nullable=True, index=True)
    # Asset type/category for UI and reporting (e.g., "Servidor", "Switch", "Firewall")
    asset_type = db.Column(db.String(100), nullable=True, index=True)
    # Catalog tag to represent type/category for taxonomy (e.g., 'Switch', 'Firewall')
    catalog_tag = db.Column(db.String(100), nullable=True, index=True)
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
        # Include asset type for UI
        try:
            data['asset_type'] = self.asset_type
        except Exception:
            # If the column doesn't exist or lazy-load fails, fallback safely
            data['asset_type'] = None
        # Include linked products (AssetProduct) only if table exists (DB-agnostic)
        try:
            from sqlalchemy import inspect as sa_inspect
            from app.extensions import db as _db
            insp = sa_inspect(_db.engine)
            has_asset_products_table = ('asset_products' in insp.get_table_names())
            asset_products_list = []
            if has_asset_products_table:
                for ap in getattr(self, 'asset_products', []) or []:
                    prod = getattr(ap, 'product', None)
                    asset_products_list.append({
                        'product_id': ap.product_id,
                        'product_name': getattr(prod, 'name', None),
                        'vendor_id': getattr(prod, 'vendor_id', None),
                        'model_name': ap.model_name,
                        'operating_system': ap.operating_system,
                        'installed_version': ap.installed_version,
                    })
            data['asset_products'] = asset_products_list
        except Exception:
            data['asset_products'] = []
        return data
