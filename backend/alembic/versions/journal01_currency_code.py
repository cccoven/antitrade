"""add trading journal base currency

Revision ID: journal01_currency_code
Revises: chat06_message_artifacts
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "journal01_currency_code"
down_revision: Union[str, None] = "chat06_message_artifacts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "journal_settings",
        sa.Column("currency_code", sa.String(length=12), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("journal_settings", "currency_code")
