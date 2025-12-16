from sqlalchemy import Column, Integer, String, Date, ForeignKey, UniqueConstraint, Index
from app.extensions.db import db

class Product(db.Model):
    __tablename__ = 'product'
    __table_args__ = (
        UniqueConstraint('vendor_id', 'name', name='uq_product_vendor_name'),
        Index('ix_product_type', 'type'),
    )

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
    # Optional type/category for taxonomy (e.g., "Switch", "Firewall", "OS")
    type = Column(String(100), nullable=True)

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
    asset_products = db.relationship(
        'AssetProduct', back_populates='product',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<Product id={self.id} name={self.name}>"
