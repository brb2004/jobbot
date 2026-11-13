"""jobs.skills

Revision ID: a12b0e400337
Revises: c0e382ebc5a0
Create Date: 2026-11-01 05:01:31.218877

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a12b0e400337'
down_revision: Union[str, Sequence[str], None] = 'c0e382ebc5a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('skills', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'skills')
