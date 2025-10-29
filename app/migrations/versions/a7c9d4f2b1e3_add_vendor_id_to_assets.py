"""Add vendor_id to assets and FK to vendor

Revision ID: a7c9d4f2b1e3
Revises: ff55b16f37f6
Create Date: 2025-10-05 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7c9d4f2b1e3'
down_revision = 'ff55b16f37f6'
branch_labels = None
depends_on = None


def upgrade():
    # Use SQLAlchemy inspector to avoid recreating existing objects
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('assets')}
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('assets')}
    existing_fks = {fk['name'] for fk in inspector.get_foreign_keys('assets')}

    # Use batch mode to support SQLite migrations
    with op.batch_alter_table('assets', schema=None) as batch_op:
        if 'vendor_id' not in existing_columns:
            batch_op.add_column(sa.Column('vendor_id', sa.Integer(), nullable=True))
        if 'ix_assets_vendor_id' not in existing_indexes:
            batch_op.create_index('ix_assets_vendor_id', ['vendor_id'])
        if 'fk_assets_vendor' not in existing_fks:
            batch_op.create_foreign_key(
                'fk_assets_vendor',
                'vendor',
                ['vendor_id'],
                ['id'],
                ondelete='SET NULL'
            )


def downgrade():
    # Use SQLAlchemy inspector to check existence before dropping
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_indexes = {idx['name'] for idx in inspector.get_indexes('assets')}
    existing_fks = {fk['name'] for fk in inspector.get_foreign_keys('assets')}
    existing_columns = {col['name'] for col in inspector.get_columns('assets')}

    # Use batch mode to safely revert changes on SQLite
    with op.batch_alter_table('assets', schema=None) as batch_op:
        if 'fk_assets_vendor' in existing_fks:
            batch_op.drop_constraint('fk_assets_vendor', type_='foreignkey')
        if 'ix_assets_vendor_id' in existing_indexes:
            batch_op.drop_index('ix_assets_vendor_id')
        if 'vendor_id' in existing_columns:
            batch_op.drop_column('vendor_id')