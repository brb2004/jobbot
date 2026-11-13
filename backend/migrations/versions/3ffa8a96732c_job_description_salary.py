"""job description + salary

Revision ID: 3ffa8a96732c
Revises: 8d8be09f2a3c
Create Date: 2026-10-30 01:50:58.927118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3ffa8a96732c'
down_revision: Union[str, Sequence[str], None] = '8d8be09f2a3c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
