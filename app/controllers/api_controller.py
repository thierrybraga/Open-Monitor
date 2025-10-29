# controllers/api_controller.py

from flask import Blueprint, jsonify, request, current_app, url_for
from flask.wrappers import Response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
# CSRF protection is handled at blueprint level
from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.asset import Asset
from app.models.risk_assessment import RiskAssessment
from app.models.sync_metadata import SyncMetadata
from app.utils.pagination import paginate_query
from app.forms.api_form import APIQueryForm
from app.services.vulnerability_service import VulnerabilityService

from app.extensions import login_manager
from typing import Any, Dict
from datetime import datetime, timedelta
from sqlalchemy import func, desc
import requests
from flask_login import current_user

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# --- Blueprint-local error handlers ---

@api_v1_bp.errorhandler(BadRequest)
def _handle_bad_request(e: BadRequest) -> Response:
    return jsonify(error=str(e)), 400

@api_v1_bp.errorhandler(NotFound)
def _handle_not_found(e: NotFound) -> Response:
    return jsonify(error='Not Found'), 404

@api_v1_bp.errorhandler(SQLAlchemyError)
def _handle_db_error(e: SQLAlchemyError) -> Response:
    current_app.logger.error("Database error", exc_info=e)
    return jsonify(error='Database error'), 500

@api_v1_bp.errorhandler(Exception)
def _handle_unexpected_error(e: Exception) -> Response:
    current_app.logger.error("Unexpected error", exc_info=e)
    raise InternalServerError()  # delegate to default 500 handler

# --- Sync Status Endpoint ---

@api_v1_bp.route('/sync/status', methods=['GET'])
def get_sync_status() -> Response:
    """
    GET /api/v1/sync/status
    Retorna informações sobre a última sincronização NVD
    """
    try:
        # Buscar última sincronização NVD
        last_sync = db.session.query(SyncMetadata).filter_by(
            key='nvd_last_sync'
        ).order_by(SyncMetadata.last_modified.desc()).first()
        
        if not last_sync:
            return jsonify({
                'status': 'never_synced',
                'last_sync_time': None,
                'last_sync_formatted': 'Nunca sincronizado',
                'sync_status': 'pending',
                'message': 'Nenhuma sincronização encontrada'
            })
        
        # Calcular tempo desde última sincronização
        now = datetime.utcnow()
        time_diff = now - last_sync.last_modified
        
        # Formatar tempo de forma amigável
        if time_diff.days > 0:
            time_ago = f"{time_diff.days} dia{'s' if time_diff.days > 1 else ''} atrás"
        elif time_diff.seconds > 3600:
            hours = time_diff.seconds // 3600
            time_ago = f"{hours} hora{'s' if hours > 1 else ''} atrás"
        elif time_diff.seconds > 60:
            minutes = time_diff.seconds // 60
            time_ago = f"{minutes} minuto{'s' if minutes > 1 else ''} atrás"
        else:
            time_ago = "Agora mesmo"
        
        # Determinar status baseado no tempo
        if time_diff.days > 1:
            sync_status = 'outdated'
        elif time_diff.seconds > 3600:  # Mais de 1 hora
            sync_status = 'warning'
        else:
            sync_status = 'recent'
        
        return jsonify({
            'status': 'success',
            'last_sync_time': last_sync.last_modified.isoformat(),
            'last_sync_formatted': time_ago,
            'sync_status': sync_status,
            'sync_type': last_sync.sync_type or 'unknown',
            'message': f'Última sincronização: {time_ago}'
        })
        
    except Exception as e:
        current_app.logger.error(f"Erro ao obter status de sincronização: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Erro interno do servidor'
        }), 500


