"""Persist market dashboard snapshots.

Revision ID: market04_dashboard_snapshots
Revises: backtest01_persistent_runs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "market04_dashboard_snapshots"
down_revision: Union[str, None] = "backtest01_persistent_runs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_dashboard_snapshots",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("market_dashboard_snapshots")
