from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, String
from sqlalchemy.orm import relationship
from app.extensions import db
from datetime import datetime, timezone

class RiskAssessment(db.Model):
    __tablename__ = 'risk_assessment'
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'vulnerability_id', name='uq_risk_asset_vuln'),
    )

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign keys
    asset_id = Column(
        Integer,
        ForeignKey('assets.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    vulnerability_id = Column(
        String,
        ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    # recommendation_id = Column(
    #     Integer,
    #     ForeignKey('recommendation.id', ondelete='SET NULL'),
    #     nullable=True,
    #     index=True
    # )
    created_by = Column(
        Integer,
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True
    )

    # Assessment data
    risk_score = Column(Float, nullable=False)

    # Timestamp
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    # Relationships
    asset = relationship(
        'Asset', back_populates='risk_assessments'
    )
    vulnerability = relationship(
        'Vulnerability', back_populates='risk_assessments'
    )
    # recommendation = relationship(
    #     'Recommendation', back_populates='risk_assessments'
    # )
    user = relationship(
        'User', back_populates='risk_assessments'
    )

    def __repr__(self):
        return (
            f"<RiskAssessment id={self.id} asset={self.asset_id} vuln={self.vulnerability_id} score={self.risk_score}>"
        )
