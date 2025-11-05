"""Add indexes for core tables (cve_* and vulnerabilities, sync_metadata)

Revision ID: e1a2b3c4d5f6
Revises: cc12a9d0b7a1
Create Date: 2025-11-05 00:30:00

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5f6'
down_revision = 'cc12a9d0b7a1'
branch_labels = None
depends_on = None


def upgrade():
    # Use IF NOT EXISTS for idempotency across SQLite/Postgres
    op.execute("CREATE INDEX IF NOT EXISTS ix_cve_vendors_vendor_cve ON cve_vendors (vendor_id, cve_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cve_products_product_cve ON cve_products (product_id, cve_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cve_parts_part_cve ON cve_parts (part, cve_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vulnerabilities_published_base ON vulnerabilities (published_date, base_severity)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sync_metadata_last_modified ON sync_metadata (last_modified)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_cve_vendors_vendor_cve")
    op.execute("DROP INDEX IF EXISTS ix_cve_products_product_cve")
    op.execute("DROP INDEX IF EXISTS ix_cve_parts_part_cve")
    op.execute("DROP INDEX IF EXISTS ix_vulnerabilities_published_base")
    op.execute("DROP INDEX IF EXISTS ix_sync_metadata_last_modified")