# forms/report_form.py

"""
Formulários para configuração e geração de relatórios de cybersegurança.
"""

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (
    StringField, TextAreaField, SelectField, DateTimeField, 
    SelectMultipleField, BooleanField, IntegerField, HiddenField,
    FieldList, FormField, RadioField
)
from wtforms.validators import (
    DataRequired, Length, Optional, NumberRange, 
    ValidationError, Email
)
from wtforms.widgets import CheckboxInput, ListWidget
from datetime import datetime, timedelta
from typing import List, Tuple


class MultiCheckboxField(SelectMultipleField):
    """Campo personalizado para múltiplas seleções com checkboxes."""
    widget = ListWidget(prefix_label=False)
    option_widget = CheckboxInput()


class ReportConfigForm(FlaskForm):
    """Formulário principal para configuração de relatórios."""
    
    # Informações básicas
    title = StringField(
        'Título do Relatório',
        validators=[DataRequired(message='Título é obrigatório'), 
                   Length(min=1, max=255, message='Título deve ter entre 1 e 255 caracteres')],
        render_kw={'placeholder': 'Ex: Relatório de Vulnerabilidades Q4 2024'}
    )
    
    description = TextAreaField(
        'Descrição',
        validators=[Optional(), Length(max=1000, message='Descrição deve ter no máximo 1000 caracteres')],
        render_kw={'placeholder': 'Descrição detalhada do relatório...', 'rows': 3}
    )
    
    # Tipo de relatório
    report_type = SelectField(
        'Tipo de Relatório',
        validators=[DataRequired(message='Tipo de relatório é obrigatório')],
        choices=[
            ('executivo', 'Executivo - Visão estratégica para liderança'),
        ('tecnico', 'Técnico - Detalhes técnicos para equipes de TI'),
        ('estudo_tecnico', 'Estudo Técnico - Análise técnica aprofundada'),
        ('pentest', 'Pentest - Resultados de testes de penetração'),
        ('bia', 'BIA - Análise de Impacto no Negócio'),
        ('kpi_kri', 'KPI/KRI - Indicadores de Performance e Risco')
        ]
    )
    
    # Escopo do relatório
    scope = RadioField(
        'Escopo do Relatório',
        validators=[DataRequired(message='Escopo é obrigatório')],
        choices=[
            ('todos_ativos', 'Todos os Ativos'),
            ('por_tags', 'Por Tags'),
            ('por_grupos', 'Por Grupos'),
            ('customizado', 'Customizado')
        ],
        default='todos_ativos'
    )
    
    # Configurações específicas do escopo
    selected_tags = MultiCheckboxField(
        'Tags Selecionadas',
        validators=[Optional()],
        choices=[],  # Será preenchido dinamicamente
        render_kw={'class': 'scope-config', 'data-scope': 'por_tags'}
    )
    
    selected_groups = MultiCheckboxField(
        'Grupos Selecionados',
        validators=[Optional()],
        choices=[],  # Será preenchido dinamicamente
        render_kw={'class': 'scope-config', 'data-scope': 'por_grupos'}
    )
    
    custom_assets = MultiCheckboxField(
        'Ativos Específicos',
        validators=[Optional()],
        choices=[],  # Será preenchido dinamicamente
        render_kw={'class': 'scope-config', 'data-scope': 'customizado'}
    )
    
    # Período de análise
    period_start = DateTimeField(
        'Data de Início',
        validators=[DataRequired(message='Data de início é obrigatória')],
        format='%Y-%m-%d',
        render_kw={'type': 'date'}
    )
    
    period_end = DateTimeField(
        'Data de Fim',
        validators=[DataRequired(message='Data de fim é obrigatória')],
        format='%Y-%m-%d',
        render_kw={'type': 'date'}
    )
    
    # Nível de detalhe
    detail_level = SelectField(
        'Nível de Detalhe',
        validators=[DataRequired(message='Nível de detalhe é obrigatório')],
        choices=[
            ('resumido', 'Resumido - Principais métricas e insights'),
            ('completo', 'Completo - Análise detalhada com todos os dados')
        ],
        default='resumido'
    )
    
    # Configurações avançadas
    include_charts = BooleanField(
        'Incluir Gráficos Interativos',
        default=True,
        render_kw={'checked': True}
    )
    
    include_ai_analysis = BooleanField(
        'Incluir Análise de IA',
        default=True,
        render_kw={'checked': True}
    )
    
    include_recommendations = BooleanField(
        'Incluir Recomendações',
        default=True,
        render_kw={'checked': True}
    )
    
    include_executive_summary = BooleanField(
        'Incluir Resumo Executivo',
        default=True,
        render_kw={'checked': True}
    )
    
    # Tipos de análise de IA
    ai_analysis_types = MultiCheckboxField(
        'Tipos de Análise de IA',
        validators=[Optional()],
        choices=[
            ('executive_summary', 'Resumo Executivo'),
            ('business_impact', 'Análise de Impacto no Negócio'),
            ('technical_analysis', 'Análise Técnica'),
            ('remediation_plan', 'Plano de Remediação'),
            ('cisa_kev_analysis', 'Análise CISA KEV'),
            ('epss_analysis', 'Análise EPSS'),
            ('vendor_product_analysis', 'Análise de Fornecedores/Produtos')
        ],
        default=['executive_summary', 'business_impact']
    )
    
    # Configurações de gráficos
    chart_types = MultiCheckboxField(
        'Tipos de Gráficos',
        validators=[Optional()],
        choices=[
            ('cvss_distribution', 'Distribuição CVSS'),
            ('top_assets_risk', 'Top Ativos por Risco'),
            ('vulnerability_trend', 'Tendência de Vulnerabilidades'),
            ('risk_matrix', 'Matriz de Risco'),
            ('asset_vulnerability_heatmap', 'Heatmap Ativos × Vulnerabilidades'),
            ('kpi_timeline', 'Timeline KPI/KRI'),
            ('security_maturity_radar', 'Radar de Maturidade de Segurança')
        ],
        default=['cvss_distribution', 'top_assets_risk', 'vulnerability_trend']
    )
    
    # Tags personalizadas
    custom_tags = StringField(
        'Tags Personalizadas',
        validators=[Optional(), Length(max=500, message='Tags devem ter no máximo 500 caracteres')],
        render_kw={'placeholder': 'tag1, tag2, tag3...'}
    )
    
    # Configurações de exportação
    auto_export = BooleanField(
        'Exportar Automaticamente',
        default=False
    )
    
    export_format = SelectField(
        'Formato de Exportação',
        validators=[Optional()],
        choices=[
            ('pdf', 'PDF'),
            ('html', 'HTML'),
            ('docx', 'Word Document')
        ],
        default='pdf'
    )
    
    # Configurações de notificação
    notify_completion = BooleanField(
        'Notificar ao Concluir',
        default=True,
        render_kw={'checked': True}
    )
    
    notification_email = StringField(
        'Email para Notificação',
        validators=[Optional(), Email(message='Email inválido')],
        render_kw={'placeholder': 'seu@email.com'}
    )

    # Upload opcional de CSV com colunas na ordem: hostid, alias, os
    csv_file = FileField(
        'Importar CSV de Ativos (hostid, alias, os)',
        validators=[Optional(), FileAllowed(['csv'], 'Apenas arquivos CSV são permitidos.')]
    )
    
    def validate_period_end(self, field):
        """Valida se a data de fim é posterior à data de início."""
        if self.period_start.data and field.data:
            if field.data <= self.period_start.data:
                raise ValidationError('Data de fim deve ser posterior à data de início')
    
    def validate_selected_tags(self, field):
        """Valida tags quando escopo é 'por_tags'."""
        if self.scope.data == 'por_tags' and not field.data:
            raise ValidationError('Selecione pelo menos uma tag quando escopo for "Por Tags"')
    
    def validate_selected_groups(self, field):
        """Valida grupos quando escopo é 'por_grupos'."""
        if self.scope.data == 'por_grupos' and not field.data:
            raise ValidationError('Selecione pelo menos um grupo quando escopo for "Por Grupos"')
    
    def validate_custom_assets(self, field):
        """Valida ativos quando escopo é 'customizado'."""
        if self.scope.data == 'customizado' and not field.data:
            raise ValidationError('Selecione pelo menos um ativo quando escopo for "Customizado"')


