"""assistant long-term memories

Revision ID: memory01_assistant_memories
Revises: chat01_pending_state
Create Date: 2026-07-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "memory01_assistant_memories"
down_revision: Union[str, None] = "chat01_pending_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "assistant_memories",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_index("idx_assistant_memories_user_updated", "assistant_memories",
                    ["user_id", sa.text("updated_at DESC")])


def downgrade() -> None:
    op.drop_table("assistant_memories")
