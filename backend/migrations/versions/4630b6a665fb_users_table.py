"""users table

Revision ID: 4630b6a665fb
Revises: 629bdec192ea
Create Date: 2026-10-30 01:22:52.028817

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4630b6a665fb'
down_revision: Union[str, Sequence[str], None] = '629bdec192ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('users',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('users')
