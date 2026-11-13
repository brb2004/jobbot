"""jobs.closed_at

Revision ID: af83b058c052
Revises: a12b0e400337
Create Date: 2026-11-08 23:51:09.491640

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'af83b058c052'
down_revision: Union[str, Sequence[str], None] = 'a12b0e400337'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'closed_at')
