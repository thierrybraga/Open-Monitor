"""add catalog_tag to assets

Revision ID: add_catalog_tag_to_assets
Revises: 
Create Date: 2025-11-11 12:35:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_catalog_tag_to_assets'
down_revision = 'ab12cd34ef56'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('assets', sa.Column('catalog_tag', sa.String(length=100), nullable=True))
    except Exception:
        # Column may already exist; ignore
        pass
    try:
        op.create_index('ix_assets_catalog_tag', 'assets', ['catalog_tag'])
    except Exception:
        # Index may already exist; ignore
        pass


def downgrade():
    try:
        op.drop_index('ix_assets_catalog_tag', table_name='assets')
    except Exception:
        pass
    try:
        op.drop_column('assets', 'catalog_tag')
    except Exception:
        pass