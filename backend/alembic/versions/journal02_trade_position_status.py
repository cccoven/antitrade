"""Add explicit open/closed lifecycle status to trades.

Revision ID: journal02_trade_position_status
Revises: agent01_automation_and_imports
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "journal02_trade_position_status"
down_revision: Union[str, None] = "agent01_automation_and_imports"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "trades",
        sa.Column(
            "position_status",
            sa.String(),
            nullable=False,
            server_default="open",
        ),
    )
    op.execute(
        """
        UPDATE trades
        SET position_status = 'closed'
        WHERE close_time IS NOT NULL
           OR close_price IS NOT NULL
           OR pnl IS NOT NULL
        """
    )
    op.create_check_constraint(
        "ck_trades_position_status",
        "trades",
        "position_status IN ('open','closed')",
    )
    op.create_index(
        "idx_trades_user_position_status",
        "trades",
        ["user_id", "position_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_trades_user_position_status", table_name="trades")
    op.drop_constraint(
        "ck_trades_position_status",
        "trades",
        type_="check",
    )
    op.drop_column("trades", "position_status")
