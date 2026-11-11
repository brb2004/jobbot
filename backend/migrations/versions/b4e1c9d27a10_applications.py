"""applications: jobs a user applied to (removed from their matches)"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "b4e1c9d27a10"
down_revision = "7c3e9a1f4b2d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "job_id", name="uq_applications_user_job"),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_table("applications")
