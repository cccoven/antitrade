"""add built-in in-app notification inbox

Revision ID: notify02_in_app_inbox
Revises: google01_oauth_identities
Create Date: 2026-07-30

"""
from datetime import datetime, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = "notify02_in_app_inbox"
down_revision: Union[str, None] = "google01_oauth_identities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notification_deliveries",
        sa.Column("read_at", sa.String(), nullable=True),
    )
    op.create_index(
        "idx_notification_deliveries_channel_read",
        "notification_deliveries",
        ["channel_id", "read_at", "created_at"],
    )

    connection = op.get_bind()
    user_ids = connection.execute(sa.text(
        """
        SELECT users.id
        FROM users
        WHERE NOT EXISTS (
            SELECT 1
            FROM notification_channels
            WHERE notification_channels.user_id = users.id
              AND notification_channels.channel_type = 'in_app'
        )
        """
    )).scalars().all()
    if user_ids:
        now = datetime.now(timezone.utc).isoformat()
        channels = sa.table(
            "notification_channels",
            sa.column("id", sa.String()),
            sa.column("user_id", sa.String()),
            sa.column("channel_type", sa.String()),
            sa.column("name", sa.String()),
            sa.column("status", sa.String()),
            sa.column("address", sa.String()),
            sa.column("metadata", sa.JSON()),
            sa.column("locale", sa.String()),
            sa.column("verification_token_hash", sa.String()),
            sa.column("verification_expires_at", sa.String()),
            sa.column("last_error_code", sa.String()),
            sa.column("last_error_at", sa.String()),
            sa.column("created_at", sa.String()),
            sa.column("updated_at", sa.String()),
        )
        op.bulk_insert(
            channels,
            [
                {
                    "id": str(uuid4()),
                    "user_id": user_id,
                    "channel_type": "in_app",
                    "name": "In-app",
                    "status": "active",
                    "address": None,
                    "metadata": {"builtin": True},
                    "locale": "zh",
                    "verification_token_hash": None,
                    "verification_expires_at": None,
                    "last_error_code": None,
                    "last_error_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
                for user_id in user_ids
            ],
        )

    existing_targets = connection.execute(sa.text(
        """
        SELECT DISTINCT ON (
            subscriptions.user_id,
            subscriptions.event_type,
            subscriptions.subject_type,
            subscriptions.subject_id
        )
            subscriptions.user_id,
            channels.id AS channel_id,
            subscriptions.event_type,
            subscriptions.subject_type,
            subscriptions.subject_id,
            subscriptions.locale
        FROM notification_subscriptions AS subscriptions
        JOIN notification_channels AS channels
          ON channels.user_id = subscriptions.user_id
         AND channels.channel_type = 'in_app'
        WHERE subscriptions.enabled = true
          AND subscriptions.channel_id <> channels.id
          AND subscriptions.subject_type <> 'automation_task'
          AND NOT EXISTS (
              SELECT 1
              FROM notification_subscriptions AS existing
              WHERE existing.user_id = subscriptions.user_id
                AND existing.channel_id = channels.id
                AND existing.event_type = subscriptions.event_type
                AND existing.subject_type = subscriptions.subject_type
                AND existing.subject_id = subscriptions.subject_id
          )
        ORDER BY
            subscriptions.user_id,
            subscriptions.event_type,
            subscriptions.subject_type,
            subscriptions.subject_id,
            subscriptions.updated_at DESC
        """
    )).mappings().all()
    if existing_targets:
        now = datetime.now(timezone.utc).isoformat()
        subscriptions = sa.table(
            "notification_subscriptions",
            sa.column("id", sa.String()),
            sa.column("user_id", sa.String()),
            sa.column("channel_id", sa.String()),
            sa.column("event_type", sa.String()),
            sa.column("subject_type", sa.String()),
            sa.column("subject_id", sa.String()),
            sa.column("enabled", sa.Boolean()),
            sa.column("locale", sa.String()),
            sa.column("created_at", sa.String()),
            sa.column("updated_at", sa.String()),
        )
        op.bulk_insert(
            subscriptions,
            [
                {
                    "id": str(uuid4()),
                    "user_id": target["user_id"],
                    "channel_id": target["channel_id"],
                    "event_type": target["event_type"],
                    "subject_type": target["subject_type"],
                    "subject_id": target["subject_id"],
                    "enabled": True,
                    "locale": target["locale"],
                    "created_at": now,
                    "updated_at": now,
                }
                for target in existing_targets
            ],
        )


def downgrade() -> None:
    op.execute("DELETE FROM notification_channels WHERE channel_type = 'in_app'")
    op.drop_index(
        "idx_notification_deliveries_channel_read",
        table_name="notification_deliveries",
    )
    op.drop_column("notification_deliveries", "read_at")
