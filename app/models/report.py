# models/report.py

"""
Modelo para relatórios de cybersegurança.
Suporta diferentes tipos de relatórios com configurações flexíveis.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base_model import BaseModel
from app.models.user import User
import enum


class ReportType(enum.Enum):
    """Tipos de relatórios disponíveis."""
    EXECUTIVE = "executivo"
    TECHNICAL = "tecnico"
    TECHNICAL_STUDY = "estudo_tecnico"  # Estudo Técnico
    PENTEST = "pentest"
    BIA = "bia"  # Business Impact Analysis
    KPI_KRI = "kpi_kri"


class ReportScope(enum.Enum):
    """Escopo do relatório."""
    ALL_ASSETS = "todos_ativos"
    BY_TAGS = "por_tags"
    BY_GROUPS = "por_grupos"
    CUSTOM = "customizado"


class DetailLevel(enum.Enum):
    """Nível de detalhe do relatório."""
    SUMMARY = "resumido"
    COMPLETE = "completo"


class ReportStatus(enum.Enum):
    """Status do relatório."""
    PENDING = "pendente"
    GENERATING = "gerando"
    COMPLETED = "concluido"
    FAILED = "falhou"
    EXPORTED = "exportado"


class ImpactLevel(enum.Enum):
    """Nível de impacto."""
    LOW = "baixo"
    MEDIUM = "medio"
    HIGH = "alto"
    CRITICAL = "critico"


class UrgencyLevel(enum.Enum):
    """Nível de urgência."""
    LOW = "baixo"
    MEDIUM = "medio"
    HIGH = "alto"
    URGENT = "urgente"


class MaturityLevel(enum.Enum):
    """Nível de maturidade."""
    LEVEL_1 = "nivel_1"
    LEVEL_2 = "nivel_2"
    LEVEL_3 = "nivel_3"
    LEVEL_4 = "nivel_4"
    LEVEL_5 = "nivel_5"


class Report(BaseModel):
    """
    Modelo para relatórios de cybersegurança.
    
    Attributes:
        title: Título do relatório
        description: Descrição detalhada
        report_type: Tipo do relatório (executivo, técnico, etc.)
        scope: Escopo do relatório (todos ativos, tags, grupos)
        detail_level: Nível de detalhe (resumido, completo)
        period_start: Data de início do período analisado
        period_end: Data de fim do período analisado
        scope_config: Configuração específica do escopo (JSON)
        status: Status atual do relatório
        generated_at: Data/hora de geração
        generated_by_id: ID do usuário que gerou
        content: Conteúdo do relatório (JSON)
        charts_data: Dados dos gráficos (JSON)
        ai_analysis: Análise gerada pela IA (JSON)
        executive_summary: Resumo executivo
        recommendations: Recomendações
        impact_level: Nível de impacto
        urgency_level: Nível de urgência
        completeness_score: Score de completude (0-100)
        maturity_level: Nível de maturidade
        tags: Tags do relatório
        file_path: Caminho do arquivo exportado
        file_size: Tamanho do arquivo em bytes
        export_format: Formato de exportação
        report_metadata: Metadados adicionais (JSON)
    """
    
    __tablename__ = 'reports'
    __table_args__ = {'extend_existing': True}
    
    # Campos básicos
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Configuração do relatório
    report_type: Mapped[ReportType] = mapped_column(SQLEnum(ReportType), nullable=False)
    scope: Mapped[ReportScope] = mapped_column(SQLEnum(ReportScope), nullable=False)
    detail_level: Mapped[DetailLevel] = mapped_column(SQLEnum(DetailLevel), nullable=False)
    
    # Período analisado
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    
    # Configuração específica do escopo
    scope_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # Status e geração
    status: Mapped[ReportStatus] = mapped_column(SQLEnum(ReportStatus), default=ReportStatus.PENDING)
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    generated_by_id: Mapped[int] = mapped_column(ForeignKey('users.id'), nullable=False)
    
    # Conteúdo do relatório
    content: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    charts_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    ai_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    ai_analysis_types: Mapped[Optional[List[str]]] = mapped_column(JSON)  # Tipos de análise de IA habilitados
    
    # Seções específicas
    executive_summary: Mapped[Optional[str]] = mapped_column(Text)
    recommendations: Mapped[Optional[str]] = mapped_column(Text)
    
    # Badges e classificações
    impact_level: Mapped[Optional[ImpactLevel]] = mapped_column(SQLEnum(ImpactLevel))
    urgency_level: Mapped[Optional[UrgencyLevel]] = mapped_column(SQLEnum(UrgencyLevel))
    completeness_score: Mapped[Optional[int]] = mapped_column(Integer)  # 0-100
    maturity_level: Mapped[Optional[MaturityLevel]] = mapped_column(SQLEnum(MaturityLevel))
    
    # Tags e categorização
    tags: Mapped[Optional[str]] = mapped_column(String(500))  # Separadas por vírgula
    
    # Exportação
    file_path: Mapped[Optional[str]] = mapped_column(String(500))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)
    export_format: Mapped[Optional[str]] = mapped_column(String(10))  # PDF, HTML, etc.
    
    # Metadados adicionais
    report_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    
    # Relacionamentos
    generated_by: Mapped[User] = relationship('User', back_populates='reports')
    
    def __repr__(self) -> str:
        return f"<Report(id={self.id}, title='{self.title}', type='{self.report_type.value}', status='{self.status.value}')>"
    
    @property
    def tags_list(self) -> List[str]:
        """Retorna as tags como lista."""
        if not self.tags:
            return []
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]
    
    @tags_list.setter
    def tags_list(self, tags: List[str]) -> None:
        """Define as tags a partir de uma lista."""
        self.tags = ', '.join(tags) if tags else None
    
    @property
    def is_completed(self) -> bool:
        """Verifica se o relatório foi concluído."""
        return self.status == ReportStatus.COMPLETED
    
    @property
    def is_exportable(self) -> bool:
        """Verifica se o relatório pode ser exportado."""
        return self.status in [ReportStatus.COMPLETED, ReportStatus.EXPORTED]
    
    @property
    def duration_days(self) -> int:
        """Retorna a duração do período em dias."""
        return (self.period_end - self.period_start).days
    
    @property
    def export_formats(self) -> List[str]:
        try:
            meta = self.report_metadata or {}
            configured = meta.get('export_formats')
            if isinstance(configured, list) and configured:
                return configured
        except Exception:
            pass
        return ['html', 'pdf', 'json', 'docx']
    
    def get_badge_color(self, badge_type: str) -> str:
        """Retorna a cor do badge baseada no tipo e valor."""
        colors = {
            'impact': {
                ImpactLevel.LOW: 'success',
                ImpactLevel.MEDIUM: 'warning', 
                ImpactLevel.HIGH: 'danger',
                ImpactLevel.CRITICAL: 'dark'
            },
            'urgency': {
                UrgencyLevel.LOW: 'success',
                UrgencyLevel.MEDIUM: 'info',
                UrgencyLevel.HIGH: 'warning',
                UrgencyLevel.URGENT: 'danger'
            },
            'maturity': {
                MaturityLevel.LEVEL_1: 'danger',
                MaturityLevel.LEVEL_2: 'warning',
                MaturityLevel.LEVEL_3: 'info',
                MaturityLevel.LEVEL_4: 'primary',
                MaturityLevel.LEVEL_5: 'success'
            }
        }
        
        if badge_type == 'impact' and self.impact_level:
            return colors['impact'].get(self.impact_level, 'secondary')
        elif badge_type == 'urgency' and self.urgency_level:
            return colors['urgency'].get(self.urgency_level, 'secondary')
        elif badge_type == 'maturity' and self.maturity_level:
            return colors['maturity'].get(self.maturity_level, 'secondary')
        elif badge_type == 'completeness':
            if self.completeness_score is None:
                return 'secondary'
            elif self.completeness_score >= 90:
                return 'success'
            elif self.completeness_score >= 70:
                return 'info'
            elif self.completeness_score >= 50:
                return 'warning'
            else:
                return 'danger'
        
        return 'secondary'
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte o relatório para dicionário."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'report_type': self.report_type.value,
            'scope': self.scope.value,
            'detail_level': self.detail_level.value,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'scope_config': self.scope_config,
            'status': self.status.value,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'generated_by_id': self.generated_by_id,
            'content': self.content,
            'charts_data': self.charts_data,
            'ai_analysis': self.ai_analysis,
            'executive_summary': self.executive_summary,
            'recommendations': self.recommendations,
            'impact_level': self.impact_level.value if self.impact_level else None,
            'urgency_level': self.urgency_level.value if self.urgency_level else None,
            'completeness_score': self.completeness_score,
            'maturity_level': self.maturity_level.value if self.maturity_level else None,
            'tags': self.tags_list,
            'file_path': self.file_path,
            'file_size': self.file_size,
            'export_format': self.export_format,
            'metadata': self.report_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    # --- Propriedades de leitura para filtros e opções salvos em JSON ---
    @property
    def asset_ids(self) -> List[int]:
        cfg = self.scope_config or {}
        ids = cfg.get('custom_assets') or cfg.get('asset_ids') or []
        try:
            return [int(x) for x in ids]
        except Exception:
            return ids

    @property
    def asset_tags(self) -> List[str]:
        cfg = self.scope_config or {}
        return cfg.get('selected_tags') or cfg.get('asset_tags') or []

    @property
    def asset_groups(self) -> List[str]:
        cfg = self.scope_config or {}
        return cfg.get('selected_groups') or cfg.get('asset_groups') or []

    @property
    def include_ai_analysis(self) -> bool:
        meta = self.report_metadata or {}
        val = meta.get('include_ai_analysis')
        if val is None:
            # fallback: considerar True se tipos forem definidos
            return bool(self.ai_analysis_types)
        return bool(val)

    @property
    def include_charts(self) -> bool:
        meta = self.report_metadata or {}
        return bool(meta.get('include_charts'))

    @property
    def chart_types(self) -> List[str]:
        meta = self.report_metadata or {}
        charts = meta.get('chart_types') or []
        # Normalizar nomes
        normalized: List[str] = []
        for c in charts:
            normalized.append('vulnerability_trend' if c == 'vulnerability_trends' else c)
        return normalized

    @property
    def notify_completion(self) -> bool:
        meta = self.report_metadata or {}
        return bool(meta.get('notify_completion'))

    @property
    def notification_email(self) -> Optional[str]:
        meta = self.report_metadata or {}
        return meta.get('notification_email')