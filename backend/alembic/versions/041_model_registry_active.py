"""model registry training hash + active pointer (D1)

Revision ID: 041_model_registry_active
Revises: 040_portfolio_equity_snapshots
Create Date: 2026-07-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "041_model_registry_active"
down_revision: Union[str, Sequence[str], None] = "040_portfolio_equity_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_versions",
        sa.Column("training_data_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "model_versions",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.create_table(
        "model_active_pointer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("active_model_version_id", sa.Uuid(), nullable=True),
        sa.Column("previous_model_version_id", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["active_model_version_id"],
            ["model_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["previous_model_version_id"],
            ["model_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("model_active_pointer")
    op.drop_column("model_versions", "is_active")
    op.drop_column("model_versions", "training_data_hash")
