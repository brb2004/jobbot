"""job requirements cache

Revision ID: 06fa2eb3073c
Revises: a86bb9f0119e
Create Date: 2026-10-30 05:29:10.845991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '06fa2eb3073c'
down_revision: Union[str, Sequence[str], None] = 'a86bb9f0119e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('requirements', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'requirements')
