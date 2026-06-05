"""Add structured job run summaries

Revision ID: 008
Revises: 007
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "job_runs",
        sa.Column(
            "summary",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.alter_column("job_runs", "summary", server_default=None)
    op.create_index(
        "ix_job_runs_job_started",
        "job_runs",
        ["job_name", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_runs_job_started", table_name="job_runs")
    op.drop_column("job_runs", "summary")
