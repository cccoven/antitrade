"""trade plans, rules, and structured review fields

Revision ID: trade01_plans_rules_review
Revises: memory01_assistant_memories
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "trade01_plans_rules_review"
down_revision: Union[str, None] = "memory01_assistant_memories"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("trades", sa.Column("plan_id", sa.String(), nullable=True))
    op.add_column("trades", sa.Column("target_price", sa.Float(), nullable=True))
    op.add_column("trades", sa.Column("stop_loss", sa.Float(), nullable=True))
    op.add_column("trades", sa.Column("setup_type", sa.String(), nullable=True))
    op.add_column("trades", sa.Column("emotional_state", sa.String(), nullable=True))
    op.add_column("trades", sa.Column("mistakes", sa.Text(), server_default="[]", nullable=False))
    op.add_column("trades", sa.Column("confidence", sa.Integer(), nullable=True))
    op.add_column("trades", sa.Column("execution_quality", sa.Integer(), nullable=True))

    op.create_table(
        "trade_plans",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("market", sa.String(), server_default="stock", nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=True),
        sa.Column("stop_loss", sa.Float(), nullable=False),
        sa.Column("account_size", sa.Float(), nullable=False),
        sa.Column("risk_percent", sa.Float(), nullable=False),
        sa.Column("thesis", sa.Text(), server_default="", nullable=False),
        sa.Column("strategy_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active", nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("direction IN ('long','short')", name="ck_trade_plans_direction"),
        sa.CheckConstraint("status IN ('active','converted')", name="ck_trade_plans_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trade_plans_user_status", "trade_plans", ["user_id", "status"])

    op.create_table(
        "trading_rules",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("rule_type", sa.String(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("weight", sa.String(), server_default="important", nullable=False),
        sa.Column("active", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("weight IN ('critical','important','nice_to_have')", name="ck_trading_rules_weight"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trading_rules_user_active", "trading_rules", ["user_id", "active"])

    op.create_table(
        "trade_rule_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("trade_id", sa.String(), nullable=False),
        sa.Column("rule_id", sa.String(), nullable=True),
        sa.Column("rule_name", sa.String(), nullable=False),
        sa.Column("rule_type", sa.String(), nullable=False),
        sa.Column("weight", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("detail", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint("status IN ('passed','failed','not_applicable')", name="ck_trade_rule_results_status"),
        sa.ForeignKeyConstraint(["rule_id"], ["trading_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["trade_id"], ["trades.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trade_rule_results_trade", "trade_rule_results", ["trade_id"])


def downgrade() -> None:
    op.drop_index("idx_trade_rule_results_trade", table_name="trade_rule_results")
    op.drop_table("trade_rule_results")
    op.drop_index("idx_trading_rules_user_active", table_name="trading_rules")
    op.drop_table("trading_rules")
    op.drop_index("idx_trade_plans_user_status", table_name="trade_plans")
    op.drop_table("trade_plans")
    op.drop_column("trades", "execution_quality")
    op.drop_column("trades", "confidence")
    op.drop_column("trades", "mistakes")
    op.drop_column("trades", "emotional_state")
    op.drop_column("trades", "setup_type")
    op.drop_column("trades", "stop_loss")
    op.drop_column("trades", "target_price")
    op.drop_column("trades", "plan_id")
