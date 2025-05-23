from sqlalchemy import Column, Integer, Text, ForeignKey
from ..extensions.db import db

class Reference(db.Model):
    __tablename__ = 'reference'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to Vulnerability
    vulnerability_id = Column(
        Integer,
        ForeignKey('vulnerabilities.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # URL of the external reference
    url = Column(Text, nullable=False)

    # Foreign key to ReferenceType
    reference_type_id = Column(
        Integer,
        ForeignKey('reference_type.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Relationships
    vulnerability = db.relationship(
        'Vulnerability', back_populates='references'
    )
    reference_type = db.relationship(
        'ReferenceType', back_populates='references'
    )

    def __repr__(self):
        return f"<Reference id={self.id} url={self.url}>"
