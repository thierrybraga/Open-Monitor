# controllers/report_controller.py

"""
Controller para gerenciamento e geração de relatórios de cybersegurança.
Responsável por processar solicitações de relatórios, compilar dados e gerar conteúdo.
"""

import logging
import json
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from flask_login import current_user, login_required
# from flask_login import login_required  # Removido - não requer mais login
from sqlalchemy import and_, or_
from app.extensions.middleware import audit_log
from app.extensions import db

# Models
from app.models.report import Report, ReportType, ReportScope, DetailLevel, ReportStatus
from app.models.asset import Asset
from app.models.vulnerability import Vulnerability
from app.models.user import User

# Forms
from app.forms.report_form import ReportConfigForm, ReportFilterForm, ReportExportForm, QuickReportForm
from app.services.report_data_service import ReportDataService
from app.services.report_ai_service import ReportAIService
from app.services.pdf_export_service import PDFExportService
from app.services.report_badge_service import ReportBadgeService
from app.services.report_notification_service import ReportNotificationService, NotificationEvent, NotificationPriority
from app.services.report_config_service import ReportConfigService
from app.services.report_cache_service import ReportCacheService

# Schemas
from app.schemas.report_schema import ReportResponseSchema, ReportContentSchema, ReportStatsSchema
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Blueprint para relatórios
report_bp = Blueprint('report', __name__, url_prefix='/reports')

# Inicializar serviços
data_service = ReportDataService()
ai_service = ReportAIService()
pdf_service = PDFExportService()
badge_service = ReportBadgeService()
notification_service = ReportNotificationService()
config_service = ReportConfigService()
cache_service = ReportCacheService()

# Schemas para serialização
report_schema = ReportResponseSchema()
reports_schema = ReportResponseSchema(many=True)
content_schema = ReportContentSchema()
stats_schema = ReportStatsSchema()


