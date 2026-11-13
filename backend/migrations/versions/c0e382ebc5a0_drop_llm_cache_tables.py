"""drop llm cache tables

Revision ID: c0e382ebc5a0
Revises: 9171203b9685
Create Date: 2026-11-01 04:53:09.995218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'c0e382ebc5a0'
down_revision: Union[str, Sequence[str], None] = '9171203b9685'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_table('term_vectors')
    op.drop_table('term_matches')


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table('term_matches',
    sa.Column('requirement', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('skill', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('verdict', sa.BOOLEAN(), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('requirement', 'skill', name=op.f('term_matches_pkey'))
    )
    op.create_table('term_vectors',
    sa.Column('term', sa.TEXT(), autoincrement=False, nullable=False),
    sa.Column('vector', postgresql.ARRAY(sa.DOUBLE_PRECISION(precision=53)), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('term', name=op.f('term_vectors_pkey'))
    )
