# schemas/report_schema.py

"""
Schemas para serialização e validação de dados de relatórios.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from datetime import datetime
from typing import Dict, Any


class ReportConfigSchema(Schema):
    """Schema para configuração de relatórios."""
    
    # Configuração básica
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    
    # Tipo e escopo
    report_type = fields.Str(
        required=True,
        validate=validate.OneOf(['executivo', 'tecnico', 'estudo_tecnico', 'pentest', 'bia', 'kpi_kri'])
    )
    scope = fields.Str(
        required=True,
        validate=validate.OneOf(['todos_ativos', 'por_tags', 'por_grupos', 'customizado'])
    )
    detail_level = fields.Str(
        required=True,
        validate=validate.OneOf(['resumido', 'completo'])
    )
    
    # Período
    period_start = fields.DateTime(required=True)
    period_end = fields.DateTime(required=True)
    
    # Configuração específica do escopo
    scope_config = fields.Dict(allow_none=True)
    
    # Tags
    tags = fields.List(fields.Str(), allow_none=True)
    
    @validates_schema
    def validate_period(self, data, **kwargs):
        """Valida se o período é válido."""
        if 'period_start' in data and 'period_end' in data:
            if data['period_start'] >= data['period_end']:
                raise ValidationError('period_end deve ser posterior a period_start')
    
    @validates_schema
    def validate_scope_config(self, data, **kwargs):
        """Valida a configuração do escopo."""
        scope = data.get('scope')
        scope_config = data.get('scope_config', {})
        
        if scope == 'por_tags' and not scope_config.get('tags'):
            raise ValidationError('Tags são obrigatórias quando escopo é "por_tags"')
        
        if scope == 'por_grupos' and not scope_config.get('groups'):
            raise ValidationError('Grupos são obrigatórios quando escopo é "por_grupos"')


class ReportResponseSchema(Schema):
    """Schema para resposta de relatórios."""
    
    id = fields.Int(dump_only=True)
    title = fields.Str()
    description = fields.Str(allow_none=True)
    report_type = fields.Str()
    scope = fields.Str()
    detail_level = fields.Str()
    period_start = fields.DateTime()
    period_end = fields.DateTime()
    scope_config = fields.Dict(allow_none=True)
    status = fields.Str()
    generated_at = fields.DateTime(allow_none=True)
    generated_by_id = fields.Int()
    
    # Badges e classificações
    impact_level = fields.Str(allow_none=True)
    urgency_level = fields.Str(allow_none=True)
    completeness_score = fields.Int(allow_none=True)
    maturity_level = fields.Str(allow_none=True)
    
    # Tags e exportação
    tags = fields.List(fields.Str(), allow_none=True)
    file_path = fields.Str(allow_none=True)
    file_size = fields.Int(allow_none=True)
    export_format = fields.Str(allow_none=True)
    
    # Timestamps
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class ReportContentSchema(Schema):
    """Schema para conteúdo detalhado do relatório."""
    
    id = fields.Int(dump_only=True)
    title = fields.Str()
    description = fields.Str(allow_none=True)
    report_type = fields.Str()
    scope = fields.Str()
    detail_level = fields.Str()
    period_start = fields.DateTime()
    period_end = fields.DateTime()
    scope_config = fields.Dict(allow_none=True)
    status = fields.Str()
    generated_at = fields.DateTime(allow_none=True)
    generated_by_id = fields.Int()
    
    # Conteúdo completo
    content = fields.Dict(allow_none=True)
    charts_data = fields.Dict(allow_none=True)
    ai_analysis = fields.Dict(allow_none=True)
    executive_summary = fields.Str(allow_none=True)
    recommendations = fields.Str(allow_none=True)
    
    # Badges e classificações
    impact_level = fields.Str(allow_none=True)
    urgency_level = fields.Str(allow_none=True)
    completeness_score = fields.Int(allow_none=True)
    maturity_level = fields.Str(allow_none=True)
    
    # Tags e metadados
    tags = fields.List(fields.Str(), allow_none=True)
    metadata = fields.Dict(allow_none=True)
    
    # Exportação
    file_path = fields.Str(allow_none=True)
    file_size = fields.Int(allow_none=True)
    export_format = fields.Str(allow_none=True)
    
    # Timestamps
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class ChartDataSchema(Schema):
    """Schema para dados de gráficos."""
    
    chart_type = fields.Str(required=True)
    title = fields.Str(required=True)
    data = fields.Dict(required=True)
    options = fields.Dict(allow_none=True)


class AIAnalysisSchema(Schema):
    """Schema para análise de IA."""
    
    executive_summary = fields.Str(allow_none=True)
    risk_analysis = fields.Str(allow_none=True)
    business_impact = fields.Str(allow_none=True)
    recommendations = fields.List(fields.Str(), allow_none=True)
    key_findings = fields.List(fields.Str(), allow_none=True)
    threat_landscape = fields.Str(allow_none=True)
    compliance_status = fields.Str(allow_none=True)


class ReportExportSchema(Schema):
    """Schema para exportação de relatórios."""
    
    report_id = fields.Int(required=True)
    format = fields.Str(
        required=True,
        validate=validate.OneOf(['pdf', 'html', 'docx', 'json'])
    )
    include_charts = fields.Bool(load_default=True)
    include_raw_data = fields.Bool(load_default=False)
    template = fields.Str(allow_none=True)


class ReportFilterSchema(Schema):
    """Schema para filtros de relatórios."""
    
    report_type = fields.List(fields.Str(), allow_none=True)
    status = fields.List(fields.Str(), allow_none=True)
    generated_by = fields.List(fields.Int(), allow_none=True)
    date_from = fields.DateTime(allow_none=True)
    date_to = fields.DateTime(allow_none=True)
    tags = fields.List(fields.Str(), allow_none=True)
    impact_level = fields.List(fields.Str(), allow_none=True)
    urgency_level = fields.List(fields.Str(), allow_none=True)
    
    # Paginação
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=10, validate=validate.Range(min=1, max=100))
    
    # Ordenação
    sort_by = fields.Str(
        load_default='created_at',
        validate=validate.OneOf([
            'created_at', 'updated_at', 'generated_at', 'title',
            'report_type', 'status', 'impact_level', 'urgency_level'
        ])
    )
    sort_order = fields.Str(
        load_default='desc',
        validate=validate.OneOf(['asc', 'desc'])
    )


class ReportStatsSchema(Schema):
    """Schema para estatísticas de relatórios."""
    
    total_reports = fields.Int()
    reports_by_type = fields.Dict()
    reports_by_status = fields.Dict()
    reports_by_impact = fields.Dict()
    reports_by_urgency = fields.Dict()
    average_generation_time = fields.Float()
    total_file_size = fields.Int()
    most_used_tags = fields.List(fields.Dict())


# Instâncias dos schemas para uso
report_config_schema = ReportConfigSchema()
report_response_schema = ReportResponseSchema()
report_content_schema = ReportContentSchema()
chart_data_schema = ChartDataSchema()
ai_analysis_schema = AIAnalysisSchema()
report_export_schema = ReportExportSchema()
report_filter_schema = ReportFilterSchema()
report_stats_schema = ReportStatsSchema()

# Schemas para múltiplos itens
reports_response_schema = ReportResponseSchema(many=True)
charts_data_schema = ChartDataSchema(many=True)