@report_bp.route('/')
def list_reports():
    """Lista todos os relatórios com filtros."""
    try:
        # Formulário de filtros
        filter_form = ReportFilterForm(request.args)
        
        # Query base - mostra todos os relatórios
        query = Report.query
        
        # Aplicar filtros
        if filter_form.report_type.data:
            try:
                types = [ReportType(t) for t in filter_form.report_type.data]
                query = query.filter(Report.report_type.in_(types))
            except Exception:
                logger.warning("Filtro de tipo de relatório inválido, ignorando.")
        
        if filter_form.status.data:
            try:
                statuses = [ReportStatus(s) for s in filter_form.status.data]
                query = query.filter(Report.status.in_(statuses))
            except Exception:
                logger.warning("Filtro de status inválido, ignorando.")
        
        if filter_form.date_from.data:
            query = query.filter(Report.created_at >= filter_form.date_from.data)
        
        if filter_form.date_to.data:
            query = query.filter(Report.created_at <= filter_form.date_to.data)
        
        # Ordenação
        query = query.order_by(Report.created_at.desc())
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 10
        reports = query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Estatísticas rápidas - todos os relatórios
        stats = {
            'total_reports': Report.query.count(),
            'pending_reports': Report.query.filter_by(status=ReportStatus.PENDING).count(),
            'completed_reports': Report.query.filter_by(status=ReportStatus.COMPLETED).count(),
            'failed_reports': Report.query.filter_by(status=ReportStatus.FAILED).count()
        }
        
        # Query string dos filtros (sem o parâmetro de página)
        args = request.args.to_dict(flat=True)
        args.pop('page', None)
        filter_qs = urlencode(args)
        
        return render_template(
            'reports/report_list.html',
            reports=reports,
            filter_form=filter_form,
            stats=stats,
            filter_qs=filter_qs
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar relatórios: {e}")
        flash('Erro ao carregar relatórios.', 'error')
        # Criar um formulário vazio para evitar erro no template
        filter_form = ReportFilterForm()
        return render_template('reports/report_list.html', reports=None, stats={}, filter_form=filter_form, filter_qs="")


@report_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create_report():
    """Cria um novo relatório com configurações detalhadas."""
    # Detectar se a requisição espera JSON (fetch/AJAX)
    wants_json = False
    try:
        wants_json = (
            'application/json' in ((request.headers.get('Accept', '') or '').lower())
        ) or (
            request.headers.get('X-Requested-With', '') == 'XMLHttpRequest'
        )
    except Exception:
        wants_json = False

    try:
        form = ReportConfigForm()

        # Preencher choices dinâmicas antes de validar/submeter
        try:
            assets = Asset.query.all()
        except Exception:
            assets = []

        # Choices de ativos customizados (id, label)
        try:
            form.custom_assets.choices = [
                (str(a.id), f"{a.name} ({a.ip_address})") for a in assets
            ]
        except Exception:
            form.custom_assets.choices = []

        # Choices de tags (usa tags predefinidas do serviço de badges)
        try:
            tag_choices = sorted(
                [(t.id, t.name) for t in getattr(badge_service, 'predefined_tags', {}).values()],
                key=lambda x: x[1].lower()
            )
            form.selected_tags.choices = tag_choices
        except Exception:
            form.selected_tags.choices = []

        # Choices de grupos (derivados do status dos ativos)
        try:
            group_values = sorted({(a.status or '').strip() for a in assets if (a.status or '').strip()})
            form.selected_groups.choices = [(g, g.capitalize()) for g in group_values]
        except Exception:
            form.selected_groups.choices = []
        
        if form.validate_on_submit():
            # Se não houver confirmação, renderizar página de revisão
            if not request.form.get('confirm'):
                def map_labels(selected_values, choices):
                    try:
                        label_map = {str(val): label for val, label in choices}
                        return [label_map.get(str(v), str(v)) for v in (selected_values or [])]
                    except Exception:
                        return selected_values or []

                review_data = {
                    'title': form.title.data,
                    'description': form.description.data,
                    'report_type': form.report_type.data,
                    'detail_level': form.detail_level.data,
                    'period_start': form.period_start.data,
                    'period_end': form.period_end.data,
                    'scope': form.scope.data,
                    'selected_tags_labels': map_labels(form.selected_tags.data, form.selected_tags.choices),
                    'selected_groups_labels': map_labels(form.selected_groups.data, form.selected_groups.choices),
                    'custom_assets_labels': map_labels(form.custom_assets.data, form.custom_assets.choices),
                    'include_charts': bool(form.include_charts.data),
                    'chart_types_labels': map_labels(form.chart_types.data, form.chart_types.choices),
                    'include_ai_analysis': bool(form.include_ai_analysis.data),
                    'ai_analysis_types_labels': map_labels(form.ai_analysis_types.data, form.ai_analysis_types.choices),
                    'include_recommendations': bool(form.include_recommendations.data),
                    'include_executive_summary': bool(form.include_executive_summary.data),
                    'auto_export': bool(form.auto_export.data),
                    'export_format': form.export_format.data,
                    'notify_completion': bool(form.notify_completion.data),
                    'notification_email': form.notification_email.data,
                    'custom_tags': form.custom_tags.data or ''
                }
                form_data = request.form.to_dict(flat=False)
                return render_template('reports/report_review.html', form=form, review=review_data, form_data=form_data)

            # Obter configurações padrão (sem usuário específico)
            try:
                export_config = config_service.get_export_config('SYSTEM', 1)
                chart_config = config_service.get_chart_config('SYSTEM', 1)
                branding_config = config_service.get_branding_config('SYSTEM', 1)
            except Exception as e:
                logger.warning(f"Erro ao obter configurações padrão: {e}")
                export_config = chart_config = branding_config = None
            
            # Montar escopo e metadados
            try:
                report_type_enum = ReportType(form.report_type.data)
            except Exception:
                report_type_enum = ReportType.EXECUTIVE
            
            try:
                scope_enum = ReportScope(form.scope.data)
            except Exception:
                scope_enum = ReportScope.ALL_ASSETS
            
            # Processar CSV opcional para restringir o escopo por ativos
            try:
                file_field = getattr(form, 'csv_file', None)
                asset_ids_from_csv = []
                csv_rows = []
                if file_field and file_field.data:
                    fs = file_field.data
                    try:
                        fs.stream.seek(0)
                        raw = fs.stream.read()
                    except Exception:
                        raw = b''
                    try:
                        text = raw.decode('utf-8')
                    except Exception:
                        try:
                            text = raw.decode('latin-1')
                        except Exception:
                            text = ''
                    if text:
                        import csv, io
                        reader = csv.reader(io.StringIO(text))
                        for row in reader:
                            if not row:
                                continue
                            hostid = (row[0] or '').strip() if len(row) > 0 else ''
                            alias = (row[1] or '').strip() if len(row) > 1 else ''
                            os_val = (row[2] or '').strip() if len(row) > 2 else ''
                            if not hostid and not alias:
                                continue
                            csv_rows.append({'hostid': hostid, 'alias': alias, 'os': os_val})
                        hostids = [r['hostid'] for r in csv_rows if r.get('hostid')]
                        aliases = [r['alias'] for r in csv_rows if r.get('alias')]
                        if hostids or aliases:
                            try:
                                matches = Asset.query.filter(or_(Asset.ip_address.in_(hostids), Asset.name.in_(aliases))).all()
                            except Exception:
                                matches = []
                            asset_ids_from_csv = [a.id for a in matches]
                # Se houver ativos do CSV, ajustar escopo para customizado
                if asset_ids_from_csv:
                    scope_enum = ReportScope.CUSTOM
            except Exception as e:
                logger.warning(f"Falha ao processar arquivo CSV na criação de relatório: {e}")

            try:
                detail_enum = DetailLevel(form.detail_level.data)
            except Exception:
                detail_enum = DetailLevel.SUMMARY

            scope_config = {
                'selected_tags': form.selected_tags.data or [],
                'selected_groups': form.selected_groups.data or [],
                'custom_assets': form.custom_assets.data or []
            }

            # Incluir dados do CSV processado no scope_config
            try:
                if 'asset_ids_from_csv' in locals() and asset_ids_from_csv:
                    scope_config['asset_ids'] = asset_ids_from_csv
                if 'csv_rows' in locals() and csv_rows:
                    scope_config['csv_hosts'] = csv_rows
            except Exception:
                pass

            report_metadata = {
                'include_charts': bool(form.include_charts.data),
                'chart_types': form.chart_types.data or [],
                'include_ai_analysis': bool(form.include_ai_analysis.data),
                'ai_analysis_types': form.ai_analysis_types.data or [],
                'include_recommendations': bool(form.include_recommendations.data),
                'include_executive_summary': bool(form.include_executive_summary.data),
                'auto_export': bool(form.auto_export.data),
                'export_format': form.export_format.data,
                'notify_completion': bool(form.notify_completion.data),
                'notification_email': form.notification_email.data,
                'custom_tags': form.custom_tags.data or ''
            }

            # Determinar usuário gerador
            user_id = None
            try:
                if current_user and getattr(current_user, 'is_authenticated', False):
                    user_id = current_user.id
                else:
                    fallback_user = User.query.filter_by(is_active=True).order_by(User.id.asc()).first()
                    if fallback_user:
                        user_id = fallback_user.id
            except Exception:
                user_id = None

            if not user_id:
                flash('Nenhum usuário ativo encontrado. Faça login para criar relatório.', 'error')
                return redirect(url_for('auth.login'))

            # Criar novo relatório (persistindo apenas colunas conhecidas)
            report = Report(
                title=form.title.data,
                description=form.description.data,
                report_type=report_type_enum,
                scope=scope_enum,
                detail_level=detail_enum,
                period_start=form.period_start.data,
                period_end=form.period_end.data,
                scope_config=scope_config,
                status=ReportStatus.PENDING,
                generated_by_id=user_id,
                export_format=form.export_format.data,
                ai_analysis_types=report_metadata.get('ai_analysis_types', []),
                report_metadata=report_metadata
            )

            # Definir tags personalizadas se fornecidas
            if form.custom_tags.data:
                report.tags = form.custom_tags.data

            db.session.add(report)
            db.session.commit()

            # Log da criação
            try:
                audit_log('create', 'report', str(report.id), {
                    'title': report.title,
                    'type': report.report_type.value,
                    'scope': report.scope.value
                })
            except Exception as e:
                logger.warning(f"Falha ao registrar audit log para relatório {report.id}: {e}")
            
            # Gerar badges e sugerir tags (não persistimos badges; tags já foram definidas se personalizadas)
            try:
                _ = badge_service.get_applicable_badges(report)
                _ = badge_service.suggest_tags(report)
            except Exception as e:
                logger.warning(f"Erro ao sugerir badges/tags para relatório {report.id}: {e}")
            
            # Enviar notificação de criação
            try:
                notification_service.send_notification(
                    event='report_created',
                    report=report,
                    user=None  # Sem usuário específico
                )
            except Exception as e:
                logger.warning(f"Erro ao enviar notificação de criação do relatório {report.id}: {e}")
            
            # Iniciar geração do relatório em background
            try:
                _generate_report_async(report.id)
                flash('Relatório criado e geração iniciada com sucesso!', 'success')
            except Exception as e:
                logger.error(f"Erro ao iniciar geração do relatório {report.id}: {e}")
                report.status = ReportStatus.FAILED
                meta = report.report_metadata or {}
                meta['error_message'] = str(e)
                report.report_metadata = meta
                db.session.commit()
                flash('Relatório criado, mas houve erro na geração. Tente novamente.', 'warning')
            
            if wants_json:
                return jsonify({
                    'success': True,
                    'redirect_url': url_for('report.view_report', report_id=report.id)
                })
            else:
                return redirect(url_for('report.view_report', report_id=report.id))
        
        # Validação falhou: retornar JSON se for submissão via fetch/AJAX
        if wants_json:
            return jsonify({
                'success': False,
                'message': 'Falha na validação do formulário',
                'errors': form.errors
            }), 400
        else:
            logger.warning(f"Falha na validação do formulário de relatório: {form.errors}")
            # Renderizar formulário
            return render_template(
                'reports/report_create.html',
                form=form,
            )
        
    except Exception as e:
        logger.exception(f"Erro ao criar relatório: {e}")
        if wants_json:
            return jsonify({
                'success': False,
                'message': 'Erro ao criar relatório',
                'error': str(e)
            }), 500
        else:
            flash(f'Erro ao criar relatório: {str(e)}', 'error')
            return redirect(url_for('report.list_reports'))


@report_bp.route('/quick-create', methods=['GET', 'POST'])
@login_required
def quick_create_report():
    """Cria um relatório rápido com configurações simplificadas."""
    # Detectar se a requisição espera JSON (fetch/AJAX)
    wants_json = False
    try:
        wants_json = (
            'application/json' in ((request.headers.get('Accept', '') or '').lower())
        ) or (
            request.headers.get('X-Requested-With', '') == 'XMLHttpRequest'
        )
    except Exception:
        wants_json = False

    try:
        form = QuickReportForm()
        
        if form.validate_on_submit():
            # Período a partir de período em dias
            try:
                days = int(form.period_days.data or '30')
            except Exception:
                days = 30
            period_end = datetime.utcnow()
            period_start = period_end - timedelta(days=days)

            # Enums e configs rápidas
            try:
                report_type_enum = ReportType(form.report_type.data)
            except Exception:
                report_type_enum = ReportType.EXECUTIVE

            # Escopo rápido: críticos = customizado com flag
            scope_cfg = {}
            if form.scope.data == 'todos_ativos':
                scope_enum = ReportScope.ALL_ASSETS
            else:
                scope_enum = ReportScope.CUSTOM
                scope_cfg['critical_only'] = True

            # Processar CSV opcional para restringir o escopo por ativos
            try:
                file_field = getattr(form, 'csv_file', None)
                asset_ids_from_csv = []
                if file_field and file_field.data:
                    fs = file_field.data
                    try:
                        fs.stream.seek(0)
                        raw = fs.stream.read()
                    except Exception:
                        raw = b''
                    try:
                        text = raw.decode('utf-8')
                    except Exception:
                        try:
                            text = raw.decode('latin-1')
                        except Exception:
                            text = ''
                    if text:
                        import csv, io
                        reader = csv.reader(io.StringIO(text))
                        rows = []
                        for row in reader:
                            if not row:
                                continue
                            hostid = (row[0] or '').strip() if len(row) > 0 else ''
                            alias = (row[1] or '').strip() if len(row) > 1 else ''
                            os_val = (row[2] or '').strip() if len(row) > 2 else ''
                            if not hostid and not alias:
                                continue
                            rows.append({'hostid': hostid, 'alias': alias, 'os': os_val})
                        hostids = [r['hostid'] for r in rows if r.get('hostid')]
                        aliases = [r['alias'] for r in rows if r.get('alias')]
                        if hostids or aliases:
                            try:
                                matches = Asset.query.filter(or_(Asset.ip_address.in_(hostids), Asset.name.in_(aliases))).all()
                            except Exception:
                                matches = []
                            asset_ids_from_csv = [a.id for a in matches]
                            scope_cfg['csv_hosts'] = rows
                # Se houver ativos do CSV, ajustar escopo para customizado e definir asset_ids
                if asset_ids_from_csv:
                    scope_cfg['asset_ids'] = asset_ids_from_csv
                    scope_enum = ReportScope.CUSTOM
            except Exception as e:
                logger.warning(f"Falha ao processar arquivo CSV no Quick Create: {e}")

            # Mapear nível de detalhe opcional
            try:
                detail_level_enum = DetailLevel(form.detail_level.data or 'resumido')
            except Exception:
                detail_level_enum = DetailLevel.SUMMARY

            # Preparar metadados
            report_metadata = {
                'include_charts': True,
                'chart_types': ['cvss_distribution', 'top_assets_risk', 'vulnerability_trend'],
                'include_ai_analysis': True,
                # Defaults will be overwritten below based on report_type
                'ai_analysis_types': ['executive_summary'],
                'auto_export': True,
                'export_format': 'html'
            }

            # Criar relatório rápido
            # Definir tipos padrão de análise de IA por tipo de relatório
            ai_defaults_map = {
                ReportType.EXECUTIVE: ['executive_summary', 'business_impact'],
                ReportType.TECHNICAL: ['executive_summary', 'technical_analysis', 'cisa_kev_analysis', 'epss_analysis'],
                ReportType.TECHNICAL_STUDY: ['technical_analysis', 'vendor_product_analysis', 'cisa_kev_analysis', 'epss_analysis'],
                ReportType.PENTEST: ['technical_analysis', 'remediation_plan'],
                ReportType.BIA: ['executive_summary', 'business_impact', 'remediation_plan'],
                ReportType.KPI_KRI: ['executive_summary']
            }
            ai_types_default = ai_defaults_map.get(report_type_enum, ['executive_summary'])
            report_metadata['ai_analysis_types'] = ai_types_default

            # Ajustar tipos de gráficos padrão por tipo de relatório
            try:
                if report_type_enum == ReportType.KPI_KRI:
                    report_metadata['chart_types'] = ['kpi_timeline', 'vulnerability_trend']
                elif report_type_enum == ReportType.EXECUTIVE:
                    report_metadata['chart_types'] = ['cvss_distribution', 'top_assets_risk']
                else:
                    report_metadata['chart_types'] = report_metadata['chart_types']
            except Exception:
                pass

            # Usar campos opcionais do formulário quando fornecidos
            title_value = (form.title.data or '').strip()
            description_value = (form.description.data or '').strip()

            # Determinar usuário gerador
            user_id = None
            try:
                if current_user and getattr(current_user, 'is_authenticated', False):
                    user_id = current_user.id
                else:
                    fallback_user = User.query.filter_by(is_active=True).order_by(User.id.asc()).first()
                    if fallback_user:
                        user_id = fallback_user.id
            except Exception:
                user_id = None

            if not user_id:
                error_msg = 'Nenhum usuário ativo encontrado. Faça login para criar relatório.'
                if wants_json:
                    return jsonify({'success': False, 'message': error_msg}), 401
                else:
                    flash(error_msg, 'error')
                    return redirect(url_for('auth.login'))

            report = Report(
                title=title_value if title_value else f"Relatório Rápido - {report_type_enum.value}",
                description=description_value if description_value else f"Relatório gerado automaticamente para os últimos {days} dias",
                report_type=report_type_enum,
                scope=scope_enum,
                detail_level=detail_level_enum,
                period_start=period_start,
                period_end=period_end,
                scope_config=scope_cfg,
                status=ReportStatus.PENDING,
                generated_by_id=user_id,
                export_format='html',
                ai_analysis_types=ai_types_default,
                report_metadata=report_metadata
            )

            db.session.add(report)
            db.session.commit()
            
            # Log da criação
            try:
                audit_log('create', 'report', str(report.id), {
                    'title': report.title,
                    'type': report.report_type.value,
                    'quick_create': True
                })
            except Exception as e:
                logger.warning(f"Falha ao registrar audit log para relatório rápido {report.id}: {e}")
            
            # Iniciar geração
            try:
                _generate_report_async(report.id)
                flash('Relatório rápido criado e geração iniciada!', 'success')
            except Exception as e:
                logger.error(f"Erro ao gerar relatório rápido {report.id}: {e}")
                report.status = ReportStatus.FAILED
                report.error_message = str(e)
                db.session.commit()
                flash('Erro na geração do relatório rápido.', 'error')
            
            if wants_json:
                return jsonify({
                    'success': True,
                    'redirect_url': url_for('report.view_report', report_id=report.id)
                })
            else:
                return redirect(url_for('report.view_report', report_id=report.id))
        
        # Validação falhou: retornar JSON se for submissão via fetch/AJAX
        if wants_json:
            return jsonify({
                'success': False,
                'message': 'Falha na validação do formulário',
                'errors': form.errors
            }), 400
        else:
            logger.warning(f"Falha na validação do formulário rápido: {form.errors}")
            return render_template('reports/report_quick_create.html', form=form)
        
    except Exception as e:
        logger.exception(f"Erro ao criar relatório rápido: {e}")
        if wants_json:
            return jsonify({
                'success': False,
                'message': 'Erro ao criar relatório rápido.',
                'error': str(e),
                'redirect_url': url_for('report.quick_create_report')
            }), 500
        flash('Erro ao criar relatório rápido.', 'error')
        # Evitar loop de redirecionamento: renderizar a página com erro (status 500)
        try:
            fallback_form = QuickReportForm()
        except Exception:
            fallback_form = None
        return render_template('reports/report_quick_create.html', form=fallback_form), 500


@report_bp.route('/<int:report_id>')
def view_report(report_id):
    """Visualiza um relatório específico."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        # Verificar se o relatório está completo
        if report.status == ReportStatus.PENDING:
            flash('Relatório ainda está sendo gerado. Aguarde...', 'info')
        elif report.status == ReportStatus.FAILED:
            flash(f'Erro na geração do relatório: {report.error_message}', 'error')
        
        return render_template('reports/report_view.html', report=report)
        
    except Exception as e:
        logger.error(f"Erro ao visualizar relatório {report_id}: {e}")
        flash('Erro ao carregar relatório.', 'error')
        return redirect(url_for('report.list_reports'))


@report_bp.route('/<int:report_id>/regenerate', methods=['POST'])
def regenerate_report(report_id):
    """Regenera um relatório existente."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        # Resetar status e limpar dados anteriores
        report.status = ReportStatus.PENDING
        report.error_message = None
        report.content = None
        report.ai_analysis = None
        report.charts_data = None
        report.generated_at = None
        
        db.session.commit()
        
        # Log da regeneração
        audit_log('regenerate', 'report', str(report.id), {
            'title': report.title
        })
        
        # Iniciar nova geração
        try:
            _generate_report_async(report.id)
            flash('Regeneração do relatório iniciada!', 'success')
        except Exception as e:
            logger.error(f"Erro ao regenerar relatório {report.id}: {e}")
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            db.session.commit()
            flash('Erro ao regenerar relatório.', 'error')
        
        return redirect(url_for('report.view_report', report_id=report.id))
        
    except Exception as e:
        logger.error(f"Erro ao regenerar relatório {report_id}: {e}")
        flash('Erro ao regenerar relatório.', 'error')
        return redirect(url_for('report.list_reports'))


@report_bp.route('/<int:report_id>/delete', methods=['POST'])
def delete_report(report_id):
    """Deleta um relatório."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        # Log da exclusão
        audit_log('delete', 'report', str(report.id), {
            'title': report.title
        })
        
        db.session.delete(report)
        db.session.commit()
        
        flash('Relatório deletado com sucesso.', 'success')
        return redirect(url_for('report.list_reports'))
        
    except Exception as e:
        logger.error(f"Erro ao deletar relatório {report_id}: {e}")
        flash('Erro ao deletar relatório.', 'error')
        return redirect(url_for('report.list_reports'))


@report_bp.route('/<int:report_id>/export/<format>')
def export_report(report_id, format):
    """Exporta um relatório em formato específico."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        if report.status != ReportStatus.COMPLETED:
            flash('Relatório ainda não está pronto para exportação.', 'warning')
            return redirect(url_for('report.view_report', report_id=report.id))
        
        # Permitir exportação mesmo quando atributos não persistentes não existem
        default_formats = ['html', 'pdf', 'json', 'docx']
        available_formats = getattr(report, 'export_formats', default_formats)
        if format not in available_formats:
            flash(f'Formato {format} não disponível para este relatório.', 'error')
            return redirect(url_for('report.view_report', report_id=report.id))
        
        # Log da exportação
        audit_log('export', 'report', str(report.id), {
            'format': format
        })
        
        if format == 'pdf':
            try:
                file_path = pdf_service.export_to_pdf(report)
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=f"relatorio_{report.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mimetype='application/pdf'
                )
            except Exception as e:
                logger.error(f"Erro ao exportar PDF do relatório {report.id}: {e}")
                flash('Erro ao gerar PDF. Tente novamente.', 'error')
                return redirect(url_for('report.view_report', report_id=report.id))
        elif format == 'html':
            return _export_html(report)
        elif format == 'json':
            return _export_json(report)
        elif format == 'docx':
            try:
                file_path = pdf_service.export_to_docx(report)
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=f"relatorio_{report.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                    mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                )
            except Exception as e:
                logger.error(f"Erro ao exportar DOCX do relatório {report.id}: {e}")
                flash('Erro ao gerar DOCX. Tente novamente.', 'error')
                return redirect(url_for('report.view_report', report_id=report.id))
        else:
            flash('Formato de exportação não suportado.', 'error')
            return redirect(url_for('report.view_report', report_id=report.id))
        
    except Exception as e:
        logger.error(f"Erro ao exportar relatório {report_id}: {e}")
        flash('Erro ao exportar relatório.', 'error')
        return redirect(url_for('report.view_report', report_id=report.id))


