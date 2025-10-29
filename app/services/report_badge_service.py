"""
Serviço para gerenciamento de badges e tags de relatórios
Fornece sistema de classificação, categorização e marcação visual
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class BadgeType(Enum):
    """Tipos de badges disponíveis"""
    SEVERITY = "severity"
    STATUS = "status"
    COMPLIANCE = "compliance"
    QUALITY = "quality"
    AUTOMATION = "automation"
    PRIORITY = "priority"
    CATEGORY = "category"
    CUSTOM = "custom"

class BadgeStyle(Enum):
    """Estilos visuais dos badges"""
    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    DANGER = "danger"
    WARNING = "warning"
    INFO = "info"
    LIGHT = "light"
    DARK = "dark"

@dataclass
class Badge:
    """Classe para representar um badge"""
    id: str
    label: str
    type: BadgeType
    style: BadgeStyle
    icon: Optional[str] = None
    description: Optional[str] = None
    auto_assign: bool = False
    conditions: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None

@dataclass
class Tag:
    """Classe para representar uma tag"""
    id: str
    name: str
    color: str
    description: Optional[str] = None
    category: Optional[str] = None
    usage_count: int = 0
    created_at: Optional[datetime] = None

class ReportBadgeService:
    """Serviço para gerenciamento de badges e tags de relatórios"""
    
    def __init__(self):
        self.predefined_badges = self._initialize_predefined_badges()
        self.predefined_tags = self._initialize_predefined_tags()
        
    def _initialize_predefined_badges(self) -> Dict[str, Badge]:
        """Inicializa badges predefinidos do sistema"""
        badges = {}
        
        # Badges de Severidade
        severity_badges = [
            Badge("critical", "Crítico", BadgeType.SEVERITY, BadgeStyle.DANGER, 
                  "bi-exclamation-triangle-fill", "Vulnerabilidades críticas identificadas",
                  auto_assign=True, conditions={"critical_vulns": {"$gt": 0}}),
            Badge("high_risk", "Alto Risco", BadgeType.SEVERITY, BadgeStyle.WARNING,
                  "bi-exclamation-triangle", "Alto número de vulnerabilidades de risco",
                  auto_assign=True, conditions={"high_vulns": {"$gt": 5}}),
            Badge("secure", "Seguro", BadgeType.SEVERITY, BadgeStyle.SUCCESS,
                  "bi-shield-check", "Nenhuma vulnerabilidade crítica ou alta",
                  auto_assign=True, conditions={"critical_vulns": 0, "high_vulns": 0})
        ]
        
        # Badges de Status
        status_badges = [
            Badge("completed", "Concluído", BadgeType.STATUS, BadgeStyle.SUCCESS,
                  "bi-check-circle-fill", "Relatório gerado com sucesso"),
            Badge("processing", "Processando", BadgeType.STATUS, BadgeStyle.INFO,
                  "bi-arrow-clockwise", "Relatório em processamento"),
            Badge("failed", "Falhou", BadgeType.STATUS, BadgeStyle.DANGER,
                  "bi-x-circle-fill", "Falha na geração do relatório"),
            Badge("pending", "Pendente", BadgeType.STATUS, BadgeStyle.SECONDARY,
                  "bi-clock", "Relatório aguardando processamento")
        ]
        
        # Badges de Compliance
        compliance_badges = [
            Badge("iso27001", "ISO 27001", BadgeType.COMPLIANCE, BadgeStyle.PRIMARY,
                  "bi-award", "Conforme com ISO 27001"),
            Badge("nist", "NIST", BadgeType.COMPLIANCE, BadgeStyle.PRIMARY,
                  "bi-award", "Conforme com NIST Framework"),
            Badge("gdpr", "GDPR", BadgeType.COMPLIANCE, BadgeStyle.INFO,
                  "bi-shield-lock", "Conforme com GDPR"),
            Badge("lgpd", "LGPD", BadgeType.COMPLIANCE, BadgeStyle.INFO,
                  "bi-shield-lock", "Conforme com LGPD"),
            Badge("pci_dss", "PCI DSS", BadgeType.COMPLIANCE, BadgeStyle.WARNING,
                  "bi-credit-card", "Conforme com PCI DSS")
        ]
        
        # Badges de Qualidade
        quality_badges = [
            Badge("ai_enhanced", "IA Aprimorado", BadgeType.QUALITY, BadgeStyle.INFO,
                  "bi-robot", "Relatório com análise de IA"),
            Badge("comprehensive", "Abrangente", BadgeType.QUALITY, BadgeStyle.PRIMARY,
                  "bi-list-check", "Análise completa e detalhada"),
            Badge("automated", "Automatizado", BadgeType.AUTOMATION, BadgeStyle.SECONDARY,
                  "bi-gear", "Gerado automaticamente"),
            Badge("manual_review", "Revisão Manual", BadgeType.QUALITY, BadgeStyle.WARNING,
                  "bi-person-check", "Revisado manualmente por especialista")
        ]
        
        # Badges de Prioridade
        priority_badges = [
            Badge("urgent", "Urgente", BadgeType.PRIORITY, BadgeStyle.DANGER,
                  "bi-lightning-fill", "Requer ação imediata"),
            Badge("high_priority", "Alta Prioridade", BadgeType.PRIORITY, BadgeStyle.WARNING,
                  "bi-arrow-up-circle", "Alta prioridade de resolução"),
            Badge("normal", "Normal", BadgeType.PRIORITY, BadgeStyle.INFO,
                  "bi-dash-circle", "Prioridade normal"),
            Badge("low_priority", "Baixa Prioridade", BadgeType.PRIORITY, BadgeStyle.LIGHT,
                  "bi-arrow-down-circle", "Baixa prioridade")
        ]
        
        # Badges de Categoria
        category_badges = [
            Badge("pentest", "Pentest", BadgeType.CATEGORY, BadgeStyle.DARK,
                  "bi-bug", "Teste de penetração"),
            Badge("vulnerability_scan", "Scan de Vulnerabilidades", BadgeType.CATEGORY, BadgeStyle.INFO,
                  "bi-search", "Varredura de vulnerabilidades"),
            Badge("compliance_audit", "Auditoria de Compliance", BadgeType.CATEGORY, BadgeStyle.PRIMARY,
                  "bi-clipboard-check", "Auditoria de conformidade"),
            Badge("risk_assessment", "Avaliação de Risco", BadgeType.CATEGORY, BadgeStyle.WARNING,
                  "bi-exclamation-diamond", "Avaliação de riscos"),
            Badge("incident_response", "Resposta a Incidentes", BadgeType.CATEGORY, BadgeStyle.DANGER,
                  "bi-shield-exclamation", "Resposta a incidentes de segurança")
        ]
        
        # Consolidar todos os badges
        all_badges = (severity_badges + status_badges + compliance_badges + 
                     quality_badges + priority_badges + category_badges)
        
        for badge in all_badges:
            badges[badge.id] = badge
            
        return badges
    
    def _initialize_predefined_tags(self) -> Dict[str, Tag]:
        """Inicializa tags predefinidas do sistema"""
        tags = {}
        
        predefined_tags = [
            # Tags de Tecnologia
            Tag("web_app", "Aplicação Web", "#007bff", "Aplicações web e APIs", "technology"),
            Tag("database", "Banco de Dados", "#28a745", "Sistemas de banco de dados", "technology"),
            Tag("network", "Rede", "#ffc107", "Infraestrutura de rede", "technology"),
            Tag("cloud", "Cloud", "#17a2b8", "Serviços em nuvem", "technology"),
            Tag("mobile", "Mobile", "#6f42c1", "Aplicações móveis", "technology"),
            Tag("iot", "IoT", "#fd7e14", "Internet das Coisas", "technology"),
            
            # Tags de Ambiente
            Tag("production", "Produção", "#dc3545", "Ambiente de produção", "environment"),
            Tag("staging", "Homologação", "#ffc107", "Ambiente de homologação", "environment"),
            Tag("development", "Desenvolvimento", "#28a745", "Ambiente de desenvolvimento", "environment"),
            Tag("testing", "Teste", "#6c757d", "Ambiente de teste", "environment"),
            
            # Tags de Criticidade
            Tag("business_critical", "Crítico para Negócio", "#dc3545", "Sistemas críticos para o negócio", "criticality"),
            Tag("customer_facing", "Voltado ao Cliente", "#fd7e14", "Sistemas que atendem clientes", "criticality"),
            Tag("internal_only", "Apenas Interno", "#6c757d", "Sistemas de uso interno", "criticality"),
            
            # Tags de Compliance
            Tag("pci_scope", "Escopo PCI", "#007bff", "Dentro do escopo PCI DSS", "compliance"),
            Tag("gdpr_data", "Dados GDPR", "#28a745", "Processa dados pessoais GDPR", "compliance"),
            Tag("financial_data", "Dados Financeiros", "#ffc107", "Processa dados financeiros", "compliance"),
            Tag("healthcare", "Saúde", "#17a2b8", "Sistemas de saúde (HIPAA)", "compliance"),
            
            # Tags de Tipo de Ativo
            Tag("server", "Servidor", "#6c757d", "Servidores físicos ou virtuais", "asset_type"),
            Tag("workstation", "Estação de Trabalho", "#007bff", "Computadores de usuários", "asset_type"),
            Tag("firewall", "Firewall", "#dc3545", "Dispositivos de firewall", "asset_type"),
            Tag("router", "Roteador", "#ffc107", "Equipamentos de roteamento", "asset_type"),
            Tag("switch", "Switch", "#28a745", "Switches de rede", "asset_type"),
            
            # Tags de Metodologia
            Tag("owasp", "OWASP", "#6f42c1", "Baseado em metodologia OWASP", "methodology"),
            Tag("nist", "NIST", "#007bff", "Baseado em framework NIST", "methodology"),
            Tag("iso27001", "ISO 27001", "#28a745", "Conforme ISO 27001", "methodology"),
            Tag("cis", "CIS Controls", "#17a2b8", "Baseado em CIS Controls", "methodology"),
            
            # Tags de Frequência
            Tag("daily", "Diário", "#28a745", "Relatório diário", "frequency"),
            Tag("weekly", "Semanal", "#007bff", "Relatório semanal", "frequency"),
            Tag("monthly", "Mensal", "#ffc107", "Relatório mensal", "frequency"),
            Tag("quarterly", "Trimestral", "#fd7e14", "Relatório trimestral", "frequency"),
            Tag("annual", "Anual", "#6f42c1", "Relatório anual", "frequency"),
            
            # Tags de Origem
            Tag("automated_scan", "Scan Automatizado", "#6c757d", "Gerado por scan automatizado", "source"),
            Tag("manual_test", "Teste Manual", "#007bff", "Teste manual de segurança", "source"),
            Tag("third_party", "Terceiros", "#fd7e14", "Avaliação por terceiros", "source"),
            Tag("internal_audit", "Auditoria Interna", "#28a745", "Auditoria interna", "source")
        ]
        
        for tag in predefined_tags:
            tag.created_at = datetime.now()
            tags[tag.id] = tag
            
        return tags
    
    def get_badges_for_report(self, report) -> List[Badge]:
        """Obtém badges aplicáveis a um relatório"""
        badges = []
        
        try:
            # Badges automáticos baseados em condições
            auto_badges = self._get_automatic_badges(report)
            badges.extend(auto_badges)
            
            # Badges baseados no tipo de relatório
            type_badges = self._get_type_based_badges(report)
            badges.extend(type_badges)
            
            # Badges baseados no status
            status_badges = self._get_status_badges(report)
            badges.extend(status_badges)
            
            # Badges customizados do relatório
            if hasattr(report, 'custom_badges') and report.custom_badges:
                custom_badges = self._get_custom_badges(report.custom_badges)
                badges.extend(custom_badges)
                
        except Exception as e:
            logger.error(f"Erro ao obter badges para relatório {report.id}: {str(e)}")
            
        return badges
    
    def _get_automatic_badges(self, report) -> List[Badge]:
        """Obtém badges automáticos baseados em condições"""
        badges = []
        
        try:
            # Calcular métricas do relatório
            metrics = self._calculate_report_metrics(report)
            
            # Verificar condições para badges automáticos
            for badge_id, badge in self.predefined_badges.items():
                if badge.auto_assign and badge.conditions:
                    if self._check_badge_conditions(metrics, badge.conditions):
                        badges.append(badge)
                        
        except Exception as e:
            logger.warning(f"Erro ao calcular badges automáticos: {str(e)}")
            
        return badges
    
    def _get_type_based_badges(self, report) -> List[Badge]:
        """Obtém badges baseados no tipo de relatório"""
        badges = []
        
        type_mapping = {
            'pentest': ['pentest'],
            'vulnerability_scan': ['vulnerability_scan'],
            'compliance': ['compliance_audit'],
            'risk_assessment': ['risk_assessment'],
            'incident': ['incident_response'],
            'estudo_tecnico': ['technical_analysis']
        }
        
        report_type = report.report_type.value if hasattr(report.report_type, 'value') else str(report.report_type)
        badge_ids = type_mapping.get(report_type, [])
        
        for badge_id in badge_ids:
            if badge_id in self.predefined_badges:
                badges.append(self.predefined_badges[badge_id])
                
        return badges
    
    def _get_status_badges(self, report) -> List[Badge]:
        """Obtém badges baseados no status do relatório"""
        badges = []
        
        status_mapping = {
            'completed': 'completed',
            'processing': 'processing',
            'failed': 'failed',
            'pending': 'pending'
        }
        
        report_status = report.status.value if hasattr(report.status, 'value') else str(report.status)
        badge_id = status_mapping.get(report_status)
        
        if badge_id and badge_id in self.predefined_badges:
            badges.append(self.predefined_badges[badge_id])
            
        return badges
    
    def _get_custom_badges(self, custom_badge_ids: List[str]) -> List[Badge]:
        """Obtém badges customizados"""
        badges = []
        
        for badge_id in custom_badge_ids:
            if badge_id in self.predefined_badges:
                badges.append(self.predefined_badges[badge_id])
                
        return badges
    
    def _calculate_report_metrics(self, report) -> Dict[str, Any]:
        """Calcula métricas do relatório para avaliação de badges"""
        metrics = {
            'critical_vulns': 0,
            'high_vulns': 0,
            'medium_vulns': 0,
            'low_vulns': 0,
            'total_vulns': 0,
            'avg_cvss': 0.0,
            'has_ai_analysis': False,
            'has_manual_review': False,
            'compliance_frameworks': [],
            'asset_count': 0
        }
        
        try:
            if report.content and hasattr(report.content, 'vulnerabilities'):
                vulns = report.content.vulnerabilities
                if isinstance(vulns, dict) and 'details' in vulns:
                    vuln_list = vulns['details']
                    metrics['total_vulns'] = len(vuln_list)
                    
                    cvss_scores = []
                    for vuln in vuln_list:
                        severity = vuln.get('severity', '').lower()
                        if severity == 'critical':
                            metrics['critical_vulns'] += 1
                        elif severity == 'high':
                            metrics['high_vulns'] += 1
                        elif severity == 'medium':
                            metrics['medium_vulns'] += 1
                        elif severity == 'low':
                            metrics['low_vulns'] += 1
                            
                        if vuln.get('cvss_score'):
                            cvss_scores.append(float(vuln['cvss_score']))
                    
                    if cvss_scores:
                        metrics['avg_cvss'] = sum(cvss_scores) / len(cvss_scores)
            
            # Verificar se tem análise de IA
            if hasattr(report, 'ai_analysis') and report.ai_analysis:
                metrics['has_ai_analysis'] = True
                
            # Verificar frameworks de compliance
            if hasattr(report, 'compliance_frameworks'):
                metrics['compliance_frameworks'] = report.compliance_frameworks or []
                
        except Exception as e:
            logger.warning(f"Erro ao calcular métricas: {str(e)}")
            
        return metrics
    
    def _check_badge_conditions(self, metrics: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Verifica se as condições do badge são atendidas"""
        try:
            for field, condition in conditions.items():
                if field not in metrics:
                    return False
                    
                value = metrics[field]
                
                if isinstance(condition, dict):
                    # Operadores MongoDB-style
                    for operator, expected in condition.items():
                        if operator == '$gt' and not (value > expected):
                            return False
                        elif operator == '$gte' and not (value >= expected):
                            return False
                        elif operator == '$lt' and not (value < expected):
                            return False
                        elif operator == '$lte' and not (value <= expected):
                            return False
                        elif operator == '$eq' and not (value == expected):
                            return False
                        elif operator == '$ne' and not (value != expected):
                            return False
                        elif operator == '$in' and value not in expected:
                            return False
                        elif operator == '$nin' and value in expected:
                            return False
                else:
                    # Comparação direta
                    if value != condition:
                        return False
                        
            return True
            
        except Exception as e:
            logger.warning(f"Erro ao verificar condições do badge: {str(e)}")
            return False
    
    def get_suggested_tags(self, report) -> List[Tag]:
        """Sugere tags baseadas no conteúdo do relatório"""
        suggested_tags = []
        
        try:
            # Tags baseadas no tipo de relatório
            type_tags = self._get_type_tags(report)
            suggested_tags.extend(type_tags)
            
            # Tags baseadas no conteúdo
            content_tags = self._get_content_based_tags(report)
            suggested_tags.extend(content_tags)
            
            # Tags baseadas em compliance
            compliance_tags = self._get_compliance_tags(report)
            suggested_tags.extend(compliance_tags)
            
            # Tags baseadas na frequência
            frequency_tags = self._get_frequency_tags(report)
            suggested_tags.extend(frequency_tags)
            
        except Exception as e:
            logger.error(f"Erro ao sugerir tags: {str(e)}")
            
        return suggested_tags
    
    def _get_type_tags(self, report) -> List[Tag]:
        """Obtém tags baseadas no tipo de relatório"""
        tags = []
        
        type_mapping = {
            'pentest': ['pentest', 'manual_test'],
            'vulnerability_scan': ['vulnerability_scan', 'automated_scan'],
            'compliance': ['compliance_audit', 'internal_audit'],
            'executive': ['business_critical'],
            'technical': ['automated_scan'],
            'estudo_tecnico': ['technical_analysis', 'deep_analysis']
        }
        
        report_type = report.report_type.value if hasattr(report.report_type, 'value') else str(report.report_type)
        tag_ids = type_mapping.get(report_type, [])
        
        for tag_id in tag_ids:
            if tag_id in self.predefined_tags:
                tags.append(self.predefined_tags[tag_id])
                
        return tags
    
    def _get_content_based_tags(self, report) -> List[Tag]:
        """Obtém tags baseadas no conteúdo do relatório"""
        tags = []
        
        try:
            # Analisar título e descrição para palavras-chave
            text_content = f"{report.title} {report.description or ''}".lower()
            
            keyword_mapping = {
                'web': ['web_app'],
                'database': ['database'],
                'network': ['network'],
                'cloud': ['cloud'],
                'mobile': ['mobile'],
                'iot': ['iot'],
                'server': ['server'],
                'firewall': ['firewall'],
                'production': ['production'],
                'staging': ['staging'],
                'development': ['development']
            }
            
            for keyword, tag_ids in keyword_mapping.items():
                if keyword in text_content:
                    for tag_id in tag_ids:
                        if tag_id in self.predefined_tags:
                            tags.append(self.predefined_tags[tag_id])
                            
        except Exception as e:
            logger.warning(f"Erro ao analisar conteúdo para tags: {str(e)}")
            
        return tags
    
    def _get_compliance_tags(self, report) -> List[Tag]:
        """Obtém tags baseadas em frameworks de compliance"""
        tags = []
        
        try:
            if hasattr(report, 'compliance_frameworks') and report.compliance_frameworks:
                framework_mapping = {
                    'pci_dss': ['pci_scope'],
                    'gdpr': ['gdpr_data'],
                    'iso27001': ['iso27001'],
                    'nist': ['nist'],
                    'hipaa': ['healthcare']
                }
                
                for framework in report.compliance_frameworks:
                    framework_lower = framework.lower()
                    for fw_key, tag_ids in framework_mapping.items():
                        if fw_key in framework_lower:
                            for tag_id in tag_ids:
                                if tag_id in self.predefined_tags:
                                    tags.append(self.predefined_tags[tag_id])
                                    
        except Exception as e:
            logger.warning(f"Erro ao obter tags de compliance: {str(e)}")
            
        return tags
    
    def _get_frequency_tags(self, report) -> List[Tag]:
        """Obtém tags baseadas na frequência do relatório"""
        tags = []
        
        try:
            if hasattr(report, 'schedule') and report.schedule:
                schedule_mapping = {
                    'daily': ['daily'],
                    'weekly': ['weekly'],
                    'monthly': ['monthly'],
                    'quarterly': ['quarterly'],
                    'annual': ['annual']
                }
                
                schedule_lower = report.schedule.lower()
                for schedule_key, tag_ids in schedule_mapping.items():
                    if schedule_key in schedule_lower:
                        for tag_id in tag_ids:
                            if tag_id in self.predefined_tags:
                                tags.append(self.predefined_tags[tag_id])
                                
        except Exception as e:
            logger.warning(f"Erro ao obter tags de frequência: {str(e)}")
            
        return tags
    
    def create_custom_badge(self, label: str, badge_type: BadgeType, 
                           style: BadgeStyle, icon: Optional[str] = None,
                           description: Optional[str] = None) -> Badge:
        """Cria um badge customizado"""
        badge_id = f"custom_{label.lower().replace(' ', '_')}"
        
        badge = Badge(
            id=badge_id,
            label=label,
            type=badge_type,
            style=style,
            icon=icon,
            description=description,
            auto_assign=False,
            created_at=datetime.now()
        )
        
        return badge
    
    def create_custom_tag(self, name: str, color: str, 
                         description: Optional[str] = None,
                         category: Optional[str] = None) -> Tag:
        """Cria uma tag customizada"""
        tag_id = f"custom_{name.lower().replace(' ', '_')}"
        
        tag = Tag(
            id=tag_id,
            name=name,
            color=color,
            description=description,
            category=category,
            usage_count=0,
            created_at=datetime.now()
        )
        
        return tag
    
    def get_badge_html(self, badge: Badge) -> str:
        """Gera HTML para exibição do badge"""
        icon_html = f'<i class="{badge.icon} me-1"></i>' if badge.icon else ''
        
        return f'''
        <span class="badge bg-{badge.style.value} me-1" 
              title="{badge.description or badge.label}"
              data-bs-toggle="tooltip">
            {icon_html}{badge.label}
        </span>
        '''
    
    def get_tag_html(self, tag: Tag) -> str:
        """Gera HTML para exibição da tag"""
        return f'''
        <span class="badge me-1" 
              style="background-color: {tag.color}; color: white;"
              title="{tag.description or tag.name}"
              data-bs-toggle="tooltip">
            {tag.name}
        </span>
        '''
    
    def get_all_predefined_badges(self) -> Dict[str, Badge]:
        """Retorna todos os badges predefinidos"""
        return self.predefined_badges.copy()
    
    def get_all_predefined_tags(self) -> Dict[str, Tag]:
        """Retorna todas as tags predefinidas"""
        return self.predefined_tags.copy()
    
    def get_badges_by_type(self, badge_type: BadgeType) -> List[Badge]:
        """Retorna badges filtrados por tipo"""
        return [badge for badge in self.predefined_badges.values() 
                if badge.type == badge_type]
    
    def get_tags_by_category(self, category: str) -> List[Tag]:
        """Retorna tags filtradas por categoria"""
        return [tag for tag in self.predefined_tags.values() 
                if tag.category == category]