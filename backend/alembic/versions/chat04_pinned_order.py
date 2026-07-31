"""separate pinned and regular conversation ordering

Revision ID: chat04_pinned_order
Revises: chat03_conversation_order
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat04_pinned_order"
down_revision: Union[str, None] = "chat03_conversation_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("pinned_order", sa.Integer(), nullable=True),
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY sort_order, updated_at DESC, id
                ) - 1 AS position
            FROM chat_conversations
        )
        UPDATE chat_conversations AS conversation
        SET sort_order = ranked.position
        FROM ranked
        WHERE conversation.id = ranked.id
        """
    )
    op.execute(
        "UPDATE chat_conversations SET pinned_order = sort_order WHERE pinned_at IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "pinned_order")
