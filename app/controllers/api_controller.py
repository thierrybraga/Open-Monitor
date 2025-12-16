# controllers/api_controller.py

from flask import Blueprint, jsonify, request, current_app, url_for, session
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
from datetime import datetime, timedelta, timezone
from sqlalchemy import func, desc, or_, cast, Text, text
from sqlalchemy.orm import load_only
import requests
import os
from datetime import datetime, timezone, timedelta
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
    # Sempre retornar detalhes do erro para facilitar depuração desta rota
    try:
        detail = str(getattr(e, 'orig', e))
    except Exception:
        detail = str(e)
    return jsonify(error='Database error', detail=detail), 500

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
        
        # Calcular tempo desde última sincronização com tolerância a naive datetimes
        now = datetime.now(timezone.utc)
        last_mod = last_sync.last_modified
        try:
            if getattr(last_mod, 'tzinfo', None) is None:
                last_mod = last_mod.replace(tzinfo=timezone.utc)
        except Exception:
            pass
        time_diff = now - last_mod
        
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

# --- Diagnostics: Database/MER ---

@api_v1_bp.route('/diagnostics/db', methods=['GET'])
def get_db_diagnostics() -> Response:
    try:
        from sqlalchemy import func
        from app.models.vendor import Vendor
        from app.models.cve_vendor import CVEVendor
        from app.models.product import Product
        from app.models.cve_product import CVEProduct
        from app.models.cvss_metric import CVSSMetric
        from app.models.vulnerability import Vulnerability
        try:
            from app.models.cve_part import CVEPart
            parts_count = int(db.session.query(func.count(CVEPart.cve_id)).scalar() or 0)
        except Exception:
            parts_count = None

        vendors_count = int(db.session.query(func.count(Vendor.id)).scalar() or 0)
        cve_vendors_count = int(db.session.query(func.count(CVEVendor.vendor_id)).scalar() or 0)
        products_count = int(db.session.query(func.count(Product.id)).scalar() or 0)
        cve_products_count = int(db.session.query(func.count(CVEProduct.product_id)).scalar() or 0)
        vulnerabilities_count = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
        cvss_metrics_count = int(db.session.query(func.count(CVSSMetric.id)).scalar() or 0)
        try:
            non_null_nvd_vendors = int(db.session.query(func.count(Vulnerability.cve_id)).filter(Vulnerability.nvd_vendors_data.isnot(None)).scalar() or 0)
        except Exception:
            non_null_nvd_vendors = None
        try:
            non_null_nvd_products = int(db.session.query(func.count(Vulnerability.cve_id)).filter(Vulnerability.nvd_products_data.isnot(None)).scalar() or 0)
        except Exception:
            non_null_nvd_products = None

        # Sync metadata snapshot
        def _get_meta(key: str):
            m = db.session.query(SyncMetadata).filter_by(key=key).first()
            return (m.value if m and m.value is not None else None)

        meta_snapshot = {
            'nvd_first_sync_completed': _get_meta('nvd_first_sync_completed'),
            'nvd_sync_progress_status': _get_meta('nvd_sync_progress_status'),
            'nvd_sync_progress_total': _get_meta('nvd_sync_progress_total'),
            'nvd_sync_progress_current': _get_meta('nvd_sync_progress_current'),
            'nvd_sync_progress_last_cve': _get_meta('nvd_sync_progress_last_cve'),
            'nvd_sync_progress_saving': _get_meta('nvd_sync_progress_saving')
        }

        # Top vendors by CVE count (sample)
        top_vendors = []
        try:
            rows = (
                db.session.query(Vendor.name, func.count(func.distinct(CVEVendor.cve_id)).label('cve_count'))
                .join(CVEVendor, CVEVendor.vendor_id == Vendor.id)
                .group_by(Vendor.id, Vendor.name)
                .order_by(func.count(func.distinct(CVEVendor.cve_id)).desc(), Vendor.name.asc())
                .limit(10)
                .all()
            )
            for name, cnt in rows:
                top_vendors.append({'name': name, 'cve_count': int(cnt or 0)})
        except Exception:
            top_vendors = []

        return jsonify({
            'status': 'success',
            'counts': {
                'vendors': vendors_count,
                'cve_vendors': cve_vendors_count,
                'products': products_count,
                'cve_products': cve_products_count,
                'vulnerabilities': vulnerabilities_count,
                'cvss_metrics': cvss_metrics_count,
                'cve_parts': parts_count,
                'vulns_with_nvd_vendors_json': non_null_nvd_vendors,
                'vulns_with_nvd_products_json': non_null_nvd_products
            },
            'meta': meta_snapshot,
            'samples': {
                'top_vendors': top_vendors
            }
        }), 200
    except Exception as e:
        current_app.logger.error(f"Erro em /diagnostics/db: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Erro interno do servidor'}), 500

@api_v1_bp.route('/me', methods=['GET'])
def get_me() -> Response:
    try:
        return jsonify({
            'is_authenticated': bool(getattr(current_user, 'is_authenticated', False)),
            'is_admin': bool(getattr(current_user, 'is_admin', False)),
            'user_id': int(getattr(current_user, 'id', 0) or 0)
        }), 200
    except Exception:
        return jsonify({'is_authenticated': False, 'is_admin': False}), 200

@api_v1_bp.route('/system/bootstrap', methods=['GET'])
def get_system_bootstrap() -> Response:
    try:
        try:
            db.session.rollback()
        except Exception:
            pass
        from app.models.user import User
        active_cnt = db.session.query(User).filter(
            (User.is_active == True) &
            (User.password_hash.isnot(None)) &
            (db.func.length(User.password_hash) > 0)
        ).count()
        has_admin_user = db.session.query(User).filter(User.is_admin == True).count() > 0
        has_active_user = (active_cnt > 0) or has_admin_user

        first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
        first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
        first_sync_completed = first_done_val in ('1','true','yes')

        status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
        status_val = str(status_meta.value or '').strip().lower() if status_meta and status_meta.value is not None else 'idle'
        total_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_total').first()
        current_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
        try:
            total_est = int(total_meta.value) if total_meta and total_meta.value and str(total_meta.value).isdigit() else None
        except Exception:
            total_est = None
        try:
            current_val = int(current_meta.value) if current_meta and current_meta.value and str(current_meta.value).isdigit() else None
        except Exception:
            current_val = None
        try:
            if isinstance(total_est, int) and total_est > 0:
                if not isinstance(current_val, int) or current_val < total_est:
                    first_sync_completed = False
        except Exception:
            pass
        derived_in_progress = (status_val in ('processing','saving')) or (isinstance(total_est, int) and isinstance(current_val, int) and total_est > 0 and current_val > 0 and current_val < total_est)
        sync_in_progress = bool(derived_in_progress)
        from sqlalchemy import func
        from app.models.vulnerability import Vulnerability
        local_total_cves = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)

        req_meta = db.session.query(SyncMetadata).filter_by(key='require_root_setup').first()
        req_val = (req_meta.value or '').strip().lower() if req_meta and req_meta.value else ''
        require_root_setup = (req_val not in ('false','0','no'))
        if has_active_user and require_root_setup:
            require_root_setup = False
            try:
                if req_meta:
                    req_meta.value = 'false'
                else:
                    req_meta = SyncMetadata(key='require_root_setup', value='false')
                    db.session.add(req_meta)
                db.session.commit()
            except Exception:
                db.session.rollback()

        try:
            nvd_total_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_total').first()
            nvd_total_estimate = int(nvd_total_meta.value) if nvd_total_meta and nvd_total_meta.value and str(nvd_total_meta.value).isdigit() else None
        except Exception:
            nvd_total_estimate = None
        next_refresh_seconds = 10 if (not first_sync_completed or sync_in_progress) else 600

        # Status do banco de dados
        db_status = {}
        try:
            from sqlalchemy import inspect
            from pathlib import Path
            from sqlalchemy import func
            from app.models.vendor import Vendor
            from app.models.product import Product
            from app.models.cve_vendor import CVEVendor
            from app.models.cve_product import CVEProduct
            from app.models.vulnerability import Vulnerability
            engine_name = str(getattr(db.engine.url, 'drivername', 'unknown'))
            tables_count = 0
            try:
                insp = inspect(db.engine)
                tables_count = len(insp.get_table_names())
            except Exception:
                tables_count = 0
            db_status['engine'] = engine_name
            db_status['tables_count'] = tables_count
            # Contagens principais para verificação rápida de população NVD
            try:
                db_status['counts'] = {
                    'vendors': int(db.session.query(func.count(Vendor.id)).scalar() or 0),
                    'products': int(db.session.query(func.count(Product.id)).scalar() or 0),
                    'cve_vendors': int(db.session.query(func.count(CVEVendor.cve_id)).scalar() or 0),
                    'cve_products': int(db.session.query(func.count(CVEProduct.product_id)).scalar() or 0),
                    'vulnerabilities': int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
                }
            except Exception:
                db_status['counts'] = {}
            if engine_name.startswith('sqlite'):
                db_path = getattr(db.engine.url, 'database', None)
                db_status['sqlite_path'] = db_path
                exists = False
                size_bytes = None
                try:
                    if db_path:
                        p = Path(db_path)
                        exists = p.exists()
                        if exists:
                            try:
                                size_bytes = p.stat().st_size
                            except Exception:
                                size_bytes = None
                except Exception:
                    exists = False
                    size_bytes = None
                db_status['sqlite_exists'] = exists
                db_status['sqlite_size_bytes'] = size_bytes
            try:
                last_sync_meta = db.session.query(SyncMetadata).filter_by(key='nvd_last_sync').first()
                if last_sync_meta:
                    db_status['last_sync'] = {
                        'timestamp': last_sync_meta.value,
                        'status': getattr(last_sync_meta, 'status', None)
                    }
            except Exception:
                pass
        except Exception:
            db_status = {}

        # total_cves deve refletir o total disponível na NIST quando estimado,
        # com fallback para o total local quando ainda não houver estimativa
        total_cves = nvd_total_estimate if isinstance(nvd_total_estimate, int) else local_total_cves
        return jsonify({
            'has_active_user': has_active_user,
            'first_sync_completed': first_sync_completed,
            'sync_in_progress': sync_in_progress,
            'require_root_setup': require_root_setup,
            'total_cves': total_cves,
            'next_refresh_seconds': next_refresh_seconds,
            'nvd_total_estimate': nvd_total_estimate,
            'local_total_cves': local_total_cves,
            'db_status': db_status
        }), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao obter bootstrap status: {e}", exc_info=True)
        return jsonify({'error': 'Erro ao obter bootstrap status'}), 500

