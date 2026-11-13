"""users.preferences (was missing from migrations)

Revision ID: 950cd1114756
Revises: cc7cdbeac338
Create Date: 2026-11-09 04:45:23.863329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '950cd1114756'
down_revision: Union[str, Sequence[str], None] = 'cc7cdbeac338'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS preferences JSONB")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS preferences")
