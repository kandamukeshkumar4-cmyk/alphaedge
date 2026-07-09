"""persist cross-venue market matches (G02)

Revision ID: 034_venue_market_matches
Revises: 033_analyst_brief_tools_used
Create Date: 2026-07-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "034_venue_market_matches"
down_revision: Union[str, Sequence[str], None] = "033_analyst_brief_tools_used"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "venue_market_matches",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("pm_slug", sa.String(length=128), nullable=False),
        sa.Column("ks_slug", sa.String(length=128), nullable=False),
        sa.Column("pm_title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("ks_title", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=True),
        sa.Column("stale", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "matched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("pm_slug", "ks_slug", name="uq_venue_market_match_pair"),
    )
    op.create_index(
        "ix_venue_market_matches_confidence",
        "venue_market_matches",
        ["confidence"],
    )


def downgrade() -> None:
    op.drop_index("ix_venue_market_matches_confidence", table_name="venue_market_matches")
    op.drop_table("venue_market_matches")
