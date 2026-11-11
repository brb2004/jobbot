"""users.digest_opt_out_at: unsubscribed from the weekly email"""
import sqlalchemy as sa
from alembic import op

revision = "c2a8f4d6e193"
down_revision = "b7d3e5f1a284"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("digest_opt_out_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "digest_opt_out_at")
