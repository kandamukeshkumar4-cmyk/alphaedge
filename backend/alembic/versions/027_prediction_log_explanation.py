"""prediction_logs explanation column (T11 SHAP top features)

Revision ID: 027_prediction_log_explanation
Revises: 026_analyst_eval_aggregates
Create Date: 2026-07-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027_prediction_log_explanation"
down_revision: Union[str, Sequence[str], None] = "026_analyst_eval_aggregates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "prediction_logs",
        sa.Column("explanation", sa.JSON(), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("prediction_logs", "explanation")
