"""
models/enums.py

Centralized enum definitions for SQLAlchemy models.
"""

from sqlalchemy import Enum as SQLEnum

# Common severity levels for CVEs
severity_levels = SQLEnum(
    'LOW', 'MEDIUM', 'HIGH', 'CRITICAL',
    name='severity_levels',
    create_type=True  # ensure the enumeration type is created in the database
)

# Status of vulnerabilities on assets
asset_vuln_status = SQLEnum(
    'OPEN', 'MITIGATED', 'CLOSED',
    name='asset_vuln_status',
    create_type=True  # ensure the enumeration type is created in the database
)
