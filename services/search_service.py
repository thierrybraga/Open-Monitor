
"""
SearchService handles business logic for searching vulnerabilities.

This service provides methods to perform searches on vulnerability data,
interacting with the database via SQLAlchemy.
"""

from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from models.vulnerability import Vulnerability


class SearchService:
    """Service for searching vulnerability data."""

    def __init__(self, session: Session):
        """
        Initialize the service with a database session.

        Args:
            session: SQLAlchemy session for database operations.
        """
        self.session = session

    def search(self, query: str) -> List[Dict[str, Any]]:
        """
        Search for vulnerabilities matching the query string.

        Performs a case-insensitive search on CVE ID, title, and description fields.

        Args:
            query: The search term to match against vulnerability data.

        Returns:
            List of dictionaries containing matching vulnerability data.

        Raises:
            RuntimeError: If the search operation fails.
        """
        try:
            if not query or not query.strip():
                return []

            # Clean and prepare the query for LIKE search
            search_term = f"%{query.strip().lower()}%"

            # Query vulnerabilities where cve_id, title, or description match the search term
            results = (
                self.session.query(Vulnerability)
                .filter(
                    func.lower(Vulnerability.cve_id).like(search_term) |
                    func.lower(Vulnerability.title).like(search_term) |
                    func.lower(Vulnerability.description).like(search_term)
                )
                .order_by(Vulnerability.published_date.desc())
                .limit(50)  # Limit results to prevent performance issues
                .all()
            )

            # Convert results to a list of dictionaries
            return [
                {
                    'cve_id': vuln.cve_id,
                    'title': vuln.title,
                    'description': vuln.description,
                    'severity': vuln.severity,
                    'published_date': vuln.published_date,
                }
                for vuln in results
            ]
        except Exception as e:
            raise RuntimeError(f"Error performing search for query '{query}': {e}")