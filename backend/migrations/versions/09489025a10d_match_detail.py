"""match detail

Revision ID: 09489025a10d
Revises: e5e77096b252
Create Date: 2026-10-30 03:57:52.469961

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '09489025a10d'
down_revision: Union[str, Sequence[str], None] = 'e5e77096b252'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('match_scores', sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('match_scores', 'detail')
