"""chat pending_state

Revision ID: chat01_pending_state
Revises: feed01_feed_tables
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "chat01_pending_state"
down_revision: Union[str, None] = "feed01_feed_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_conversations", sa.Column("pending_state", sa.JSON(), nullable=True))
    op.add_column("chat_conversations", sa.Column("pending_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_conversations", "pending_at")
    op.drop_column("chat_conversations", "pending_state")
