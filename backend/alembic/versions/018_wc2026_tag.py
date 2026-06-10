"""markets.tournament_tag for WC2026 grouping

Revision ID: 018_wc2026_tag
Revises: 017_user_onboarding, 017_position_settled
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018_wc2026_tag"
down_revision: Union[str, Sequence[str], None] = (
    "017_user_onboarding",
    "017_position_settled",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("tournament_tag", sa.String(length=32), nullable=True),
    )
    op.create_index("ix_markets_tournament_tag", "markets", ["tournament_tag"])


def downgrade() -> None:
    op.drop_index("ix_markets_tournament_tag", table_name="markets")
    op.drop_column("markets", "tournament_tag")