class ReportFilterForm(FlaskForm):
    """Formulário para filtrar relatórios existentes."""
    
    # Filtros básicos
    search = StringField(
        'Buscar',
        validators=[Optional()],
        render_kw={'placeholder': 'Buscar por título ou descrição...'}
    )
    
    report_type = MultiCheckboxField(
        'Tipo de Relatório',
        validators=[Optional()],
        choices=[
            ('executivo', 'Executivo'),
            ('tecnico', 'Técnico'),
            ('estudo_tecnico', 'Estudo Técnico'),
            ('pentest', 'Pentest'),
            ('bia', 'BIA'),
            ('kpi_kri', 'KPI/KRI')
        ]
    )
    
    status = MultiCheckboxField(
        'Status',
        validators=[Optional()],
        choices=[
            ('pendente', 'Pendente'),
            ('gerando', 'Gerando'),
            ('concluido', 'Concluído'),
            ('falhou', 'Falhou'),
            ('exportado', 'Exportado')
        ]
    )
    
    # Filtros por data
    date_from = DateTimeField(
        'Data de',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={'type': 'date'}
    )
    
    date_to = DateTimeField(
        'Data até',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={'type': 'date'}
    )
    
    # Filtros por classificação
    impact_level = MultiCheckboxField(
        'Nível de Impacto',
        validators=[Optional()],
        choices=[
            ('baixo', 'Baixo'),
            ('medio', 'Médio'),
            ('alto', 'Alto'),
            ('critico', 'Crítico')
        ]
    )
    
    urgency_level = MultiCheckboxField(
        'Nível de Urgência',
        validators=[Optional()],
        choices=[
            ('baixo', 'Baixo'),
            ('medio', 'Médio'),
            ('alto', 'Alto'),
            ('urgente', 'Urgente')
        ]
    )
    
    # Ordenação
    sort_by = SelectField(
        'Ordenar por',
        validators=[Optional()],
        choices=[
            ('created_at', 'Data de Criação'),
            ('updated_at', 'Última Atualização'),
            ('generated_at', 'Data de Geração'),
            ('title', 'Título'),
            ('report_type', 'Tipo'),
            ('status', 'Status')
        ],
        default='created_at'
    )
    
    sort_order = SelectField(
        'Ordem',
        validators=[Optional()],
        choices=[
            ('desc', 'Decrescente'),
            ('asc', 'Crescente')
        ],
        default='desc'
    )


