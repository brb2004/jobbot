"""skills_version

Revision ID: 5dacd521e229
Revises: af83b058c052
Create Date: 2026-11-08 23:54:16.903580

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5dacd521e229'
down_revision: Union[str, Sequence[str], None] = 'af83b058c052'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('skills_version', sa.String(length=12), nullable=True))
    op.add_column('resumes', sa.Column('skills_version', sa.String(length=12), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('resumes', 'skills_version')
    op.drop_column('jobs', 'skills_version')
