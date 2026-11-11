"""boards.misses (consecutive 404 crawls) and digest_sent (one weekly digest per user per week)"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3c9d2a7b815"
down_revision = "e8b1c4d6f203"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("boards", sa.Column("misses", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "digest_sent",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week", sa.String(8), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "week"),
    )


def downgrade() -> None:
    op.drop_table("digest_sent")
    op.drop_column("boards", "misses")
