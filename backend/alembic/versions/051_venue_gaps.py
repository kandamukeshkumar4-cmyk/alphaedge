"""cross-venue implied probability gaps (Loop V58 D2)

Revision ID: 051_venue_gaps
Revises: 050_whale_flow
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051_venue_gaps"
down_revision: Union[str, Sequence[str], None] = "050_whale_flow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venue_gaps",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pm_slug", sa.String(length=128), nullable=False),
        sa.Column("ks_slug", sa.String(length=128), nullable=False),
        sa.Column("pm_implied", sa.Numeric(6, 4), nullable=False),
        sa.Column("ks_implied", sa.Numeric(6, 4), nullable=False),
        sa.Column("gap", sa.Numeric(8, 4), nullable=False),
        sa.Column("abs_gap", sa.Numeric(8, 4), nullable=False),
        sa.Column("match_confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("pm_captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ks_captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("pm_slug", "ks_slug", name="uq_venue_gaps_pair"),
    )
    op.create_index("ix_venue_gaps_abs_gap", "venue_gaps", ["abs_gap"])
    op.create_index("ix_venue_gaps_captured", "venue_gaps", ["captured_at"])


def downgrade() -> None:
    op.drop_index("ix_venue_gaps_captured", table_name="venue_gaps")
    op.drop_index("ix_venue_gaps_abs_gap", table_name="venue_gaps")
    op.drop_table("venue_gaps")
