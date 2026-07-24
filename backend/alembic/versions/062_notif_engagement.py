"""Loop V90 N1: engagement notifications schema

Reshape ``notifications`` to the frozen V90 contract (user str, read bool,
tighter string lengths) and add ``notification_preferences`` +
``push_subscriptions``.

Revision ID: 062_notif_engagement
Revises: 061_scanner_test_runs
Create Date: 2026-07-23

Revision id MUST stay under 32 characters
(alembic_version.version_num is varchar(32)).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "062_notif_engagement"
down_revision: Union[str, Sequence[str], None] = "061_scanner_test_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- reshape notifications (V24 -> V90 frozen contract) ---
    op.add_column(
        "notifications",
        sa.Column("user", sa.String(length=64), nullable=True),
    )
    op.execute(
        sa.text("UPDATE notifications SET \"user\" = user_id::text WHERE \"user\" IS NULL")
    )
    op.alter_column("notifications", "user", nullable=False)

    op.add_column(
        "notifications",
        sa.Column(
            "read",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )
    op.execute(
        sa.text(
            "UPDATE notifications SET read = TRUE WHERE read_at IS NOT NULL"
        )
    )

    op.alter_column(
        "notifications",
        "type",
        existing_type=sa.String(length=64),
        type_=sa.String(length=24),
        existing_nullable=False,
    )
    op.alter_column(
        "notifications",
        "title",
        existing_type=sa.String(length=256),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
    op.alter_column(
        "notifications",
        "body",
        existing_type=sa.Text(),
        type_=sa.String(length=1000),
        existing_nullable=False,
        postgresql_using="LEFT(body, 1000)",
    )
    op.alter_column(
        "notifications",
        "link",
        existing_type=sa.String(length=512),
        type_=sa.String(length=300),
        existing_nullable=True,
    )

    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_constraint(
        "notifications_user_id_fkey", "notifications", type_="foreignkey"
    )
    op.drop_column("notifications", "user_id")
    op.drop_column("notifications", "read_at")

    op.create_index("ix_notifications_user", "notifications", ["user"])
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user", "created_at"],
    )

    # --- preferences (defaults: all channels on) ---
    op.create_table(
        "notification_preferences",
        sa.Column("user", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column(
            "email_digest",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "in_app",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "fired_alerts",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )

    # --- web-push subscription store (JSON only; no send in v1) ---
    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user", sa.String(length=64), nullable=False),
        sa.Column("subscription", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_push_subscriptions_user", "push_subscriptions", ["user"])


def downgrade() -> None:
    op.drop_index("ix_push_subscriptions_user", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
    op.drop_table("notification_preferences")

    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index("ix_notifications_user", table_name="notifications")

    op.add_column(
        "notifications",
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE notifications SET user_id = NULLIF(\"user\", '')::uuid "
            "WHERE user_id IS NULL"
        )
    )
    op.alter_column("notifications", "user_id", nullable=False)
    op.create_foreign_key(
        "notifications_user_id_fkey",
        "notifications",
        "users",
        ["user_id"],
        ["id"],
    )

    op.add_column(
        "notifications",
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE notifications SET read_at = created_at WHERE read IS TRUE"
        )
    )

    op.alter_column(
        "notifications",
        "link",
        existing_type=sa.String(length=300),
        type_=sa.String(length=512),
        existing_nullable=True,
    )
    op.alter_column(
        "notifications",
        "body",
        existing_type=sa.String(length=1000),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "notifications",
        "title",
        existing_type=sa.String(length=200),
        type_=sa.String(length=256),
        existing_nullable=False,
    )
    op.alter_column(
        "notifications",
        "type",
        existing_type=sa.String(length=24),
        type_=sa.String(length=64),
        existing_nullable=False,
    )

    op.drop_column("notifications", "read")
    op.drop_column("notifications", "user")

    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", "created_at"],
    )
