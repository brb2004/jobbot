"""term vectors

Revision ID: 732fa89934e1
Revises: d0fa45f3dfed
Create Date: 2026-10-30 05:52:49.365603

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '732fa89934e1'
down_revision: Union[str, Sequence[str], None] = 'd0fa45f3dfed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('term_vectors',
    sa.Column('term', sa.String(length=255), nullable=False),
    sa.Column('vector', postgresql.ARRAY(sa.Float()), nullable=False),
    sa.PrimaryKeyConstraint('term')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('term_vectors')
