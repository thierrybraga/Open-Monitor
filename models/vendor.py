from sqlalchemy import Column, Integer, String
from ..extensions.db import db

class Vendor(db.Model):
    __tablename__ = 'vendor'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Vendor details
    name = Column(String(255), unique=True, nullable=False)
    website = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)

    # Relationships
    cve_vendors = db.relationship(
        'CVEVendor', back_populates='vendor',
        cascade='all, delete-orphan'
    )
    products = db.relationship(
        'Product', back_populates='vendor',
        cascade='all, delete-orphan'
    )
    monitoring_rules = db.relationship(
        'MonitoringRule', back_populates='vendor',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Vendor id={self.id} name={self.name}>"
