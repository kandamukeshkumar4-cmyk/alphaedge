"""U06 agent_clones + agent_clone_runs tables

Revision ID: 029_agent_clones
Revises: 028_analyst_brief_persona
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029_agent_clones"
down_revision: Union[str, Sequence[str], None] = "028_analyst_brief_persona"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_clones",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("clone_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("markets", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("edge_threshold", sa.Numeric(5, 4), nullable=False, server_default="0.05"),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("paper_trading_only", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_agent_clones_user_id", "agent_clones", ["user_id"])
    op.create_index(
        "ix_agent_clones_clone_id_version",
        "agent_clones",
        ["clone_id", "version"],
        unique=True,
    )
    op.create_index("ix_agent_clones_clone_id", "agent_clones", ["clone_id"])

    op.create_table(
        "agent_clone_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            "clone_version_id",
            sa.Uuid(as_uuid=True),
            sa.ForeignKey("agent_clones.id"),
            nullable=False,
        ),
        sa.Column("clone_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("market_slug", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("trace", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("result", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agent_clone_runs_clone_id", "agent_clone_runs", ["clone_id"])
    op.create_index(
        "ix_agent_clone_runs_clone_id_created",
        "agent_clone_runs",
        ["clone_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("agent_clone_runs")
    op.drop_table("agent_clones")
