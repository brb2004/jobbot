"""resumes: one per user, deleted with the user (UNIQUE + FK). Indexes: match_scores(job_id), open jobs."""
from alembic import op

revision = "a4e6b2c9d071"
down_revision = "f3c9d2a7b815"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Resumes whose user is gone, then all but one per user (the last written row; their scores cascade).
    op.execute("DELETE FROM resumes WHERE user_id NOT IN (SELECT id FROM users)")
    op.execute("DELETE FROM resumes a USING resumes b WHERE a.user_id = b.user_id AND a.ctid < b.ctid")
    op.drop_index("ix_resumes_user_id", table_name="resumes")
    op.create_unique_constraint("uq_resumes_user_id", "resumes", ["user_id"])   # its index replaces the old one
    op.create_foreign_key("fk_resumes_user_id", "resumes", "users", ["user_id"], ["id"], ondelete="CASCADE")
    op.create_index("ix_match_scores_job_id", "match_scores", ["job_id"])
    op.create_index("ix_jobs_open", "jobs", ["id"], postgresql_where="closed_at IS NULL")


def downgrade() -> None:
    op.drop_index("ix_jobs_open", table_name="jobs")
    op.drop_index("ix_match_scores_job_id", table_name="match_scores")
    op.drop_constraint("fk_resumes_user_id", "resumes", type_="foreignkey")
    op.drop_constraint("uq_resumes_user_id", "resumes", type_="unique")
    op.create_index("ix_resumes_user_id", "resumes", ["user_id"])
