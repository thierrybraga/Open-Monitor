# controllers/api_controller.py

from flask import Blueprint, jsonify, request, current_app, url_for
from flask.wrappers import Response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from ..extensions import db
from ..models.vulnerability import Vulnerability
from ..models.asset import Asset
from ..models.risk_assessment import RiskAssessment
from ..utils.pagination import paginate_query
from ..forms.api_form import APIQueryForm
from typing import Any, Dict
from ..extensions import login_manager

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


# --- Helpers ---

def _apply_filters(query, params: APIQueryForm) -> Any:
    if params.severity.data:
        query = query.filter_by(base_severity=params.severity.data)
    if params.vendor.data:
        query = query.filter_by(vendor=params.vendor.data)
    return query


def _paginate_and_serialize(
    query, params: APIQueryForm
) -> Dict[str, Any]:
    pag = paginate_query(
        query.order_by(Vulnerability.published_date.desc()),
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
    # no extra filters for assets yet…
    result = _paginate_and_serialize(query, form)
    return jsonify(result), 200


@api_v1_bp.route('/assets', methods=['POST'])
def create_asset() -> Response:
    """
    POST /api/v1/assets
    JSON body: { name: str, ip_address: str }
    """
    data = request.get_json(silent=False)
    name = data.get('name')
    ip   = data.get('ip_address')
    if not name or not ip:
        raise BadRequest("Fields 'name' and 'ip_address' are required")

    asset = Asset(name=name, ip_address=ip)
    try:
        with db.session.begin():
            db.session.add(asset)
    except SQLAlchemyError:
        raise InternalServerError()

    loc = url_for('api_v1.list_assets')
    return jsonify(asset.to_dict()), 201, {'Location': loc}


# --- Health Check ---

@api_v1_bp.route('/health', methods=['GET'])
def api_health() -> Response:
    """
    GET /api/v1/health
    """
    try:
        db.session.execute('SELECT 1')
        return jsonify(status='healthy', service='api_v1'), 200
    except Exception as e:
        current_app.logger.error("Health check failed", exc_info=e)
        return jsonify(status='unhealthy', error=str(e)), 500
