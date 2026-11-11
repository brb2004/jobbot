"""jobs.external_id: bigint -> text, so Ashby and Lever posting ids (UUIDs) fit beside Greenhouse's numbers.

Rewrites the table once (~90k rows: seconds); uq_jobs_board_external is rebuilt with it.
"""
import sqlalchemy as sa
from alembic import op

revision = "d4f7a1c3e925"
down_revision = "c2a8f4d6e193"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("jobs", "external_id", type_=sa.String(64), existing_type=sa.BigInteger(),
                    postgresql_using="external_id::text")


def downgrade() -> None:
    # Only Greenhouse rows have numeric ids; drop the others first or the cast fails.
    op.execute("DELETE FROM jobs WHERE board LIKE '%:%'")
    op.alter_column("jobs", "external_id", type_=sa.BigInteger(), existing_type=sa.String(64),
                    postgresql_using="external_id::bigint")
