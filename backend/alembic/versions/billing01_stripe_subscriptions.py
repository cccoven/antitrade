"""Stripe subscriptions and metered entitlement usage.

Revision ID: billing01_stripe_subscriptions
Revises: chat07_message_attachments
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "billing01_stripe_subscriptions"
down_revision: Union[str, None] = "chat07_message_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "billing_accounts",
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("stripe_customer_id", sa.String(), nullable=True, unique=True),
        sa.Column("stripe_subscription_id", sa.String(), nullable=True, unique=True),
        sa.Column("stripe_price_id", sa.String(), nullable=True),
        sa.Column("plan", sa.String(), nullable=False, server_default="free"),
        sa.Column("status", sa.String(), nullable=False, server_default="none"),
        sa.Column("billing_interval", sa.String(), nullable=True),
        sa.Column("current_period_start", sa.String(), nullable=True),
        sa.Column("current_period_end", sa.String(), nullable=True),
        sa.Column(
            "cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("plan IN ('free','pro')", name="ck_billing_accounts_plan"),
        sa.CheckConstraint(
            "status IN ('none','incomplete','incomplete_expired','trialing','active',"
            "'past_due','canceled','unpaid','paused')",
            name="ck_billing_accounts_status",
        ),
        sa.CheckConstraint(
            "billing_interval IS NULL OR billing_interval IN ('month','year')",
            name="ck_billing_accounts_interval",
        ),
    )

    op.create_table(
        "billing_usage_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("metric", sa.String(), nullable=False),
        sa.Column("feature", sa.String(), nullable=False),
        sa.Column("units", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(), nullable=False),
        sa.Column("occurred_at", sa.String(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "metric", "request_id", name="uq_billing_usage_request"
        ),
    )
    op.create_index(
        "idx_billing_usage_period",
        "billing_usage_events",
        ["user_id", "metric", "occurred_at"],
    )

    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("processed_at", sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
    op.drop_index("idx_billing_usage_period", table_name="billing_usage_events")
    op.drop_table("billing_usage_events")
    op.drop_table("billing_accounts")
