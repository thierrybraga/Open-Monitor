# E:\Open-Monitor\models\cve_vendor.py

from sqlalchemy import Column, String, Integer, ForeignKey, PrimaryKeyConstraint, Index
from sqlalchemy.orm import relationship
from ..extensions import db # <-- CORRIGIDO: Importação relativa para db
from .base_model import BaseModel
from .vulnerability import Vulnerability # <-- Adicionado: Importa a classe Vulnerability
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .vendor import Vendor # Esta importação deve ser aqui para type hinting

class CVEVendor(BaseModel, db.Model):
    """
    Modelo de associação para a relação Muitos-para-Muitos entre Vulnerability e Vendor.
    Representa que uma Vulnerability está associada a um Vendor específico.
    """
    __tablename__ = 'cve_vendors'

    cve_id: str = Column(String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
                         nullable=False, index=True,
                         doc="Chave estrangeira para o CVE ID em vulnerabilities.")
    vendor_id: int = Column(Integer, ForeignKey('vendor.id', ondelete='CASCADE'),
                            nullable=False, index=True,
                            doc="Chave estrangeira para o ID do fornecedor em vendor.")

    __table_args__ = (
        PrimaryKeyConstraint('cve_id', 'vendor_id', name='pk_cve_vendor'),
    )

    vulnerability: Vulnerability = relationship( # Removido as aspas para usar o type hint direto
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