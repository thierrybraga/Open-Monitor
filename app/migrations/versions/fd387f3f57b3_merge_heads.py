"""merge heads

Revision ID: fd387f3f57b3
Revises: 2025_10_31_add_vendor_lower_and_cve_part_partial_indexes, 9ecf1bfada54, cc12a9d0b7a1
Create Date: 2025-11-04 22:39:23.364910

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd387f3f57b3'
down_revision = ('2025_10_31_add_vendor_lower_and_cve_part_partial_indexes', '9ecf1bfada54', 'cc12a9d0b7a1')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
