import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f7d2b9a4c618"
down_revision = "e6b2c8d4f017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("degree", sa.SmallInteger(), nullable=True))
    op.add_column("users", sa.Column("links", postgresql.JSONB(none_as_null=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "links")
    op.drop_column("jobs", "degree")
