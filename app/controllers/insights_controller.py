from flask import Blueprint, jsonify, request
from typing import Dict, Any
from flask.wrappers import Response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from flask_login import current_user, login_required

from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.asset import Asset
from app.models.asset_vulnerability import AssetVulnerability
from app.models.monitoring_rule import MonitoringRule


insights_api_bp = Blueprint('insights_api', __name__, url_prefix='/api/insights')

def _json_success(data: Dict[str, Any], status: int = 200):
    return jsonify({'success': True, 'data': data}), status

def _json_error(message: str, status: int = 500):
    return jsonify({'success': False, 'error': message}), status

@insights_api_bp.errorhandler(BadRequest)
def _handle_bad_request(e: BadRequest) -> Response:
    return jsonify(error=str(e)), 400

@insights_api_bp.errorhandler(NotFound)
def _handle_not_found(e: NotFound) -> Response:
    return jsonify(error='Not Found'), 404

@insights_api_bp.errorhandler(SQLAlchemyError)
def _handle_db_error(e: SQLAlchemyError) -> Response:
    try:
        detail = str(getattr(e, 'orig', e))
    except Exception:
        detail = str(e)
    return jsonify(error='Database error', detail=detail), 500

@insights_api_bp.errorhandler(Exception)
def _handle_unexpected_error(e: Exception) -> Response:
    raise InternalServerError()


