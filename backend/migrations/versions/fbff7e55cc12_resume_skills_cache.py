"""resume skills cache

Revision ID: fbff7e55cc12
Revises: 06fa2eb3073c
Create Date: 2026-10-30 05:42:00.652516

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fbff7e55cc12'
down_revision: Union[str, Sequence[str], None] = '06fa2eb3073c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
