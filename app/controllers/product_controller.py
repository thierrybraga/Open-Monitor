import logging
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request
from flask.wrappers import Response
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from app.extensions import db
from app.models.product import Product
from app.models.vendor import Vendor
from app.models.asset_product import AssetProduct
from app.models.version_reference import VersionReference
from sqlalchemy import func
import sqlalchemy as sa

logger = logging.getLogger(__name__)

product_api_bp = Blueprint('product_api', __name__, url_prefix='/api/products')

@product_api_bp.errorhandler(BadRequest)
def _handle_bad_request(e: BadRequest) -> Response:
    return jsonify(error=str(e)), 400

@product_api_bp.errorhandler(NotFound)
def _handle_not_found(e: NotFound) -> Response:
    return jsonify(error='Not Found'), 404

@product_api_bp.errorhandler(SQLAlchemyError)
def _handle_db_error(e: SQLAlchemyError) -> Response:
    try:
        detail = str(getattr(e, 'orig', e))
    except Exception:
        detail = str(e)
    return jsonify(error='Database error', detail=detail), 500

@product_api_bp.errorhandler(Exception)
def _handle_unexpected_error(e: Exception) -> Response:
    raise InternalServerError()


@product_api_bp.route('/vendors/<int:vendor_id>', methods=['GET'])
def list_products_by_vendor(vendor_id: int):
    """Lista produtos pertencentes ao vendor informado, com suporte a filtro por nome (q).

    Retorna JSON no formato { items: [{id, name, vendor_id}], total: N }
    """
    try:
        q = (request.args.get('q') or '').strip()
        # Suporte a limite configurável (com valores seguros)
        try:
            limit = int(request.args.get('limit', 200))
        except Exception:
            limit = 200
        # Normaliza limites para proteger o servidor
        limit = max(1, min(limit, 1000))

        query = db.session.query(Product).filter(Product.vendor_id == vendor_id)
        if q:
            like = f"%{q}%"
            query = query.filter(Product.name.ilike(like))
        items: List[Product] = query.order_by(Product.name.asc()).limit(limit).all()
        data: List[Dict[str, Any]] = [
            { 'id': p.id, 'name': p.name, 'vendor_id': p.vendor_id }
            for p in items
        ]
        return jsonify({ 'success': True, 'items': data, 'total': len(data) })
    except Exception as e:
        logger.error('Failed to list products by vendor', exc_info=True)
        return jsonify({ 'success': False, 'items': [], 'total': 0 }), 200


@product_api_bp.route('/vendors/by-name/<string:vendor_name>', methods=['GET'])
def list_products_by_vendor_name(vendor_name: str):
    """Lista produtos pertencentes ao vendor informado por nome (case-insensitive).

    Suporta filtro por nome (q) e limite.
    Retorna JSON no formato { items: [{id, name, vendor_id}], total: N }
    """
    try:
        if not vendor_name:
            return jsonify({ 'items': [], 'total': 0 }), 200
        # Normalizar nome
        vn = vendor_name.strip()
        if not vn:
            return jsonify({ 'items': [], 'total': 0 }), 200

        # Resolver vendor por nome (case-insensitive)
        vendor = db.session.query(Vendor).filter(func.lower(Vendor.name) == vn.lower()).first()
        if not vendor:
            return jsonify({ 'items': [], 'total': 0 }), 200

        q = (request.args.get('q') or '').strip()
        try:
            limit = int(request.args.get('limit', 200))
        except Exception:
            limit = 200
        limit = max(1, min(limit, 1000))

        query = db.session.query(Product).filter(Product.vendor_id == vendor.id)
        if q:
            like = f"%{q}%"
            query = query.filter(Product.name.ilike(like))
        items = query.order_by(Product.name.asc()).limit(limit).all()
        data = [{ 'id': p.id, 'name': p.name, 'vendor_id': p.vendor_id } for p in items]
        return jsonify({ 'items': data, 'total': len(data) })
    except Exception:
        logger.error('Failed to list products by vendor name', exc_info=True)
        return jsonify({ 'items': [], 'total': 0 }), 200


