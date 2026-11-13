"""term matches cache

Revision ID: aa78ca08a21f
Revises: 732fa89934e1
Create Date: 2026-10-30 06:07:07.881012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'aa78ca08a21f'
down_revision: Union[str, Sequence[str], None] = '732fa89934e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('term_matches',
    sa.Column('requirement', sa.String(length=255), nullable=False),
    sa.Column('skill', sa.String(length=255), nullable=False),
    sa.Column('verdict', sa.Boolean(), nullable=False),
    sa.PrimaryKeyConstraint('requirement', 'skill')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('term_matches')
