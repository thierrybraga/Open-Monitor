# cvss_metric.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship, validates
from app.extensions import db
from app.models.base_model import BaseModel
import logging

logger = logging.getLogger(__name__)

class CVSSMetric(BaseModel, db.Model):
    """
    Modelo unificado para armazenar métricas CVSS de todas as versões (v2, v3.0, v3.1, v4.0).
    Substitui tanto CVSSMetric quanto SeverityMetric para evitar duplicação.
    """
    __tablename__ = 'cvss_metrics'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cve_id = Column(
        String, ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )

    # Informações da versão CVSS
    cvss_version = Column(String(10), nullable=False, doc="Versão do CVSS (ex: '2.0', '3.0', '3.1', '4.0')")
    is_primary = Column(Boolean, default=True, nullable=False, doc="Indica se esta é a métrica principal para o CVE")
    
    # Métricas Base (presentes em todas as versões)
    base_score = Column(Float, nullable=False, doc="CVSS Base Score")
    base_severity = Column(String(10), nullable=False, doc="Severidade base (LOW, MEDIUM, HIGH, CRITICAL)")
    base_vector = Column(String(500), nullable=False, doc="CVSS Base Vector String")
    
    # Métricas de Exploitabilidade e Impacto
    exploitability_score = Column(Float, nullable=True, doc="Score de exploitabilidade")
    impact_score = Column(Float, nullable=True, doc="Score de impacto")
    
    # Métricas Temporais (opcionais)
    temporal_score = Column(Float, nullable=True, doc="CVSS Temporal Score")
    temporal_vector = Column(String(255), nullable=True, doc="CVSS Temporal Vector String")
    
    # Métricas Ambientais (opcionais)
    environmental_score = Column(Float, nullable=True, doc="CVSS Environmental Score")
    environmental_vector = Column(String(255), nullable=True, doc="CVSS Environmental Vector String")
    
    # Componentes específicos do CVSS v3.x/v4.x
    attack_vector = Column(String(50), nullable=True, doc="Vetor de ataque (NETWORK, ADJACENT, LOCAL, PHYSICAL)")
    attack_complexity = Column(String(50), nullable=True, doc="Complexidade do ataque (LOW, HIGH)")
    privileges_required = Column(String(50), nullable=True, doc="Privilégios necessários (NONE, LOW, HIGH)")
    user_interaction = Column(String(50), nullable=True, doc="Interação do usuário (NONE, REQUIRED)")
    scope = Column(String(50), nullable=True, doc="Escopo (UNCHANGED, CHANGED)")
    confidentiality_impact = Column(String(50), nullable=True, doc="Impacto na confidencialidade")
    integrity_impact = Column(String(50), nullable=True, doc="Impacto na integridade")
    availability_impact = Column(String(50), nullable=True, doc="Impacto na disponibilidade")
    
    # Componentes específicos do CVSS v2.x
    access_vector = Column(String(50), nullable=True, doc="Vetor de acesso CVSS v2 (LOCAL, ADJACENT_NETWORK, NETWORK)")
    access_complexity = Column(String(50), nullable=True, doc="Complexidade de acesso CVSS v2 (HIGH, MEDIUM, LOW)")
    authentication = Column(String(50), nullable=True, doc="Autenticação CVSS v2 (MULTIPLE, SINGLE, NONE)")

    # Relacionamento
    vulnerability = relationship(
        'Vulnerability', back_populates='metrics', lazy='select', foreign_keys=[cve_id]
    )

    @validates('cvss_version')
    def validate_cvss_version(self, key: str, value: str) -> str:
        """Valida se a versão CVSS é suportada."""
        valid_versions = ['2.0', '3.0', '3.1', '4.0']
        if value not in valid_versions:
            raise ValueError(f"Versão CVSS inválida: {value}. Versões suportadas: {valid_versions}")
        return value

    @validates('base_score', 'temporal_score', 'environmental_score', 'exploitability_score', 'impact_score')
    def validate_scores(self, key: str, value: float) -> float:
        """Valida se os scores estão no range válido."""
        if value is not None and not 0.0 <= value <= 10.0:
            raise ValueError(f"{key} deve estar entre 0.0 e 10.0")
        return value

    @validates('base_severity')
    def validate_base_severity(self, key: str, value: str) -> str:
        """Valida se a severidade é válida."""
        valid_severities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'NONE', 'N/A']
        if value.upper() not in valid_severities:
            raise ValueError(f"Severidade inválida: {value}. Severidades válidas: {valid_severities}")
        return value.upper()

    def get_primary_score(self) -> float:
        """Retorna o score principal (temporal se disponível, senão ambiental, senão base)."""
        if self.environmental_score is not None:
            return self.environmental_score
        elif self.temporal_score is not None:
            return self.temporal_score
        else:
            return self.base_score

    def to_dict(self) -> dict:
        """Serializa a métrica CVSS para dicionário."""
        return {
            'id': self.id,
            'cve_id': self.cve_id,
            'cvss_version': self.cvss_version,
            'is_primary': self.is_primary,
            'base_score': self.base_score,
            'base_severity': self.base_severity,
            'base_vector': self.base_vector,
            'exploitability_score': self.exploitability_score,
            'impact_score': self.impact_score,
            'temporal_score': self.temporal_score,
            'temporal_vector': self.temporal_vector,
            'environmental_score': self.environmental_score,
            'environmental_vector': self.environmental_vector,
            'attack_vector': self.attack_vector,
            'attack_complexity': self.attack_complexity,
            'privileges_required': self.privileges_required,
            'user_interaction': self.user_interaction,
            'scope': self.scope,
            'confidentiality_impact': self.confidentiality_impact,
            'integrity_impact': self.integrity_impact,
            'availability_impact': self.availability_impact,
            'access_vector': self.access_vector,
            'access_complexity': self.access_complexity,
            'authentication': self.authentication,
            'primary_score': self.get_primary_score(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return (f"<CVSSMetric id={self.id} cve={self.cve_id} version={self.cvss_version} "
                f"score={self.base_score} primary={self.is_primary}>")