@product_api_bp.route('/vendors/<int:vendor_id>/metadata', methods=['GET'])
def list_vendor_metadata(vendor_id: int):
    """Retorna metadados agregados (modelos, sistemas operacionais e versões) para um vendor.

    Formato: { models: [str], operating_systems: [str], versions: [str] }
    """
    try:
        # Limite opcional para controlar volume
        try:
            limit = int(request.args.get('limit', 200))
        except Exception:
            limit = 200
        limit = max(1, min(limit, 2000))

        # Modelos distintos vinculados a produtos do vendor
        models_rows = (
            db.session.query(func.distinct(func.trim(AssetProduct.model_name)))
            .join(Product, AssetProduct.product_id == Product.id)
            .filter(
                Product.vendor_id == vendor_id,
                AssetProduct.model_name.isnot(None),
                func.length(func.trim(AssetProduct.model_name)) > 0,
            )
            .order_by(func.lower(func.trim(AssetProduct.model_name)).asc())
            .limit(limit)
            .all()
        )
        models = [r[0] for r in models_rows if r and r[0]]

        # Sistemas operacionais distintos
        os_rows = (
            db.session.query(func.distinct(func.trim(AssetProduct.operating_system)))
            .join(Product, AssetProduct.product_id == Product.id)
            .filter(
                Product.vendor_id == vendor_id,
                AssetProduct.operating_system.isnot(None),
                func.length(func.trim(AssetProduct.operating_system)) > 0,
            )
            .order_by(func.lower(func.trim(AssetProduct.operating_system)).asc())
            .limit(limit)
            .all()
        )
        operating_systems = [r[0] for r in os_rows if r and r[0]]

        # Versões instaladas distintas a partir de AssetProduct
        ap_versions_rows = (
            db.session.query(func.distinct(func.trim(AssetProduct.installed_version)))
            .join(Product, AssetProduct.product_id == Product.id)
            .filter(
                Product.vendor_id == vendor_id,
                AssetProduct.installed_version.isnot(None),
                func.length(func.trim(AssetProduct.installed_version)) > 0,
            )
            .order_by(func.lower(func.trim(AssetProduct.installed_version)).asc())
            .limit(limit)
            .all()
        )
        ap_versions = [r[0] for r in ap_versions_rows if r and r[0]]

        # Versões referenciadas por CVEs (VersionReference)
        vr_versions_rows = (
            db.session.query(func.distinct(func.trim(VersionReference.affected_version)))
            .join(Product, VersionReference.product_id == Product.id)
            .filter(
                Product.vendor_id == vendor_id,
                VersionReference.affected_version.isnot(None),
                func.length(func.trim(VersionReference.affected_version)) > 0,
            )
            .order_by(func.lower(func.trim(VersionReference.affected_version)).asc())
            .limit(limit)
            .all()
        )
        vr_versions = [r[0] for r in vr_versions_rows if r and r[0]]

        # Unificar e ordenar versões
        versions_set = {v.strip() for v in (ap_versions + vr_versions) if isinstance(v, str)}
        versions = sorted(versions_set, key=lambda s: s.lower())[:limit]

        return jsonify({
            'models': models,
            'operating_systems': operating_systems,
            'versions': versions,
        })
    except Exception:
        logger.error('Failed to list vendor metadata', exc_info=True)
        return jsonify({ 'models': [], 'operating_systems': [], 'versions': [] }), 200


@product_api_bp.route('/<int:product_id>/metadata', methods=['GET'])
def list_product_metadata(product_id: int):
    """Retorna metadados (modelos, sistemas operacionais e versões) específicos de um produto.

    Formato: { models: [str], operating_systems: [str], versions: [str] }
    """
    try:
        try:
            limit = int(request.args.get('limit', 200))
        except Exception:
            limit = 200
        limit = max(1, min(limit, 2000))

        # Detecta se a tabela asset_products existe para evitar falhas em ambientes sem a tabela
        try:
            has_asset_products_table = bool(
                db.session.execute(
                    sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name='asset_products'")
                ).scalar()
            )
        except Exception:
            # Fallback conservador: assume que existe
            has_asset_products_table = True

        # Modelos e SO a partir de AssetProduct
        models: List[str] = []
        if has_asset_products_table:
            models_rows = (
                db.session.query(func.distinct(func.trim(AssetProduct.model_name)))
                .filter(
                    AssetProduct.product_id == product_id,
                    AssetProduct.model_name.isnot(None),
                    func.length(func.trim(AssetProduct.model_name)) > 0,
                )
                .order_by(func.lower(func.trim(AssetProduct.model_name)).asc())
                .limit(limit)
                .all()
            )
            models = [r[0] for r in models_rows if r and r[0]]

        operating_systems: List[str] = []
        if has_asset_products_table:
            os_rows = (
                db.session.query(func.distinct(func.trim(AssetProduct.operating_system)))
                .filter(
                    AssetProduct.product_id == product_id,
                    AssetProduct.operating_system.isnot(None),
                    func.length(func.trim(AssetProduct.operating_system)) > 0,
                )
                .order_by(func.lower(func.trim(AssetProduct.operating_system)).asc())
                .limit(limit)
                .all()
            )
            operating_systems = [r[0] for r in os_rows if r and r[0]]

        # Versões: AssetProduct + VersionReference
        ap_versions: List[str] = []
        if has_asset_products_table:
            ap_versions_rows = (
                db.session.query(func.distinct(func.trim(AssetProduct.installed_version)))
                .filter(
                    AssetProduct.product_id == product_id,
                    AssetProduct.installed_version.isnot(None),
                    func.length(func.trim(AssetProduct.installed_version)) > 0,
                )
                .order_by(func.lower(func.trim(AssetProduct.installed_version)).asc())
                .limit(limit)
                .all()
            )
            ap_versions = [r[0] for r in ap_versions_rows if r and r[0]]

        vr_versions_rows = (
            db.session.query(func.distinct(func.trim(VersionReference.affected_version)))
            .filter(
                VersionReference.product_id == product_id,
                VersionReference.affected_version.isnot(None),
                func.length(func.trim(VersionReference.affected_version)) > 0,
            )
            .order_by(func.lower(func.trim(VersionReference.affected_version)).asc())
            .limit(limit)
            .all()
        )
        vr_versions = [r[0] for r in vr_versions_rows if r and r[0]]

        versions_set = {v.strip() for v in (ap_versions + vr_versions) if isinstance(v, str)}
        versions = sorted(versions_set, key=lambda s: s.lower())[:limit]

        return jsonify({
            'models': models,
            'operating_systems': operating_systems,
            'versions': versions,
        })
    except Exception:
        logger.error('Failed to list product metadata', exc_info=True)
        return jsonify({ 'models': [], 'operating_systems': [], 'versions': [] }), 200
