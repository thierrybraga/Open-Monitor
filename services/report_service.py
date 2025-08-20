
"""
ReportService handles business logic for generating vulnerability reports.

This service provides methods to fetch report data for a specified period,
aggregating vulnerability statistics and trends from the database via SQLAlchemy.
"""

from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from models.vulnerability import Vulnerability
from models.asset import Asset
from models.report import Report
from extensions import db


class ReportService:
    """Service for generating vulnerability report data."""

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def get_report_data(self, period: str) -> Dict[str, Any]:
        """
        Fetch report data for the specified period.

        Generates statistics including total vulnerabilities, counts by severity,
        and a trend of vulnerabilities over time within the period.

        Args:
            period: The report period ('daily', 'weekly', 'monthly', 'quarterly', 'yearly').

        Returns:
            Dictionary containing report data with total counts, severity counts,
            and trend data.

        Raises:
            ValueError: If the period is invalid.
            RuntimeError: If the database query fails.
        """
        valid_periods = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly']
        if period not in valid_periods:
            raise ValueError(f"Invalid period: {period}. Must be one of {valid_periods}")

        try:
            # Determine the time range based on the period
            now = datetime.utcnow()
            if period == 'daily':
                start_date = now - timedelta(days=1)
                group_by = func.date_trunc('hour', Vulnerability.published_date)
            elif period == 'weekly':
                start_date = now - timedelta(days=7)
                group_by = func.date_trunc('day', Vulnerability.published_date)
            elif period == 'monthly':
                start_date = now - timedelta(days=30)
                group_by = func.date_trunc('day', Vulnerability.published_date)
            elif period == 'quarterly':
                start_date = now - timedelta(days=90)
                group_by = func.date_trunc('week', Vulnerability.published_date)
            else:  # yearly
                start_date = now - timedelta(days=365)
                group_by = func.date_trunc('month', Vulnerability.published_date)

            # Fetch total and severity counts
            counts_query = (
                self.session.query(
                    func.count().label('total'),
                    func.count(func.nullif(Vulnerability.severity == 'critical', False)).label('critical'),
                    func.count(func.nullif(Vulnerability.severity == 'high', False)).label('high'),
                    func.count(func.nullif(Vulnerability.severity == 'medium', False)).label('medium'),
                    func.count(func.nullif(Vulnerability.severity == 'low', False)).label('low')
                )
                .filter(Vulnerability.published_date >= start_date)
                .one()
            )

            # Fetch trend data (counts over time)
            trend_query = (
                self.session.query(
                    group_by.label('time'),
                    func.count().label('count')
                )
                .filter(Vulnerability.published_date >= start_date)
                .group_by(group_by)
                .order_by(group_by)
                .all()
            )

            # Format trend data
            trend_data = [
                {'time': row.time.strftime('%Y-%m-%d %H:%M:%S'), 'count': row.count}
                for row in trend_query
            ]

            return {
                'period': period,
                'start_date': start_date.strftime('%Y-%m-%d %H:%M:%S'),
                'end_date': now.strftime('%Y-%m-%d %H:%M:%S'),
                'counts': {
                    'total': counts_query.total,
                    'critical': counts_query.critical,
                    'high': counts_query.high,
                    'medium': counts_query.medium,
                    'low': counts_query.low
                },
                'trend': trend_data
            }
        except ValueError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"Error fetching report data for period '{period}': {e}")

def generate_report():
    return None