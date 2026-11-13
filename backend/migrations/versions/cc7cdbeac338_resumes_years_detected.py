"""resumes.years_detected

Revision ID: cc7cdbeac338
Revises: dac94873bd52
Create Date: 2026-11-09 01:21:15.213319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cc7cdbeac338'
down_revision: Union[str, Sequence[str], None] = 'dac94873bd52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('resumes', sa.Column('years_detected', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'years_detected')
