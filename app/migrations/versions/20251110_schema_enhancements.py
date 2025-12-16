"""Schema enhancements: product type, asset_type, indexes, constraints

Revision ID: f3a8a9e4b2c7
Revises: None
Create Date: 2025-11-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f3a8a9e4b2c7'
down_revision = '1b2c3d4e5f6a'
branch_labels = None
depends_on = None


def upgrade():
    try:
        bind = op.get_bind()
        if bind.dialect.name == 'sqlite':
            op.execute("PRAGMA busy_timeout=10000")
            op.execute("DROP TABLE IF EXISTS _alembic_tmp_product")
    except Exception:
        pass
    # Use batch mode for SQLite compatibility when altering constraints/columns
    with op.batch_alter_table('product') as batch_op:
        batch_op.add_column(sa.Column('type', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_product_type', ['type'], unique=False)
        batch_op.create_unique_constraint('uq_product_vendor_name', ['vendor_id', 'name'])

    with op.batch_alter_table('assets') as batch_op:
        batch_op.add_column(sa.Column('asset_type', sa.String(length=100), nullable=True))
        batch_op.create_index('ix_assets_asset_type', ['asset_type'], unique=False)

    # Indexes on AssetProduct metadata fields (no constraints altered)
    op.create_index('ix_asset_products_model_name', 'asset_products', ['model_name'], unique=False)
    op.create_index('ix_asset_products_operating_system', 'asset_products', ['operating_system'], unique=False)
    op.create_index('ix_asset_products_installed_version', 'asset_products', ['installed_version'], unique=False)


def downgrade():
    # Drop AssetProduct metadata indexes
    op.drop_index('ix_asset_products_installed_version', table_name='asset_products')
    op.drop_index('ix_asset_products_operating_system', table_name='asset_products')
    op.drop_index('ix_asset_products_model_name', table_name='asset_products')

    # Drop assets.asset_type index and column in batch mode
    with op.batch_alter_table('assets') as batch_op:
        batch_op.drop_index('ix_assets_asset_type')
        batch_op.drop_column('asset_type')

    # Drop product constraints and indexes, then column in batch mode
    with op.batch_alter_table('product') as batch_op:
        batch_op.drop_constraint('uq_product_vendor_name', type_='unique')
        batch_op.drop_index('ix_product_type')
        batch_op.drop_column('type')
