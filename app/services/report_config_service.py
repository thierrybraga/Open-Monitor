# services/report_config_service.py

"""
Serviço para gerenciar configurações de relatórios.
Permite personalizar templates, formatos, notificações e outras configurações.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class ConfigScope(Enum):
    """Escopo das configurações."""
    GLOBAL = "global"
    USER = "user"
    ORGANIZATION = "organization"
    REPORT_TYPE = "report_type"


class ConfigCategory(Enum):
    """Categoria das configurações."""
    TEMPLATES = "templates"
    EXPORT = "export"
    NOTIFICATIONS = "notifications"
    CHARTS = "charts"
    AI_ANALYSIS = "ai_analysis"
    SCHEDULING = "scheduling"
    BRANDING = "branding"
    SECURITY = "security"


@dataclass
class ReportTemplate:
    """Template de relatório personalizado."""
    id: str
    name: str
    description: str
    report_type: str
    template_path: str
    css_path: Optional[str] = None
    js_path: Optional[str] = None
    default_config: Dict[str, Any] = None
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExportConfig:
    """Configuração de exportação."""
    format: str
    enabled: bool = True
    template: Optional[str] = None
    options: Dict[str, Any] = None
    quality: str = "high"  # low, medium, high
    compression: bool = False
    watermark: bool = False
    password_protected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ChartConfig:
    """Configuração de gráficos."""
    chart_type: str
    enabled: bool = True
    default_options: Dict[str, Any] = None
    color_scheme: str = "default"
    animation: bool = True
    responsive: bool = True
    export_formats: List[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrandingConfig:
    """Configuração de marca/identidade visual."""
    company_name: str
    logo_url: Optional[str] = None
    primary_color: str = "#007bff"
    secondary_color: str = "#6c757d"
    font_family: str = "Arial, sans-serif"
    header_template: Optional[str] = None
    footer_template: Optional[str] = None
    custom_css: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReportConfigService:
    """Serviço para gerenciar configurações de relatórios."""

    def __init__(self):
        self.configs = {}
        self.templates = {}
        self._initialize_default_configs()

    def _initialize_default_configs(self):
        """Inicializa configurações padrão."""
        # Templates padrão
        self.templates = {
            'executive': ReportTemplate(
                id='executive_default',
                name='Executive Report Template',
                description='Template padrão para relatórios executivos',
                report_type='executive',
                template_path='reports/report_executive.html',
                css_path='css/executive.css',
                default_config={
                    'include_charts': True,
                    'chart_types': ['risk_distribution', 'security_trend', 'maturity_radar'],
                    'include_ai_analysis': True,
                    'ai_analysis_types': ['executive_summary', 'business_impact']
                }
            ),
            'technical': ReportTemplate(
                id='technical_default',
                name='Technical Report Template',
                description='Template padrão para relatórios técnicos',
                report_type='technical',
                template_path='reports/report_technical.html',
                css_path='css/technical.css',
                default_config={
                    'include_charts': True,
                    'chart_types': ['cvss_distribution', 'vulnerability_trends', 'asset_heatmap'],
                    'include_ai_analysis': True,
                    'ai_analysis_types': ['technical_analysis', 'remediation_plan']
                }
            ),
            'compliance': ReportTemplate(
                id='compliance_default',
                name='Compliance Report Template',
                description='Template padrão para relatórios de compliance',
                report_type='compliance',
                template_path='reports/report_compliance.html',
                css_path='css/compliance.css',
                default_config={
                    'include_charts': True,
                    'chart_types': ['compliance_score', 'control_status', 'gap_analysis'],
                    'include_ai_analysis': False
                }
            )
        }

        # Configurações de exportação padrão
        self.configs['export'] = {
            'pdf': ExportConfig(
                format='pdf',
                template='default_pdf.html',
                options={
                    'page_size': 'A4',
                    'orientation': 'portrait',
                    'margin': '1cm',
                    'print_media_type': True
                },
                quality='high'
            ),
            'html': ExportConfig(
                format='html',
                template='export_html.html',
                options={
                    'standalone': True,
                    'include_css': True,
                    'minify': False
                }
            ),
            'docx': ExportConfig(
                format='docx',
                options={
                    'template': 'default_template.docx',
                    'include_images': True,
                    'table_style': 'modern'
                }
            )
        }

        # Configurações de gráficos padrão
        self.configs['charts'] = {
            'cvss_distribution': ChartConfig(
                chart_type='doughnut',
                default_options={
                    'responsive': True,
                    'maintainAspectRatio': False,
                    'plugins': {
                        'legend': {'position': 'bottom'},
                        'title': {'display': True, 'text': 'Distribuição CVSS'}
                    }
                },
                color_scheme='severity',
                export_formats=['png', 'svg', 'pdf']
            ),
            'vulnerability_trends': ChartConfig(
                chart_type='line',
                default_options={
                    'responsive': True,
                    'scales': {
                        'y': {'beginAtZero': True}
                    }
                },
                color_scheme='timeline'
            ),
            'risk_matrix': ChartConfig(
                chart_type='scatter',
                default_options={
                    'responsive': True,
                    'scales': {
                        'x': {'title': {'display': True, 'text': 'Probabilidade'}},
                        'y': {'title': {'display': True, 'text': 'Impacto'}}
                    }
                },
                color_scheme='risk'
            )
        }

        # Configuração de marca padrão
        self.configs['branding'] = BrandingConfig(
            company_name='Open Monitor',
            primary_color='#007bff',
            secondary_color='#6c757d',
            font_family='Inter, system-ui, sans-serif'
        )

    def get_config(self, category: str, scope: ConfigScope = ConfigScope.GLOBAL, 
                   user_id: Optional[int] = None, org_id: Optional[int] = None) -> Dict[str, Any]:
        """Obtém configuração por categoria e escopo."""
        try:
            config_key = self._build_config_key(category, scope, user_id, org_id)
            
            # Buscar configuração específica
            if config_key in self.configs:
                return self.configs[config_key]
            
            # Fallback para configuração global
            if category in self.configs:
                return self.configs[category]
            
            return {}
            
        except Exception as e:
            logger.error(f"Erro ao obter configuração {category}: {e}")
            return {}

    def set_config(self, category: str, config: Dict[str, Any], 
                   scope: ConfigScope = ConfigScope.GLOBAL,
                   user_id: Optional[int] = None, org_id: Optional[int] = None) -> bool:
        """Define configuração por categoria e escopo."""
        try:
            config_key = self._build_config_key(category, scope, user_id, org_id)
            self.configs[config_key] = config
            
            logger.info(f"Configuração {category} definida para escopo {scope.value}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao definir configuração {category}: {e}")
            return False

    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """Obtém template por ID."""
        return self.templates.get(template_id)

    def get_templates_by_type(self, report_type: str) -> List[ReportTemplate]:
        """Obtém templates por tipo de relatório."""
        return [
            template for template in self.templates.values()
            if template.report_type == report_type and template.is_active
        ]

    def add_custom_template(self, template: ReportTemplate) -> bool:
        """Adiciona template personalizado."""
        try:
            template.created_at = datetime.now(timezone.utc)
            template.updated_at = datetime.now(timezone.utc)
            self.templates[template.id] = template
            
            logger.info(f"Template personalizado {template.id} adicionado")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao adicionar template {template.id}: {e}")
            return False

    def update_template(self, template_id: str, updates: Dict[str, Any]) -> bool:
        """Atualiza template existente."""
        try:
            if template_id not in self.templates:
                return False
            
            template = self.templates[template_id]
            for key, value in updates.items():
                if hasattr(template, key):
                    setattr(template, key, value)
            
            template.updated_at = datetime.now(timezone.utc)
            
            logger.info(f"Template {template_id} atualizado")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar template {template_id}: {e}")
            return False

    def get_export_config(self, format: str, user_id: Optional[int] = None) -> ExportConfig:
        """Obtém configuração de exportação por formato."""
        export_configs = self.get_config('export', ConfigScope.USER, user_id)
        
        if format in export_configs:
            return export_configs[format]
        
        # Fallback para configuração global
        global_configs = self.get_config('export')
        return global_configs.get(format, ExportConfig(format=format))

    def get_chart_config(self, chart_type: str, user_id: Optional[int] = None) -> ChartConfig:
        """Obtém configuração de gráfico por tipo."""
        chart_configs = self.get_config('charts', ConfigScope.USER, user_id)
        
        if chart_type in chart_configs:
            return chart_configs[chart_type]
        
        # Fallback para configuração global
        global_configs = self.get_config('charts')
        return global_configs.get(chart_type, ChartConfig(chart_type=chart_type))

    def get_branding_config(self, org_id: Optional[int] = None) -> BrandingConfig:
        """Obtém configuração de marca."""
        branding = self.get_config('branding', ConfigScope.ORGANIZATION, org_id=org_id)
        
        if branding:
            return branding
        
        return self.configs['branding']

    def validate_config(self, category: str, config: Dict[str, Any]) -> tuple[bool, List[str]]:
        """Valida configuração antes de salvar."""
        errors = []
        
        try:
            if category == 'export':
                for format_name, format_config in config.items():
                    if not isinstance(format_config, dict):
                        errors.append(f"Configuração de {format_name} deve ser um objeto")
                    elif 'format' not in format_config:
                        errors.append(f"Campo 'format' obrigatório para {format_name}")
            
            elif category == 'charts':
                for chart_name, chart_config in config.items():
                    if not isinstance(chart_config, dict):
                        errors.append(f"Configuração de {chart_name} deve ser um objeto")
                    elif 'chart_type' not in chart_config:
                        errors.append(f"Campo 'chart_type' obrigatório para {chart_name}")
            
            elif category == 'branding':
                required_fields = ['company_name', 'primary_color']
                for field in required_fields:
                    if field not in config:
                        errors.append(f"Campo '{field}' obrigatório para branding")
            
            return len(errors) == 0, errors
            
        except Exception as e:
            logger.error(f"Erro ao validar configuração {category}: {e}")
            return False, [f"Erro de validação: {str(e)}"]

    def export_config(self, category: Optional[str] = None, 
                     scope: ConfigScope = ConfigScope.GLOBAL) -> Dict[str, Any]:
        """Exporta configurações para backup/migração."""
        try:
            if category:
                return {category: self.get_config(category, scope)}
            
            # Exportar todas as configurações
            export_data = {
                'configs': {},
                'templates': {},
                'metadata': {
                    'exported_at': datetime.utcnow().isoformat(),
                    'version': '1.0'
                }
            }
            
            # Exportar configurações
            for cat in ConfigCategory:
                export_data['configs'][cat.value] = self.get_config(cat.value, scope)
            
            # Exportar templates
            for template_id, template in self.templates.items():
                export_data['templates'][template_id] = template.to_dict()
            
            return export_data
            
        except Exception as e:
            logger.error(f"Erro ao exportar configurações: {e}")
            return {}

    def import_config(self, config_data: Dict[str, Any]) -> bool:
        """Importa configurações de backup."""
        try:
            # Importar configurações
            if 'configs' in config_data:
                for category, config in config_data['configs'].items():
                    self.set_config(category, config)
            
            # Importar templates
            if 'templates' in config_data:
                for template_id, template_data in config_data['templates'].items():
                    template = ReportTemplate(**template_data)
                    self.templates[template_id] = template
            
            logger.info("Configurações importadas com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao importar configurações: {e}")
            return False

    def _build_config_key(self, category: str, scope: ConfigScope, 
                         user_id: Optional[int] = None, org_id: Optional[int] = None) -> str:
        """Constrói chave de configuração baseada no escopo."""
        if scope == ConfigScope.USER and user_id:
            return f"{category}_user_{user_id}"
        elif scope == ConfigScope.ORGANIZATION and org_id:
            return f"{category}_org_{org_id}"
        elif scope == ConfigScope.REPORT_TYPE:
            return f"{category}_type"
        else:
            return category

    def reset_to_defaults(self, category: str, scope: ConfigScope = ConfigScope.GLOBAL,
                         user_id: Optional[int] = None, org_id: Optional[int] = None) -> bool:
        """Reseta configuração para padrões."""
        try:
            config_key = self._build_config_key(category, scope, user_id, org_id)
            
            if config_key in self.configs:
                del self.configs[config_key]
            
            logger.info(f"Configuração {category} resetada para padrões")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao resetar configuração {category}: {e}")
            return False
