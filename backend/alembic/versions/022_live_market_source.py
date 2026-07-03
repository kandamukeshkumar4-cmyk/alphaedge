"""markets live-source mapping columns

Revision ID: 022_live_market_source
Revises: 021_paper_order_sell_close
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022_live_market_source"
down_revision: Union[str, Sequence[str], None] = "021_paper_order_sell_close"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="seed"),
    )
    op.add_column(
        "markets",
        sa.Column("external_slug", sa.String(length=256), nullable=True),
    )
    op.add_column(
        "markets",
        sa.Column("external_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "markets",
        sa.Column("image_url", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "markets",
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_markets_source", "markets", ["source"])
    op.create_index(
        "ix_markets_external_slug",
        "markets",
        ["external_slug"],
        unique=True,
        postgresql_where=sa.text("external_slug IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_markets_external_slug", table_name="markets")
    op.drop_index("ix_markets_source", table_name="markets")
    op.drop_column("markets", "last_synced_at")
    op.drop_column("markets", "image_url")
    op.drop_column("markets", "external_id")
    op.drop_column("markets", "external_slug")
    op.drop_column("markets", "source")
