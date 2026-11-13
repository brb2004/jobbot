"""resume skills cache

Revision ID: d0fa45f3dfed
Revises: fbff7e55cc12
Create Date: 2026-10-30 05:43:28.878826

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'd0fa45f3dfed'
down_revision: Union[str, Sequence[str], None] = 'fbff7e55cc12'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('resumes', sa.Column('skills', postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'skills')
