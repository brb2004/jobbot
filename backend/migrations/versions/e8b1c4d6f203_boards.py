"""boards: real company names for Greenhouse board slugs"""
import sqlalchemy as sa
from alembic import op

revision = "e8b1c4d6f203"
down_revision = "d2f7a8c3e915"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "boards",
        sa.Column("slug", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("boards")
