"""persist assistant message image attachments

Revision ID: chat07_message_attachments
Revises: journal01_currency_code
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat07_message_attachments"
down_revision: Union[str, None] = "journal01_currency_code"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_message_attachments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("asset_id", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["asset_id"], ["uploaded_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "asset_id",
            name="uq_chat_message_attachments_message_asset",
        ),
    )
    op.create_index(
        "idx_chat_message_attachments_message",
        "chat_message_attachments",
        ["message_id", "sort_order"],
    )
    op.create_index(
        "idx_chat_message_attachments_asset",
        "chat_message_attachments",
        ["asset_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_chat_message_attachments_asset",
        table_name="chat_message_attachments",
    )
    op.drop_index(
        "idx_chat_message_attachments_message",
        table_name="chat_message_attachments",
    )
    op.drop_table("chat_message_attachments")
