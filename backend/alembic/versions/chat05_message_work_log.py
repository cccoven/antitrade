"""persist assistant work logs

Revision ID: chat05_message_work_log
Revises: chat04_pinned_order
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat05_message_work_log"
down_revision: Union[str, None] = "chat04_pinned_order"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("work_log", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "work_log")
