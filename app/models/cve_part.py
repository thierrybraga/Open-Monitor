from sqlalchemy import Column, String, PrimaryKeyConstraint, Index
from app.extensions import db


class CVEPart(db.Model):
    """
    Associação simples entre CVE e o "part" da CPE (a, o, h).
    Permite filtrar rapidamente CVEs por tipo de catálogo sem varrer JSON.
    """
    __tablename__ = 'cve_parts'
    __allow_unmapped__ = True

    cve_id = Column(String, nullable=False, index=True)
    part = Column(String(1), nullable=False, index=True, doc="CPE part: 'a' (software), 'o' (os), 'h' (hardware)")

    __table_args__ = (
        PrimaryKeyConstraint('cve_id', 'part', name='pk_cve_part'),
        Index('ix_cve_parts_part_cve', 'part', 'cve_id'),
    )

    def __repr__(self) -> str:
        return f"<CVEPart cve_id={self.cve_id} part={self.part}>"