# API Endpoints

@report_bp.route('/api/reports', methods=['GET'])
def api_list_reports():
    """API para listar relatórios."""
    try:
        reports = Report.query.all()  # Mostra todos os relatórios
        return jsonify(reports_schema.dump(reports))
    except Exception as e:
        logger.error(f"Erro na API de listagem: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/reports/<int:report_id>', methods=['GET'])
def api_get_report(report_id):
    """API para obter um relatório específico."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        return jsonify(report_schema.dump(report))
    except Exception as e:
        logger.error(f"Erro na API de obtenção: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/reports/<int:report_id>/status', methods=['GET'])
def api_report_status(report_id):
    """API para verificar status de um relatório."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        error_msg = None
        try:
            meta = report.report_metadata or {}
            error_msg = meta.get('error_message')
        except Exception:
            error_msg = None

        # Calcular progresso com resiliência
        try:
            progress = _calculate_progress(report)
        except Exception as calc_err:
            logger.warning(f"Falha ao calcular progresso do relatório {report.id}: {calc_err}")
            progress = 0

        # Serializar generated_at com segurança
        try:
            generated_at = report.generated_at.isoformat() if report.generated_at else None
        except Exception as gen_err:
            logger.warning(f"Falha ao serializar generated_at do relatório {report.id}: {gen_err}")
            generated_at = None

        # Serializar status com tolerância
        try:
            status_str = report.status.value if hasattr(report.status, 'value') else str(report.status)
        except Exception as status_err:
            logger.warning(f"Falha ao serializar status do relatório {report.id}: {status_err}")
            status_str = None

        return jsonify({
            'id': report.id,
            'status': status_str,
            'progress': progress,
            'error_message': error_msg,
            'generated_at': generated_at
        })
    except Exception as e:
        logger.error(f"Erro na API de status: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/stats', methods=['GET'])
def api_report_stats():
    """API para estatísticas de relatórios."""
    try:
        stats = {
            'total_reports': Report.query.count(),  # Conta todos os relatórios
            'by_type': {},
            'by_status': {},
            'recent_reports': []
        }
        
        # Estatísticas por tipo
        for report_type in ReportType:
            count = Report.query.filter_by(
                report_type=report_type
            ).count()
            stats['by_type'][report_type.value] = count
        
        # Estatísticas por status
        for status in ReportStatus:
            count = Report.query.filter_by(
                status=status
            ).count()
            stats['by_status'][status.value] = count
        
        # Relatórios recentes
        recent = Report.query.order_by(Report.created_at.desc()).limit(5).all()
        
        stats['recent_reports'] = [
            {
                'id': r.id,
                'title': r.title,
                'type': r.report_type.value,
                'status': r.status.value,
                'created_at': r.created_at.isoformat()
            }
            for r in recent
        ]
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Erro na API de estatísticas: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/reports/<int:report_id>/charts', methods=['GET'])
def api_report_charts(report_id):
    """API para obter dados de gráficos de um relatório."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        if not report.charts_data:
            return jsonify({'error': 'Dados de gráficos não disponíveis'}), 404
        
        return jsonify(report.charts_data)
    except Exception as e:
        logger.error(f"Erro na API de gráficos: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/reports/<int:report_id>/badges', methods=['GET'])
def api_report_badges(report_id):
    """API para obter badges de um relatório."""
    try:
        report = Report.query.filter_by(
            id=report_id
        ).first_or_404()
        
        badges = badge_service.get_applicable_badges(report)
        tags = badge_service.suggest_tags(report)
        
        return jsonify({
            'badges': [badge.to_dict() for badge in badges],
            'tags': [tag.to_dict() for tag in tags]
        })
    except Exception as e:
        logger.error(f"Erro na API de badges: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/notifications/channels', methods=['GET', 'POST'])
def api_notification_channels():
    """API para gerenciar canais de notificação."""
    try:
        if request.method == 'GET':
            channels = notification_service.get_user_channels(1)
            return jsonify([channel.to_dict() for channel in channels])
        
        elif request.method == 'POST':
            data = request.get_json()
            channel_type = data.get('type')
            config = data.get('config', {})
            
            if channel_type == 'email':
                notification_service.add_email_channel(
                    user_id=1,
                    email=config.get('email'),
                    events=config.get('events', [])
                )
            elif channel_type == 'slack':
                notification_service.add_slack_channel(
                    user_id=1,
                    webhook_url=config.get('webhook_url'),
                    channel=config.get('channel'),
                    events=config.get('events', [])
                )
            elif channel_type == 'webhook':
                notification_service.add_webhook_channel(
                    user_id=1,
                    url=config.get('url'),
                    headers=config.get('headers', {}),
                    events=config.get('events', [])
                )
            else:
                return jsonify({'error': 'Tipo de canal não suportado'}), 400
            
            return jsonify({'message': 'Canal adicionado com sucesso'}), 201
            
    except Exception as e:
        logger.error(f"Erro na API de canais de notificação: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


@report_bp.route('/api/notifications/history', methods=['GET'])
def api_notification_history():
    """API para obter histórico de notificações."""
    try:
        history = notification_service.get_notification_history(
            user_id=1,
            limit=request.args.get('limit', 50, type=int)
        )
        return jsonify([notification.to_dict() for notification in history])
    except Exception as e:
        logger.error(f"Erro na API de histórico de notificações: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500


# Funções auxiliares

def _generate_report_async(report_id):
    """
    Gera um relatório de forma assíncrona.
    Em uma implementação real, isso seria executado em uma task queue (Celery, RQ, etc.)
    """
    try:
        report = Report.query.get(report_id)
        if not report:
            logger.error(f"Relatório {report_id} não encontrado")
            return
        
        # Marcar como em processamento
        report.status = ReportStatus.GENERATING
        db.session.commit()
        
        # Verificar cache primeiro
        cache_key = f"report_data_{report_id}"
        report_data = cache_service.get_report_data(cache_key)
        
        if not report_data:
            # Compilar dados se não estiver em cache
            logger.info(f"Compilando dados para relatório {report_id}")
            report_data = data_service.compile_report_data(
                asset_ids=report.asset_ids,
                asset_tags=report.asset_tags,
                asset_groups=report.asset_groups,
                period_start=report.period_start,
                period_end=report.period_end,
                scope=report.scope,
                detail_level=report.detail_level
            )
            
            # Armazenar no cache
            cache_service.set_report_data(cache_key, report_data)
        else:
            logger.info(f"Dados do relatório {report_id} obtidos do cache")
        
        # Gerar conteúdo base
        content = _generate_base_content(report, report_data)
        
        # Gerar análise de IA se solicitado
        ai_analysis = {}
        if report.include_ai_analysis and report.ai_analysis_types:
            logger.info(f"Gerando análise de IA para relatório {report_id}")
            ai_analysis = _generate_ai_analysis(report, report_data)
        
        # Gerar dados de gráficos se solicitado
        chart_data = {}
        if report.include_charts and report.chart_types:
            logger.info(f"Gerando dados de gráficos para relatório {report_id}")
            chart_data = _generate_chart_data(report, report_data)
        
        # Compor conteúdo final conforme estrutura esperada pelo template
        try:
            composed_content = _compose_display_content(
                content or {},
                ai_analysis or {},
                chart_data or {},
                report_data or {},
                report
            )
        except Exception as _compose_err:
            logger.warning(f"Falha ao compor conteúdo de exibição: {_compose_err}")
            composed_content = content or {}

        # Atualizar relatório com dados gerados
        report.content = composed_content
        report.ai_analysis = ai_analysis
        report.charts_data = chart_data
        report.status = ReportStatus.COMPLETED
        report.generated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Enviar notificação de conclusão (respeitando preferências)
        try:
            user = User.query.get(report.generated_by_id)

            # Preparar dados para notificação
            by_severity = report_data.get('vulnerabilities', {}).get('by_severity', {})
            critical_count = by_severity.get('Critical') or by_severity.get('critical') or 0
            high_count = by_severity.get('High') or by_severity.get('high') or 0
            risk_score = report_data.get('risks', {}).get('overall_score', 0)
            processing_time = "N/A"
            try:
                if report.created_at and report.generated_at:
                    delta = report.generated_at - report.created_at
                    processing_time = f"{int(delta.total_seconds())}s"
            except Exception:
                pass

            report_url = url_for('report.view_report', report_id=report.id, _external=True)

            notification_payload = {
                'title': report.title,
                'type': report.report_type.value,
                'url': report_url,
                'created_at': report.created_at or datetime.utcnow(),
                'created_by': (getattr(user, 'username', None) or getattr(user, 'email', None) or 'Sistema'),
                'scope': report.scope.value,
                'completed_at': report.generated_at or datetime.utcnow(),
                'processing_time': processing_time,
                'total_vulnerabilities': report_data.get('vulnerabilities', {}).get('total_vulnerabilities', 0),
                'critical_vulnerabilities': critical_count,
                'high_vulnerabilities': high_count,
                'risk_score': risk_score,
                'attempts': 1,
                'max_attempts': 1,
            }
            meta = report.report_metadata or {}
            notify_enabled = bool(meta.get('notify_completion'))
            recipient_email = meta.get('notification_email')

            if notify_enabled:
                notification_service.send_notification(
                    event=NotificationEvent.REPORT_COMPLETED,
                    report_data=notification_payload,
                    priority=NotificationPriority.NORMAL,
                    custom_data={'recipient_email': recipient_email} if recipient_email else None,
                )

                # Verificar se há vulnerabilidades críticas para notificação especial
                if critical_count:
                    notification_service.send_notification(
                        event=NotificationEvent.CRITICAL_VULNERABILITIES,
                        report_data={**notification_payload, 'critical_vulnerabilities': critical_count},
                        priority=NotificationPriority.HIGH,
                        custom_data={'critical_count': critical_count, 'recipient_email': recipient_email} if recipient_email else {'critical_count': critical_count}
                    )
        except Exception as e:
            logger.warning(f"Erro ao enviar notificação de conclusão do relatório {report_id}: {e}")

        # Auto-exportar relatório se configurado
        try:
            meta = report.report_metadata or {}
            if bool(meta.get('auto_export')):
                export_format = (meta.get('export_format') or 'pdf').lower()
                result = pdf_service.export_report(report, format_type=export_format)
                filepath = result.get('filepath')
                meta['auto_export_result'] = {
                    'format': export_format,
                    'filepath': filepath,
                    'exported_at': datetime.utcnow().isoformat()
                }
                report.report_metadata = meta
                db.session.commit()
                logger.info(f"Auto-export realizado para relatório {report_id} em {export_format}: {filepath}")
        except Exception as export_err:
            logger.warning(f"Falha na auto-exportação do relatório {report_id}: {export_err}")

        logger.info(f"Relatório {report_id} gerado com sucesso")
        
    except Exception as e:
        logger.error(f"Erro ao gerar relatório {report_id}: {e}")
        report = Report.query.get(report_id)
        if report:
            report.status = ReportStatus.FAILED
            meta = report.report_metadata or {}
            meta['error_message'] = str(e)
            report.report_metadata = meta
            db.session.commit()
            
            # Enviar notificação de falha (respeitando preferências)
            try:
                user = User.query.get(report.generated_by_id)

                report_url = url_for('report.view_report', report_id=report.id, _external=True)
                failure_payload = {
                    'title': report.title,
                    'type': report.report_type.value,
                    'url': report_url,
                    'created_at': report.created_at or datetime.utcnow(),
                    'created_by': (getattr(user, 'username', None) or getattr(user, 'email', None) or 'Sistema'),
                    'scope': report.scope.value,
                    'completed_at': report.generated_at,
                    'failed_at': datetime.utcnow(),
                    'processing_time': 'N/A',
                    'total_vulnerabilities': report_data.get('vulnerabilities', {}).get('total_vulnerabilities', 0) if 'vulnerabilities' in (report_data or {}) else 0,
                    'risk_score': report_data.get('risks', {}).get('overall_score', 0) if 'risks' in (report_data or {}) else 0,
                    'error_message': str(e),
                    'attempts': 1,
                    'max_attempts': 3,
                }

                meta = report.report_metadata or {}
                notify_enabled = bool(meta.get('notify_completion'))
                recipient_email = meta.get('notification_email')

                if notify_enabled:
                    notification_service.send_notification(
                        event=NotificationEvent.REPORT_FAILED,
                        report_data=failure_payload,
                        priority=NotificationPriority.HIGH,
                        custom_data={'recipient_email': recipient_email} if recipient_email else None,
                    )
            except Exception as notify_error:
                logger.warning(f"Erro ao enviar notificação de falha do relatório {report_id}: {notify_error}")


def _generate_base_content(report, report_data):
    """Gera o conteúdo base do relatório."""
    def _fmt_date(value):
        try:
            if isinstance(value, datetime):
                return value.strftime('%Y-%m-%d')
            if isinstance(value, str):
                try:
                    iso = value.replace('Z', '+00:00')
                    dt = datetime.fromisoformat(iso)
                    return dt.strftime('%Y-%m-%d')
                except Exception:
                    return value
            return str(value)
        except Exception:
            return str(value)
    # Extrair apenas dados serializáveis para evitar objetos ORM em JSON
    assets_info = report_data.get('assets', {}) or {}
    vulnerabilities_info = report_data.get('vulnerabilities', {}) or {}
    risks_info = report_data.get('risks', {}) or {}
    timeline_info = report_data.get('timeline', {}) or {}

    # Resumo seguro
    assets_summary = {
        'total_assets': assets_info.get('total_assets', 0),
        'assets_by_status': assets_info.get('assets_by_status', {}),
        'assets_with_vulnerabilities': assets_info.get('assets_with_vulnerabilities', 0),
        'total_vulnerabilities': assets_info.get('total_vulnerabilities', 0),
        'vulnerability_coverage': assets_info.get('vulnerability_coverage', 0),
    }

    vulnerabilities_summary = {
        'total_vulnerabilities': vulnerabilities_info.get('total_vulnerabilities', 0),
        'by_severity': vulnerabilities_info.get('by_severity', {}),
        'cvss_stats': vulnerabilities_info.get('cvss_stats', {}),
        'epss_stats': vulnerabilities_info.get('epss_stats', {}),
        'patch_coverage': vulnerabilities_info.get('patch_coverage', {}),
        'vendor_product_data': vulnerabilities_info.get('vendor_product_data', {}),
        'cisa_kev_data': vulnerabilities_info.get('cisa_kev_data', {}),
    }

    risks_summary = {
        'risk_statistics': risks_info.get('risk_statistics', {}),
        'total_assessments': risks_info.get('total_assessments', 0),
    }

    # Timeline com datas como strings
    vulnerability_timeline = [
        {'date': _fmt_date(item.get('date')), 'count': item.get('count', 0)}
        for item in (timeline_info.get('vulnerability_timeline') or [])
    ]
    risk_timeline = [
        {'date': _fmt_date(item.get('date')), 'avg_risk': float(item.get('avg_risk', 0) or 0), 'count': item.get('count', 0)}
        for item in (timeline_info.get('risk_timeline') or [])
    ]
    kpi_timeline = timeline_info.get('kpi_timeline') or {'labels': [], 'kpis': []}

    content = {
        'summary': {
            'period': f"{_fmt_date(report.period_start)} a {_fmt_date(report.period_end)}",
            'scope': report.scope.value,
            'detail_level': report.detail_level.value,
        },
        'assets_summary': assets_summary,
        'vulnerabilities_summary': vulnerabilities_summary,
        'risks_summary': risks_summary,
        'timeline': {
            'vulnerability_timeline': vulnerability_timeline,
            'risk_timeline': risk_timeline,
            'kpi_timeline': kpi_timeline,
        },
        'metadata': {
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'report_type': report.report_type.value,
            'version': '1.0'
        }
    }
    
    return content


def _generate_ai_analysis(report, report_data):
    """Gera análise de IA para o relatório."""
    ai_analysis = {}
    
    def _normalize_ai_output(val, analysis_type):
        if isinstance(val, dict) and 'markdown' in val:
            return val
        # Envolver string simples em formato estruturado
        return {
            'type': analysis_type,
            'markdown': val if isinstance(val, str) else json.dumps(val, ensure_ascii=False, default=str),
            'created_at': datetime.utcnow().isoformat(),
            'model': 'unknown',
            'request_id': f'ctrl_{analysis_type}_{int(datetime.utcnow().timestamp())}'
        }
    
    try:
        for analysis_type in report.ai_analysis_types:
            if analysis_type == 'executive_summary':
                val = ai_service.generate_executive_summary(
                    report_data, report.report_type.value
                )
                ai_analysis['executive_summary'] = _normalize_ai_output(val, 'executive_summary')
            elif analysis_type == 'business_impact':
                # Obter atributos de ativos e mapeamentos CVE
                asset_attributes = _get_asset_attributes(report_data.get('assets', {}))
                cve_mappings = _get_cve_mappings(report_data.get('vulnerabilities', {}))
                
                val = ai_service.generate_business_impact_analysis(
                    report_data, asset_attributes, cve_mappings
                )
                ai_analysis['business_impact'] = _normalize_ai_output(val, 'business_impact')
            elif analysis_type == 'remediation_plan':
                priority_vulns = _get_priority_vulnerabilities(report_data.get('vulnerabilities', {}))
                
                val = ai_service.generate_remediation_plan(
                    report_data, priority_vulns
                )
                ai_analysis['remediation_plan'] = _normalize_ai_output(val, 'remediation_plan')
            elif analysis_type == 'technical_analysis':
                cve_details = _get_cve_details(report_data.get('vulnerabilities', {}))
                
                val = ai_service.generate_technical_analysis(
                    report_data.get('vulnerabilities', {}), cve_details
                )
                ai_analysis['technical_analysis'] = _normalize_ai_output(val, 'technical_analysis')
            elif analysis_type == 'cisa_kev_analysis':
                # Nova análise específica para CISA KEV
                cisa_kev_data = report_data.get('vulnerabilities', {}).get('cisa_kev_data', {})
                val = ai_service.generate_cisa_kev_analysis(
                    cisa_kev_data, report_data.get('vulnerabilities', {})
                )
                ai_analysis['cisa_kev_analysis'] = _normalize_ai_output(val, 'cisa_kev_analysis')
            elif analysis_type == 'epss_analysis':
                # Nova análise específica para EPSS
                epss_data = report_data.get('vulnerabilities', {}).get('epss_data', {})
                val = ai_service.generate_epss_analysis(
                    epss_data, report_data.get('vulnerabilities', {})
                )
                ai_analysis['epss_analysis'] = _normalize_ai_output(val, 'epss_analysis')
            elif analysis_type == 'vendor_product_analysis':
                # Nova análise específica para vendors/products
                vendor_product_data = report_data.get('vulnerabilities', {}).get('vendor_product_data', {})
                val = ai_service.generate_vendor_product_analysis(
                    vendor_product_data, report_data.get('vulnerabilities', {})
                )
                ai_analysis['vendor_product_analysis'] = _normalize_ai_output(val, 'vendor_product_analysis')
    
    except Exception as e:
        logger.error(f"Erro ao gerar análise de IA: {e}")
        ai_analysis['error'] = f"Erro na geração de análise: {str(e)}"
    
    return ai_analysis


def _generate_chart_data(report, report_data):
    """Gera dados para gráficos do relatório."""
    chart_data = {}
    
    try:
        vulnerabilities = report_data.get('vulnerabilities', {})
        timeline = report_data.get('timeline', {})
        
        for chart_type in report.chart_types:
            # Verificar cache para cada tipo de gráfico
            cache_key = f"chart_{chart_type}_{report.id}"
            cached_chart = cache_service.get_chart_data(cache_key)
            
            if cached_chart:
                chart_data[chart_type] = cached_chart
                continue
            
            # Gerar dados se não estiver em cache
            generated = None
            if chart_type == 'cvss_distribution':
                generated = _generate_cvss_distribution_data(vulnerabilities)
            elif chart_type == 'top_assets_risk':
                generated = _generate_top_assets_risk_data(report_data)
            elif chart_type == 'vulnerability_trend':
                generated = _generate_vulnerability_trends_data(report_data)
            elif chart_type == 'risk_matrix':
                generated = _generate_risk_matrix_data(report_data)
            elif chart_type == 'asset_vulnerability_heatmap':
                generated = _generate_heatmap_data(report_data)
            elif chart_type == 'kpi_timeline':
                generated = _generate_kpi_timeline_data(timeline)
            elif chart_type == 'security_maturity':
                generated = _generate_security_maturity_data(report_data)

            if generated is not None:
                chart_data[chart_type] = generated
                cache_service.set_chart_data(cache_key, generated)
    
    except Exception as e:
        logger.error(f"Erro ao gerar dados de gráficos: {e}")
        chart_data['error'] = f"Erro na geração de gráficos: {str(e)}"
    
    return chart_data


def _calculate_progress(report):
    """Calcula o progresso de geração do relatório."""
    if report.status == ReportStatus.PENDING:
        return 0
    elif report.status == ReportStatus.GENERATING:
        return 50
    elif report.status == ReportStatus.COMPLETED:
        return 100
    else:  # FAILED
        return 0


def _export_pdf(report):
    """Exporta relatório em PDF."""
    # Implementação de exportação PDF será feita posteriormente
    flash('Exportação PDF em desenvolvimento.', 'info')
    return redirect(url_for('report.view_report', report_id=report.id))


def _export_html(report):
    """Exporta relatório em HTML."""
    return render_template('reports/export_html.html', report=report)


def _export_json(report):
    """Exporta relatório em JSON."""
    return jsonify(report_schema.dump(report))


# Funções auxiliares para dados específicos

def _get_asset_attributes(assets_data):
    """Obtém atributos dos ativos para análise."""
    # Implementação simplificada - expandir conforme necessário
    return assets_data.get('asset_details', [])


def _get_cve_mappings(vulnerabilities_data):
    """Obtém mapeamentos CVE para análise."""
    return vulnerabilities_data.get('cve_mappings', [])


def _get_priority_vulnerabilities(vulnerabilities_data):
    """Obtém vulnerabilidades prioritárias."""
    return vulnerabilities_data.get('priority_vulnerabilities', [])


def _get_cve_details(vulnerabilities_data):
    """Obtém detalhes das CVEs."""
    return vulnerabilities_data.get('cve_details', [])


def _generate_cvss_distribution_data(vulnerabilities):
    """Gera dados para gráfico de distribuição CVSS."""
    return {
        'type': 'histogram',
        'data': vulnerabilities.get('cvss_detailed', {}),
        'title': 'Distribuição de Scores CVSS'
    }


def _generate_top_assets_risk_data(report_data):
    """Gera dados para gráfico de top ativos por risco."""
    raw = report_data.get('top_assets_by_risk', []) or []
    # Converter itens para forma serializável (remover objetos ORM)
    safe_items = []
    for item in raw:
        try:
            asset = item.get('asset')
            safe_items.append({
                'asset_id': getattr(asset, 'id', None),
                'asset_name': getattr(asset, 'name', None),
                'total_risk': float(item.get('total_risk', 0) or 0),
                'risk_count': int(item.get('risk_count', 0) or 0),
                'avg_risk': float(item.get('avg_risk', 0) or 0),
            })
        except Exception:
            # Caso inesperado, manter números se existirem
            safe_items.append({
                'asset_id': None,
                'asset_name': None,
                'total_risk': float(item.get('total_risk', 0) or 0),
                'risk_count': int(item.get('risk_count', 0) or 0),
                'avg_risk': float(item.get('avg_risk', 0) or 0),
            })
    return {
        'type': 'bar',
        'data': safe_items,
        'title': 'Top Ativos por Risco'
    }


def _generate_vulnerability_trends_data(report_data):
    """Gera dados para gráfico de tendências de vulnerabilidades."""
    trends = report_data.get('trends', {})
    return {
        'type': 'line',
        'data': trends.get('trend_data', []),
        'title': 'Tendência de Vulnerabilidades'
    }


def _generate_risk_matrix_data(report_data):
    """Gera dados para matriz de risco."""
    return {
        'type': 'scatter',
        'data': report_data.get('risk_matrix', []),
        'title': 'Matriz de Risco'
    }


def _generate_heatmap_data(report_data):
    """Gera dados para heatmap de ativos x vulnerabilidades."""
    return {
        'type': 'heatmap',
        'data': report_data.get('asset_vulnerability_matrix', []),
        'title': 'Heatmap Ativos x Vulnerabilidades'
    }


def _generate_kpi_timeline_data(timeline):
    """Gera dados para timeline de KPIs."""
    return {
        'type': 'area',
        'data': timeline.get('kpi_timeline', []),
        'title': 'Timeline de KPIs/KRIs'
    }


def _generate_security_maturity_data(report_data):
    """Gera dados para gráfico de maturidade de segurança."""
    return {
        'type': 'radar',
        'data': report_data.get('security_maturity', {}),
        'title': 'Maturidade de Segurança por Domínio'
    }


def _compose_display_content(base_content, ai_analysis, chart_data, report_data, report):
    """Compoe `report.content` no formato esperado pelo template de visualização.

    - Garante `executive_summary` com campos `content`, `ai_generated` e `key_metrics`.
    - Converte `chart_data` em lista `content.charts` exibível.
    - Adiciona seções opcionais: `vulnerabilities`, `bia_analysis`, `remediation_plan`, `technical_analysis`.
    """
    try:
        content = dict(base_content or {})

        # Métricas chave
        assets = (report_data or {}).get('assets', {})
        vulns = (report_data or {}).get('vulnerabilities', {})
        risks = (report_data or {}).get('risks', {})
        by_sev = vulns.get('by_severity', {}) or {}
        critical_count = by_sev.get('Critical') or by_sev.get('critical') or 0
        high_count = by_sev.get('High') or by_sev.get('high') or 0
        total_vulns = vulns.get('total_vulnerabilities', 0) or (
            (by_sev.get('Critical') or 0) + (by_sev.get('High') or 0) + (by_sev.get('Medium') or 0) + (by_sev.get('Low') or 0)
        )
        risk_score = risks.get('overall_score', 0)

        # Sumário executivo
        ai_exec_val = (ai_analysis or {}).get('executive_summary')
        ai_exec_md = ai_exec_val.get('markdown') if isinstance(ai_exec_val, dict) else ai_exec_val
        if not ai_exec_md:
            # Fallback simples para evitar branco
            org_name = getattr(report, 'title', 'Relatório de Segurança')
            ai_exec_md = (
                f"Resumo do {org_name}:\n\n"
                f"- Ativos analisados: {assets.get('total_assets', 0)}\n"
                f"- Vulnerabilidades totais: {total_vulns}\n"
                f"- Críticas: {critical_count} | Altas: {high_count}\n"
                f"- Score geral de risco: {risk_score}"
            )

        content['executive_summary'] = {
            'content': ai_exec_md,
            'ai_generated': bool(ai_exec_val),
            'key_metrics': [
                {'label': 'Ativos', 'value': assets.get('total_assets', 0), 'color': 'primary'},
                {'label': 'Vulnerabilidades', 'value': total_vulns, 'color': 'warning'},
                {'label': 'Críticas', 'value': critical_count, 'color': 'danger'},
                {'label': 'Score de Risco', 'value': risk_score, 'color': 'info'},
            ]
        }

        # Enriquecer métricas-chave com KPIs de SLA e cobertura de patch
        try:
            patch_cov = (vulns.get('patch_coverage') or {})
            patched = int(patch_cov.get('patched', 0) or 0)
            unpatched = int(patch_cov.get('unpatched', 0) or 0)
            known_total = patched + unpatched
            patch_pct = round((patched / known_total) * 100.0, 1) if known_total > 0 else 0.0

            rem_kpis = (vulns.get('remediation_kpis') or {})
            mttr_days = float(rem_kpis.get('mttr_days', 0.0) or 0.0)
            remediation_rate = float(rem_kpis.get('remediation_rate_pct', 0.0) or 0.0)
            sla_compliance = float(rem_kpis.get('sla_compliance_pct', 0.0) or 0.0)

            # Adicionar ao executive_summary.key_metrics
            content['executive_summary']['key_metrics'].extend([
                {'label': 'Cobertura de Patch (%)', 'value': patch_pct, 'color': 'success'},
                {'label': 'MTTR (dias)', 'value': mttr_days, 'color': 'secondary'},
                {'label': 'Conformidade SLA (%)', 'value': sla_compliance, 'color': 'success' if sla_compliance >= 80 else 'warning' if sla_compliance >= 50 else 'danger'},
                {'label': 'Taxa de Remediação (%)', 'value': remediation_rate, 'color': 'info'},
            ])

            # Popular `content.kpis` para exibição de cards na UI, espelhando principais métricas
            content['kpis'] = [
                {'label': 'Vulnerabilidades', 'value': total_vulns, 'color': 'warning'},
                {'label': 'Críticas', 'value': critical_count, 'color': 'danger'},
                {'label': 'Cobertura de Patch (%)', 'value': patch_pct, 'color': 'success'},
                {'label': 'Conformidade SLA (%)', 'value': sla_compliance, 'color': 'success' if sla_compliance >= 80 else 'warning' if sla_compliance >= 50 else 'danger'},
            ]
        except Exception as _kpi_err:
            logger.warning(f"Falha ao enriquecer KPIs do sumário executivo: {_kpi_err}")

        # Vulnerabilidades
        v_summary = {}
        for sev_key, count in (by_sev or {}).items():
            v_summary[str(sev_key).lower()] = count
        if v_summary or vulns.get('details'):
            content['vulnerabilities'] = {
                'summary': v_summary,
                'details': vulns.get('details', [])
            }

        # BIA
        if (ai_analysis or {}).get('business_impact'):
            bia_val = ai_analysis.get('business_impact')
            bia_md = bia_val.get('markdown') if isinstance(bia_val, dict) else bia_val
            content['bia_analysis'] = {
                'content': bia_md,
                'ai_generated': True,
                'critical_assets': assets.get('critical_assets', [])
            }

        # Plano de remediação
        if (ai_analysis or {}).get('remediation_plan'):
            rem_val = ai_analysis.get('remediation_plan')
            rem_md = rem_val.get('markdown') if isinstance(rem_val, dict) else rem_val
            content['remediation_plan'] = {
                'content': rem_md,
                'ai_generated': True
            }

        # Análise técnica
        if (ai_analysis or {}).get('technical_analysis'):
            tech_val = ai_analysis.get('technical_analysis')
            tech_md = tech_val.get('markdown') if isinstance(tech_val, dict) else tech_val
            content['technical_analysis'] = {
                'content': tech_md,
                'ai_generated': True
            }

        # Charts: converter dict em lista com título e tipo
        charts_list = []
        if isinstance(chart_data, dict):
            for key, obj in chart_data.items():
                if not isinstance(obj, dict):
                    continue
                data_payload = obj.get('data') if 'data' in obj else obj
                title = obj.get('title') or str(key).replace('_', ' ').title()
                chart_type = obj.get('type') or 'bar'
                charts_list.append({
                    'title': title,
                    'type': chart_type,
                    'data': data_payload,
                    'size': 'medium'
                })

        # Apenas definir se houver algo para mostrar
        if charts_list:
            content['charts'] = charts_list

        return content
    except Exception as e:
        logger.error(f"Erro ao compor conteúdo de relatório: {e}")
        return base_content or {}


# ============================================================================
# ROTAS DE CONFIGURAÇÃO
# ============================================================================

@report_bp.route('/api/config/<category>')
def get_config(category):
    """Obtém configurações por categoria."""
    try:
        scope = request.args.get('scope', 'USER')
        config = config_service.get_config(category, scope, 1)
        
        return jsonify({
            'success': True,
            'config': config
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter configuração {category}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@report_bp.route('/api/config/<category>', methods=['POST'])
def set_config(category):
    """Define configurações por categoria."""
    try:
        data = request.get_json()
        scope = data.get('scope', 'USER')
        config_data = data.get('config', {})
        
        config_service.set_config(category, config_data, scope, 1)
        
        # Log da auditoria
        audit_log(
            user_id=1,
            action='config_update',
            resource_type='report_config',
            resource_id=f"{category}_{scope}",
            details={'category': category, 'scope': scope}
        )
        
        return jsonify({
            'success': True,
            'message': 'Configuração atualizada com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro ao definir configuração {category}: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@report_bp.route('/api/config/templates')
def get_templates():
    """Lista templates disponíveis."""
    try:
        templates = config_service.get_templates()
        
        return jsonify({
            'success': True,
            'templates': [template.__dict__ for template in templates]
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter templates: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@report_bp.route('/api/config/templates', methods=['POST'])
def add_template():
    """Adiciona novo template."""
    try:
        data = request.get_json()
        
        template = config_service.add_template(
            name=data['name'],
            description=data.get('description', ''),
            template_type=data['type'],
            content=data['content'],
            variables=data.get('variables', []),
            is_default=data.get('is_default', False)
        )
        
        # Log da auditoria
        audit_log(
            user_id=1,
            action='template_create',
            resource_type='report_template',
            resource_id=template.id,
            details={'name': template.name, 'type': template.type}
        )
        
        return jsonify({
            'success': True,
            'template': template.__dict__
        })
        
    except Exception as e:
        logger.error(f"Erro ao adicionar template: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


# ============================================================================
# ROTAS DE CACHE E PERFORMANCE
# ============================================================================

@report_bp.route('/api/cache/stats')
def get_cache_stats():
    """Obtém estatísticas do cache."""
    try:
        stats = cache_service.get_cache_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas do cache: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@report_bp.route('/api/cache/clear', methods=['POST'])
def clear_cache():
    """Limpa cache específico ou todos."""
    try:
        data = request.get_json()
        cache_type = data.get('type', 'all')
        report_id = data.get('report_id')
        
        if report_id:
            cache_service.invalidate_report_cache(report_id)
        elif cache_type == 'all':
            cache_service.clear_all_cache()
        else:
            cache_service.clear_cache_type(cache_type)
        
        # Log da auditoria
        audit_log(
            user_id=1,
            action='cache_clear',
            resource_type='cache',
            resource_id=cache_type,
            details={'type': cache_type, 'report_id': report_id}
        )
        
        return jsonify({
            'success': True,
            'message': 'Cache limpo com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro ao limpar cache: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500


@report_bp.route('/api/cache/preload', methods=['POST'])
def preload_cache():
    """Pré-carrega dados no cache."""
    try:
        data = request.get_json()
        report_ids = data.get('report_ids', [])
        
        for report_id in report_ids:
            cache_service.preload_report_data(report_id)
        
        return jsonify({
            'success': True,
            'message': f'Cache pré-carregado para {len(report_ids)} relatórios'
        })
        
    except Exception as e:
        logger.error(f"Erro ao pré-carregar cache: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Erro interno do servidor'
        }), 500