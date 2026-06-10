"""user onboarding columns: onboarded + display_name

Revision ID: 017_user_onboarding
Revises: 016_market_resolutions_index
Create Date: 2026-06-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017_user_onboarding"
down_revision: Union[str, None] = "016_market_resolutions_index"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "display_name")
    op.drop_column("users", "onboarded")
