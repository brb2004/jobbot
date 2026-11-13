"""job description + salary

Revision ID: 8d8be09f2a3c
Revises: 4630b6a665fb
Create Date: 2026-10-30 01:48:39.999677

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8d8be09f2a3c'
down_revision: Union[str, Sequence[str], None] = '4630b6a665fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('jobs', sa.Column('salary_min', sa.Float(), nullable=True))
    op.add_column('jobs', sa.Column('salary_max', sa.Float(), nullable=True))
    op.add_column('jobs', sa.Column('salary_currency', sa.String(length=10), nullable=True))
    op.add_column('resumes', sa.Column('filename', sa.String(length=255), nullable=True))
    op.add_column('resumes', sa.Column('raw_text', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'raw_text')
    op.drop_column('resumes', 'filename')
    op.drop_column('jobs', 'salary_currency')
    op.drop_column('jobs', 'salary_max')
    op.drop_column('jobs', 'salary_min')
    op.drop_column('jobs', 'description')
