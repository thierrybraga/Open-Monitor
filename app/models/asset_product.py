from sqlalchemy import Column, Integer, String, ForeignKey, PrimaryKeyConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions.db import db


class AssetProduct(db.Model):
    __tablename__ = 'asset_products'

    # Composite primary key: one product link per asset (can be extended to multiple later)
    asset_id = Column(Integer, ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey('product.id', ondelete='CASCADE'), nullable=False, index=True)

    # Optional metadata to improve correlation precision
    model_name = Column(String(255), nullable=True)
    operating_system = Column(String(255), nullable=True)
    installed_version = Column(String(100), nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('asset_id', 'product_id', name='pk_asset_product'),
        Index('ix_asset_products_asset_product', 'asset_id', 'product_id'),
        Index('ix_asset_products_model_name', 'model_name'),
        Index('ix_asset_products_operating_system', 'operating_system'),
        Index('ix_asset_products_installed_version', 'installed_version'),
    )

    # Relationships
    asset = relationship('Asset', backref='asset_products')
    product = relationship('Product', back_populates='asset_products')

    def __repr__(self):
        return (
            f"<AssetProduct asset_id={self.asset_id} product_id={self.product_id} "
            f"model_name={self.model_name} os={self.operating_system} version={self.installed_version}>"
        )