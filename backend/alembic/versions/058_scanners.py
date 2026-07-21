"""add scanners and scanner_runs tables

Revision ID: 058_scanners
Revises: 057_skills
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "058_scanners"
down_revision: Union[str, Sequence[str], None] = "057_skills"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scanners",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("owner", sa.String(length=64), nullable=True),
        sa.Column("spec", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), server_default="120", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "scanner_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("scanner_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["scanner_id"], ["scanners.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scanner_runs_scanner_id", "scanner_runs", ["scanner_id"])


def downgrade() -> None:
    op.drop_index("ix_scanner_runs_scanner_id", table_name="scanner_runs")
    op.drop_table("scanner_runs")
    op.drop_table("scanners")
