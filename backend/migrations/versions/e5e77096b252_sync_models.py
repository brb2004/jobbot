"""sync models

Revision ID: e5e77096b252
Revises: 3ffa8a96732c
Create Date: 2026-10-30 02:47:18.449702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5e77096b252'
down_revision: Union[str, Sequence[str], None] = '3ffa8a96732c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
