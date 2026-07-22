"""flag scanner runs executed in pre-publish test mode

Adds ``scanner_runs.is_test`` so test-mode runs (loop86 F-B) can be told apart
from production runs. Test runs never write alert feed rows or emails; the
publish gate requires at least one flagged run before draft->active.

Revision ID: 061_scanner_test_runs
Revises: 059_community
Create Date: 2026-07-22
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "061_scanner_test_runs"
down_revision: Union[str, Sequence[str], None] = "060_scanner_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "scanner_runs",
        sa.Column(
            "is_test", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
    )


def downgrade() -> None:
    op.drop_column("scanner_runs", "is_test")
