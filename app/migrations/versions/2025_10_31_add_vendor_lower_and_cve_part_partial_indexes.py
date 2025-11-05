"""Add functional and partial indexes to optimize catalog_tag filtering

Revision ID: 2025_10_31_add_vendor_lower_and_cve_part_partial_indexes
Revises: 
Create Date: 2025-10-31

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = '2025_10_31_add_vendor_lower_and_cve_part_partial_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Functional index for case-insensitive vendor name search
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_vendor_name_lower ON vendor (lower(name));
    """)

    # Partial indexes for quick filtering by CPE part
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_cve_parts_part_a ON cve_parts (cve_id) WHERE part = 'a';
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_cve_parts_part_o ON cve_parts (cve_id) WHERE part = 'o';
    """)
    op.execute("""
    CREATE INDEX IF NOT EXISTS idx_cve_parts_part_h ON cve_parts (cve_id) WHERE part = 'h';
    """)


def downgrade():
    # Drop indexes if they exist
    op.execute("""
    DROP INDEX IF EXISTS idx_vendor_name_lower;
    """)
    op.execute("""
    DROP INDEX IF EXISTS idx_cve_parts_part_a;
    """)
    op.execute("""
    DROP INDEX IF EXISTS idx_cve_parts_part_o;
    """)
    op.execute("""
    DROP INDEX IF EXISTS idx_cve_parts_part_h;
    """)