"""index on market_resolutions.slug for portfolio JOIN

Revision ID: 016_market_resolutions_index
Revises: 015_seed_catalog_markets
Create Date: 2026-06-09
"""

from typing import Sequence, Union

from alembic import op

revision: str = "016_market_resolutions_index"
down_revision: Union[str, None] = "015_seed_catalog_markets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_market_resolutions_slug", "market_resolutions", ["slug"])


def downgrade() -> None:
    op.drop_index("ix_market_resolutions_slug", table_name="market_resolutions")
