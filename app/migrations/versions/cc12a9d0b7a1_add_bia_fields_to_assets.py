"""Add BIA fields (RTO/RPO/uptime/cost) to assets

Revision ID: cc12a9d0b7a1
Revises: a7c9d4f2b1e3
Create Date: 2025-11-05 00:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'cc12a9d0b7a1'
down_revision = 'a7c9d4f2b1e3'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('assets')}

    # Use batch mode for better SQLite compatibility
    with op.batch_alter_table('assets', schema=None) as batch_op:
        if 'rto_hours' not in existing_columns:
            batch_op.add_column(sa.Column('rto_hours', sa.Integer(), nullable=True))
        if 'rpo_hours' not in existing_columns:
            batch_op.add_column(sa.Column('rpo_hours', sa.Integer(), nullable=True))
        if 'uptime_text' not in existing_columns:
            batch_op.add_column(sa.Column('uptime_text', sa.String(length=100), nullable=True))
        if 'operational_cost_per_hour' not in existing_columns:
            batch_op.add_column(sa.Column('operational_cost_per_hour', sa.Float(), nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {col['name'] for col in inspector.get_columns('assets')}

    with op.batch_alter_table('assets', schema=None) as batch_op:
        if 'rto_hours' in existing_columns:
            batch_op.drop_column('rto_hours')
        if 'rpo_hours' in existing_columns:
            batch_op.drop_column('rpo_hours')
        if 'uptime_text' in existing_columns:
            batch_op.drop_column('uptime_text')
        if 'operational_cost_per_hour' in existing_columns:
            batch_op.drop_column('operational_cost_per_hour')