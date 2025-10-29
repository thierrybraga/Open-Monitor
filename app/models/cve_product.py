# E:\Open-Monitor\models\cve_product.py

from sqlalchemy import Column, String, Integer, ForeignKey, PrimaryKeyConstraint, Index
from sqlalchemy.orm import relationship
from app.extensions import db
from app.models.vulnerability import Vulnerability # <-- Adicionado: Importa a classe Vulnerability
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.product import Product


class CVEProduct(db.Model):
    """
    Modelo de associação para a relação Muitos-para-Muitos entre Vulnerability e Product.
    Representa que uma Vulnerability afeta um Product específico.
    """
    __tablename__ = 'cve_products'
    __allow_unmapped__ = True

    cve_id: str = Column(String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
                         nullable=False, index=True,
                         doc="Chave estrangeira para o CVE ID em vulnerabilities.")
    product_id: int = Column(Integer, ForeignKey('product.id', ondelete='CASCADE'),
                            nullable=False, index=True,
                            doc="Chave estrangeira para o ID do produto em product.")

    __table_args__ = (
        PrimaryKeyConstraint('cve_id', 'product_id', name='pk_cve_product'),
    )

    vulnerability: Vulnerability = relationship(
        'Vulnerability', back_populates='products',
        doc="Relacionamento de volta para a Vulnerabilidade associada."
    )

    product: 'Product' = relationship( # Ajustado type hint para 'Product' se Product não estiver importado diretamente
        'Product', back_populates='cve_products',
        doc="Relacionamento de volta para o Produto associado."
    )

    def __repr__(self) -> str:
        """Representação string do objeto CVEProduct para depuração."""
        return f"<CVEProduct cve_id={self.cve_id} product_id={self.product_id}>"
