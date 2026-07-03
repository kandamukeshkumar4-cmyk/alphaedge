"""markets clob_token_id column (Polymarket CLOB WS subscription key)

Revision ID: 023_market_clob_token_id
Revises: 022_live_market_source
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023_market_clob_token_id"
down_revision: Union[str, Sequence[str], None] = "022_live_market_source"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("clob_token_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("markets", "clob_token_id")
