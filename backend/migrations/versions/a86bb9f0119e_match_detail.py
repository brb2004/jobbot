"""match detail

Revision ID: a86bb9f0119e
Revises: 09489025a10d
Create Date: 2026-10-30 03:58:44.468370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a86bb9f0119e'
down_revision: Union[str, Sequence[str], None] = '09489025a10d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
