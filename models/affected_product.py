# affected_product.py
from sqlalchemy import Column, String, Integer, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from extensions.db import db

class AffectedProduct(db.Model):
    __tablename__ = 'affected_products'

    vulnerability_id = Column(String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'), nullable=False)
    product_id = Column(Integer, ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    affected_versions = Column(String, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint('vulnerability_id', 'product_id', name='pk_affected_product'),
    )

    vulnerability = relationship('Vulnerability', back_populates='affected_products')
    product = relationship('Product', back_populates='affected_products')

