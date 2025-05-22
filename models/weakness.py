
"""
weakness.py

Defines the Weakness model for the Flask application.
Represents a relationship between vulnerabilities and CWE (Common Weakness Enumeration) identifiers.
Inherits from BaseModel to include auditing fields (created_at, updated_at) and utility methods.
"""

import logging
import re
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Column, ForeignKey, String, Integer, PrimaryKeyConstraint, Index
from sqlalchemy.orm import relationship, validates
from ..extensions.db import db
from .base_model import BaseModel

# Configure logging to align with settings.py
logger = logging.getLogger(__name__)

# Avoid circular imports during type checking
if TYPE_CHECKING:
    from project.models import Vulnerability

class Weakness(BaseModel):
    """
    Weakness model representing a CWE identifier associated with a vulnerability.

    Attributes:
        vulnerability_id (int): Foreign key referencing the vulnerability.
        cwe_id (str): CWE identifier (e.g., 'CWE-123').
        vulnerability (Vulnerability): Relationship to the Vulnerability model.

    Table:
        weaknesses: Stores vulnerability-CWE mappings with a composite primary key
        (vulnerability_id, cwe_id).

    Usage:
        weakness = Weakness(vulnerability_id=1, cwe_id='CWE-123')
        weakness.save()
    """
    __tablename__ = 'weaknesses'

    vulnerability_id = Column(
        Integer,
        ForeignKey('vulnerabilities.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
        doc="Foreign key referencing the vulnerability ID."
    )
    cwe_id = Column(
        String(50),
        nullable=False,
        doc="CWE identifier (e.g., 'CWE-123')."
    )

    __table_args__ = (
        PrimaryKeyConstraint('vulnerability_id', 'cwe_id', name='pk_weaknesses'),
        Index('ix_weaknesses_cwe_id', 'cwe_id'),  # Index for queries by cwe_id
    )

    vulnerability = relationship(
        'Vulnerability',
        back_populates='weaknesses',
        lazy='select',
        doc="Relationship to the associated Vulnerability."
    )

    @validates('cwe_id')
    def validate_cwe_id(self, key, value):
        """
        Validate that cwe_id follows the format 'CWE-XXX'.

        Args:
            key: The field name ('cwe_id').
            value: The CWE identifier to validate.

        Returns:
            str: The validated CWE identifier.

        Raises:
            ValueError: If the format is invalid.
        """
        if not re.match(r'^CWE-\d+$', value):
            logger.error(f"Invalid CWE ID format: {value}")
            raise ValueError(f"CWE ID must match format 'CWE-XXX' (e.g., 'CWE-123')")
        if len(value) > 50:
            logger.error(f"CWE ID too long: {value}")
            raise ValueError("CWE ID must not exceed 50 characters")
        return value

    def __repr__(self) -> str:
        """
        String representation of the Weakness instance.

        Returns:
            str: Representation of the instance.
        """
        return f"<Weakness vuln_id={self.vulnerability_id} cwe_id={self.cwe_id}>"

    @classmethod
    def find_by_cwe_id(cls, cwe_id: str) -> Optional['Weakness']:
        """
        Find a Weakness instance by CWE ID.

        Args:
            cwe_id: The CWE identifier to search for.

        Returns:
            Optional[Weakness]: The Weakness instance or None if not found.
        """
        try:
            return cls.query.filter_by(cwe_id=cwe_id).first()
        except Exception as e:
            logger.error(f"Failed to find Weakness by cwe_id {cwe_id}: {e}")
            return None

    @classmethod
    def create_weakness(cls, vulnerability_id: int, cwe_id: str) -> 'Weakness':
        """
        Create and save a new Weakness instance.

        Args:
            vulnerability_id: The ID of the associated vulnerability.
            cwe_id: The CWE identifier.

        Returns:
            Weakness: The created Weakness instance.

        Raises:
            ValueError: If validation fails.
            Exception: If the database operation fails.
        """
        try:
            weakness = cls(vulnerability_id=vulnerability_id, cwe_id=cwe_id)
            weakness.save()
            logger.debug(f"Created Weakness: {weakness}")
            return weakness
        except Exception as e:
            logger.error(f"Failed to create Weakness: {e}")
            raise