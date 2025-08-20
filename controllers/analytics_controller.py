"""Analytics API Controller

This module provides API endpoints for analytics data including:
- Overview statistics
- Top products and CWEs
- Latest CVEs
- Time-series data
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from flask import Blueprint, jsonify, request, Response
from sqlalchemy import func, desc, or_, text

from extensions import db
from models.vulnerability import Vulnerability
from services.vulnerability_service import VulnerabilityService

# Configure logger
logger = logging.getLogger(__name__)

# Create Blueprint for analytics API
analytics_api_bp = Blueprint('analytics_api', __name__, url_prefix='/api/analytics')


@analytics_api_bp.route('/overview', methods=['GET'])
def get_analytics_overview() -> Response:
    """Get overview analytics data including counts and distributions."""
    try:
        session = db.session
        vuln_service = VulnerabilityService(session)
        
        # Get basic counts
        counts = vuln_service.get_dashboard_counts()
        
        # Calculate patched vs unpatched
        old_date = datetime.now() - timedelta(days=90)
        
        patched_cves = session.query(Vulnerability).filter(
            Vulnerability.published_date < old_date,
            Vulnerability.base_severity.in_(['LOW', 'MEDIUM'])
        ).count()
        
        unpatched_cves = session.query(Vulnerability).filter(
            or_(
                Vulnerability.published_date >= old_date,
                Vulnerability.base_severity.in_(['HIGH', 'CRITICAL'])
            )
        ).count()
        
        # Calculate additional metrics
        avg_cvss = session.query(func.avg(Vulnerability.cvss_score)).scalar() or 0.0
        
        # Calculate average exploitability score using direct SQL
        from sqlalchemy import text
        try:
            # First try to get from CVSSMetric table
            result = session.execute(text(
                "SELECT AVG(exploitability_score) FROM cvss_metrics WHERE exploitability_score IS NOT NULL"
            ))
            avg_exploit_from_metrics = result.scalar()
            
            if avg_exploit_from_metrics:
                avg_exploit = round(float(avg_exploit_from_metrics), 2)
            else:
                # Fallback: calculate as 80% of CVSS score
                avg_exploit_calc = session.query(func.avg(Vulnerability.cvss_score * 0.8)).scalar()
                avg_exploit = round(float(avg_exploit_calc), 2) if avg_exploit_calc else 0.0
        except Exception as e:
            logger.error(f"Error calculating exploitability score: {e}")
            # Fallback: calculate as 80% of CVSS score
            avg_exploit_calc = session.query(func.avg(Vulnerability.cvss_score * 0.8)).scalar()
            avg_exploit = round(float(avg_exploit_calc), 2) if avg_exploit_calc else 0.0
        
        # Calculate active threats (critical vulnerabilities from last 30 days)
        recent_date = datetime.now() - timedelta(days=30)
        active_threats = session.query(Vulnerability).filter(
            Vulnerability.base_severity == 'CRITICAL',
            Vulnerability.published_date >= recent_date
        ).count()
        
        # Count unique vendors and products using relationships
        from models.cve_vendor import CVEVendor
        from models.cve_product import CVEProduct
        from models.weakness import Weakness
        from models.vendor import Vendor
        from models.product import Product
        
        vendor_count = session.query(func.count(func.distinct(Vendor.name))).scalar() or 0
        product_count = session.query(func.count(func.distinct(Product.name))).scalar() or 0
        cwe_count = session.query(func.count(func.distinct(Weakness.cwe_id))).scalar() or 0
        
        # Calculate patch coverage percentage
        total_cves = counts.get('total', 0)
        patch_coverage = (patched_cves / total_cves * 100) if total_cves > 0 else 0.0
        
        overview_data = {
            'total_cves': counts.get('total', 0),
            'critical_cves': counts.get('critical', 0),
            'high_cves': counts.get('high', 0),
            'medium_cves': counts.get('medium', 0),
            'low_cves': counts.get('low', 0),
            'patched_cves': patched_cves,
            'unpatched_cves': unpatched_cves,
            'active_threats': active_threats,
            'avg_cvss_score': round(avg_cvss, 2),
            'avg_exploit_score': round(avg_exploit, 2),
            'patch_coverage': round(patch_coverage, 1),
            'vendor_count': vendor_count,
            'product_count': product_count,
            'cwe_count': cwe_count,
            'severity_distribution': {
                'critical': counts.get('critical', 0),
                'high': counts.get('high', 0),
                'medium': counts.get('medium', 0),
                'low': counts.get('low', 0)
            }
        }
        
        return jsonify(overview_data), 200
        
    except Exception as e:
        logger.error(f"Error fetching analytics overview: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch analytics overview'}), 500


@analytics_api_bp.route('/details/<string:category>', methods=['GET'])
def get_analytics_details(category: str) -> Response:
    """Get detailed analytics data for specific categories."""
    try:
        session = db.session
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        
        if category == 'top_products':
            # Get top products by CVE count using raw SQL (ORM join not working properly)
            results = session.execute(text("""
                SELECT p.name, COUNT(cp.cve_id) as count
                FROM product p
                INNER JOIN cve_product cp ON p.id = cp.product_id
                GROUP BY p.name
                ORDER BY count DESC
                LIMIT :limit
            """), {'limit': per_page}).fetchall()
            
            data = [{
                'product': result[0],
                'count': result[1]
            } for result in results]
            
        elif category == 'top_cwes':
            # Get top CWEs by CVE count using the weakness table
            from models.weakness import Weakness
            
            results = session.query(
                Weakness.cwe_id,
                func.count(Weakness.cve_id).label('count')
            ).filter(
                Weakness.cwe_id.isnot(None),
                Weakness.cwe_id != ''
            ).group_by(
                Weakness.cwe_id
            ).order_by(
                desc('count')
            ).limit(per_page).all()
            
            data = [{
                'cwe': result.cwe_id,
                'count': result.count
            } for result in results]
            
        elif category == 'severity_distribution':
            # Get severity distribution data for pie chart
            results = db.session.query(
            Vulnerability.base_severity,
            func.count(Vulnerability.cve_id).label('count')
        ).filter(
            Vulnerability.base_severity.isnot(None)
        ).group_by(
            Vulnerability.base_severity
        ).all()
            
            data = [{
                'label': result.base_severity or 'Unknown',
                'value': result.count
            } for result in results]
            
        elif category == 'patch_status':
            # Get patch status distribution for pie chart
            # Consider CVEs older than 90 days as "patched" and newer/critical ones as "unpatched"
            ninety_days_ago = datetime.now() - timedelta(days=90)
            
            patched_count = session.query(Vulnerability).filter(
                Vulnerability.published_date < ninety_days_ago,
                Vulnerability.base_severity.in_(['LOW', 'MEDIUM'])
            ).count()
            
            unpatched_count = session.query(Vulnerability).filter(
                or_(
                    Vulnerability.published_date >= ninety_days_ago,
                    Vulnerability.base_severity.in_(['HIGH', 'CRITICAL'])
                )
            ).count()
            
            data = [
                {'label': 'Patched', 'value': patched_count},
                {'label': 'Unpatched', 'value': unpatched_count}
            ]
            
        elif category == 'latest_cves':
            # Get latest CVEs with pagination
            offset = (page - 1) * per_page
            results = session.query(Vulnerability).order_by(
                desc(Vulnerability.published_date)
            ).offset(offset).limit(per_page).all()
            
            total_count = session.query(Vulnerability).count()
            
            data = [{
                'cve_id': vuln.cve_id,
                'description': vuln.description[:200] + '...' if len(vuln.description or '') > 200 else vuln.description,
                'published_date': vuln.published_date.isoformat() if vuln.published_date else None,
                'severity': vuln.base_severity,
                'cvss_score': vuln.cvss_score,
                'patch_status': 'Patched' if vuln.published_date and vuln.published_date < datetime.now() - timedelta(days=90) else 'Unpatched'
            } for vuln in results]
            
            return jsonify({
                'data': data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total_count,
                    'pages': (total_count + per_page - 1) // per_page
                }
            }), 200
            
        else:
            return jsonify({'error': f'Unknown category: {category}'}), 400
            
        return jsonify({'data': data}), 200
        
    except Exception as e:
        logger.error(f"Error fetching analytics details for {category}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to fetch {category} data'}), 500


@analytics_api_bp.route('/timeseries/<string:metric_id>', methods=['GET'])
def get_timeseries_data(metric_id: str) -> Response:
    """Get time-series data for specific metrics."""
    try:
        session = db.session
        start_date = request.args.get('start')
        end_date = request.args.get('end')
        
        # Default to last 30 days if no dates provided
        if not start_date:
            start_date = (datetime.now() - timedelta(days=30)).date()
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            
        if not end_date:
            end_date = datetime.now().date()
        else:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        if metric_id == 'cve_history':
            # Get CVE count by day
            results = session.query(
                func.date(Vulnerability.published_date).label('date'),
                func.count(Vulnerability.id).label('count')
            ).filter(
                func.date(Vulnerability.published_date) >= start_date,
                func.date(Vulnerability.published_date) <= end_date
            ).group_by(
                func.date(Vulnerability.published_date)
            ).order_by('date').all()
            
            data = [{
                'date': result.date.isoformat(),
                'value': result.count
            } for result in results]
            
        else:
            return jsonify({'error': f'Unknown metric: {metric_id}'}), 400
            
        return jsonify({
            'metric': metric_id,
            'data': data,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching timeseries data for {metric_id}: {e}", exc_info=True)
        return jsonify({'error': f'Failed to fetch {metric_id} timeseries'}), 500


@analytics_api_bp.route('/severity-distribution', methods=['GET'])
def get_severity_distribution() -> Response:
    """Get severity distribution data for pie chart."""
    try:
        session = db.session
        
        # Get severity counts
        severity_counts = {
            'CRITICAL': session.query(Vulnerability).filter(Vulnerability.base_severity == 'CRITICAL').count(),
            'HIGH': session.query(Vulnerability).filter(Vulnerability.base_severity == 'HIGH').count(),
            'MEDIUM': session.query(Vulnerability).filter(Vulnerability.base_severity == 'MEDIUM').count(),
            'LOW': session.query(Vulnerability).filter(Vulnerability.base_severity == 'LOW').count()
        }
        
        # Format data for Chart.js
        chart_data = {
            'labels': [],
            'data': []
        }
        
        for severity, count in severity_counts.items():
            if count > 0:  # Only include severities with data
                chart_data['labels'].append(severity.title())
                chart_data['data'].append(count)
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'total': sum(severity_counts.values())
        })
        
    except Exception as e:
        logger.error(f"Error getting severity distribution: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get severity distribution'}), 500


@analytics_api_bp.route('/patch-status', methods=['GET'])
def get_patch_status() -> Response:
    """Get patch status data for pie chart."""
    try:
        session = db.session
        
        # Calculate patched vs unpatched using the same logic as overview
        old_date = datetime.now() - timedelta(days=90)
        
        patched_cves = session.query(Vulnerability).filter(
            Vulnerability.published_date < old_date,
            Vulnerability.base_severity.in_(['LOW', 'MEDIUM'])
        ).count()
        
        unpatched_cves = session.query(Vulnerability).filter(
            or_(
                Vulnerability.published_date >= old_date,
                Vulnerability.base_severity.in_(['HIGH', 'CRITICAL'])
            )
        ).count()
        
        # Format data for Chart.js
        chart_data = {
            'labels': ['Patched', 'Unpatched'],
            'data': [patched_cves, unpatched_cves]
        }
        
        return jsonify({
            'success': True,
            'data': chart_data,
            'total': patched_cves + unpatched_cves
        })
        
    except Exception as e:
        logger.error(f"Error getting patch status: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get patch status'}), 500


@analytics_api_bp.route('/query', methods=['POST'])
def run_custom_query() -> Response:
    """Run custom analytics queries."""
    try:
        payload = request.get_json()
        if not payload:
            return jsonify({'error': 'No query payload provided'}), 400
            
        # This is a placeholder for custom query functionality
        # In a real implementation, you would parse the payload and execute custom queries
        return jsonify({
            'message': 'Custom query functionality not yet implemented',
            'payload': payload
        }), 501
        
    except Exception as e:
        logger.error(f"Error running custom query: {e}", exc_info=True)
        return jsonify({'error': 'Failed to run custom query'}), 500