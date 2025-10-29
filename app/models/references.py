from sqlalchemy import Column, Integer, Text, ForeignKey, String, Boolean
from app.extensions.db import db

class Reference(db.Model):
    __tablename__ = 'reference'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to Vulnerability
    cve_id = Column(
        String,
        ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # URL of the external reference
    url = Column(Text, nullable=False)

    # Source of the reference (from NIST API)
    source = Column(String(255), nullable=True)

    # Tags from NIST API (comma-separated string)
    tags = Column(Text, nullable=True)

    # Indicates if this reference is patch-related
    is_patch = Column(Boolean, default=False, nullable=False, index=True)

    # Foreign key to ReferenceType
    reference_type_id = Column(
        Integer,
        ForeignKey('reference_type.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Relationships
    vulnerability = db.relationship(
        'Vulnerability', back_populates='references', foreign_keys=[cve_id]
    )
    reference_type = db.relationship(
        'ReferenceType', back_populates='references'
    )

    def __repr__(self):
        return f"<Reference id={self.id} url={self.url}>"
