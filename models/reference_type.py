from sqlalchemy import Column, Integer, String
from extensions.db import db

class ReferenceType(db.Model):
    __tablename__ = 'reference_type'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Name of the reference type (e.g., 'NVD', 'ExploitDB')
    name = Column(String(100), unique=True, nullable=False)

    # Relationships
    references = db.relationship(
        'Reference', back_populates='reference_type',
        cascade='all, delete-orphan'
    )

    def __repr__(self):
        return f"<ReferenceType id={self.id} name={self.name}>"