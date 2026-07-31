"""add conversation pinning

Revision ID: chat02_conversation_pinning
Revises: notify01_notification_tables
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat02_conversation_pinning"
down_revision: Union[str, None] = "notify01_notification_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_conversations", sa.Column("pinned_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_conversations", "pinned_at")
