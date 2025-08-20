from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from extensions.db import db
from datetime import datetime

class Report(db.Model):
    __tablename__ = 'reports'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign key to User
    user_id = Column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Report data
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    pdf_path = Column(String(512), nullable=True)

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship back to User
    user = relationship(
        'User', back_populates='reports'
    )

    def __repr__(self):
        return f"<Report id={self.id} title={self.title}>"
