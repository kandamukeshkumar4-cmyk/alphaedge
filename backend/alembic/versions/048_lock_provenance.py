"""per-lock forecast provenance (Loop V56 P1)

Adds nullable provenance columns to ``forecast_logs`` so every FUTURE lock can
record what produced it. Every column is nullable on purpose: forecasts locked
before this migration carry no provenance and are deliberately left untouched.
A null means "unknown", which is the honest value — V56 never backfills.

Revision ID: 048_lock_provenance
Revises: 047_social
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "048_lock_provenance"
down_revision: Union[str, Sequence[str], None] = "047_social"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forecast_logs", sa.Column("model_type", sa.String(64), nullable=True))
    op.add_column("forecast_logs", sa.Column("model_version", sa.String(64), nullable=True))
    op.add_column("forecast_logs", sa.Column("artifact_digest", sa.String(128), nullable=True))
    op.add_column(
        "forecast_logs", sa.Column("feature_schema_digest", sa.String(128), nullable=True)
    )
    op.add_column("forecast_logs", sa.Column("feature_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("forecast_logs", "feature_payload")
    op.drop_column("forecast_logs", "feature_schema_digest")
    op.drop_column("forecast_logs", "artifact_digest")
    op.drop_column("forecast_logs", "model_version")
    op.drop_column("forecast_logs", "model_type")
