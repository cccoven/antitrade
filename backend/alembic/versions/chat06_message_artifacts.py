"""persist assistant message artifacts

Revision ID: chat06_message_artifacts
Revises: chat05_message_work_log
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "chat06_message_artifacts"
down_revision: Union[str, None] = "chat05_message_work_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_messages", sa.Column("artifacts", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_messages", "artifacts")
