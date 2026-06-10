"""positions.settled flag for idempotent settlement

Revision ID: 017_position_settled
Revises: 016_market_resolutions_index
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa

revision = "017_position_settled"
down_revision = "016_market_resolutions_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "positions",
        sa.Column("settled", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.alter_column("positions", "settled", server_default=None)


def downgrade() -> None:
    op.drop_column("positions", "settled")
