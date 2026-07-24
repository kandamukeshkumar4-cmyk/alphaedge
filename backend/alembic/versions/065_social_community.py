"""social community: comments, reactions, watchlist shares

Revision ID: 065_social_community
Revises: 064_alpha_runs
Create Date: 2026-07-24

Revision id MUST stay under 32 characters
(alembic_version.version_num is varchar(32)).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "065_social_community"
down_revision: Union[str, Sequence[str], None] = "064_alpha_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_comments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("story_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_story_comments_story_id", "story_comments", ["story_id"])

    op.create_table(
        "story_reactions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("story_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="like"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "story_id", "user_id", "kind", name="uq_story_reactions_story_user_kind"
        ),
    )
    op.create_index("ix_story_reactions_story_id", "story_reactions", ["story_id"])

    op.create_table(
        "watchlist_shares",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("watchlist_shares")
    op.drop_index("ix_story_reactions_story_id", table_name="story_reactions")
    op.drop_table("story_reactions")
    op.drop_index("ix_story_comments_story_id", table_name="story_comments")
    op.drop_table("story_comments")
