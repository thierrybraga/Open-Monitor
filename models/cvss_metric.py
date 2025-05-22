# cvss_metric.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from ..extensions.db import db

class CVSSMetric(db.Model):
    __tablename__ = 'cvss_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    vulnerability_id = Column(
        Integer, ForeignKey('vulnerabilities.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    cvss_version = Column(String(10), nullable=False)
    base_score = Column(Float, nullable=False)
    base_severity = Column(String(10), nullable=False)
    exploitability_score = Column(Float, nullable=True)
    impact_score = Column(Float, nullable=True)
    vector = Column(String(255), nullable=False)

    attack_vector = Column(String(50), nullable=True)
    attack_complexity = Column(String(50), nullable=True)
    privileges_required = Column(String(50), nullable=True)
    confidentiality_impact = Column(String(50), nullable=True)
    integrity_impact = Column(String(50), nullable=True)
    availability_impact = Column(String(50), nullable=True)

    vulnerability = relationship(
        'Vulnerability', back_populates='metrics', lazy='select'
    )

    def __repr__(self):
        return (f"<CVSSMetric id={self.id} version={self.cvss_version} score={self.base_score}>")