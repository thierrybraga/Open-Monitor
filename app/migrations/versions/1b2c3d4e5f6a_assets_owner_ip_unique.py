"""Add composite unique constraint on (owner_id, ip_address) for assets

Revision ID: 1b2c3d4e5f6a
Revises: 7dcb6485ae20
Create Date: 2025-11-05 00:45:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '1b2c3d4e5f6a'
down_revision = '7dcb6485ae20'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Drop existing unique index/constraint on ip_address if present
    existing_indexes = inspector.get_indexes('assets') or []
    existing_uniques = []
    try:
        existing_uniques = inspector.get_unique_constraints('assets') or []
    except Exception:
        existing_uniques = []

    with op.batch_alter_table('assets', schema=None) as batch_op:
        # Drop unique indexes on ip_address
        for idx in existing_indexes:
            cols = [c.lower() for c in (idx.get('column_names') or [])]
            if idx.get('unique') and cols == ['ip_address']:
                name = idx.get('name')
                if name:
                    batch_op.drop_index(name)

        # Drop unique constraints on ip_address
        for uc in existing_uniques:
            cols = [c.lower() for c in (uc.get('column_names') or [])]
            if cols == ['ip_address']:
                name = uc.get('name')
                if name:
                    batch_op.drop_constraint(name, type_='unique')

        # Create composite unique constraint owner_id+ip_address
        batch_op.create_unique_constraint('uq_assets_owner_ip', ['owner_id', 'ip_address'])


def downgrade():
    with op.batch_alter_table('assets', schema=None) as batch_op:
        # Drop composite unique constraint
        batch_op.drop_constraint('uq_assets_owner_ip', type_='unique')
        # Restore uniqueness on ip_address only
        batch_op.create_unique_constraint('uq_assets_ip_address', ['ip_address'])