"""Loop V59 H2: heartbeat decision_log table (revision id <= 32 chars).

Pre-assigned 051_heartbeat (V57=049, V58=050 reserved). In this worktree
chains from head 047_social (048/049/050 absent). Orchestrator re-chains
at merge to single head: 048 -> 049 -> 050 -> 051 — do not pre-fight that.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_heartbeat"
down_revision: Union[str, Sequence[str], None] = "051_venue_gaps"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "heartbeat_decision_logs",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("position_ref", sa.String(length=256), nullable=False),
        sa.Column("rule_fired", sa.String(length=64), nullable=True),
        sa.Column("inputs_snapshot", sa.JSON(), nullable=False),
        sa.Column("action_taken", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_heartbeat_decision_logs_created",
        "heartbeat_decision_logs",
        ["created_at"],
    )
    op.create_index(
        "ix_heartbeat_decision_logs_position_ref",
        "heartbeat_decision_logs",
        ["position_ref"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_heartbeat_decision_logs_position_ref",
        table_name="heartbeat_decision_logs",
    )
    op.drop_index(
        "ix_heartbeat_decision_logs_created",
        table_name="heartbeat_decision_logs",
    )
    op.drop_table("heartbeat_decision_logs")
