"""analyst_briefs persona column (E13 analyst persona lenses)

Revision ID: 028_analyst_brief_persona
Revises: 027_prediction_log_explanation
Create Date: 2026-07-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028_analyst_brief_persona"
down_revision: Union[str, Sequence[str], None] = "027_prediction_log_explanation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "analyst_briefs",
        sa.Column("persona", sa.String(length=24), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyst_briefs", "persona")
