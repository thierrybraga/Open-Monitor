from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from extensions.db import db

class VersionReference(db.Model):
    __tablename__ = 'version_ref'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    cve_id = Column(
        String,
        ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    product_id = Column(
        Integer,
        ForeignKey('product.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Version information
    affected_version = Column(String(100), nullable=False)
    fixed_version = Column(String(100), nullable=True)

    # Relationships
    vulnerability = relationship(
        'Vulnerability', back_populates='version_references', foreign_keys=[cve_id]
    )
    product = relationship(
        'Product', back_populates='version_references'
    )

    def __repr__(self):
        return (
            f"<VersionReference id={self.id} "
            f"cve_id={self.cve_id} "
            f"product_id={self.product_id}>"
        )
