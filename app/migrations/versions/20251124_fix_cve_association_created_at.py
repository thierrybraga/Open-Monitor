"""Add missing created_at columns to cve association tables

Revision ID: 20251124_fix_cve_association_created_at
Revises: 20251124_create_missing_core_tables
Create Date: 2025-11-24

"""
from alembic import op
import sqlalchemy as sa


revision = '20251124_fix_cve_association_created_at'
down_revision = '20251124_create_missing_core_tables'
branch_labels = None
depends_on = None


def _column_names(inspector: sa.engine.reflection.Inspector, table: str) -> set:
    try:
        return {c.get('name') for c in inspector.get_columns(table)}
    except Exception:
        return set()


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # cve_vendors.created_at
    cols = _column_names(inspector, 'cve_vendors')
    if 'cve_vendors' in inspector.get_table_names() and 'created_at' not in cols:
        op.add_column('cve_vendors', sa.Column('created_at', sa.DateTime(), nullable=True))
        try:
            op.execute("UPDATE cve_vendors SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        except Exception:
            pass
        try:
            op.alter_column('cve_vendors', 'created_at', existing_type=sa.DateTime(), nullable=False)
        except Exception:
            # SQLite may not support ALTER to set NOT NULL directly
            pass

    # cve_products.created_at
    cols = _column_names(inspector, 'cve_products')
    if 'cve_products' in inspector.get_table_names() and 'created_at' not in cols:
        op.add_column('cve_products', sa.Column('created_at', sa.DateTime(), nullable=True))
        try:
            op.execute("UPDATE cve_products SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        except Exception:
            pass
        try:
            op.alter_column('cve_products', 'created_at', existing_type=sa.DateTime(), nullable=False)
        except Exception:
            pass


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'cve_vendors' in inspector.get_table_names():
        cols = _column_names(inspector, 'cve_vendors')
        if 'created_at' in cols:
            try:
                op.drop_column('cve_vendors', 'created_at')
            except Exception:
                pass

    if 'cve_products' in inspector.get_table_names():
        cols = _column_names(inspector, 'cve_products')
        if 'created_at' in cols:
            try:
                op.drop_column('cve_products', 'created_at')
            except Exception:
                pass

