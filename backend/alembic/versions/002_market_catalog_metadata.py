"""Add market catalog metadata

Revision ID: 002
Revises: 001
Create Date: 2026-06-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "markets",
        sa.Column("category", sa.String(64), nullable=False, server_default="Sports"),
    )
    op.add_column(
        "markets",
        sa.Column("icon", sa.String(32), nullable=False, server_default="basketball"),
    )
    op.add_column(
        "markets",
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "markets",
        sa.Column("traders", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "markets",
        sa.Column("market_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "markets",
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "markets",
        sa.Column("resolution", sa.Text(), nullable=False, server_default=""),
    )


def downgrade() -> None:
    for column in [
        "resolution",
        "description",
        "market_count",
        "traders",
        "volume",
        "icon",
        "category",
    ]:
        op.drop_column("markets", column)
