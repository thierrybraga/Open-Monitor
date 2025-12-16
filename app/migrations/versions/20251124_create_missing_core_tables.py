"""Create missing core association and support tables

Revision ID: 20251124_create_missing_core_tables
Revises: add_catalog_tag_to_assets
Create Date: 2025-11-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20251124_create_missing_core_tables'
down_revision = 'add_catalog_tag_to_assets'
branch_labels = None
depends_on = None


def _table_exists(inspector: sa.engine.reflection.Inspector, name: str) -> bool:
    try:
        return name in set(inspector.get_table_names())
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # cve_vendors association table
    if not _table_exists(inspector, 'cve_vendors'):
        op.create_table(
            'cve_vendors',
            sa.Column('cve_id', sa.String(), sa.ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'), nullable=False),
            sa.Column('vendor_id', sa.Integer(), sa.ForeignKey('vendor.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('cve_id', 'vendor_id', name='pk_cve_vendor'),
        )
        # Indexes
        try:
            op.create_index('ix_cve_vendors_vendor_cve', 'cve_vendors', ['vendor_id', 'cve_id'], unique=False)
        except Exception:
            pass
        try:
            op.create_index(op.f('ix_cve_vendors_cve_id'), 'cve_vendors', ['cve_id'], unique=False)
        except Exception:
            pass
        try:
            op.create_index(op.f('ix_cve_vendors_vendor_id'), 'cve_vendors', ['vendor_id'], unique=False)
        except Exception:
            pass

    # cve_products association table
    if not _table_exists(inspector, 'cve_products'):
        op.create_table(
            'cve_products',
            sa.Column('cve_id', sa.String(), sa.ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'), nullable=False),
            sa.Column('product_id', sa.Integer(), sa.ForeignKey('product.id', ondelete='CASCADE'), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.PrimaryKeyConstraint('cve_id', 'product_id', name='pk_cve_product'),
        )
        # Indexes
        try:
            op.create_index('ix_cve_products_product_cve', 'cve_products', ['product_id', 'cve_id'], unique=False)
        except Exception:
            pass
        try:
            op.create_index(op.f('ix_cve_products_cve_id'), 'cve_products', ['cve_id'], unique=False)
        except Exception:
            pass
        try:
            op.create_index(op.f('ix_cve_products_product_id'), 'cve_products', ['product_id'], unique=False)
        except Exception:
            pass

    # newsletter_subscriptions table
    if not _table_exists(inspector, 'newsletter_subscriptions'):
        op.create_table(
            'newsletter_subscriptions',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('email', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
            sa.Column('subscribed_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('unsubscribed_at', sa.DateTime(), nullable=True),
            sa.Column('preferences', sa.Text(), nullable=True),
            sa.Column('source', sa.String(length=50), nullable=True, server_default=sa.text("'website'")),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        )
        try:
            op.create_index(op.f('ix_newsletter_subscriptions_email'), 'newsletter_subscriptions', ['email'], unique=True)
        except Exception:
            pass

    # severity_metrics table
    if not _table_exists(inspector, 'severity_metrics'):
        op.create_table(
            'severity_metrics',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('cve_id', sa.String(), sa.ForeignKey('vulnerabilities.cve_id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('cvss_version', sa.String(length=10), nullable=False),
            sa.Column('base_score', sa.Float(), nullable=False),
            sa.Column('base_vector', sa.String(length=255), nullable=False),
            sa.Column('temporal_score', sa.Float(), nullable=True),
            sa.Column('temporal_vector', sa.String(length=255), nullable=True),
            sa.Column('environmental_score', sa.Float(), nullable=True),
            sa.Column('environmental_vector', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('(CURRENT_TIMESTAMP)')),
        )
        try:
            op.create_index(op.f('ix_severity_metrics_cve_id'), 'severity_metrics', ['cve_id'], unique=True)
        except Exception:
            pass

    # role table
    if not _table_exists(inspector, 'role'):
        op.create_table(
            'role',
            sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column('name', sa.String(length=50), nullable=False),
            sa.Column('description', sa.String(length=255), nullable=True),
        )
        try:
            op.create_index(op.f('ix_role_name'), 'role', ['name'], unique=True)
        except Exception:
            pass


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _table_exists(inspector, 'role'):
        try:
            op.drop_index(op.f('ix_role_name'), table_name='role')
        except Exception:
            pass
        op.drop_table('role')

    if _table_exists(inspector, 'severity_metrics'):
        try:
            op.drop_index(op.f('ix_severity_metrics_cve_id'), table_name='severity_metrics')
        except Exception:
            pass
        op.drop_table('severity_metrics')

    if _table_exists(inspector, 'newsletter_subscriptions'):
        try:
            op.drop_index(op.f('ix_newsletter_subscriptions_email'), table_name='newsletter_subscriptions')
        except Exception:
            pass
        op.drop_table('newsletter_subscriptions')

    if _table_exists(inspector, 'cve_products'):
        try:
            op.drop_index(op.f('ix_cve_products_product_id'), table_name='cve_products')
        except Exception:
            pass
        try:
            op.drop_index(op.f('ix_cve_products_cve_id'), table_name='cve_products')
        except Exception:
            pass
        try:
            op.drop_index('ix_cve_products_product_cve', table_name='cve_products')
        except Exception:
            pass
        op.drop_table('cve_products')

    if _table_exists(inspector, 'cve_vendors'):
        try:
            op.drop_index(op.f('ix_cve_vendors_vendor_id'), table_name='cve_vendors')
        except Exception:
            pass
        try:
            op.drop_index(op.f('ix_cve_vendors_cve_id'), table_name='cve_vendors')
        except Exception:
            pass
        try:
            op.drop_index('ix_cve_vendors_vendor_cve', table_name='cve_vendors')
        except Exception:
            pass
        op.drop_table('cve_vendors')

