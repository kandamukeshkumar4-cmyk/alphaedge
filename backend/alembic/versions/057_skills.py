"""add skills library registry

Revision ID: 057_skills
Revises: 056_terminal_sessions
Create Date: 2026-07-21
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "057_skills"
down_revision: Union[str, Sequence[str], None] = "056_terminal_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("icon", sa.String(length=16), nullable=True),
        sa.Column("template", sa.JSON(), nullable=False),
        sa.Column("params_schema", sa.JSON(), nullable=True),
        sa.Column("run_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )


def downgrade() -> None:
    op.drop_table("skills")