class ReportExportForm(FlaskForm):
    """Formulário para exportação de relatórios."""
    
    report_id = HiddenField(
        'ID do Relatório',
        validators=[DataRequired()]
    )
    
    format = SelectField(
        'Formato',
        validators=[DataRequired(message='Formato é obrigatório')],
        choices=[
            ('pdf', 'PDF'),
            ('html', 'HTML'),
            ('docx', 'Word Document')
        ],
        default='pdf'
    )
    
    include_charts = BooleanField(
        'Incluir Gráficos',
        default=True,
        render_kw={'checked': True}
    )
    
    include_raw_data = BooleanField(
        'Incluir Dados Brutos',
        default=False
    )
    
    template = SelectField(
        'Template',
        validators=[Optional()],
        choices=[
            ('default', 'Padrão'),
            ('executive', 'Executivo'),
            ('technical', 'Técnico'),
            ('minimal', 'Minimalista')
        ],
        default='default'
    )


class QuickReportForm(FlaskForm):
    """Formulário simplificado para relatórios rápidos."""
    
    # Campos opcionais adicionais usados pelo template
    title = StringField(
        'Título',
        validators=[Optional(), Length(min=1, max=255)],
        render_kw={'placeholder': 'Ex: Relatório de Segurança - Janeiro 2024'}
    )
    
    description = TextAreaField(
        'Descrição',
        validators=[Optional(), Length(max=1000)],
        render_kw={'rows': 3, 'placeholder': 'Descreva o contexto e objetivo do relatório...'}
    )

    # Upload opcional de CSV com colunas na ordem: hostid, alias, os
    csv_file = FileField(
        'Importar CSV de Ativos (hostid, alias, os)',
        validators=[Optional(), FileAllowed(['csv'], 'Apenas arquivos CSV são permitidos.')]
    )
    
    detail_level = SelectField(
        'Nível de Detalhe',
        validators=[Optional()],
        choices=[
            ('resumido', 'Resumido'),
            ('completo', 'Completo')
        ],
        default='resumido'
    )
    
    report_type = SelectField(
        'Tipo',
        validators=[DataRequired()],
        choices=[
            ('executivo', 'Executivo'),
            ('tecnico', 'Técnico'),
            ('estudo_tecnico', 'Estudo Técnico'),
            ('kpi_kri', 'KPI/KRI')
        ]
    )
    
    period_days = SelectField(
        'Período',
        validators=[DataRequired()],
        choices=[
            ('7', 'Últimos 7 dias'),
            ('30', 'Últimos 30 dias'),
            ('90', 'Últimos 90 dias'),
            ('365', 'Último ano')
        ],
        default='30'
    )
    
    scope = SelectField(
        'Escopo',
        validators=[DataRequired()],
        choices=[
            ('todos_ativos', 'Todos os Ativos'),
            ('criticos', 'Apenas Ativos Críticos')
        ],
        default='todos_ativos'
    )

    # Opções avançadas (Opcional) alinhadas ao template quick_create
    include_ai_analysis = BooleanField(
        'Incluir Análise de IA',
        default=True,
        render_kw={'class': 'form-check-input'}
    )

    include_charts = BooleanField(
        'Incluir Gráficos Interativos',
        default=True,
        render_kw={'class': 'form-check-input'}
    )

    auto_export_pdf = BooleanField(
        'Exportar automaticamente em PDF',
        default=False,
        render_kw={'class': 'form-check-input'}
    )

    send_notification = BooleanField(
        'Notificar quando o relatório estiver pronto',
        default=False,
        render_kw={'class': 'form-check-input'}
    )