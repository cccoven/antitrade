"""generic notification events, channels, subscriptions, and deliveries

Revision ID: notify01_notification_tables
Revises: trade01_plans_rules_review
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "notify01_notification_tables"
down_revision: Union[str, None] = "trade01_plans_rules_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_key", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=True),
        sa.Column("subject_id", sa.String(), nullable=True),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_index("idx_notification_events_type", "notification_events", ["event_type"])
    op.create_index("idx_notification_events_occurred", "notification_events", ["occurred_at"])
    op.create_index(
        "idx_notification_events_subject", "notification_events", ["subject_type", "subject_id"]
    )

    op.create_table(
        "notification_channels",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("channel_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("locale", sa.String(), nullable=False, server_default="zh"),
        sa.Column("verification_token_hash", sa.String(), nullable=True),
        sa.Column("verification_expires_at", sa.String(), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','active','disabled')", name="ck_notification_channels_status"
        ),
        sa.CheckConstraint("locale IN ('zh','en')", name="ck_notification_channels_locale"),
        sa.UniqueConstraint("user_id", "channel_type", name="uq_notification_channels_user_type"),
    )
    op.create_index("idx_notification_channels_user", "notification_channels", ["user_id"])
    op.create_index(
        "uq_notification_channels_active_address",
        "notification_channels",
        ["channel_type", "address"],
        unique=True,
        postgresql_where=sa.text("address IS NOT NULL AND status = 'active'"),
    )

    op.create_table(
        "notification_subscriptions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "channel_id", sa.String(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False, server_default=""),
        sa.Column("subject_id", sa.String(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("locale", sa.String(), nullable=False, server_default="zh"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("locale IN ('zh','en')", name="ck_notification_subscriptions_locale"),
        sa.UniqueConstraint(
            "user_id", "channel_id", "event_type", "subject_type", "subject_id",
            name="uq_notification_subscriptions_target",
        ),
    )
    op.create_index(
        "idx_notification_subscriptions_match", "notification_subscriptions",
        ["event_type", "subject_type", "subject_id", "enabled"],
    )
    op.create_index("idx_notification_subscriptions_user", "notification_subscriptions", ["user_id"])

    op.create_table(
        "notification_deliveries",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "event_id", sa.String(),
            sa.ForeignKey("notification_events.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "subscription_id", sa.String(),
            sa.ForeignKey("notification_subscriptions.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "channel_id", sa.String(),
            sa.ForeignKey("notification_channels.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.String(), nullable=True),
        sa.Column("claimed_at", sa.String(), nullable=True),
        sa.Column("sent_at", sa.String(), nullable=True),
        sa.Column("provider_message_id", sa.String(), nullable=True),
        sa.Column("last_error_code", sa.String(), nullable=True),
        sa.Column("last_error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','processing','sent','retrying','failed','expired','unknown')",
            name="ck_notification_deliveries_status",
        ),
        sa.UniqueConstraint(
            "event_id", "subscription_id", "channel_id",
            name="uq_notification_deliveries_target",
        ),
    )
    op.create_index(
        "idx_notification_deliveries_queue", "notification_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index("idx_notification_deliveries_created", "notification_deliveries", ["created_at"])


def downgrade() -> None:
    op.drop_table("notification_deliveries")
    op.drop_table("notification_subscriptions")
    op.drop_table("notification_channels")
    op.drop_table("notification_events")