@api_v1_bp.route('/sync/progress', methods=['GET'])
def get_sync_progress() -> Response:
    try:
        allow_public = False
        try:
            first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
            first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
            if first_done_val not in ('1','true','yes'):
                allow_public = True
        except Exception:
            allow_public = True
        if not allow_public:
            if not getattr(current_user, 'is_authenticated', False):
                return jsonify({'status': 'error', 'message': 'Auth required'}), 401
            if not getattr(current_user, 'is_admin', False):
                return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
        from app.models.sync_metadata import SyncMetadata
        from sqlalchemy import func
        count = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
        # Progresso em tempo real: priorizar cache Redis e fazer fallback para DB
        try:
            total = None
            current_val = None
            status_val = None
            last_cve_id = None
            saving_count = None
            saving_start = None
            try:
                from app.services.redis_cache_service import RedisCacheService
                cfg = {
                    'REDIS_CACHE_ENABLED': current_app.config.get('REDIS_CACHE_ENABLED', False),
                    'REDIS_URL': current_app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
                    'REDIS_HOST': current_app.config.get('REDIS_HOST', 'localhost'),
                    'REDIS_PORT': current_app.config.get('REDIS_PORT', 6379),
                    'REDIS_DB': current_app.config.get('REDIS_DB', 0),
                    'REDIS_PASSWORD': current_app.config.get('REDIS_PASSWORD'),
                    'CACHE_KEY_PREFIX': current_app.config.get('CACHE_KEY_PREFIX', 'nvd_cache:')
                }
                rc = RedisCacheService(cfg)
                if getattr(rc, 'enabled', False) and getattr(rc, 'redis_client', None):
                    try:
                        cv = rc.get('nvd_sync_progress_current', namespace='sync_status')
                        tv = rc.get('nvd_sync_progress_total', namespace='sync_status')
                        sv = rc.get('nvd_sync_progress_status', namespace='sync_status')
                        lv = rc.get('nvd_sync_progress_last_cve', namespace='sync_status')
                        sc = rc.get('nvd_sync_progress_saving', namespace='sync_status')
                        ss = rc.get('nvd_sync_progress_saving_start', namespace='sync_status')
                        if isinstance(cv, (int, float, str)):
                            try: current_val = int(cv)
                            except Exception: current_val = None
                        if isinstance(tv, (int, float, str)):
                            try: total = int(tv)
                            except Exception: total = None
                        if isinstance(sv, str):
                            status_val = sv
                        if isinstance(lv, str):
                            last_cve_id = lv
                        if isinstance(sc, (int, float, str)):
                            try: saving_count = int(sc)
                            except Exception: saving_count = None
                        if isinstance(ss, (int, float, str)):
                            try: saving_start = int(ss)
                            except Exception: saving_start = None
                    except Exception:
                        pass
            except Exception:
                pass
            if (total is None) or (current_val is None) or (status_val is None) or (saving_start is None):
                try:
                    total_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_total').first()
                    current_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_current').first()
                    status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                    last_cve_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_last_cve').first()
                    saving_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_saving').first()
                    saving_start_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_saving_start').first()
                    total = int(total_meta.value) if total_meta and total_meta.value and str(total_meta.value).isdigit() else total
                    current_val = int(current_meta.value) if current_meta and current_meta.value and str(current_meta.value).isdigit() else current_val
                    status_val = status_meta.value if status_meta else status_val
                    last_cve_id = (last_cve_meta.value if last_cve_meta else last_cve_id)
                    saving_count = int(saving_meta.value) if saving_meta and saving_meta.value and str(saving_meta.value).isdigit() else saving_count
                    saving_start = int(saving_start_meta.value) if saving_start_meta and saving_start_meta.value and str(saving_start_meta.value).isdigit() else saving_start
                except Exception:
                    pass
            overall_percentage = None
            if total and current_val is not None and total > 0:
                try:
                    overall_percentage = round(min(100.0, (current_val / total) * 100.0), 2)
                except Exception:
                    overall_percentage = None
            saving_percentage = None
            try:
                if isinstance(saving_count, int) and saving_count > 0:
                    try:
                        saving_start_val = int(saving_start) if saving_start is not None else 0
                    except Exception:
                        saving_start_val = 0
                    try:
                        saving_done = max(0, int(count) - saving_start_val)
                    except Exception:
                        saving_done = 0
                    try:
                        saving_done = min(saving_done, int(saving_count))
                    except Exception:
                        pass
                    try:
                        saving_percentage = round(min(100.0, (saving_done / float(saving_count)) * 100.0), 2)
                    except Exception:
                        saving_percentage = None
            except Exception:
                saving_percentage = None
            try:
                derived_status = status_val
                if isinstance(saving_count, int) and saving_count > 0:
                    derived_status = 'saving'
                elif (not derived_status or str(derived_status).strip().lower() == 'idle') and (isinstance(total, int) and isinstance(current_val, int) and total > 0 and current_val > 0 and current_val < total):
                    derived_status = 'processing'
            except Exception:
                derived_status = status_val
            return jsonify({
                'status': 'success',
                'synced_count': count,
                'total_estimate': total,
                'percentage': (saving_percentage if (isinstance(saving_count, int) and saving_count > 0) else overall_percentage),
                'live': {
                    'status': derived_status,
                    'current': current_val,
                    'total': total,
                    'last_cve_id': last_cve_id,
                    'saving_count': saving_count,
                    'saving_percentage': saving_percentage
                }
            }), 200
        except Exception:
            return jsonify({
                'status': 'success',
                'synced_count': count,
                'total_estimate': None,
                'percentage': None
            }), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao obter progresso de sincronização: {e}", exc_info=True)
        return jsonify({'status': 'error', 'message': 'Erro interno do servidor'}), 500

