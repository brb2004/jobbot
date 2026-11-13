import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "e6b2c8d4f017"
down_revision = "d5e1a7c3b902"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seen_jobs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "job_id"),
    )


def downgrade() -> None:
    op.drop_table("seen_jobs")
