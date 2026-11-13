"""resumes: up to two per user, each with a name and its own title/years settings"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "d5e1a7c3b902"
down_revision = "d4f7a1c3e925"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("uq_resumes_user_id", "resumes", type_="unique")
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])
    op.add_column("resumes", sa.Column("name", sa.String(40), nullable=True))
    op.add_column("resumes", sa.Column("title_prefs", postgresql.JSONB(none_as_null=True), nullable=True))
    op.add_column("resumes", sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(),
                                       nullable=False))


def downgrade() -> None:
    op.execute("DELETE FROM resumes a USING resumes b WHERE a.user_id = b.user_id "
               "AND (a.created_at, a.id) > (b.created_at, b.id)")
    op.drop_column("resumes", "created_at")
    op.drop_column("resumes", "title_prefs")
    op.drop_column("resumes", "name")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.create_unique_constraint("uq_resumes_user_id", "resumes", ["user_id"])
