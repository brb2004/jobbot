"""text columns for long requirement bullets

Revision ID: 6a4d5f2dc8b4
Revises: 7d67b4a0ae5c
Create Date: 2026-10-30 07:51:41.329845

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6a4d5f2dc8b4'
down_revision: Union[str, Sequence[str], None] = '7d67b4a0ae5c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('term_matches', 'requirement',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('term_matches', 'skill',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=False)
    op.alter_column('term_vectors', 'term',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.Text(),
               existing_nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('term_vectors', 'term',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    op.alter_column('term_matches', 'skill',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    op.alter_column('term_matches', 'requirement',
               existing_type=sa.Text(),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