@api_v1_bp.route('/user/tacacs', methods=['POST'])
def update_tacacs_settings():
    try:
        if not getattr(current_user, 'is_authenticated', False):
            return jsonify({'error': 'Unauthorized'}), 401
        data = request.get_json() or {}
        enabled = bool(data.get('enabled'))
        username = (data.get('username') or '').strip() or None
        secret = (data.get('secret') or '').strip() or None
        server = (data.get('server') or '').strip() or None
        try:
            port = int(data.get('port') or 49)
        except Exception:
            port = 49
        try:
            timeout = int(data.get('timeout') or 5)
        except Exception:
            timeout = 5
        try:
            from app.models.user import User
            user = db.session.query(User).get(current_user.id)
            user.tacacs_enabled = enabled
            user.tacacs_username = username
            user.tacacs_secret = secret
            user.tacacs_server = server
            user.tacacs_port = port
            user.tacacs_timeout = timeout
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'error': 'Database error'}), 500
        return jsonify({'success': True})
    except Exception:
        return jsonify({'error': 'Unexpected error'}), 500


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
        # Garantir que o banco esteja inicializado/validado antes de sincronizar
        try:
            from app.main_startup import initialize_database
            with current_app.app_context():
                initialize_database(current_app)
        except Exception as _db_init_err:
            current_app.logger.warning(f"Falha ao validar/criar tabelas antes da sincronização: {_db_init_err}")
        status_meta = SyncMetadata.query.filter_by(key='nvd_sync_progress_status').first()
        if status_meta and str((status_meta.value or '')).strip().lower() in ('processing','saving'):
            try:
                current_meta = SyncMetadata.query.filter_by(key='nvd_sync_progress_current').first()
                total_meta = SyncMetadata.query.filter_by(key='nvd_sync_progress_total').first()
                cur_val = int(current_meta.value) if current_meta and current_meta.value and str(current_meta.value).isdigit() else 0
                tot_val = int(total_meta.value) if total_meta and total_meta.value and str(total_meta.value).isdigit() else 0
                last_mod = getattr(status_meta, 'last_modified', None)
                is_stale = False
                if last_mod:
                    lm = last_mod if getattr(last_mod, 'tzinfo', None) else last_mod.replace(tzinfo=timezone.utc)
                    is_stale = (datetime.now(timezone.utc) - lm) > timedelta(seconds=30)
                if (cur_val == 0) and ((total_meta is None) or (tot_val == 0) or is_stale):
                    status_meta.value = 'idle'
                    status_meta.last_modified = datetime.now(timezone.utc)
                    db.session.commit()
                else:
                    return jsonify({'status': 'accepted', 'message': 'Sincronização já em andamento'}), 202
            except Exception:
                try:
                    status_meta.value = 'idle'
                    status_meta.last_modified = datetime.now(timezone.utc)
                    db.session.commit()
                except Exception:
                    pass
        
        # Obter parâmetros da requisição
        data = request.get_json() or {}
        full_sync = data.get('full', False)
        max_pages = data.get('max_pages', None)
        mode = str(data.get('mode') or os.getenv('OM_SYNC_MODE','pipeline')).strip().lower()
        workers_raw = data.get('workers') or os.getenv('OM_SYNC_WORKERS','10')
        try:
            max_workers = int(workers_raw)
        except Exception:
            max_workers = 10
        
        # Validar parâmetros
        if max_pages is not None and (not isinstance(max_pages, int) or max_pages <= 0):
            return jsonify({
                'status': 'error',
                'message': 'max_pages deve ser um número inteiro positivo'
            }), 400
        
        app_obj = current_app._get_current_object()
        mode_is_seq = (mode == 'sequential')
        if not mode_is_seq:
            from app.jobs.enhanced_nvd_fetcher import EnhancedNVDFetcher
            import asyncio
        def run_sync():
            from datetime import datetime as dt, timezone as tz
            try:
                with app_obj.app_context():
                    if mode_is_seq:
                        import asyncio as aio
                        import aiohttp
                        from app.jobs.nvd_fetcher import NVDFetcher
                        from app.services.vulnerability_service import VulnerabilityService
                        from app.extensions import db as _db
                        vs = VulnerabilityService(_db.session)
                        cfg = {
                            "NVD_API_BASE": app_obj.config.get("NVD_API_BASE", "https://services.nvd.nist.gov/rest/json/cves/2.0"),
                            "NVD_API_KEY": app_obj.config.get("NVD_API_KEY"),
                            "NVD_PAGE_SIZE": app_obj.config.get("NVD_PAGE_SIZE", 2000),
                            "NVD_REQUEST_TIMEOUT": app_obj.config.get("NVD_REQUEST_TIMEOUT", 30),
                            "NVD_USER_AGENT": app_obj.config.get("NVD_USER_AGENT", "Open-Monitor NVD Fetcher"),
                            "NVD_MAX_WINDOW_DAYS": app_obj.config.get("NVD_MAX_WINDOW_DAYS", 120),
                            "NVD_RATE_LIMIT": app_obj.config.get("NVD_RATE_LIMIT", (2, 1)),
                        }
                        loop = aio.new_event_loop()
                        aio.set_event_loop(loop)
                        try:
                            async def _run_seq():
                                async with aiohttp.ClientSession() as session:
                                    fetcher2 = NVDFetcher(session, cfg)
                                    return await fetcher2.update(vs, full=full_sync)
                            result = loop.run_until_complete(_run_seq())
                        finally:
                            loop.close()
                    else:
                        fetcher = EnhancedNVDFetcher(app=app_obj, max_workers=max_workers, enable_cache=True)
                        import asyncio
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        try:
                            result = loop.run_until_complete(
                                fetcher.sync_nvd(full=full_sync, max_pages=max_pages, use_parallel=True)
                            )
                        finally:
                            loop.close()
                    try:
                        app_obj.logger.info(f"Sincronização NVD concluída: {result} vulnerabilidades processadas")
                    except Exception:
                        pass
                    try:
                        from app.extensions import db
                        from app.models.sync_metadata import SyncMetadata
                        now = dt.now(tz.utc)
                        last_sync = db.session.query(SyncMetadata).filter_by(key='nvd_last_sync').first()
                        if (isinstance(result, int) and result > 0):
                            if not last_sync:
                                last_sync = SyncMetadata(
                                    key='nvd_last_sync',
                                    value=now.isoformat(),
                                    status='completed',
                                    sync_type=('completa' if full_sync else 'incremental'),
                                    last_modified=now
                                )
                                db.session.add(last_sync)
                            else:
                                last_sync.value = now.isoformat()
                                last_sync.status = 'completed'
                                last_sync.sync_type = ('completa' if full_sync else 'incremental')
                                last_sync.last_modified = now
                        else:
                            if not last_sync:
                                last_sync = SyncMetadata(
                                    key='nvd_last_sync',
                                    value=None,
                                    status='no_data',
                                    sync_type=('completa' if full_sync else 'incremental'),
                                    last_modified=now
                                )
                                db.session.add(last_sync)
                            else:
                                last_sync.status = 'no_data'
                                last_sync.sync_type = ('completa' if full_sync else 'incremental')
                                last_sync.last_modified = now
                        status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                        if status_meta:
                            status_meta.value = 'idle'
                            status_meta.last_modified = now
                        db.session.commit()
                    except Exception as _final_meta_err:
                        try:
                            app_obj.logger.warning(f"Erro ao finalizar metadata pós-sync: {_final_meta_err}")
                        except Exception:
                            pass
                        try:
                            db.session.rollback()
                        except Exception:
                            pass
                    return result
            except Exception as e:
                try:
                    app_obj.logger.error(f"Erro na sincronização NVD: {e}")
                except Exception:
                    pass
                try:
                    from app.extensions import db
                    from app.models.sync_metadata import SyncMetadata
                    now = dt.now(tz.utc)
                    status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
                    if status_meta:
                        status_meta.value = 'idle'
                        status_meta.last_modified = now
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
        
        # Executar em thread separada para não bloquear a resposta
        import threading
        if str(os.getenv('OM_DISABLE_SYNC_THREADS','')).strip().lower() != 'true':
            threading.Thread(target=run_sync, daemon=True).start()
        
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
                    last_modified=datetime.now(timezone.utc)
                )
                db.session.add(sync_metadata)
            else:
                sync_metadata.status = 'in_progress'
                sync_metadata.sync_type = sync_type.lower()
                sync_metadata.last_modified = datetime.now(timezone.utc)

            # Sinalizar progresso imediato para a página de loading
            status_meta = SyncMetadata.query.filter_by(key='nvd_sync_progress_status').first()
            if not status_meta:
                status_meta = SyncMetadata(key='nvd_sync_progress_status', value='processing')
                db.session.add(status_meta)
            else:
                status_meta.value = 'processing'
            current_meta = SyncMetadata.query.filter_by(key='nvd_sync_progress_current').first()
            if not current_meta:
                current_meta = SyncMetadata(key='nvd_sync_progress_current', value='0')
                db.session.add(current_meta)
            else:
                current_meta.value = '0'
            
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
            'mode': mode,
            'workers': max_workers,
            'started_at': datetime.now(timezone.utc).isoformat()
        }), 202  # 202 Accepted - processamento assíncrono iniciado
        
    except ImportError as e:
        current_app.logger.error(f"Erro ao importar EnhancedNVDFetcher: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Serviço de sincronização não disponível'
        }), 503
        
    except Exception as e:
        current_app.logger.error(f"Erro ao iniciar sincronização NVD: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@api_v1_bp.route('/sync/backfill', methods=['POST'])
def trigger_backfill() -> Response:
    """
    POST /api/v1/sync/backfill
    Dispara backfill das tabelas normalizadas de vendors/produtos.

    Body (JSON):
    {
        "target": "vendors" | "products" | "all",
        "batch_limit": <int>
    }
    """
    try:
        data = request.get_json() or {}
        target = str(data.get('target') or 'all').strip().lower()
        try:
            batch_limit = int(data.get('batch_limit') or 5000)
        except Exception:
            batch_limit = 5000

        def run_backfill(app):
            from app.services.bulk_database_service import BulkDatabaseService
            from sqlalchemy import func
            with app.app_context():
                svc = BulkDatabaseService(batch_size=current_app.config.get('DB_BATCH_SIZE', 500))
                stats = {}
                if target in ('vendors', 'all'):
                    s = svc.backfill_vendors_from_vulnerabilities(session=db.session, batch_limit=batch_limit)
                    stats['vendors'] = s
                if target in ('products', 'all'):
                    s = svc.backfill_products_from_vulnerabilities(session=db.session, batch_limit=batch_limit)
                    stats['products'] = s
                try:
                    from app.models.sync_metadata import SyncMetadata
                    now = datetime.now(timezone.utc)
                    meta = db.session.query(SyncMetadata).filter_by(key='last_backfill_stats').first()
                    payload = {
                        'target': target,
                        'stats': stats,
                        'completed_at': now.isoformat()
                    }
                    if not meta:
                        meta = SyncMetadata(key='last_backfill_stats', value=json.dumps(payload), last_modified=now)
                        db.session.add(meta)
                    else:
                        meta.value = json.dumps(payload)
                        meta.last_modified = now
                    db.session.commit()
                except Exception:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass

        import threading, json
        app_obj = current_app._get_current_object()
        threading.Thread(target=run_backfill, args=(app_obj,), daemon=True).start()

        return jsonify({
            'status': 'accepted',
            'message': 'Backfill iniciado',
            'target': target,
            'batch_limit': batch_limit,
            'started_at': datetime.now(timezone.utc).isoformat()
        }), 202

    except Exception as e:
        current_app.logger.error(f"Erro ao iniciar backfill: {e}")
        return jsonify({'status': 'error', 'message': 'Erro interno do servidor'}), 500


# --- Helpers ---

def _apply_filters(query, params: APIQueryForm) -> Any:
    if params.severity.data:
        query = query.filter_by(base_severity=params.severity.data)
    # Filtro por catalog_tag (NVD Catalog Tag) mapeado para CPE part com fallback via JSON
    try:
        catalog_tag = (params.catalog_tag.data or '').strip().lower() if hasattr(params, 'catalog_tag') else ''
        part_map = {
            'application': 'a',
            'operating_system': 'o',
            'hardware': 'h',
            # compatibilidade legada
            'software': 'a',
            'os': 'o'
        }
        selected_part = part_map.get(catalog_tag)
        if selected_part:
            from app.models.cve_part import CVEPart
            part_subq = db.session.query(CVEPart.cve_id).filter(CVEPart.part == selected_part)
            like_expr = f"%cpe:2.3:{selected_part}%"
            query = query.filter(
                or_(
                    Vulnerability.cve_id.in_(part_subq),
                    func.lower(cast(Vulnerability.nvd_cpe_configurations, Text)).like(like_expr)
                )
            )
    except Exception as e:
        current_app.logger.warning(f"Falha ao aplicar filtro catalog_tag: {e}")
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
    else:
        # Apply user vendor preferences globally when no explicit vendor filter is provided
        try:
            if current_user.is_authenticated:
                from app.models.sync_metadata import SyncMetadata
                from app.models.cve_vendor import CVEVendor
                key = f'user_vendor_preferences:{current_user.id}'
                sm = db.session.query(SyncMetadata).filter_by(key=key).first()
                vendor_ids: list[int] = []
                if sm and sm.value:
                    try:
                        vendor_ids = [int(x) for x in sm.value.split(',') if x.strip().isdigit()]
                    except Exception:
                        vendor_ids = []
                if vendor_ids:
                    query = (
                        query
                        .join(CVEVendor, CVEVendor.cve_id == Vulnerability.cve_id)
                        .filter(CVEVendor.vendor_id.in_(vendor_ids))
                        .distinct()
                    )
        except Exception as e:
            current_app.logger.warning(f"Falha ao aplicar preferências globais de vendor: {e}")
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
        # Validar e normalizar paginação básica
        limit = min(max(1, limit), 100)
        offset = max(0, offset)
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

@api_v1_bp.route('/account/vendor-preferences', methods=['PUT', 'POST'])
def set_vendor_preferences() -> Response:
    """Persist a list of vendor IDs as the user's preferences."""
    if not current_user.is_authenticated:
        return jsonify({ 'error': 'Authentication required' }), 401
    # Suportar payloads enviados via navigator.sendBeacon (POST com Blob)
    data = request.get_json(silent=True) or {}
    if not data and request.method == 'POST':
        try:
            raw = request.get_data(as_text=True) or ''
            import json as _json
            data = _json.loads(raw) if raw else {}
        except Exception:
            data = {}
    raw_ids = data.get('vendor_ids', [])
    if not isinstance(raw_ids, list):
        raise BadRequest('vendor_ids must be a list')

    # Sanitizar, deduplicar e validar limites
    vendor_ids: list[int] = []
    for v in raw_ids:
        try:
            vendor_ids.append(int(v))
        except Exception:
            continue
    # Remover duplicados e ordenar para consistência
    vendor_ids = sorted(set(vendor_ids))

    # Limitar quantidade máxima para evitar payloads excessivos
    MAX_PREFS = 100
    if len(vendor_ids) > MAX_PREFS:
        return jsonify({
            'success': False,
            'error': f'Número de vendors excede o máximo permitido ({MAX_PREFS})',
            'max': MAX_PREFS
        }), 400

    # Validar que IDs existem
    from app.models.vendor import Vendor
    if vendor_ids:
        existing = db.session.query(Vendor.id).filter(Vendor.id.in_(vendor_ids)).all()
        existing_ids = {row.id for row in existing}
        invalid_ids = [vid for vid in vendor_ids if vid not in existing_ids]
        if invalid_ids:
            return jsonify({
                'success': False,
                'error': 'IDs de vendor inválidos',
                'invalid_ids': invalid_ids
            }), 400
    key = f'user_vendor_preferences:{current_user.id}'
    value = ','.join(str(x) for x in vendor_ids)
    try:
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        now = datetime.now(timezone.utc)
        if not sm:
            sm = SyncMetadata(key=key, value=value, status='active', last_modified=now, sync_type='user_pref')
            db.session.add(sm)
        else:
            sm.value = value
            sm.status = 'active'
            sm.last_modified = now
            sm.sync_type = 'user_pref'
        db.session.commit()
        # Para beacon POST, responder rapidamente
        if request.method == 'POST':
            return jsonify({ 'success': True }), 200
        return jsonify({ 'success': True, 'vendor_ids': vendor_ids }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error('Erro ao salvar preferências de vendors', exc_info=e)
        return jsonify({ 'success': False, 'error': 'Database error' }), 500


# --- User Asset Preference ---

@api_v1_bp.route('/account/asset-preference', methods=['GET'])
def get_asset_preference() -> Response:
    """Retorna o asset_id preferido do usuário autenticado."""
    try:
        if not current_user.is_authenticated:
            return jsonify({ 'asset_id': None, 'authenticated': False }), 200
        from app.models.sync_metadata import SyncMetadata
        from app.models.asset import Asset
        key = f'user_asset_preference:{current_user.id}'
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        asset_id = None
        if sm and sm.value:
            raw = str(sm.value).strip()
            if raw.isdigit():
                aid = int(raw)
                exists = db.session.query(Asset.id).filter(Asset.id == aid).first()
                asset_id = aid if exists else None
        return jsonify({ 'asset_id': asset_id, 'authenticated': True }), 200
    except Exception as e:
        current_app.logger.error('Erro ao buscar preferência de asset', exc_info=e)
        return jsonify({ 'error': 'Erro ao buscar preferência' }), 500


@api_v1_bp.route('/account/asset-preference', methods=['PUT', 'POST'])
def set_asset_preference() -> Response:
    """Persiste o asset_id preferido do usuário autenticado."""
    if not current_user.is_authenticated:
        return jsonify({ 'error': 'Authentication required' }), 401
    data = request.get_json(silent=True) or {}
    if not data and request.method == 'POST':
        try:
            raw = request.get_data(as_text=True) or ''
            import json as _json
            data = _json.loads(raw) if raw else {}
        except Exception:
            data = {}
    raw_id = data.get('asset_id')
    asset_id = None
    if raw_id is None or raw_id == '':
        asset_id = None
    elif isinstance(raw_id, int):
        asset_id = raw_id
    elif isinstance(raw_id, str) and raw_id.strip().isdigit():
        asset_id = int(raw_id.strip())
    else:
        raise BadRequest('asset_id inválido')

    from app.models.asset import Asset
    if asset_id is not None:
        exists = db.session.query(Asset.id).filter(Asset.id == asset_id).first()
        if not exists:
            return jsonify({ 'success': False, 'error': 'ID de asset inválido' }), 400

    from app.models.sync_metadata import SyncMetadata
    try:
        key = f'user_asset_preference:{current_user.id}'
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        now = datetime.now(timezone.utc)
        value = (str(asset_id) if asset_id is not None else None)
        if not sm:
            sm = SyncMetadata(key=key, value=value, status='active', last_modified=now, sync_type='user_pref')
            db.session.add(sm)
        else:
            sm.value = value
            sm.status = 'active'
            sm.last_modified = now
            sm.sync_type = 'user_pref'
        db.session.commit()
        if request.method == 'POST':
            return jsonify({ 'success': True }), 200
        return jsonify({ 'success': True, 'asset_id': asset_id }), 200
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error('Erro ao salvar preferência de asset', exc_info=e)
        return jsonify({ 'success': False, 'error': 'Database error' }), 500


# --- User Settings (per-user persistence) ---
 
@api_v1_bp.route('/home/overview', methods=['GET'])
def get_home_overview() -> Response:
    """Retorna overview da Home (contadores e recentes) em JSON.

    Query params:
      - page, per_page
      - vendor_ids (lista ou CSV)
    """
    try:
        try:
            page = max(int(request.args.get('page', 1)), 1)
        except Exception:
            page = 1
        try:
            per_page = max(min(int(request.args.get('per_page', 10)), 50), 1)
        except Exception:
            per_page = 10
        vendor_ids: list[int] = []
        try:
            raw_multi = request.args.getlist('vendor_ids')
            raw_single = request.args.get('vendor_ids')
            parsed: list[int] = []
            for v in raw_multi:
                for p in str(v).split(','):
                    p = p.strip()
                    if p.isdigit():
                        parsed.append(int(p))
            if raw_single:
                for p in str(raw_single).split(','):
                    p = p.strip()
                    if p.isdigit():
                        parsed.append(int(p))
            if parsed:
                vendor_ids = sorted(list(set(parsed)))
        except Exception:
            vendor_ids = []

        sync_in_progress = False
        try:
            status_meta = db.session.query(SyncMetadata).filter_by(key='nvd_sync_progress_status').first()
            first_done_meta = db.session.query(SyncMetadata).filter_by(key='nvd_first_sync_completed').first()
            first_done_val = (first_done_meta.value or '').strip().lower() if first_done_meta and first_done_meta.value else ''
            if not first_done_meta or first_done_val not in ('1', 'true', 'yes'):
                sync_in_progress = True
            elif status_meta and (str(status_meta.value or '').strip().lower() == 'processing'):
                sync_in_progress = True
            # Fallback: se já há CVEs, não bloquear overview
            if sync_in_progress:
                from sqlalchemy import func
                total_cves = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
                if total_cves > 0:
                    sync_in_progress = False
        except Exception:
            try:
                from sqlalchemy import func
                total_cves = int(db.session.query(func.count(Vulnerability.cve_id)).scalar() or 0)
                sync_in_progress = (total_cves == 0)
            except Exception:
                sync_in_progress = True

        if sync_in_progress:
            return jsonify({
                'sync_in_progress': True,
                'counts': {
                    'total': 0,
                    'critical': 0,
                    'high': 0,
                    'medium': 0
                },
                'weekly': {
                    'total': 0,
                    'critical': 0,
                    'high': 0,
                    'medium': 0
                },
                'vulnerabilities': [],
                'pagination': { 'page': 1, 'per_page': per_page, 'total': 0, 'pages': 1 },
                'vendor_ids': vendor_ids
            }), 200

        session = db.session
        svc = VulnerabilityService(session)
        vulns, total_count = svc.get_recent_paginated(page=page, per_page=per_page, vendor_ids=vendor_ids or None)
        counts = svc.get_dashboard_counts(vendor_ids=vendor_ids or None)
        weekly = svc.get_weekly_counts(vendor_ids=vendor_ids or None)
        total_pages = (total_count + per_page - 1) // per_page if per_page > 0 else 1
        if total_pages <= 0:
            total_pages = 1
        recent = [{
            'cve_id': v.cve_id,
            'summary': None,
            'description': v.description,
            'base_severity': v.base_severity,
            'cvss_score': v.cvss_score,
            'published_date': v.published_date.isoformat() if v.published_date else None,
            'details_url': url_for('vulnerability_ui.vulnerability_details', cve_id=v.cve_id)
        } for v in vulns]
        return jsonify({
            'sync_in_progress': False,
            'counts': {
                'total': int(counts.get('total') or total_count or 0),
                'critical': int(counts.get('critical') or 0),
                'high': int(counts.get('high') or 0),
                'medium': int(counts.get('medium') or 0)
            },
            'weekly': {
                'total': int(weekly.get('total') or 0),
                'critical': int(weekly.get('critical') or 0),
                'high': int(weekly.get('high') or 0),
                'medium': int(weekly.get('medium') or 0)
            },
            'vulnerabilities': recent,
            'pagination': { 'page': page, 'per_page': per_page, 'total': total_count, 'pages': total_pages },
            'vendor_ids': vendor_ids
        }), 200
    except Exception as e:
        current_app.logger.error(f"Erro ao obter overview da Home: {e}", exc_info=True)
        return jsonify({'error': 'Erro ao obter overview'}), 500

def _default_user_settings() -> Dict[str, Any]:
    try:
        lang = current_app.config.get('HTML_LANG', 'pt-BR')
    except Exception:
        lang = 'pt-BR'
    return {
        'general': {
            'theme': 'auto',
            'language': lang,
            'timezone': 'UTC',
        },
        'security': {
            'two_factor': False,
            'login_notifications': False,
            'session_timeout': 30,
        },
        'notifications': {
            'email_notifications': True,
            'vulnerability_alerts': True,
            'report_notifications': True,
        },
        'reports': {
            'default_format': 'pdf',
            'auto_export': False,
            'include_charts': True,
        },
    }


@api_v1_bp.route('/account/user-settings', methods=['GET'])
def get_user_settings() -> Response:
    """
    Retorna configurações persistidas do usuário autenticado.
    """
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401
        key = f'user_settings:{current_user.id}'
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        settings = _default_user_settings()
        if sm and sm.value:
            try:
                import json as _json
                parsed = _json.loads(sm.value)
                if isinstance(parsed, dict):
                    settings = parsed
            except Exception:
                pass
        return jsonify({'success': True, 'settings': settings}), 200
    except Exception as e:
        current_app.logger.error('Erro ao obter configurações do usuário', exc_info=e)
        return jsonify({'success': False, 'error': 'Erro ao obter configurações'}), 500


@api_v1_bp.route('/account/user-settings', methods=['POST', 'PUT'])
def set_user_settings() -> Response:
    """
    Persiste configurações do usuário autenticado e atualiza sessão.
    """
    try:
        if not current_user.is_authenticated:
            return jsonify({'success': False, 'error': 'Authentication required'}), 401

        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            raise BadRequest('Payload must be a JSON object')

        defaults = _default_user_settings()
        sanitized: Dict[str, Any] = {}
        for section, defvals in defaults.items():
            section_data = payload.get(section) if isinstance(payload.get(section), dict) else {}
            merged = {**defvals, **section_data}
            sanitized[section] = merged

        key = f'user_settings:{current_user.id}'
        sm = db.session.query(SyncMetadata).filter_by(key=key).first()
        try:
            import json as _json
            serialized = _json.dumps(sanitized, ensure_ascii=False)
        except Exception:
            serialized = str(sanitized)

        now = datetime.utcnow()
        if sm:
            sm.value = serialized
            sm.status = 'active'
            sm.sync_type = 'user_settings'
            sm.last_modified = now
        else:
            sm = SyncMetadata(
                key=key,
                value=serialized,
                status='active',
                last_modified=now,
                sync_type='user_settings'
            )
            db.session.add(sm)
        db.session.commit()

        try:
            session['settings'] = sanitized
        except Exception:
            pass

        return jsonify({'success': True}), 200
    except BadRequest as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        db.session.rollback()
        current_app.logger.error('Erro ao salvar configurações do usuário', exc_info=e)
        return jsonify({'success': False, 'error': 'Erro ao salvar configurações'}), 500


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
    try:
        # Construir query de assets; detectar colunas ausentes (asset_type/catalog_tag) de forma agnóstica ao banco
        query = Asset.query
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        column_info = inspector.get_columns('assets')
        col_names = { (c.get('name') or '').lower() for c in column_info }
        has_asset_type_col = ('asset_type' in col_names)
        has_catalog_tag_col = ('catalog_tag' in col_names)

        # Se qualquer coluna opcional estiver ausente, limitar colunas carregadas para evitar erros
        if not (has_asset_type_col and has_catalog_tag_col):
            try:
                from sqlalchemy.orm import load_only
                query = query.options(
                    load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id)
                )
            except Exception:
                # Se load_only falhar por qualquer motivo, seguimos com a query padrão
                pass
        # Filtrar por ativos do usuário autenticado (ou nenhum se público não autenticado)
        from app.extensions.middleware import filter_by_user_assets
        query = filter_by_user_assets(query)

        # Paginação manual resiliente para evitar erros com colunas ausentes
        from sqlalchemy import func
        page = form.page.data
        per_page = form.per_page.data
        # Usar with_entities(func.count(Asset.id)) para evitar SELECT das colunas não existentes no COUNT
        total = query.with_entities(func.count(Asset.id)).scalar() or 0
        items = (
            query.order_by(Asset.id.desc())
                 .limit(per_page)
                 .offset((page - 1) * per_page)
                 .all()
        )
        pages = (total + per_page - 1) // per_page if per_page else 1
        result = {
            'data': [item.to_dict() for item in items],
            'meta': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': pages,
            }
        }
        return jsonify(result), 200
    except SQLAlchemyError as e:
        try:
            detail = str(getattr(e, 'orig', e))
        except Exception:
            detail = str(e)
        current_app.logger.error(f"Erro ao listar assets: {detail}", exc_info=e)
        return jsonify(error='Database error', detail=detail), 500
    except Exception as e:
        # Capturar erro genérico e expor detalhes para depuração em desenvolvimento
        try:
            detail = str(e)
        except Exception:
            detail = 'Erro inesperado'
        current_app.logger.error(f"Erro inesperado ao listar assets: {detail}", exc_info=e)
        return jsonify(error='Unexpected error', detail=detail, type=type(e).__name__), 500


