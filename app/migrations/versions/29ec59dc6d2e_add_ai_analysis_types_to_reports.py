"""add ai_analysis_types to reports

Revision ID: 29ec59dc6d2e
Revises: 3c644b6bbb4d
Create Date: 2025-10-14 10:09:03.974981

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '29ec59dc6d2e'
down_revision = '3c644b6bbb4d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('reports') as batch_op:
        batch_op.add_column(sa.Column('ai_analysis_types', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('reports') as batch_op:
        batch_op.drop_column('ai_analysis_types')