@api_v1_bp.route('/sync/trigger', methods=['POST'])
def trigger_nvd_sync() -> Response:
    """
    POST /api/v1/sync/trigger
    Força uma sincronização com a base de dados NVD
    
    Body (JSON):
    {
        "full": false,  // true para sincronização completa, false para incremental
        "max_pages": null  // opcional: limitar número de páginas (para testes)
    }
    """
    try:
        # Verificar se já existe uma sincronização em andamento
        # (implementar verificação de lock se necessário)
        
        # Obter parâmetros da requisição
        data = request.get_json() or {}
        full_sync = data.get('full', False)
        max_pages = data.get('max_pages', None)
        
        # Validar parâmetros
        if max_pages is not None and (not isinstance(max_pages, int) or max_pages <= 0):
            return jsonify({
                'status': 'error',
                'message': 'max_pages deve ser um número inteiro positivo'
            }), 400
        
        # Importar e inicializar o Enhanced NVD Fetcher
        from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
        import asyncio
        
        # Executar sincronização em background
        def run_sync():
            try:
                with current_app.app_context():
                    fetcher = EnhancedNVDFetcher(
                        app=current_app,
                        max_workers=10,
                        enable_cache=True
                    )
                    
                    # Executar sincronização
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        result = loop.run_until_complete(
                            fetcher.sync_nvd(
                                full=full_sync,
                                max_pages=max_pages,
                                use_parallel=True
                            )
                        )
                        current_app.logger.info(f"Sincronização NVD concluída: {result} vulnerabilidades processadas")
                        return result
                    finally:
                        loop.close()
                        
            except Exception as e:
                current_app.logger.error(f"Erro na sincronização NVD: {e}")
                raise
        
        # Executar em thread separada para não bloquear a resposta
        from concurrent.futures import ThreadPoolExecutor
        import threading
        
        # Criar executor para executar em background
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(run_sync)
        
        # Registrar início da sincronização
        sync_type = "COMPLETA" if full_sync else "INCREMENTAL"
        current_app.logger.info(f"Iniciando sincronização NVD {sync_type} via API")
        
        # Atualizar metadata de sincronização para indicar que está em andamento
        try:
            sync_metadata = SyncMetadata.query.filter_by(key='nvd_last_sync').first()
            if not sync_metadata:
                sync_metadata = SyncMetadata(
                    key='nvd_last_sync',
                    status='in_progress',
                    sync_type=sync_type.lower(),
                    last_modified=datetime.utcnow()
                )
                db.session.add(sync_metadata)
            else:
                sync_metadata.status = 'in_progress'
                sync_metadata.sync_type = sync_type.lower()
                sync_metadata.last_modified = datetime.utcnow()
            
            db.session.commit()
        except Exception as e:
            current_app.logger.warning(f"Erro ao atualizar metadata de sincronização: {e}")
            db.session.rollback()
        
        return jsonify({
            'status': 'success',
            'message': f'Sincronização {sync_type} iniciada com sucesso',
            'sync_type': sync_type.lower(),
            'full_sync': full_sync,
            'max_pages': max_pages,
            'started_at': datetime.utcnow().isoformat()
        }), 202  # 202 Accepted - processamento assíncrono iniciado
        
    except ImportError as e:
        current_app.logger.error(f"Erro ao importar EnhancedNVDFetcher: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Serviço de sincronização não disponível'
        }), 503
        
    except Exception as e:
        current_app.logger.error(f"Erro ao iniciar sincronização NVD: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Erro interno do servidor'
        }), 500


# --- Helpers ---

def _apply_filters(query, params: APIQueryForm) -> Any:
    if params.severity.data:
        query = query.filter_by(base_severity=params.severity.data)
    # Vendor filtering via CVEVendor -> Vendor relationship
    if params.vendor.data:
        try:
            from app.models.cve_vendor import CVEVendor
            from app.models.vendor import Vendor
            # Support multiple vendors via comma-separated names
            raw = params.vendor.data
            names = [n.strip() for n in raw.split(',') if n.strip()]
            if names:
                lowered = [n.lower() for n in names]
                query = (
                    query
                    .join(CVEVendor, CVEVendor.cve_id == Vulnerability.cve_id)
                    .join(Vendor, Vendor.id == CVEVendor.vendor_id)
                    .filter(func.lower(Vendor.name).in_(lowered))
                    .distinct()
                )
        except Exception as e:
            current_app.logger.warning(f"Falha ao aplicar filtro de vendor: {e}")
    return query