@api_v1_bp.route('/assets', methods=['POST'])
def create_asset() -> Response:
    """
    POST /api/v1/assets
    JSON body: { 
      name: str, 
      ip_address: str, 
      vendor?: str, 
      vendor_id?: int,
      rto_hours?: int,
      rpo_hours?: int,
      uptime_text?: str,
      operational_cost_per_hour?: float
    }
    """
    # Em modo público, exigir autenticação para cadastro de assets via API
    public_mode = current_app.config.get('PUBLIC_MODE', False)
    login_enabled_public = current_app.config.get('LOGIN_ENABLED_IN_PUBLIC_MODE', False)
    if public_mode and login_enabled_public:
        if not current_user.is_authenticated:
            return jsonify({'error': 'authentication_required', 'message': 'Faça login para cadastrar ativos.'}), 401

    data = request.get_json(silent=False)
    name = data.get('name')
    ip_raw = (data.get('ip_address') or '').strip()
    if not name or not ip_raw:
        raise BadRequest("Fields 'name' and 'ip_address' are required")

    # Validar e normalizar IP
    try:
        import ipaddress
        ip_obj = ipaddress.ip_address(ip_raw)
        ip = str(ip_obj)
    except Exception:
        raise BadRequest("Invalid 'ip_address'. Provide a valid IPv4 or IPv6.")

    vendor_name = (data.get('vendor') or '').strip()
    asset_type = (data.get('asset_type') or '').strip() or None
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
                    if isinstance(provided_owner, int):
                        owner_id = provided_owner
                    elif isinstance(provided_owner, str) and provided_owner.isdigit():
                        owner_id = int(provided_owner)
                    else:
                        # Se não fornecido, usar o próprio admin autenticado como owner
                        owner_id = (current_user.id if current_user.is_authenticated else None)
            except Exception:
                owner_id = (current_user.id if getattr(current_user, 'is_authenticated', False) else None)

            # Owner obrigatório: se não houver owner, bloquear a criação
            if not owner_id:
                raise BadRequest("Field 'owner_id' is required or must be the authenticated user")

            # Parse optional BIA fields
            def _parse_int(v):
                try:
                    return int(v) if v is not None and str(v).strip() != '' else None
                except Exception:
                    return None
            def _parse_float(v):
                try:
                    return float(v) if v is not None and str(v).strip() != '' else None
                except Exception:
                    return None

            rto_hours = _parse_int(data.get('rto_hours'))
            rpo_hours = _parse_int(data.get('rpo_hours'))
            uptime_text = data.get('uptime_text')
            operational_cost_per_hour = _parse_float(data.get('operational_cost_per_hour'))

            try:
                from sqlalchemy import inspect
                insp = inspect(db.engine)
                colnames = [c['name'] for c in insp.get_columns('assets')]
                has_asset_type_col = ('asset_type' in colnames)
            except Exception:
                has_asset_type_col = True

            if has_asset_type_col:
                asset = Asset(
                    name=name,
                    ip_address=ip,
                    vendor_id=vendor.id if vendor else None,
                    owner_id=owner_id,
                    asset_type=asset_type,
                    rto_hours=rto_hours,
                    rpo_hours=rpo_hours,
                    uptime_text=uptime_text,
                    operational_cost_per_hour=operational_cost_per_hour,
                )
                db.session.add(asset)
                db.session.flush()
            else:
                # Inserção direta via SQL sem a coluna asset_type
                insert_cols = [
                    'name', 'ip_address', 'status', 'owner_id', 'vendor_id',
                    'rto_hours', 'rpo_hours', 'uptime_text', 'operational_cost_per_hour'
                ]
                params = {
                    'name': name,
                    'ip_address': ip,
                    'status': 'active',
                    'owner_id': owner_id,
                    'vendor_id': (vendor.id if vendor else None),
                    'rto_hours': rto_hours,
                    'rpo_hours': rpo_hours,
                    'uptime_text': uptime_text,
                    'operational_cost_per_hour': operational_cost_per_hour,
                }
                placeholders = ', '.join([f":{c}" for c in insert_cols])
                colnames = ', '.join(insert_cols)
                db.session.execute(
                    text(f"INSERT INTO assets ({colnames}) VALUES ({placeholders})"),
                    params
                )
                # Recupera o ID gerado (SQLite)
                new_id = db.session.execute(text("SELECT last_insert_rowid()")).scalar()
                # Carregar o asset recem criado SEM tentar selecionar asset_type
                try:
                    asset = (
                        Asset.query.options(
                            load_only(Asset.id, Asset.name, Asset.ip_address, Asset.status, Asset.vendor_id, Asset.owner_id,
                                      Asset.rto_hours, Asset.rpo_hours, Asset.uptime_text, Asset.operational_cost_per_hour)
                        ).get(new_id)
                    )
                except Exception:
                    asset = Asset(id=new_id, name=name, ip_address=ip, status='active', vendor_id=(vendor.id if vendor else None), owner_id=owner_id)

            # Vincular produto ao asset, se fornecido
            try:
                from app.models.asset_product import AssetProduct
                from app.models.product import Product

                raw_pid = data.get('product_id')
                product_id = None
                if isinstance(raw_pid, int):
                    product_id = raw_pid
                elif isinstance(raw_pid, str) and raw_pid.isdigit():
                    product_id = int(raw_pid)

                product_name = (data.get('product_name') or '').strip()
                model_name = (data.get('model_name') or '').strip() or None
                operating_system = (data.get('operating_system') or '').strip() or None
                installed_version = (data.get('installed_version') or '').strip() or None

                # Resolver product_id por nome dentro do vendor, se necessário
                if not product_id and product_name and vendor:
                    prod = (
                        db.session.query(Product)
                        .filter(Product.vendor_id == vendor.id, func.lower(Product.name) == product_name.lower())
                        .first()
                    )
                    product_id = prod.id if prod else None

                if product_id:
                    link = (
                        db.session.query(AssetProduct)
                        .filter_by(asset_id=asset.id, product_id=product_id)
                        .first()
                    )
                    if not link:
                        link = AssetProduct(asset_id=asset.id, product_id=product_id)
                        db.session.add(link)
                    # Atualizar metadados do vínculo
                    link.model_name = model_name or link.model_name
                    link.operating_system = operating_system or link.operating_system
                    link.installed_version = installed_version or link.installed_version
                else:
                    # Não bloquear criação do asset por ausência de product_id
                    pass
            except Exception:
                # Não bloquear criação caso vínculo falhe
                pass
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
        # Imports adicionais para filtro por vendors
        from sqlalchemy import union
        from app.models.cve_vendor import CVEVendor
        from app.models.cve_product import CVEProduct
        from app.models.product import Product
        from app.models.sync_metadata import SyncMetadata
        from flask_login import current_user
        
        # Instanciar o serviço com a sessão do banco
        vuln_service = VulnerabilityService(db.session)
        
        # Determinar vendor_ids selecionados (URL sobrescreve preferências do usuário)
        raw_vendor_ids_list = request.args.getlist('vendor_ids')
        raw_vendor_ids_param = request.args.get('vendor_ids', '')
        selected_vendor_ids: list[int] = []
        if raw_vendor_ids_list:
            for item in raw_vendor_ids_list:
                for p in str(item).split(','):
                    p = p.strip()
                    if p.isdigit():
                        selected_vendor_ids.append(int(p))
        elif raw_vendor_ids_param:
            for p in str(raw_vendor_ids_param).split(','):
                p = p.strip()
                if p.isdigit():
                    selected_vendor_ids.append(int(p))
        else:
            try:
                if current_user.is_authenticated:
                    key = f'user_vendor_preferences:{current_user.id}'
                    pref = db.session.query(SyncMetadata).filter_by(key=key).first()
                    if pref and pref.value:
                        selected_vendor_ids = [int(x) for x in pref.value.split(',') if x.strip().isdigit()]
            except Exception:
                selected_vendor_ids = []
        # Normalizar lista única
        selected_vendor_ids = sorted(list(set(selected_vendor_ids)))
        
        # Construir consulta base com filtro por vendors quando aplicável
        base_query = db.session.query(Vulnerability)
        if selected_vendor_ids:
            try:
                cves_por_vendor = (
                    db.session
                    .query(CVEVendor.cve_id)
                    .filter(CVEVendor.vendor_id.in_(selected_vendor_ids))
                )
                cves_por_produto_vendor = (
                    db.session
                    .query(CVEProduct.cve_id)
                    .join(Product, Product.id == CVEProduct.product_id)
                    .filter(Product.vendor_id.in_(selected_vendor_ids))
                )
                cves_unificados_sq = union(cves_por_vendor, cves_por_produto_vendor).subquery()
                base_query = base_query.filter(
                    Vulnerability.cve_id.in_(db.session.query(cves_unificados_sq.c.cve_id))
                ).distinct()
            except Exception:
                # Fallback simples: apenas por CVEVendor
                base_query = (
                    base_query
                    .join(CVEVendor, CVEVendor.cve_id == Vulnerability.cve_id)
                    .filter(CVEVendor.vendor_id.in_(selected_vendor_ids))
                    .distinct()
                )
        
        # Distribuição por severidade
        severity_data = (
            base_query
            .with_entities(
                Vulnerability.base_severity,
                func.count(Vulnerability.cve_id).label('count')
            )
            .group_by(Vulnerability.base_severity)
            .all()
        )
        
        severity_distribution = {
            'labels': [item[0] or 'Unknown' for item in severity_data],
            'data': [item[1] for item in severity_data]
        }
        
        # Tendência semanal (últimas 8 semanas)
        end_date = datetime.now()
        start_date = end_date - timedelta(weeks=8)
        
        # Para SQLite, usar strftime para agrupar por semana
        weekly_data = (
            base_query
            .with_entities(
                func.strftime('%Y-%W', Vulnerability.published_date).label('week'),
                func.count(Vulnerability.cve_id).label('count')
            )
            .filter(Vulnerability.published_date >= start_date)
            .group_by(func.strftime('%Y-%W', Vulnerability.published_date))
            .order_by('week')
            .all()
        )
        
        weekly_trend = {
            'labels': [f'Semana {item[0]}' if item[0] else 'Unknown' for item in weekly_data],
            'data': [item[1] for item in weekly_data]
        }
        
        # Timeline de vulnerabilidades (últimos 30 dias)
        timeline_start = end_date - timedelta(days=30)
        
        # Para SQLite, usar strftime para agrupar por data
        timeline_data = (
            base_query
            .with_entities(
                func.strftime('%Y-%m-%d', Vulnerability.published_date).label('date'),
                func.count(Vulnerability.cve_id).label('count')
            )
            .filter(Vulnerability.published_date >= timeline_start)
            .group_by(func.strftime('%Y-%m-%d', Vulnerability.published_date))
            .order_by('date')
            .all()
        )
        
        vulnerability_timeline = {
            'labels': [item[0] if item[0] else 'Unknown' for item in timeline_data],
            'data': [item[1] for item in timeline_data]
        }
        
        # Top 5 CVSS Scores
        top_cvss_data = (
            base_query
            .with_entities(
                Vulnerability.cve_id,
                Vulnerability.cvss_score
            )
            .filter(Vulnerability.cvss_score.isnot(None))
            .order_by(desc(Vulnerability.cvss_score))
            .limit(5)
            .all()
        )
        
        top_cvss = {
            'labels': [item[0] for item in top_cvss_data],
            'data': [float(item[1]) if item[1] else 0 for item in top_cvss_data]
        }
        
        # Estatísticas gerais
        stats = vuln_service.get_dashboard_counts(selected_vendor_ids or None)
        
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
