from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from ..extensions.db import db
from datetime import datetime

class RiskAssessment(db.Model):
    __tablename__ = 'risk_assessment'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    asset_id = Column(
        Integer,
        ForeignKey('asset.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    vulnerability_id = Column(
        Integer,
        ForeignKey('vulnerabilities.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    recommendation_id = Column(
        Integer,
        ForeignKey('recommendation.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )
    created_by = Column(
        Integer,
        ForeignKey('user.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Assessment data
    risk_score = Column(Float, nullable=False)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    asset = relationship(
        'Asset', back_populates='risk_assessments'
    )
    vulnerability = relationship(
        'Vulnerability', back_populates='risk_assessments'
    )
    recommendation = relationship(
        'Recommendation', back_populates='risk_assessments'
    )
    user = relationship(
        'User', back_populates='risk_assessments'
    )

    def __repr__(self):
        return (
            f"<RiskAssessment id={self.id} asset={self.asset_id} vuln={self.vulnerability_id} score={self.risk_score}>"
        )
