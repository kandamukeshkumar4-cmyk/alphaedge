"""Add forecaster recovery codes

Revision ID: 007
Revises: 006
Create Date: 2026-06-04
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("forecasters", sa.Column("recovery_code_hash", sa.String(64), nullable=True))
    op.execute(
        """
        UPDATE forecasters
        SET recovery_code_hash =
            md5(id::text || ':alphaedge-recovery-code-v1') ||
            md5('alphaedge-recovery-code-v1:' || id::text)
        WHERE recovery_code_hash IS NULL
        """
    )
    op.alter_column("forecasters", "recovery_code_hash", nullable=False)
    op.create_index(
        "ix_forecasters_recovery_code_hash",
        "forecasters",
        ["recovery_code_hash"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_forecasters_recovery_code_hash", table_name="forecasters")
    op.drop_column("forecasters", "recovery_code_hash")
