"""users.email_verified_at; accounts made before verification existed count as verified"""
import sqlalchemy as sa
from alembic import op

revision = "7c3e9a1f4b2d"
down_revision = "950cd1114756"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET email_verified_at = now()")


def downgrade() -> None:
    op.drop_column("users", "email_verified_at")
