"""jobs.source_updated_at: Greenhouse's updated_at, to re-fetch edited postings"""
import sqlalchemy as sa
from alembic import op

revision = "b7d3e5f1a284"
down_revision = "a4e6b2c9d071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("source_updated_at", sa.String(40), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "source_updated_at")
