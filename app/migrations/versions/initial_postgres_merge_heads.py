"""Merge heads for consolidated initial Postgres baseline

Revision ID: initial_postgres
Revises: 20251124_fix_cve_association_created_at, 6451daf6d6af
Create Date: 2025-12-04 01:00:00

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = 'initial_postgres'
down_revision = ('20251124_fix_cve_association_created_at', '6451daf6d6af')
branch_labels = None
depends_on = None


def upgrade():
    # Merge only: no schema changes; consolidates multiple heads into one
    pass


def downgrade():
    # Merge only: cannot downgrade to multiple heads automatically
    pass

