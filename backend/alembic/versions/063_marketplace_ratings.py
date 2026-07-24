"""marketplace ratings + is_featured flags

Revision ID: 063_marketplace_ratings
Revises: 062_notif_engagement
Create Date: 2026-07-24

Adds skill_ratings / scanner_ratings (one rating per user per ref) and
is_featured columns on skills + scanners for admin-curated marketplace.

Revision id MUST stay under 32 characters
(alembic_version.version_num is varchar(32)).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "063_marketplace_ratings"
down_revision: Union[str, Sequence[str], None] = "062_notif_engagement"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "skills",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.add_column(
        "scanners",
        sa.Column(
            "is_featured",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "skill_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("stars >= 1 AND stars <= 5", name="ck_skill_ratings_stars"),
        sa.ForeignKeyConstraint(["ref_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user", "ref_id", name="uq_skill_ratings_user_ref"),
    )
    op.create_index("ix_skill_ratings_ref_id", "skill_ratings", ["ref_id"])

    op.create_table(
        "scanner_ratings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.Uuid(), nullable=False),
        sa.Column("stars", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("stars >= 1 AND stars <= 5", name="ck_scanner_ratings_stars"),
        sa.ForeignKeyConstraint(["ref_id"], ["scanners.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user", "ref_id", name="uq_scanner_ratings_user_ref"),
    )
    op.create_index("ix_scanner_ratings_ref_id", "scanner_ratings", ["ref_id"])


def downgrade() -> None:
    op.drop_index("ix_scanner_ratings_ref_id", table_name="scanner_ratings")
    op.drop_table("scanner_ratings")
    op.drop_index("ix_skill_ratings_ref_id", table_name="skill_ratings")
    op.drop_table("skill_ratings")
    op.drop_column("scanners", "is_featured")
    op.drop_column("skills", "is_featured")
