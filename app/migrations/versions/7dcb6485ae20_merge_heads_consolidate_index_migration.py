"""Merge heads: consolidate index migration

Revision ID: 7dcb6485ae20
Revises: e1a2b3c4d5f6, fd387f3f57b3
Create Date: 2025-11-04 22:50:51.102541

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7dcb6485ae20'
down_revision = ('e1a2b3c4d5f6', 'fd387f3f57b3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