@insights_api_bp.route('/overview', methods=['GET'])
@login_required
def get_insights_overview():
    """Returns lightweight overview counts for Insights cards."""
    try:
        session = db.session

        # Se autenticado, filtrar por ativos do usuário
        owner_id = current_user.id

        # Vulnerabilidades críticas APENAS entre as vinculadas a ativos do usuário (se autenticado)
        q_critical = session.query(func.count(func.distinct(AssetVulnerability.vulnerability_id)))\
            .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)\
            .filter(Vulnerability.base_severity == 'CRITICAL')
        if owner_id:
            q_critical = q_critical.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                   .filter(Asset.owner_id == owner_id)
        critical_count = q_critical.scalar() or 0

        q_assets = session.query(func.count(Asset.id))
        assets_count = q_assets.scalar() or 0

        q_rules = session.query(func.count(MonitoringRule.id))
        if owner_id:
            q_rules = q_rules.filter(MonitoringRule.user_id == owner_id)
        monitoring_rules_count = q_rules.scalar() or 0

        # Métricas adicionais baseadas em ativos do usuário
        q_assets_with_vulns = session.query(func.count(func.distinct(AssetVulnerability.asset_id)))
        if owner_id:
            q_assets_with_vulns = q_assets_with_vulns.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                               .filter(Asset.owner_id == owner_id)
        assets_with_vulns_count = q_assets_with_vulns.scalar() or 0

        q_assets_with_critical = session.query(func.count(func.distinct(AssetVulnerability.asset_id)))\
            .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)\
            .filter(Vulnerability.base_severity == 'CRITICAL')
        if owner_id:
            q_assets_with_critical = q_assets_with_critical.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                                   .filter(Asset.owner_id == owner_id)
        assets_with_critical_count = q_assets_with_critical.scalar() or 0

        q_assets_without_vendor = session.query(func.count(Asset.id)).filter(Asset.vendor_id.is_(None))
        if owner_id:
            q_assets_without_vendor = q_assets_without_vendor.filter(Asset.owner_id == owner_id)
        assets_without_vendor_count = q_assets_without_vendor.scalar() or 0

        q_assets_without_owner = session.query(func.count(Asset.id)).filter(Asset.owner_id.is_(None))
        if owner_id:
            q_assets_without_owner = q_assets_without_owner.filter(Asset.owner_id == owner_id)
        assets_without_owner_count = q_assets_without_owner.scalar() or 0

        # Fallback global quando usuário não possui ativos
        # Manter assets_count estritamente como contagem de ativos do usuário
        if int(assets_count) == 0:
            try:
                critical_count = (
                    session.query(func.count(func.distinct(AssetVulnerability.vulnerability_id)))
                    .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)
                    .filter(Vulnerability.base_severity == 'CRITICAL')
                    .scalar()
                ) or 0
                monitoring_rules_count = session.query(func.count(MonitoringRule.id)).scalar() or 0
                assets_with_vulns_count = (
                    session.query(func.count(func.distinct(AssetVulnerability.asset_id)))
                    .scalar()
                ) or 0
                assets_with_critical_count = (
                    session.query(func.count(func.distinct(AssetVulnerability.asset_id)))
                    .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)
                    .filter(Vulnerability.base_severity == 'CRITICAL')
                    .scalar()
                ) or 0
                assets_without_vendor_count = (
                    session.query(func.count(Asset.id))
                    .filter(Asset.vendor_id.is_(None))
                    .scalar()
                ) or 0
                assets_without_owner_count = (
                    session.query(func.count(Asset.id))
                    .filter(Asset.owner_id.is_(None))
                    .scalar()
                ) or 0
            except Exception:
                pass

        data: Dict[str, Any] = {
            'critical_count': int(critical_count),
            'assets_count': int(assets_count),
            'monitoring_rules_count': int(monitoring_rules_count),
            'assets_with_vulns_count': int(assets_with_vulns_count),
            'assets_with_critical_count': int(assets_with_critical_count),
            'assets_without_vendor_count': int(assets_without_vendor_count),
            'assets_without_owner_count': int(assets_without_owner_count),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
        return _json_success(data, 200)
    except Exception as e:
        return _json_error(str(e), 500)

@insights_api_bp.route('/severity-distribution', methods=['GET'])
@login_required
def severity_distribution():
    try:
        session = db.session
        owner_id = current_user.id
        rows = (
            session.query(
                Vulnerability.base_severity,
                func.count(func.distinct(Vulnerability.cve_id))
            )
            .join(AssetVulnerability, AssetVulnerability.vulnerability_id == Vulnerability.cve_id)
            .join(Asset, Asset.id == AssetVulnerability.asset_id)
            .filter(Asset.owner_id == owner_id)
            .group_by(Vulnerability.base_severity)
            .all()
        )
        if not rows:
            try:
                rows = (
                    session.query(
                        Vulnerability.base_severity,
                        func.count(func.distinct(Vulnerability.cve_id))
                    )
                    .group_by(Vulnerability.base_severity)
                    .all()
                )
            except Exception:
                rows = []
        labels = []
        data = []
        for sev, cnt in rows:
            if sev and cnt:
                labels.append(sev.title())
                data.append(int(cnt))
        return _json_success({'labels': labels, 'data': data}, 200)
    except Exception as e:
        return _json_error(str(e), 500)

@insights_api_bp.route('/timeseries/asset_vulns', methods=['GET'])
@login_required
def asset_vulns_timeseries():
    try:
        session = db.session
        start = request.args.get('start')
        end = request.args.get('end')
        if not start:
            start_date = (datetime.now(timezone.utc) - timedelta(days=30)).date()
        else:
            start_date = datetime.strptime(start, '%Y-%m-%d').date()
        if not end:
            end_date = datetime.now(timezone.utc).date()
        else:
            end_date = datetime.strptime(end, '%Y-%m-%d').date()
        owner_id = current_user.id
        date_col = func.date(Vulnerability.published_date)
        rows = (
            session.query(
                date_col.label('d'),
                func.count(func.distinct(Vulnerability.cve_id))
            )
            .join(AssetVulnerability, AssetVulnerability.vulnerability_id == Vulnerability.cve_id)
            .join(Asset, Asset.id == AssetVulnerability.asset_id)
            .filter(Asset.owner_id == owner_id)
            .filter(Vulnerability.published_date >= datetime.combine(start_date, datetime.min.time()))
            .filter(Vulnerability.published_date <= datetime.combine(end_date, datetime.max.time()))
            .group_by('d')
            .order_by('d')
            .all()
        )
        if not rows:
            try:
                rows = (
                    session.query(
                        date_col.label('d'),
                        func.count(func.distinct(Vulnerability.cve_id))
                    )
                    .filter(Vulnerability.published_date >= datetime.combine(start_date, datetime.min.time()))
                    .filter(Vulnerability.published_date <= datetime.combine(end_date, datetime.max.time()))
                    .group_by('d')
                    .order_by('d')
                    .all()
                )
            except Exception:
                rows = []
        data = [
            {'date': (d.isoformat() if hasattr(d, 'isoformat') else str(d)), 'value': int(cnt)}
            for d, cnt in rows
        ]
        return _json_success({'rows': data, 'data': data, 'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()}}, 200)
    except Exception as e:
        return _json_error(str(e), 500)