def _paginate_and_serialize(
    query, params: APIQueryForm
) -> Dict[str, Any]:
    # Determine the model type and apply appropriate ordering
    model = query.column_descriptions[0]['type']
    if model == Vulnerability:
        ordered_query = query.order_by(Vulnerability.published_date.desc())
    elif model == Asset:
        ordered_query = query.order_by(Asset.id.desc())
    else:
        # Default ordering by published_date for other models
        ordered_query = query.order_by(Vulnerability.published_date.desc())
    
    pag = paginate_query(
        ordered_query,
        page=params.page.data,
        per_page=params.per_page.data
    )
    return {
        'data': [item.to_dict() for item in pag.items],
        'meta': {
            'page': pag.page,
            'per_page': pag.per_page,
            'total': pag.total,
            'pages': pag.pages,
        }
    }


# --- Endpoints CVE ---

@api_v1_bp.route('/cves', methods=['GET'])
def get_cves() -> Response:
    """
    GET /api/v1/cves
    Query params:
      - page, per_page, severity, vendor
    """
    form = APIQueryForm(request.args)
    if not form.validate():
        raise BadRequest(form.errors)

    query = Vulnerability.query
    query = _apply_filters(query, form)

    result = _paginate_and_serialize(query, form)
    return jsonify(result), 200


@api_v1_bp.route('/cves/<string:cve_id>', methods=['GET'])
def get_cve(cve_id: str) -> Response:
    """
    GET /api/v1/cves/{cve_id}
    """
    v = Vulnerability.query.filter_by(cve_id=cve_id).first()
    if not v:
        raise NotFound()
    return jsonify(v.to_dict()), 200


# alias
@api_v1_bp.route('/vulnerabilities', methods=['GET'])
def list_vulnerabilities() -> Response:
    return get_cves()

