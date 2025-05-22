# E:\Open-Monitor\models\severity_metric.py

# Suas importações existentes
from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from ..extensions import db
from .base_model import BaseModel
from .vulnerability import Vulnerability # <-- Adicionado: Importa a classe Vulnerability
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Se SeverityMetric precisar fazer type hinting para Vulnerability
    pass # A importação acima já é suficiente para o runtime

class SeverityMetric(BaseModel, db.Model):
    """
    Modelo para armazenar métricas de severidade de vulnerabilidades,
    como CVSS base, temporal, ambiental e seus vetores.
    """
    __tablename__ = 'severity_metrics'

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    cve_id: str = Column(String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
                         nullable=False, unique=True, index=True,
                         doc="Chave estrangeira para o CVE ID em vulnerabilities.")

    # CVSS v3.x Base Metrics
    cvss_version: str = Column(String(10), nullable=False, doc="Versão do CVSS (ex: '3.1').")
    base_score: float = Column(Float, nullable=False, doc="CVSS Base Score.")
    base_vector: str = Column(String(255), nullable=False, doc="CVSS Base Vector String.")

    # CVSS v3.x Temporal Metrics (opcionais)
    temporal_score: float = Column(Float, nullable=True, doc="CVSS Temporal Score (opcional).")
    temporal_vector: str = Column(String(255), nullable=True, doc="CVSS Temporal Vector String (opcional).")

    # CVSS v3.x Environmental Metrics (opcionais)
    environmental_score: float = Column(Float, nullable=True, doc="CVSS Environmental Score (opcional).")
    environmental_vector: str = Column(String(255), nullable=True, doc="CVSS Environmental Vector String (opcional).")

    # Relacionamento de volta para a Vulnerabilidade (um-para-um)
    # uselist=False indica um relacionamento um-para-um
    vulnerability: Vulnerability = relationship(
        'Vulnerability',
        back_populates='severity_metrics', # Deve ser o nome do atributo no modelo Vulnerability
        uselist=False, # Indica um relacionamento um-para-um
        doc="Relacionamento para a Vulnerabilidade associada (um-para-um)."
    )

    def __repr__(self) -> str:
        """Representação string do objeto SeverityMetric para depuração."""
        return f"<SeverityMetric cve_id={self.cve_id} score={self.base_score}>"

    # Outros métodos como to_dict() podem ser adicionados se não forem herdados de BaseModel
    # Exemplo:
    # def to_dict(self) -> Dict[str, Any]:
    #     return {
    #         'id': self.id,
    #         'cve_id': self.cve_id,
    #         'cvss_version': self.cvss_version,
    #         'base_score': self.base_score,
    #         'base_vector': self.base_vector,
    #         'temporal_score': self.temporal_score,
    #         'temporal_vector': self.temporal_vector,
    #         'environmental_score': self.environmental_score,
    #         'environmental_vector': self.environmental_vector,
    #         'created_at': self.created_at.isoformat() if self.created_at else None,
    #         'updated_at': self.updated_at.isoformat() if self.updated_at else None,
    #     }