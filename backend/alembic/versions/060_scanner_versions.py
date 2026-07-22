"""add scanner_versions history table

Revision ID: 060_scanner_versions
Revises: 059_community
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "060_scanner_versions"
down_revision: Union[str, Sequence[str], None] = "059_community"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanner_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scanner_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scanner_id", "version", name="uq_scanner_versions_scanner_ver"),
    )
    op.create_index(
        "ix_scanner_versions_scanner_id", "scanner_versions", ["scanner_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scanner_versions_scanner_id", table_name="scanner_versions")
    op.drop_table("scanner_versions")
