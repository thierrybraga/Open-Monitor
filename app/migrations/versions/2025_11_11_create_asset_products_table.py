"""Create asset_products table with composite PK and FKs

Revision ID: ab12cd34ef56
Revises: f3a8a9e4b2c7
Create Date: 2025-11-11

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ab12cd34ef56'
down_revision = 'f3a8a9e4b2c7'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'asset_products' not in existing_tables:
        op.create_table(
            'asset_products',
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('product_id', sa.Integer(), nullable=False),
            sa.Column('model_name', sa.String(length=255), nullable=True),
            sa.Column('operating_system', sa.String(length=255), nullable=True),
            sa.Column('installed_version', sa.String(length=100), nullable=True),
            sa.PrimaryKeyConstraint('asset_id', 'product_id', name='pk_asset_product'),
            sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], name='fk_asset_products_asset', ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['product_id'], ['product.id'], name='fk_asset_products_product', ondelete='CASCADE'),
        )

        # Composite index to accelerate lookups by (asset_id, product_id)
        op.execute("CREATE INDEX IF NOT EXISTS ix_asset_products_asset_product ON asset_products (asset_id, product_id)")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'asset_products' in existing_tables:
        # Drop composite index if it exists
        op.execute("DROP INDEX IF EXISTS ix_asset_products_asset_product")
        op.drop_table('asset_products')