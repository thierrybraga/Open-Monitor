from sqlalchemy import Column, Integer, String, Date, ForeignKey
from extensions.db import db

class Product(db.Model):
    __tablename__ = 'product'

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Key to Vendor
    vendor_id = Column(
        Integer,
        ForeignKey('vendor.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Product details
    name = Column(String(255), nullable=False)

    # Relationships
    vendor = db.relationship(
        'Vendor',
        back_populates='products'
    )
    cve_products = db.relationship(
        'CVEProduct', back_populates='product',
        cascade='all, delete-orphan'
    )
    version_references = db.relationship(
        'VersionReference', back_populates='product',
        cascade='all, delete-orphan'
    )
    affected_products = db.relationship(
        'AffectedProduct', back_populates='product',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Product id={self.id} name={self.name} version={self.version}>"