# --- Vendors Endpoint ---
@api_v1_bp.route('/vendors', methods=['GET'])
def list_vendors() -> Response:
    """Lista vendors (id, name) com suporte a busca parcial e limite."""
    try:
        from app.models.vendor import Vendor
        from sqlalchemy import func
        q = (request.args.get('q', '') or '').strip().lower()
        try:
            limit = int(request.args.get('limit', 20))
        except Exception:
            limit = 20
        try:
            offset = int(request.args.get('offset', 0))
        except Exception:
            offset = 0
        query = db.session.query(Vendor)
        if q:
            like = f"%{q}%"
            query = query.filter(func.lower(Vendor.name).like(like))
        total = query.count()
        vendors = query.order_by(Vendor.name.asc()).offset(offset).limit(limit).all()
        return jsonify({
            'data': [{'id': v.id, 'name': v.name} for v in vendors],
            'meta': { 'total': total, 'limit': limit, 'offset': offset, 'q': q }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao listar vendors: {e}", exc_info=e)
        return jsonify({'error': 'Erro ao listar vendors'}), 500

# --- User Vendor Preferences ---
@api_v1_bp.route('/account/vendor-preferences', methods=['GET'])
def get_vendor_preferences() -> Response:
    """Return the current user's saved vendor IDs for filtering."""
    try:
        if not current_user.is_authenticated:
            return jsonify({ 'vendor_ids': [], 'authenticated': False }), 200
        key = f'user_vendor_preferences:{current_user.id}'
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        vendor_ids: list[int] = []
        if sm and sm.value:
            try:
                vendor_ids = [int(x) for x in sm.value.split(',') if x.strip().isdigit()]
            except Exception:
                vendor_ids = []
        return jsonify({ 'vendor_ids': vendor_ids, 'authenticated': True }), 200
    except Exception as e:
        current_app.logger.error('Erro ao buscar preferências de vendors', exc_info=e)
        return jsonify({ 'error': 'Erro ao buscar preferências' }), 500

@api_v1_bp.route('/account/vendor-preferences', methods=['PUT'])
def set_vendor_preferences() -> Response:
    """Persist a list of vendor IDs as the user's preferences."""
    if not current_user.is_authenticated:
        return jsonify({ 'error': 'Authentication required' }), 401
    data = request.get_json(silent=True) or {}
    raw_ids = data.get('vendor_ids', [])
    if not isinstance(raw_ids, list):
        raise BadRequest('vendor_ids must be a list')
    # Sanitize to integers
    vendor_ids: list[int] = []
    for v in raw_ids:
        try:
            vendor_ids.append(int(v))
        except Exception:
            continue
    key = f'user_vendor_preferences:{current_user.id}'
    value = ','.join(str(x) for x in vendor_ids)
    try:
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        now = datetime.utcnow()
        if not sm:
            sm = SyncMetadata(key=key, value=value, status='active', last_modified=now, sync_type='user_pref')
            db.session.add(sm)
        else:
            sm.value = value
            sm.status = 'active'
            sm.last_modified = now
            sm.sync_type = 'user_pref'
        db.session.commit()
        return jsonify({ 'success': True, 'vendor_ids': vendor_ids }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error('Erro ao salvar preferências de vendors', exc_info=e)
        return jsonify({ 'success': False, 'error': 'Database error' }), 500


# --- Endpoints RiskAssessment ---

@api_v1_bp.route('/risk/<string:cve_id>', methods=['GET'])
def get_risk(cve_id: str) -> Response:
    """
    GET /api/v1/risk/{cve_id}
    """
    risk = RiskAssessment.query.filter_by(cve_id=cve_id).first()
    if not risk:
        raise NotFound()
    return jsonify(risk.to_dict()), 200


@api_v1_bp.route('/risk', methods=['POST'])
def create_risk() -> Response:
    """
    POST /api/v1/risk
    JSON body: { cve_id: str, score: float, details?: str }
    """
    data = request.get_json(silent=False)
    cve_id = data.get('cve_id')
    if not cve_id:
        raise BadRequest("Field 'cve_id' is required")
    risk = RiskAssessment(
        cve_id=cve_id,
        score=data.get('score', 0.0),
        details=data.get('details', '')
    )
    try:
        with db.session.begin():
            db.session.add(risk)
    except SQLAlchemyError as e:
        raise InternalServerError() from e

    loc = url_for('api_v1.get_risk', cve_id=cve_id)
    return jsonify(risk.to_dict()), 201, {'Location': loc}


# --- Endpoints Asset ---

@api_v1_bp.route('/assets', methods=['GET'])
def list_assets() -> Response:
    """
    GET /api/v1/assets
    """
    form = APIQueryForm(request.args)
    if not form.validate():
        raise BadRequest(form.errors)

    query = Asset.query
    # Filtrar por ativos do usuário autenticado (ou nenhum se público não autenticado)
    from app.extensions.middleware import filter_by_user_assets
    query = filter_by_user_assets(query)
    result = _paginate_and_serialize(query, form)
    return jsonify(result), 200


@api_v1_bp.route('/assets', methods=['POST'])
def create_asset() -> Response:
    """
    POST /api/v1/assets
    JSON body: { name: str, ip_address: str, vendor?: str, vendor_id?: int }
    """
    data = request.get_json(silent=False)
    name = data.get('name')
    ip   = data.get('ip_address')
    if not name or not ip:
        raise BadRequest("Fields 'name' and 'ip_address' are required")

    vendor_name = (data.get('vendor') or '').strip()
    vendor_id = data.get('vendor_id')
    from app.models.vendor import Vendor
    vendor = None

    try:
        with db.session.begin():
            if vendor_id:
                vendor = Vendor.query.get(vendor_id)
                if not vendor:
                    raise BadRequest("Invalid vendor_id")
            elif vendor_name:
                vendor = Vendor.query.filter(func.lower(Vendor.name) == vendor_name.lower()).first()
                if not vendor:
                    vendor = Vendor(name=vendor_name)
                    db.session.add(vendor)
                    db.session.flush()  # ensure vendor.id is set

            # Determinar owner_id: se usuário público/logado, vincular ao usuário
            from flask_login import current_user
            owner_id = None
            try:
                if current_user.is_authenticated and not getattr(current_user, 'is_admin', False):
                    owner_id = current_user.id
                else:
                    # Para admins, permitir definir explicitamente via payload
                    provided_owner = data.get('owner_id')
                    owner_id = provided_owner if isinstance(provided_owner, int) else None
            except Exception:
                owner_id = None

            asset = Asset(name=name, ip_address=ip, vendor_id=vendor.id if vendor else None, owner_id=owner_id)
            db.session.add(asset)
    except SQLAlchemyError:
        raise InternalServerError()

    # Trigger automatic CVE sync for the asset's vendor associations
    try:
        from app.services.vulnerability_service import VulnerabilityService
        vuln_service = VulnerabilityService(db.session)
        created_links = vuln_service.sync_asset_vulnerabilities_for_asset(asset.id)
        current_app.logger.info({'created_asset_vuln_links': created_links})
    except Exception:
        pass

    return jsonify({'id': asset.id, 'name': asset.name, 'ip_address': asset.ip_address}), 201


# --- Health Check ---

@api_v1_bp.route('/tickets', methods=['POST'])
def create_ticket() -> Response:
    """
    POST /api/v1/tickets
    Cria um novo ticket de suporte
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'Dados não fornecidos'}), 400
        
        # Validação básica
        required_fields = ['title', 'description', 'priority']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'Campo {field} é obrigatório'}), 400
        
        # TODO: Implementar modelo de Ticket e salvar no banco
        # Por enquanto, simular criação de ticket
        ticket_data = {
            'id': f'TKT-{hash(data.get("title", ""))}'[:10],
            'title': data.get('title'),
            'description': data.get('description'),
            'priority': data.get('priority'),
            'cve_id': data.get('cve_id'),
            'status': 'open',
            'created_at': 'now'
        }
        
        current_app.logger.info(f"Ticket criado: {ticket_data}")
        
        return jsonify({
            'success': True,
            'message': 'Ticket criado com sucesso',
            'ticket': ticket_data
        }), 201
        
    except Exception as e:
        current_app.logger.error("Erro ao criar ticket", exc_info=e)
        return jsonify({'success': False, 'message': str(e)}), 500

@api_v1_bp.route('/vulnerabilities/<string:cve_id>/mitigate', methods=['POST'])
def start_mitigation(cve_id: str) -> Response:
    """
    POST /api/v1/vulnerabilities/{cve_id}/mitigate
    Inicia o processo de mitigação para uma vulnerabilidade
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'Dados não fornecidos'}), 400
        
        # Verificar se a vulnerabilidade existe
        vulnerability = Vulnerability.query.filter_by(cve_id=cve_id).first()
        if not vulnerability:
            return jsonify({'success': False, 'message': 'Vulnerabilidade não encontrada'}), 404
        
        # Validação básica
        action = data.get('action')
        if action != 'start_mitigation':
            return jsonify({'success': False, 'message': 'Ação inválida'}), 400
        
        # TODO: Implementar modelo de Mitigação e salvar no banco
        # Por enquanto, simular início de mitigação
        mitigation_data = {
            'id': f'MIT-{hash(cve_id)}'[:10],
            'cve_id': cve_id,
            'status': 'in_progress',
            'action': action,
            'user_id': data.get('user_id'),
            'timestamp': data.get('timestamp'),
            'started_at': 'now'
        }
        
        current_app.logger.info(f"Mitigação iniciada para {cve_id}: {mitigation_data}")
        
        return jsonify({
            'success': True,
            'message': 'Processo de mitigação iniciado com sucesso',
            'mitigation': mitigation_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Erro ao iniciar mitigação para {cve_id}", exc_info=e)
        return jsonify({'success': False, 'message': str(e)}), 500


@api_v1_bp.route('/dashboard/charts', methods=['GET'])
def get_dashboard_charts_data() -> Response:
    """
    GET /api/v1/dashboard/charts
    Retorna dados para os gráficos do dashboard
    """
    try:
        from app.services.vulnerability_service import VulnerabilityService
        
        # Instanciar o serviço com a sessão do banco
        vuln_service = VulnerabilityService(db.session)
        
        # Distribuição por severidade
        severity_data = db.session.query(
            Vulnerability.base_severity,
            func.count(Vulnerability.cve_id).label('count')
        ).group_by(Vulnerability.base_severity).all()
        
        severity_distribution = {
            'labels': [item[0] or 'Unknown' for item in severity_data],
            'data': [item[1] for item in severity_data]
        }
        
        # Tendência semanal (últimas 8 semanas)
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=8)
        
        # Para SQLite, usar strftime para agrupar por semana
        weekly_data = db.session.query(
            func.strftime('%Y-%W', Vulnerability.published_date).label('week'),
            func.count(Vulnerability.cve_id).label('count')
        ).filter(
            Vulnerability.published_date >= start_date
        ).group_by(
            func.strftime('%Y-%W', Vulnerability.published_date)
        ).order_by('week').all()
        
        weekly_trend = {
            'labels': [f'Semana {item[0]}' if item[0] else 'Unknown' for item in weekly_data],
            'data': [item[1] for item in weekly_data]
        }
        
        # Timeline de vulnerabilidades (últimos 30 dias)
        timeline_start = end_date - timedelta(days=30)
        
        # Para SQLite, usar strftime para agrupar por data
        timeline_data = db.session.query(
            func.strftime('%Y-%m-%d', Vulnerability.published_date).label('date'),
            func.count(Vulnerability.cve_id).label('count')
        ).filter(
            Vulnerability.published_date >= timeline_start
        ).group_by(
            func.strftime('%Y-%m-%d', Vulnerability.published_date)
        ).order_by('date').all()
        
        vulnerability_timeline = {
            'labels': [item[0] if item[0] else 'Unknown' for item in timeline_data],
            'data': [item[1] for item in timeline_data]
        }
        
        # Top 5 CVSS Scores
        top_cvss_data = db.session.query(
            Vulnerability.cve_id,
            Vulnerability.cvss_score
        ).filter(
            Vulnerability.cvss_score.isnot(None)
        ).order_by(
            desc(Vulnerability.cvss_score)
        ).limit(5).all()
        
        top_cvss = {
            'labels': [item[0] for item in top_cvss_data],
            'data': [float(item[1]) if item[1] else 0 for item in top_cvss_data]
        }
        
        # Estatísticas gerais
        stats = vuln_service.get_dashboard_counts()
        
        return jsonify({
            'severity_distribution': severity_distribution,
            'weekly_trend': weekly_trend,
            'vulnerability_timeline': vulnerability_timeline,
            'top_cvss': top_cvss,
            'stats': stats,
            'last_updated': datetime.now().isoformat()
        }), 200
        
    except Exception as e:
        current_app.logger.error("Erro ao buscar dados dos gráficos do dashboard", exc_info=e)
        return jsonify({'error': 'Erro interno do servidor'}), 500


# IP geolocation lookup endpoint
@api_v1_bp.route('/search/ip', methods=['GET'])
def ip_lookup() -> Response:
    """
    GET /api/v1/search/ip?query=<ip_or_domain>
    Retorna dados de geolocalização e ISP/Organização.
    """
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'status': 'error', 'message': 'Parâmetro "query" é obrigatório.'}), 400

    try:
        url = f"http://ip-api.com/json/{query}?fields=status,message,query,lat,lon,country,regionName,city,isp,org"
        resp = requests.get(url, timeout=10)
        data = resp.json() if resp.ok else {}

        if not resp.ok or data.get('status') != 'success':
            msg = data.get('message') or 'Falha na consulta de geolocalização.'
            return jsonify({'status': 'error', 'message': msg}), 502

        location = ", ".join([part for part in [data.get('city'), data.get('regionName'), data.get('country')] if part])
        result = {
            'status': 'success',
            'ip': data.get('query'),
            'isp': data.get('isp'),
            'organization': data.get('org'),
            'location': location,
            'latitude': data.get('lat'),
            'longitude': data.get('lon')
        }
        return jsonify(result)
    except requests.Timeout:
        return jsonify({'status': 'error', 'message': 'Tempo de resposta excedido na consulta de geolocalização.'}), 504
    except Exception as e:
        current_app.logger.error(f"Erro ao consultar geolocalização: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Erro interno do servidor.'}), 500

@api_v1_bp.route('/health', methods=['GET'])
def api_health() -> Response:
    """
    GET /api/v1/health
    """
    try:
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        return jsonify(status='healthy', service='api_v1'), 200
    except Exception as e:
        current_app.logger.error("Health check failed", exc_info=e)
        return jsonify(status='unhealthy', error=str(e)), 500
