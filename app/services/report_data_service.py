# services/report_data_service.py

"""
Service para compilação de dados para relatórios de cybersegurança.
Responsável por coletar e processar dados de ativos, vulnerabilidades, CVEs, etc.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from sqlalchemy import func, and_, or_, desc, asc, text
from sqlalchemy.orm import Session, joinedload, selectinload
from app.extensions import db
from app.models.asset import Asset
from app.models.vulnerability import Vulnerability
from app.models.asset_vulnerability import AssetVulnerability
from app.models.weakness import Weakness
from app.models.cve_product import CVEProduct
from app.models.product import Product

from app.models.risk_assessment import RiskAssessment
from app.models.cvss_metric import CVSSMetric
from app.models.references import Reference
from app.models.user import User
from app.models.enums import severity_levels, asset_vuln_status
from app.models.version_reference import VersionReference
from app.models.affected_product import AffectedProduct
from app.models.asset_product import AssetProduct
import logging
import json

logger = logging.getLogger(__name__)


class ReportDataService:
    """Service para compilação de dados para relatórios."""
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or db.session
    
    def compile_asset_data(self, 
                          asset_ids: Optional[List[int]] = None,
                          tags: Optional[List[str]] = None,
                          groups: Optional[List[str]] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Compila dados de ativos baseado nos filtros fornecidos.
        
        Args:
            asset_ids: Lista de IDs específicos de ativos
            tags: Lista de tags para filtrar ativos
            groups: Lista de grupos para filtrar ativos
            start_date: Data de início para filtros temporais
            end_date: Data de fim para filtros temporais
            
        Returns:
            Dicionário com dados compilados dos ativos
        """
        try:
            # Query base para ativos
            query = self.session.query(Asset).options(
                joinedload(Asset.owner),
                selectinload(Asset.vulnerabilities).joinedload(AssetVulnerability.vulnerability),
                selectinload(Asset.risk_assessments)
            )
            
            # Aplicar filtros
            if asset_ids:
                query = query.filter(Asset.id.in_(asset_ids))
            
            # TODO: Implementar filtros por tags e grupos quando os campos estiverem disponíveis
            # if tags:
            #     query = query.filter(Asset.tags.any(Tag.name.in_(tags)))
            # if groups:
            #     query = query.filter(Asset.group_id.in_(groups))
            
            if start_date:
                query = query.filter(Asset.created_at >= start_date)
            if end_date:
                query = query.filter(Asset.created_at <= end_date)
            
            assets = query.all()
            
            # Compilar estatísticas
            total_assets = len(assets)
            assets_by_status = {}
            assets_with_vulnerabilities = 0
            total_vulnerabilities = 0
            asset_details: List[Dict[str, Any]] = []
            
            for asset in assets:
                # Contar por status
                status = asset.status or 'unknown'
                assets_by_status[status] = assets_by_status.get(status, 0) + 1
                
                # Contar vulnerabilidades
                vuln_count = len(asset.vulnerabilities)
                if vuln_count > 0:
                    assets_with_vulnerabilities += 1
                    total_vulnerabilities += vuln_count

                # Severidade agregada por ativo
                sev_counts = {'Critical': 0, 'High': 0, 'Medium': 0, 'Low': 0, 'Unknown': 0}
                for av in asset.vulnerabilities:
                    try:
                        sev = (av.vulnerability.base_severity or 'Unknown').capitalize()
                    except Exception:
                        sev = 'Unknown'
                    if sev not in sev_counts:
                        sev = 'Unknown'
                    sev_counts[sev] += 1

                # Heurística simples de criticidade
                criticality = 'LOW'
                if sev_counts['Critical'] > 0:
                    criticality = 'HIGH'
                elif sev_counts['High'] >= 3:
                    criticality = 'HIGH'
                elif (sev_counts['High'] + sev_counts['Medium']) > 0:
                    criticality = 'MEDIUM'

                # Montar detalhes do ativo usados na BIA
                asset_details.append({
                    'id': asset.id,
                    'name': asset.name,
                    'ip_address': asset.ip_address,
                    'status': asset.status,
                    'vendor_name': getattr(asset.vendor, 'name', None),
                    'criticality': criticality,
                    'severity_breakdown': sev_counts,
                    'type': 'asset',
                    # BIA Fields
                    'rto_hours': asset.rto_hours,
                    'rpo_hours': asset.rpo_hours,
                    'uptime_text': asset.uptime_text,
                    'operational_cost_per_hour': asset.operational_cost_per_hour,
                })
            
            return {
                'assets': assets,
                'total_assets': total_assets,
                'assets_by_status': assets_by_status,
                'assets_with_vulnerabilities': assets_with_vulnerabilities,
                'total_vulnerabilities': total_vulnerabilities,
                'vulnerability_coverage': (assets_with_vulnerabilities / total_assets * 100) if total_assets > 0 else 0,
                'asset_details': asset_details
            }

        except Exception as e:
            logger.error(f"Erro ao compilar dados de ativos: {e}")
            raise
    
    def compile_vulnerability_data(self,
                                 asset_ids: Optional[List[int]] = None,
                                 severity_levels: Optional[List[str]] = None,
                                 start_date: Optional[datetime] = None,
                                 end_date: Optional[datetime] = None,
                                 include_cisa_kev: bool = True,
                                 include_epss: bool = True,
                                 vendor_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Compila dados de vulnerabilidades com enriquecimento CISA KEV e EPSS.
        
        Args:
            asset_ids: Lista de IDs de ativos para filtrar
            severity_levels: Lista de níveis de severidade
            start_date: Data de início para filtros temporais
            end_date: Data de fim para filtros temporais
            include_cisa_kev: Incluir dados CISA KEV
            include_epss: Incluir dados EPSS
            
        Returns:
            Dicionário com dados compilados das vulnerabilidades
        """
        try:
            # Query base para vulnerabilidades
            query = self.session.query(Vulnerability).options(
                selectinload(Vulnerability.metrics),
                selectinload(Vulnerability.weaknesses),
                selectinload(Vulnerability.references),
                selectinload(Vulnerability.assets).joinedload(AssetVulnerability.asset),
                selectinload(Vulnerability.products).joinedload(CVEProduct.product).joinedload(Product.vendor),
                selectinload(Vulnerability.vendors),
                selectinload(Vulnerability.version_references).joinedload(VersionReference.product),
                selectinload(Vulnerability.affected_products).joinedload(AffectedProduct.product)
            )
            
            # Aplicar filtros
            if asset_ids:
                query = query.join(AssetVulnerability).filter(
                    AssetVulnerability.asset_id.in_(asset_ids)
                )
            
            if severity_levels:
                query = query.filter(Vulnerability.base_severity.in_(severity_levels))
            
            if start_date:
                query = query.filter(Vulnerability.published_date >= start_date)
            if end_date:
                query = query.filter(Vulnerability.published_date <= end_date)
            
            # Filtro por vendor quando fornecido
            if vendor_name:
                try:
                    from sqlalchemy import union
                    from app.models.cve_vendor import CVEVendor
                    from app.models.vendor import Vendor
                    vn = (vendor_name or '').strip().lower()
                    cves_por_vendor = (
                        self.session
                        .query(CVEVendor.cve_id)
                        .join(Vendor, Vendor.id == CVEVendor.vendor_id)
                        .filter(func.lower(Vendor.name) == vn)
                    )
                    cves_por_produto_vendor = (
                        self.session
                        .query(CVEProduct.cve_id)
                        .join(Product, Product.id == CVEProduct.product_id)
                        .join(Vendor, Vendor.id == Product.vendor_id)
                        .filter(func.lower(Vendor.name) == vn)
                    )
                    unificados = union(cves_por_vendor, cves_por_produto_vendor).subquery()
                    query = query.filter(Vulnerability.cve_id.in_(unificados))
                except Exception:
                    pass

            vulnerabilities = query.all()

            # Listas de detalhes para exibição e IA
            details: List[Dict[str, Any]] = []
            cve_details: List[Dict[str, Any]] = []
            
            # Compilar estatísticas básicas
            total_vulnerabilities = len(vulnerabilities)
            by_severity = {}
            cvss_scores = []
            cwe_distribution = {}
            patch_coverage = {'patched': 0, 'unpatched': 0, 'unknown': 0}
            
            # Dados enriquecidos
            cisa_kev_data = {'total': 0, 'overdue': 0, 'upcoming_due': 0, 'actions': {}}
            epss_data = {'scores': [], 'high_probability': 0, 'percentiles': []}
            vendor_product_data = {'vendors': set(), 'products': set(), 'top_vendors': {}, 'top_products': {}, 'vendor_products': {}}
            cvss_detailed = {'v2': 0, 'v3_0': 0, 'v3_1': 0, 'v4_0': 0, 'metrics_distribution': {}}
            version_mappings: List[Dict[str, Any]] = []
            fortios_histogram = {'counts': {}}
            fortios_installed_histogram = {'counts': {}}

            # KPIs de Remediação/SLA
            remediation_kpis = {
                'mttr_days': 0.0,
                'remediation_rate_pct': 0.0,
                'sla_compliance_pct': 0.0,
                'backlog_over_sla': 0,
                'sla_thresholds_days': {
                    'CRITICAL': 15,
                    'HIGH': 30,
                    'MEDIUM': 60,
                    'LOW': 90
                },
                'status_counts': {
                    'OPEN': 0,
                    'MITIGATED': 0,
                    'CLOSED': 0
                }
            }

            # Coletar dados de AssetVulnerability para calcular MTTR e SLA
            try:
                av_query = self.session.query(AssetVulnerability).join(Vulnerability)
                if asset_ids:
                    av_query = av_query.filter(AssetVulnerability.asset_id.in_(asset_ids))
                if severity_levels:
                    av_query = av_query.filter(Vulnerability.base_severity.in_(severity_levels))
                if start_date:
                    av_query = av_query.filter(AssetVulnerability.created_at >= start_date)
                if end_date:
                    av_query = av_query.filter(AssetVulnerability.created_at <= end_date)

                asset_vulns = av_query.options(joinedload(AssetVulnerability.vulnerability)).all()

                total_av = len(asset_vulns)
                if total_av > 0:
                    resolved_statuses = {'MITIGATED', 'CLOSED'}
                    resolved_count = 0
                    sla_compliant_count = 0
                    backlog_over_sla = 0
                    mttr_accum_days = 0.0

                    now_dt = datetime.utcnow()
                    thresholds = remediation_kpis['sla_thresholds_days']

                    for av in asset_vulns:
                        # Contagem por status
                        status_val = (av.status or 'OPEN')
                        remediation_kpis['status_counts'][status_val] = remediation_kpis['status_counts'].get(status_val, 0) + 1

                        sev = None
                        try:
                            sev = (getattr(av.vulnerability, 'base_severity', None) or 'UNKNOWN').upper()
                        except Exception:
                            sev = 'UNKNOWN'

                        created = av.created_at or av.updated_at
                        mitigated = av.mitigation_date

                        if status_val in resolved_statuses and mitigated and created:
                            # MTTR
                            delta_days = max((mitigated - created).total_seconds() / 86400.0, 0)
                            mttr_accum_days += delta_days
                            resolved_count += 1

                            # SLA compliance (por severidade)
                            thr = thresholds.get(sev)
                            if thr is not None and (delta_days <= float(thr)):
                                sla_compliant_count += 1

                        elif status_val == 'OPEN' and created:
                            # Backlog fora do SLA
                            age_days = max((now_dt - created).total_seconds() / 86400.0, 0)
                            thr = thresholds.get(sev)
                            if thr is not None and (age_days > float(thr)):
                                backlog_over_sla += 1

                    # Finalizar KPIs
                    remediation_kpis['backlog_over_sla'] = backlog_over_sla
                    if resolved_count > 0:
                        remediation_kpis['mttr_days'] = round(mttr_accum_days / resolved_count, 1)
                        remediation_kpis['sla_compliance_pct'] = round((sla_compliant_count / resolved_count) * 100.0, 1)
                    remediation_kpis['remediation_rate_pct'] = round((resolved_count / total_av) * 100.0, 1)
            except Exception as e:
                logger.warning(f"Falha ao calcular KPIs de remediação/SLA: {e}")

            for vuln in vulnerabilities:
                # Severidade
                severity = vuln.base_severity or 'UNKNOWN'
                by_severity[severity] = by_severity.get(severity, 0) + 1
                
                # CVSS Score
                if vuln.cvss_score:
                    cvss_scores.append(vuln.cvss_score)
                
                # CWE Distribution
                for weakness in vuln.weaknesses:
                    cwe_id = weakness.cwe_id
                    cwe_distribution[cwe_id] = cwe_distribution.get(cwe_id, 0) + 1
                
                # Patch Coverage
                if vuln.patch_available is True:
                    patch_coverage['patched'] += 1
                elif vuln.patch_available is False:
                    patch_coverage['unpatched'] += 1
                else:
                    patch_coverage['unknown'] += 1
                
                # CISA KEV Data
                if include_cisa_kev and vuln.cisa_kev_data:
                    cisa_kev_data['total'] += 1
                    
                    # Verificar datas de vencimento
                    if vuln.cisa_due_date:
                        today = datetime.now().date()
                        due_date = vuln.cisa_due_date
                        
                        if due_date < today:
                            cisa_kev_data['overdue'] += 1
                        elif due_date <= today + timedelta(days=30):
                            cisa_kev_data['upcoming_due'] += 1
                    
                    # Ações requeridas
                    if vuln.cisa_required_action:
                        action = vuln.cisa_required_action
                        cisa_kev_data['actions'][action] = cisa_kev_data['actions'].get(action, 0) + 1
                
                # EPSS Data
                if include_epss and vuln.epss_score is not None:
                    epss_data['scores'].append(vuln.epss_score)
                    if vuln.epss_percentile is not None:
                        epss_data['percentiles'].append(vuln.epss_percentile)
                    
                    # Alta probabilidade de exploração (EPSS > 0.7)
                    if vuln.epss_score > 0.7:
                        epss_data['high_probability'] += 1
                
                # Vendor/Product Data
                if vuln.nvd_vendors_data:
                    try:
                        vendors = json.loads(vuln.nvd_vendors_data) if isinstance(vuln.nvd_vendors_data, str) else vuln.nvd_vendors_data
                        for vendor in vendors:
                            vendor_product_data['vendors'].add(vendor)
                            vendor_product_data['top_vendors'][vendor] = vendor_product_data['top_vendors'].get(vendor, 0) + 1
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                if vuln.nvd_products_data:
                    try:
                        products = json.loads(vuln.nvd_products_data) if isinstance(vuln.nvd_products_data, str) else vuln.nvd_products_data
                        for product in products:
                            vendor_product_data['products'].add(product)
                            vendor_product_data['top_products'][product] = vendor_product_data['top_products'].get(product, 0) + 1
                    except (json.JSONDecodeError, TypeError):
                        pass

                try:
                    for cp in getattr(vuln, 'products', []) or []:
                        prod = getattr(cp, 'product', None)
                        if not prod:
                            continue
                        vname = getattr(getattr(prod, 'vendor', None), 'name', None)
                        pname = getattr(prod, 'name', None)
                        if not vname or not pname:
                            continue
                        vp = vendor_product_data['vendor_products'].get(vname) or {}
                        entry = vp.get(pname) or {'count': 0, 'cves': []}
                        entry['count'] = int(entry['count']) + 1
                        cve_id_val = getattr(vuln, 'cve_id', None)
                        if cve_id_val:
                            entry['cves'].append(cve_id_val)
                        vp[pname] = entry
                        vendor_product_data['vendor_products'][vname] = vp
                except Exception:
                    pass
                
                # CVSS Detailed Metrics
                for metric in vuln.metrics:
                    version = metric.cvss_version
                    if version == '2.0':
                        cvss_detailed['v2'] += 1
                    elif version == '3.0':
                        cvss_detailed['v3_0'] += 1
                    elif version == '3.1':
                        cvss_detailed['v3_1'] += 1
                    elif version == '4.0':
                        cvss_detailed['v4_0'] += 1
                    
                    # Distribuição de métricas
                    if metric.base_score:
                        score_range = self._get_score_range(metric.base_score)
                        cvss_detailed['metrics_distribution'][score_range] = cvss_detailed['metrics_distribution'].get(score_range, 0) + 1

                # Construir detalhes para visualização
                try:
                    affected_assets: List[Dict[str, Any]] = []
                    for av in getattr(vuln, 'assets', []) or []:
                        asset = getattr(av, 'asset', None)
                        if asset:
                            affected_assets.append({
                                'name': getattr(asset, 'name', None),
                                'ip_address': getattr(asset, 'ip_address', None),
                                # O template espera status.value; fornecer objeto-like com 'value'
                                'status': ({'value': getattr(av, 'status', None)} if getattr(av, 'status', None) is not None else None)
                            })

                    details.append({
                        'cve_id': getattr(vuln, 'cve_id', None),
                        'title': getattr(vuln, 'title', None),
                        'description': getattr(vuln, 'description', ''),
                        'severity': (getattr(vuln, 'base_severity', 'UNKNOWN') or 'UNKNOWN').lower(),
                        'cvss_score': getattr(vuln, 'cvss_score', None),
                        'published_date': getattr(vuln, 'published_date', None),
                        'last_modified': getattr(vuln, 'last_update', None),
                        'affected_assets': affected_assets
                    })

                    cve_details.append({
                        'cve_id': getattr(vuln, 'cve_id', None),
                        'description': getattr(vuln, 'description', '')
                    })
                except Exception:
                    # Em caso de qualquer falha ao compor detalhes individuais, seguir processamento geral
                    pass

                try:
                    for vr in getattr(vuln, 'version_references', []) or []:
                        prod = getattr(vr, 'product', None)
                        pname = getattr(prod, 'name', '') if prod else ''
                        vendor = getattr(getattr(prod, 'vendor', None), 'name', '') if prod else ''
                        entry = {
                            'cve_id': getattr(vuln, 'cve_id', None),
                            'vendor': vendor,
                            'product': pname,
                            'affected_version': getattr(vr, 'affected_version', None),
                            'fixed_version': getattr(vr, 'fixed_version', None),
                            'patch_available': getattr(vuln, 'patch_available', None)
                        }
                        version_mappings.append(entry)

                        try:
                            if pname and ('fortios' in pname.lower()) and (vuln.patch_available is False):
                                av = str(getattr(vr, 'affected_version', '') or '').strip()
                                if av:
                                    fortios_histogram['counts'][av] = int(fortios_histogram['counts'].get(av, 0) or 0) + 1
                        except Exception:
                            pass
                except Exception:
                    pass

                try:
                    if vuln.patch_available is False:
                        for av in getattr(vuln, 'assets', []) or []:
                            asset = getattr(av, 'asset', None)
                            if not asset:
                                continue
                            for ap in getattr(asset, 'asset_products', []) or []:
                                os_name = str(getattr(ap, 'operating_system', '') or '').lower()
                                ver = str(getattr(ap, 'installed_version', '') or '').strip()
                                if ('fortios' in os_name) and ver:
                                    fortios_installed_histogram['counts'][ver] = int(fortios_installed_histogram['counts'].get(ver, 0) or 0) + 1
                except Exception:
                    pass
            
            # Calcular estatísticas CVSS
            cvss_stats = {}
            if cvss_scores:
                cvss_stats = {
                    'mean': sum(cvss_scores) / len(cvss_scores),
                    'min': min(cvss_scores),
                    'max': max(cvss_scores),
                    'count': len(cvss_scores)
                }
            
            # Calcular estatísticas EPSS
            epss_stats = {}
            if epss_data['scores']:
                epss_stats = {
                    'mean': sum(epss_data['scores']) / len(epss_data['scores']),
                    'min': min(epss_data['scores']),
                    'max': max(epss_data['scores']),
                    'count': len(epss_data['scores']),
                    'high_probability_percentage': (epss_data['high_probability'] / len(epss_data['scores'])) * 100
                }
            
            # Top vendors e products
            vendor_product_data['top_vendors'] = dict(sorted(vendor_product_data['top_vendors'].items(), key=lambda x: x[1], reverse=True)[:10])
            vendor_product_data['top_products'] = dict(sorted(vendor_product_data['top_products'].items(), key=lambda x: x[1], reverse=True)[:10])
            vendor_product_data['vendors'] = len(vendor_product_data['vendors'])
            vendor_product_data['products'] = len(vendor_product_data['products'])
            
            return {
                'vulnerabilities': vulnerabilities,
                'total_vulnerabilities': total_vulnerabilities,
                'by_severity': by_severity,
                'cvss_stats': cvss_stats,
                'cvss_detailed': cvss_detailed,
                'cwe_distribution': cwe_distribution,
                'patch_coverage': patch_coverage,
                'cisa_kev_data': cisa_kev_data,
                'epss_data': epss_data,
                'epss_stats': epss_stats,
                'vendor_product_data': vendor_product_data,
                'version_mappings': version_mappings,
                'fortios_histogram': fortios_histogram,
                'fortios_installed_histogram': fortios_installed_histogram,
                'remediation_kpis': remediation_kpis,
                # Estruturas esperadas pelos templates e serviços de IA
                'details': details,
                'cve_details': cve_details
            }
            
        except Exception as e:
            logger.error(f"Erro ao compilar dados de vulnerabilidades: {e}")
            return {}
    
    def _get_score_range(self, score: float) -> str:
        """Retorna a faixa de score CVSS."""
        if score < 4.0:
            return 'Low (0.0-3.9)'
        elif score < 7.0:
            return 'Medium (4.0-6.9)'
        elif score < 9.0:
            return 'High (7.0-8.9)'
        else:
            return 'Critical (9.0-10.0)'
    
    def compile_cisa_kev_analysis(self) -> Dict[str, Any]:
        """
        Compila análise específica de vulnerabilidades CISA KEV.
        
        Returns:
            Dicionário com análise detalhada CISA KEV
        """
        try:
            # Vulnerabilidades CISA KEV
            kev_vulns = self.session.query(Vulnerability).filter(
                Vulnerability.cisa_kev_data.isnot(None)
            ).options(
                selectinload(Vulnerability.assets).joinedload(AssetVulnerability.asset)
            ).all()
            
            today = datetime.now().date()
            analysis = {
                'total_kev': len(kev_vulns),
                'overdue': 0,
                'due_soon': 0,  # próximos 30 dias
                'due_later': 0,
                'no_due_date': 0,
                'by_severity': {},
                'by_action': {},
                'affected_assets': 0,
                'remediation_timeline': {},
                'compliance_status': 'non_compliant'  # compliant, partial, non_compliant
            }
            
            affected_assets = set()
            
            for vuln in kev_vulns:
                # Contagem por severidade
                severity = vuln.base_severity or 'UNKNOWN'
                analysis['by_severity'][severity] = analysis['by_severity'].get(severity, 0) + 1
                
                # Ações requeridas
                if vuln.cisa_required_action:
                    action = vuln.cisa_required_action
                    analysis['by_action'][action] = analysis['by_action'].get(action, 0) + 1
                
                # Análise de datas de vencimento
                if vuln.cisa_due_date:
                    # Converter para date de forma resiliente (aceita date, datetime ou string ISO)
                    try:
                        raw_due = vuln.cisa_due_date
                        if isinstance(raw_due, datetime):
                            due_date = raw_due.date()
                        elif hasattr(raw_due, 'strftime') and hasattr(raw_due, 'year'):
                            # Já é um date
                            due_date = raw_due
                        elif isinstance(raw_due, str):
                            try:
                                # Tenta ISO completo
                                due_dt = datetime.fromisoformat(raw_due.replace('Z', '+00:00'))
                                due_date = due_dt.date()
                            except Exception:
                                # Tenta apenas a parte de data
                                from datetime import datetime as _dt
                                due_date = _dt.strptime(raw_due[:10], '%Y-%m-%d').date()
                        else:
                            due_date = raw_due

                        days_until_due = (due_date - today).days

                        if days_until_due < 0:
                            analysis['overdue'] += 1
                        elif days_until_due <= 30:
                            analysis['due_soon'] += 1
                        else:
                            analysis['due_later'] += 1

                        # Timeline de remediação
                        month_key = due_date.strftime('%Y-%m') if hasattr(due_date, 'strftime') else str(due_date)[:7]
                        analysis['remediation_timeline'][month_key] = analysis['remediation_timeline'].get(month_key, 0) + 1
                    except Exception as _e:
                        logger.warning(f"Falha ao processar cisa_due_date '{vuln.cisa_due_date}': {_e}")
                        analysis['no_due_date'] += 1
                else:
                    analysis['no_due_date'] += 1
                
                # Ativos afetados
                for asset_vuln in vuln.assets:
                    affected_assets.add(asset_vuln.asset_id)
            
            analysis['affected_assets'] = len(affected_assets)
            
            # Status de compliance
            if analysis['overdue'] == 0:
                if analysis['due_soon'] == 0:
                    analysis['compliance_status'] = 'compliant'
                else:
                    analysis['compliance_status'] = 'partial'
            else:
                analysis['compliance_status'] = 'non_compliant'
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro ao compilar análise CISA KEV: {e}")
            return {}
    
    def compile_epss_analysis(self) -> Dict[str, Any]:
        """
        Compila análise específica de scores EPSS.
        
        Returns:
            Dicionário com análise detalhada EPSS
        """
        try:
            # Vulnerabilidades com dados EPSS
            epss_vulns = self.session.query(Vulnerability).filter(
                Vulnerability.epss_score.isnot(None)
            ).options(
                selectinload(Vulnerability.assets).joinedload(AssetVulnerability.asset)
            ).all()
            
            analysis = {
                'total_with_epss': len(epss_vulns),
                'score_distribution': {
                    'very_low': 0,    # 0.0-0.1
                    'low': 0,         # 0.1-0.3
                    'medium': 0,      # 0.3-0.7
                    'high': 0,        # 0.7-0.9
                    'very_high': 0    # 0.9-1.0
                },
                'percentile_distribution': {
                    'bottom_25': 0,
                    'middle_50': 0,
                    'top_25': 0,
                    'top_10': 0,
                    'top_1': 0
                },
                'high_risk_vulns': [],  # EPSS > 0.7 e CVSS > 7.0
                'priority_vulns': [],   # Top 10% EPSS e CISA KEV
                'exploitation_trends': {},
                'affected_assets_high_risk': 0
            }
            
            high_risk_assets = set()
            
            for vuln in epss_vulns:
                score = vuln.epss_score
                percentile = vuln.epss_percentile
                
                # Distribuição de scores
                if score <= 0.1:
                    analysis['score_distribution']['very_low'] += 1
                elif score <= 0.3:
                    analysis['score_distribution']['low'] += 1
                elif score <= 0.7:
                    analysis['score_distribution']['medium'] += 1
                elif score <= 0.9:
                    analysis['score_distribution']['high'] += 1
                else:
                    analysis['score_distribution']['very_high'] += 1
                
                # Distribuição de percentis
                if percentile:
                    if percentile >= 99:
                        analysis['percentile_distribution']['top_1'] += 1
                    elif percentile >= 90:
                        analysis['percentile_distribution']['top_10'] += 1
                    elif percentile >= 75:
                        analysis['percentile_distribution']['top_25'] += 1
                    elif percentile >= 25:
                        analysis['percentile_distribution']['middle_50'] += 1
                    else:
                        analysis['percentile_distribution']['bottom_25'] += 1
                
                # Vulnerabilidades de alto risco
                if score > 0.7 and vuln.cvss_score and vuln.cvss_score > 7.0:
                    analysis['high_risk_vulns'].append({
                        'cve_id': vuln.cve_id,
                        'epss_score': score,
                        'cvss_score': vuln.cvss_score,
                        'severity': vuln.base_severity,
                        'affected_assets': len(vuln.assets)
                    })
                    
                    # Contar ativos afetados por vulnerabilidades de alto risco
                    for asset_vuln in vuln.assets:
                        high_risk_assets.add(asset_vuln.asset_id)
                
                # Vulnerabilidades prioritárias (Top 10% EPSS + CISA KEV)
                if percentile and percentile >= 90 and vuln.cisa_kev_data:
                    analysis['priority_vulns'].append({
                        'cve_id': vuln.cve_id,
                        'epss_score': score,
                        'epss_percentile': percentile,
                        'cvss_score': vuln.cvss_score,
                        'cisa_due_date': vuln.cisa_due_date.isoformat() if vuln.cisa_due_date else None,
                        'affected_assets': len(vuln.assets)
                    })
            
            analysis['affected_assets_high_risk'] = len(high_risk_assets)
            
            # Ordenar listas por prioridade
            analysis['high_risk_vulns'].sort(key=lambda x: (x['epss_score'], x['cvss_score']), reverse=True)
            analysis['priority_vulns'].sort(key=lambda x: (x['epss_percentile'], x['epss_score']), reverse=True)
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erro ao compilar análise EPSS: {e}")
            return {}

    def compile_risk_data(self,
                         asset_ids: Optional[List[int]] = None,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Compila dados de avaliação de risco.
        
        Args:
            asset_ids: Lista de IDs de ativos
            start_date: Data de início
            end_date: Data de fim
            
        Returns:
            Dicionário com dados de risco compilados
        """
        try:
            # Query base para avaliações de risco
            query = self.session.query(RiskAssessment).options(
                joinedload(RiskAssessment.asset),
                joinedload(RiskAssessment.vulnerability),
                joinedload(RiskAssessment.user)
            )
            
            # Aplicar filtros
            if asset_ids:
                query = query.filter(RiskAssessment.asset_id.in_(asset_ids))
            
            if start_date:
                query = query.filter(RiskAssessment.created_at >= start_date)
            if end_date:
                query = query.filter(RiskAssessment.created_at <= end_date)
            
            risk_assessments = query.all()
            
            # Compilar estatísticas
            risk_scores = [ra.risk_score for ra in risk_assessments]
            
            risk_stats = {}
            if risk_scores:
                risk_stats = {
                    'mean': sum(risk_scores) / len(risk_scores),
                    'min': min(risk_scores),
                    'max': max(risk_scores),
                    'count': len(risk_scores)
                }
            
            # Distribuição de risco por asset
            risk_by_asset = {}
            for ra in risk_assessments:
                asset_id = ra.asset_id
                if asset_id not in risk_by_asset:
                    risk_by_asset[asset_id] = {
                        'asset': ra.asset,
                        'risk_scores': [],
                        'total_risk': 0
                    }
                risk_by_asset[asset_id]['risk_scores'].append(ra.risk_score)
                risk_by_asset[asset_id]['total_risk'] += ra.risk_score
            
            return {
                'risk_assessments': risk_assessments,
                'risk_statistics': risk_stats,
                'risk_by_asset': risk_by_asset,
                'total_assessments': len(risk_assessments),
                'overall_score': (risk_stats.get('mean') if risk_stats else 0)
            }
            
        except Exception as e:
            logger.error(f"Erro ao compilar dados de risco: {e}")
            raise
    
    def compile_timeline_data(self,
                           start_date: datetime,
                           end_date: datetime,
                           asset_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Compila dados de timeline para gráficos temporais.
        
        Args:
            start_date: Data de início
            end_date: Data de fim
            asset_ids: Lista de IDs de ativos (opcional)
            
        Returns:
            Dicionário com dados de timeline
        """
        try:
            # Vulnerabilidades por data
            vuln_query = self.session.query(
                func.date(Vulnerability.published_date).label('date'),
                func.count(Vulnerability.cve_id).label('count')
            ).filter(
                and_(
                    Vulnerability.published_date >= start_date,
                    Vulnerability.published_date <= end_date
                )
            )
            
            if asset_ids:
                vuln_query = vuln_query.join(AssetVulnerability).filter(
                    AssetVulnerability.asset_id.in_(asset_ids)
                )
            
            vuln_timeline = vuln_query.group_by(
                func.date(Vulnerability.published_date)
            ).order_by('date').all()
            
            # Avaliações de risco por data
            risk_query = self.session.query(
                func.date(RiskAssessment.created_at).label('date'),
                func.avg(RiskAssessment.risk_score).label('avg_risk'),
                func.count(RiskAssessment.id).label('count')
            ).filter(
                and_(
                    RiskAssessment.created_at >= start_date,
                    RiskAssessment.created_at <= end_date
                )
            )
            
            if asset_ids:
                risk_query = risk_query.filter(RiskAssessment.asset_id.in_(asset_ids))
            
            risk_timeline = risk_query.group_by(
                func.date(RiskAssessment.created_at)
            ).order_by('date').all()

            # Derivar KPI timeline alinhando datas no intervalo solicitado
            try:
                # Construir lista de labels (YYYY-MM-DD) para cada dia do intervalo
                total_days = (end_date.date() - start_date.date()).days
                labels = [
                    (start_date.date() + timedelta(days=i)).strftime('%Y-%m-%d')
                    for i in range(total_days + 1)
                ]

                # Mapear contagens de vulnerabilidades por data
                vt_map = {str(item.date): int(item.count) for item in vuln_timeline}
                # Mapear risco médio por data
                rt_map = {str(item.date): float(item.avg_risk) if item.avg_risk is not None else 0.0 for item in risk_timeline}

                vuln_counts = [vt_map.get(label, 0) for label in labels]
                avg_risk_values = [rt_map.get(label, 0.0) for label in labels]

                kpi_timeline = {
                    'labels': labels,
                    'kpis': [
                        {
                            'name': 'Vulnerabilidades publicadas',
                            'values': vuln_counts,
                            'fill': True
                        },
                        {
                            'name': 'Risco médio (avaliações)',
                            'values': avg_risk_values,
                            'fill': False
                        }
                    ]
                }
            except Exception as e:
                logger.warning(f"Falha ao derivar KPI timeline: {e}")
                kpi_timeline = {
                    'labels': [],
                    'kpis': []
                }

            return {
                'vulnerability_timeline': [
                    {'date': item.date, 'count': item.count}
                    for item in vuln_timeline
                ],
                'risk_timeline': [
                    {'date': item.date, 'avg_risk': float(item.avg_risk), 'count': item.count}
                    for item in risk_timeline
                ],
                'kpi_timeline': kpi_timeline
            }
            
        except Exception as e:
            logger.error(f"Erro ao compilar dados de timeline: {e}")
            raise
    
    def get_top_assets_by_risk(self,
                              limit: int = 10,
                              asset_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        """
        Obtém os ativos com maior risco.
        
        Args:
            limit: Número máximo de ativos a retornar
            asset_ids: Lista de IDs de ativos para filtrar
            
        Returns:
            Lista de ativos ordenados por risco
        """
        try:
            # Query para somar riscos por ativo
            query = self.session.query(
                Asset,
                func.sum(RiskAssessment.risk_score).label('total_risk'),
                func.count(RiskAssessment.id).label('risk_count')
            ).join(RiskAssessment).options(
                joinedload(Asset.owner)
            )
            
            if asset_ids:
                query = query.filter(Asset.id.in_(asset_ids))
            
            top_assets = query.group_by(Asset.id).order_by(
                desc('total_risk')
            ).limit(limit).all()
            
            return [
                {
                    'asset': asset,
                    'total_risk': float(total_risk),
                    'risk_count': risk_count,
                    'avg_risk': float(total_risk / risk_count) if risk_count > 0 else 0
                }
                for asset, total_risk, risk_count in top_assets
            ]
            
        except Exception as e:
            logger.error(f"Erro ao obter top ativos por risco: {e}")
            raise
    
    def get_vulnerability_trends(self,
                               days: int = 30,
                               asset_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        """
        Obtém tendências de vulnerabilidades nos últimos dias.
        
        Args:
            days: Número de dias para análise
            asset_ids: Lista de IDs de ativos
            
        Returns:
            Dicionário com dados de tendências
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Vulnerabilidades por dia
            query = self.session.query(
                func.date(Vulnerability.published_date).label('date'),
                func.count(Vulnerability.cve_id).label('count'),
                Vulnerability.base_severity
            ).filter(
                and_(
                    Vulnerability.published_date >= start_date,
                    Vulnerability.published_date <= end_date
                )
            )
            
            if asset_ids:
                query = query.join(AssetVulnerability).filter(
                    AssetVulnerability.asset_id.in_(asset_ids)
                )
            
            trends = query.group_by(
                func.date(Vulnerability.published_date),
                Vulnerability.base_severity
            ).order_by('date').all()
            
            # Organizar dados por data e severidade
            trend_data = {}
            for item in trends:
                # Em alguns bancos (ex.: SQLite), func.date() pode retornar string.
                # Formatar de forma resiliente sem assumir tipo específico.
                try:
                    date_val = getattr(item, 'date', None)
                    if hasattr(date_val, 'strftime'):
                        date_str = date_val.strftime('%Y-%m-%d')
                    elif isinstance(date_val, str):
                        # Normalmente já vem como 'YYYY-MM-DD'; garantir apenas os 10 primeiros chars
                        date_str = date_val[:10]
                    else:
                        date_str = str(date_val)
                except Exception:
                    date_str = str(getattr(item, 'date', ''))

                if date_str not in trend_data:
                    trend_data[date_str] = {}
                trend_data[date_str][item.base_severity] = item.count
            
            return {
                'trend_data': trend_data,
                'period_days': days,
                'start_date': start_date,
                'end_date': end_date
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter tendências de vulnerabilidades: {e}")
            raise
    
    def compile_report_data(self,
                           asset_ids: Optional[List[int]] = None,
                           asset_tags: Optional[List[str]] = None,
                           asset_groups: Optional[List[str]] = None,
                           period_start: Optional[datetime] = None,
                           period_end: Optional[datetime] = None,
                           scope: Optional[str] = None,
                           detail_level: Optional[str] = None,
                           vendor_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Método principal para compilação de dados de relatórios.
        Compatível com a interface esperada pelo controller.
        
        Args:
            asset_ids: Lista de IDs de ativos
            asset_tags: Lista de tags de ativos
            asset_groups: Lista de grupos de ativos
            period_start: Data de início do período
            period_end: Data de fim do período
            scope: Escopo do relatório
            detail_level: Nível de detalhe
            
        Returns:
            Dicionário com todos os dados compilados e enriquecidos
        """
        return self.compile_comprehensive_report_data(
            asset_ids=asset_ids,
            tags=asset_tags,
            groups=asset_groups,
            start_date=period_start,
            end_date=period_end,
            severity_filter=None,
            vendor_name=vendor_name
        )

    def compile_comprehensive_report_data(self,
                                        asset_ids: Optional[List[int]] = None,
                                        tags: Optional[List[str]] = None,
                                        groups: Optional[List[str]] = None,
                                        start_date: Optional[datetime] = None,
                                        end_date: Optional[datetime] = None,
                                        severity_filter: Optional[List[str]] = None,
                                        vendor_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Compila todos os dados necessários para um relatório abrangente.
        
        Args:
            asset_ids: Lista de IDs de ativos
            tags: Lista de tags
            groups: Lista de grupos
            start_date: Data de início
            end_date: Data de fim
            severity_filter: Filtro de severidade
            
        Returns:
            Dicionário com todos os dados compilados
        """
        try:
            logger.info("Iniciando compilação de dados abrangentes para relatório")
            
            # Compilar dados de ativos
            asset_data = self.compile_asset_data(
                asset_ids=asset_ids,
                tags=tags,
                groups=groups,
                start_date=start_date,
                end_date=end_date
            )
            
            # Compilar dados de vulnerabilidades com enriquecimento
            vulnerability_data = self.compile_vulnerability_data(
                asset_ids=asset_ids,
                severity_levels=severity_filter,
                start_date=start_date,
                end_date=end_date,
                include_cisa_kev=True,
                include_epss=True,
                vendor_name=vendor_name
            )
            
            # Compilar dados de risco
            risk_data = self.compile_risk_data(
                asset_ids=asset_ids,
                start_date=start_date,
                end_date=end_date
            )
            
            # Obter top ativos por risco
            top_assets = self.get_top_assets_by_risk(
                limit=10,
                asset_ids=asset_ids
            )
            
            # Obter tendências se houver período definido
            timeline_data = {}
            if start_date and end_date:
                timeline_data = self.compile_timeline_data(
                    start_date=start_date,
                    end_date=end_date,
                    asset_ids=asset_ids
                )
            
            # Obter tendências dos últimos 30 dias
            trend_data = self.get_vulnerability_trends(
                days=30,
                asset_ids=asset_ids
            )
            
            # Compilar análises enriquecidas
            cisa_kev_data = self.compile_cisa_kev_analysis()
            epss_data = self.compile_epss_analysis()

            matrix_data = self.compile_asset_vulnerability_matrix(asset_ids=asset_ids)

            # Montar tabela de enums agregados para consumo por prompts/HTML
            try:
                vp_data = vulnerability_data.get('vendor_product_data', {}) if isinstance(vulnerability_data, dict) else {}
                sev_counts = vulnerability_data.get('by_severity', {}) if isinstance(vulnerability_data, dict) else {}
                cwe_dist = vulnerability_data.get('cwe_distribution', {}) if isinstance(vulnerability_data, dict) else {}
                enum_table = {
                    'vendors_total': int(vp_data.get('vendors', 0) or 0),
                    'products_total': int(vp_data.get('products', 0) or 0),
                    'cves_total': int(vulnerability_data.get('total_vulnerabilities', 0) or 0) if isinstance(vulnerability_data, dict) else 0,
                    'cwes_total': int(len(cwe_dist or {})),
                    'severity_counts': sev_counts or {},
                    'catalog_tag_counts': {}
                }
                # Contagem por catalog_tag a partir dos ativos
                try:
                    catalog_counts: Dict[str, int] = {}
                    for a in (asset_data.get('assets') or []):
                        tag = getattr(a, 'catalog_tag', None)
                        if tag:
                            catalog_counts[str(tag)] = int(catalog_counts.get(str(tag), 0)) + 1
                    enum_table['catalog_tag_counts'] = catalog_counts
                except Exception:
                    enum_table['catalog_tag_counts'] = {}
            except Exception:
                enum_table = {
                    'vendors_total': 0,
                    'products_total': 0,
                    'cves_total': 0,
                    'cwes_total': 0,
                    'severity_counts': {},
                    'catalog_tag_counts': {}
                }
            
            logger.info("Compilação de dados concluída com sucesso")
            
            return {
                'assets': asset_data,
                'vulnerabilities': vulnerability_data,
                'risks': risk_data,
                'top_assets_by_risk': top_assets,
                'timeline': timeline_data,
                'trends': trend_data,
                'cisa_kev_analysis': cisa_kev_data,
                'epss_analysis': epss_data,
                'asset_vulnerability_matrix': matrix_data,
                'enums_table': enum_table,
                'compilation_timestamp': datetime.now(),
                'filters_applied': {
                    'asset_ids': asset_ids,
                    'tags': tags,
                    'groups': groups,
                    'start_date': start_date,
                    'end_date': end_date,
                    'severity_filter': severity_filter
                }
            }
            
        except Exception as e:
            logger.error(f"Erro na compilação abrangente de dados: {e}")
            raise

    def compile_asset_vulnerability_matrix(self, asset_ids: Optional[List[int]] = None) -> Dict[str, Any]:
        try:
            query = self.session.query(AssetVulnerability).join(Asset).join(Vulnerability)
            if asset_ids:
                query = query.filter(AssetVulnerability.asset_id.in_(asset_ids))
            rows = query.all()
            asset_map: Dict[int, Dict[str, Any]] = {}
            for av in rows:
                asset = getattr(av, 'asset', None)
                vuln = getattr(av, 'vulnerability', None)
                if not asset or not vuln:
                    continue
                aid = getattr(asset, 'id', None)
                name = getattr(asset, 'name', None) or f"Ativo {aid}"
                sev = (getattr(vuln, 'base_severity', 'LOW') or 'LOW').upper()
                if aid not in asset_map:
                    asset_map[aid] = {'name': name, 'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
                if sev not in asset_map[aid]:
                    sev = 'LOW'
                asset_map[aid][sev] += 1
            items = list(asset_map.values())
            items.sort(key=lambda x: (x['CRITICAL']*100 + x['HIGH']*10 + x['MEDIUM']), reverse=True)
            labels = [x['name'] for x in items]
            critical = [x['CRITICAL'] for x in items]
            high = [x['HIGH'] for x in items]
            medium = [x['MEDIUM'] for x in items]
            low = [x['LOW'] for x in items]
            datasets = [
                {'label': 'Crítico', 'data': critical, 'backgroundColor': '#dc3545', 'borderColor': '#dc3545', 'borderWidth': 1},
                {'label': 'Alto', 'data': high, 'backgroundColor': '#fd7e14', 'borderColor': '#fd7e14', 'borderWidth': 1},
                {'label': 'Médio', 'data': medium, 'backgroundColor': '#ffc107', 'borderColor': '#ffc107', 'borderWidth': 1},
                {'label': 'Baixo', 'data': low, 'backgroundColor': '#28a745', 'borderColor': '#28a745', 'borderWidth': 1},
            ]
            return {'labels': labels, 'datasets': datasets}
        except Exception as e:
            logger.error(f"Erro ao compilar matriz de vulnerabilidades por ativo: {e}")
            return {'labels': [], 'datasets': []}
