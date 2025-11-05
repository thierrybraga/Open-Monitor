from flask import Blueprint, jsonify
from typing import Dict, Any
from sqlalchemy import func
from datetime import datetime
from flask_login import current_user

from app.extensions import db
from app.models.vulnerability import Vulnerability
from app.models.asset import Asset
from app.models.asset_vulnerability import AssetVulnerability
from app.models.monitoring_rule import MonitoringRule


insights_api_bp = Blueprint('insights_api', __name__, url_prefix='/api/insights')


@insights_api_bp.route('/overview', methods=['GET'])
def get_insights_overview():
    """Returns lightweight overview counts for Insights cards."""
    try:
        session = db.session

        # Se autenticado, filtrar por ativos do usuário
        owner_id = current_user.id if getattr(current_user, 'is_authenticated', False) else None

        # Vulnerabilidades críticas APENAS entre as vinculadas a ativos do usuário (se autenticado)
        q_critical = session.query(func.count(func.distinct(AssetVulnerability.vulnerability_id)))\
            .join(Vulnerability, Vulnerability.cve_id == AssetVulnerability.vulnerability_id)\
            .filter(Vulnerability.base_severity == 'CRITICAL')
        if owner_id:
            q_critical = q_critical.join(Asset, Asset.id == AssetVulnerability.asset_id)\
                                   .filter(Asset.owner_id == owner_id)
        critical_count = q_critical.scalar() or 0

        q_assets = session.query(func.count(Asset.id))
        if owner_id:
            q_assets = q_assets.filter(Asset.owner_id == owner_id)
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

        data: Dict[str, Any] = {
            'critical_count': int(critical_count),
            'assets_count': int(assets_count),
            'monitoring_rules_count': int(monitoring_rules_count),
            'assets_with_vulns_count': int(assets_with_vulns_count),
            'assets_with_critical_count': int(assets_with_critical_count),
            'assets_without_vendor_count': int(assets_without_vendor_count),
            'assets_without_owner_count': int(assets_without_owner_count),
            'updated_at': datetime.utcnow().isoformat() + 'Z'
        }
        return jsonify({'success': True, 'data': data}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500