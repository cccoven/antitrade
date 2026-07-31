"""add persistent conversation ordering

Revision ID: chat03_conversation_order
Revises: chat02_conversation_pinning
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat03_conversation_order"
down_revision: Union[str, None] = "chat02_conversation_pinning"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("chat_conversations", "sort_order")
