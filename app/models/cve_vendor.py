# E:\Open-Monitor\models\cve_vendor.py

from sqlalchemy import Column, String, Integer, ForeignKey, PrimaryKeyConstraint, Index, DateTime
from sqlalchemy.orm import relationship
from app.extensions import db
from app.models.vulnerability import Vulnerability
from typing import TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from app.models.vendor import Vendor

class CVEVendor(db.Model):
    """
    Modelo de associação para a relação Muitos-para-Muitos entre Vulnerability e Vendor.
    Representa que uma Vulnerability está associada a um Vendor específico.
    """
    __tablename__ = 'cve_vendors'
    __allow_unmapped__ = True

    cve_id: str = Column(String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
                         nullable=False, index=True,
                         doc="Chave estrangeira para o CVE ID em vulnerabilities.")
    vendor_id: int = Column(Integer, ForeignKey('vendor.id', ondelete='CASCADE'),
                            nullable=False, index=True,
                            doc="Chave estrangeira para o ID do fornecedor em vendor.")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint('cve_id', 'vendor_id', name='pk_cve_vendor'),
        Index('ix_cve_vendors_vendor_cve', 'vendor_id', 'cve_id'),
    )

    vulnerability: Vulnerability = relationship(
        'Vulnerability', back_populates='vendors',
        doc="Relacionamento de volta para a Vulnerabilidade associada."
    )

    vendor: 'Vendor' = relationship( # Ajustado type hint para 'Vendor' se Vendor não estiver importado diretamente
        'Vendor', back_populates='cve_vendors',
        doc="Relacionamento de volta para o Fornecedor associado."
    )

    def __repr__(self) -> str:
        """Representação string do objeto CVEVendor para depuração."""
        return f"<CVEVendor cve_id={self.cve_id} vendor_id={self.vendor_id}>"
