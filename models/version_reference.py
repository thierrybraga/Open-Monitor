from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from ..extensions.db import db

class VersionReference(db.Model):
    __tablename__ = 'version_ref'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    vulnerability_id = Column(
        Integer,
        ForeignKey('vulnerabilities.id', ondelete='CASCADE'),
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
        'Vulnerability', back_populates='version_references'
    )
    product = relationship(
        'Product', back_populates='version_references'
    )

    def __repr__(self):
        return (
            f"<VersionReference id={self.id} "
            f"vuln_id={self.vulnerability_id} "
            f"product_id={self.product_id}>"
        )
