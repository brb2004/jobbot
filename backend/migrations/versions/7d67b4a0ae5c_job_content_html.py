"""job content_html

Revision ID: 7d67b4a0ae5c
Revises: aa78ca08a21f
Create Date: 2026-10-30 06:56:51.675487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7d67b4a0ae5c'
down_revision: Union[str, Sequence[str], None] = 'aa78ca08a21f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('content_html', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'content_html')
