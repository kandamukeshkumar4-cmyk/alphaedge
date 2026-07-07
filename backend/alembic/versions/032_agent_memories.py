"""loop3 agent_memories — resolved-market memory the agent graph recalls.

One row per resolved market/forecast (model vs market prob at close, outcome,
Brier, rationale). ``embedding`` is a nullable JSON list of floats so the design
stays portable: no pgvector dependency (Neon may not have it); recall falls back
to category/keyword similarity.

Revision ID: 032_agent_memories
Revises: 031_weather_forecast_logs
Create Date: 2026-07-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032_agent_memories"
down_revision: Union[str, Sequence[str], None] = "031_weather_forecast_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column("market_slug", sa.String(128), nullable=False),
        sa.Column("category", sa.String(64), nullable=False, server_default="General"),
        sa.Column("question", sa.Text(), nullable=False, server_default=""),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("model_prob_at_close", sa.Float(), nullable=True),
        sa.Column("market_prob_at_close", sa.Float(), nullable=True),
        sa.Column("brier", sa.Float(), nullable=True),
        sa.Column("rationale_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_memories_category_created",
        "agent_memories",
        ["category", "created_at"],
    )
    op.create_index("ix_agent_memories_slug", "agent_memories", ["market_slug"])


def downgrade() -> None:
    op.drop_index("ix_agent_memories_slug", table_name="agent_memories")
    op.drop_index("ix_agent_memories_category_created", table_name="agent_memories")
    op.drop_table("agent_memories")
