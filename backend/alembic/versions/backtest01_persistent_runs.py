"""Replace completed-only backtest results with persistent run records.

Revision ID: backtest01_persistent_runs
Revises: market03_feed_instrument_ids
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "backtest01_persistent_runs"
down_revision: Union[str, None] = "market03_feed_instrument_ids"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("strategy_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("strategy_config", sa.Text(), nullable=False),
        sa.Column(
            "run_kind",
            sa.String(),
            nullable=False,
            server_default="standard",
        ),
        sa.Column("analysis_config", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("requested_date_from", sa.String(), nullable=True),
        sa.Column("requested_date_to", sa.String(), nullable=True),
        sa.Column("actual_date_from", sa.String(), nullable=True),
        sa.Column("actual_date_to", sa.String(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("completed_at", sa.String(), nullable=True),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["backtest_strategies.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_backtest_runs_user_created",
        "backtest_runs",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_backtest_runs_strategy_id",
        "backtest_runs",
        ["strategy_id"],
    )
    op.create_index("idx_backtest_runs_status", "backtest_runs", ["status"])

    connection = op.get_bind()
    old_results = sa.table(
        "backtest_results",
        sa.column("id", sa.String()),
        sa.column("strategy_id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("date_from", sa.String()),
        sa.column("date_to", sa.String()),
        sa.column("result", sa.Text()),
        sa.column("created_at", sa.String()),
    )
    strategies = sa.table(
        "backtest_strategies",
        sa.column("id", sa.String()),
        sa.column("name", sa.String()),
        sa.column("config", sa.Text()),
    )
    new_runs = sa.table(
        "backtest_runs",
        sa.column("id", sa.String()),
        sa.column("strategy_id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("strategy_name", sa.String()),
        sa.column("strategy_config", sa.Text()),
        sa.column("run_kind", sa.String()),
        sa.column("analysis_config", sa.Text()),
        sa.column("status", sa.String()),
        sa.column("requested_date_from", sa.String()),
        sa.column("requested_date_to", sa.String()),
        sa.column("actual_date_from", sa.String()),
        sa.column("actual_date_to", sa.String()),
        sa.column("result", sa.Text()),
        sa.column("created_at", sa.String()),
        sa.column("started_at", sa.String()),
        sa.column("completed_at", sa.String()),
        sa.column("updated_at", sa.String()),
    )

    rows = connection.execute(
        sa.select(
            old_results.c.id,
            old_results.c.strategy_id,
            old_results.c.user_id,
            old_results.c.date_from,
            old_results.c.date_to,
            old_results.c.result,
            old_results.c.created_at,
            strategies.c.name,
            strategies.c.config,
        ).join(strategies, strategies.c.id == old_results.c.strategy_id)
    ).mappings()
    for row in rows:
        connection.execute(
            sa.insert(new_runs).values(
                id=row["id"],
                strategy_id=row["strategy_id"],
                user_id=row["user_id"],
                strategy_name=row["name"],
                strategy_config=row["config"],
                run_kind="standard",
                analysis_config=None,
                status="completed",
                requested_date_from=row["date_from"],
                requested_date_to=row["date_to"],
                actual_date_from=row["date_from"],
                actual_date_to=row["date_to"],
                result=row["result"],
                created_at=row["created_at"],
                started_at=row["created_at"],
                completed_at=row["created_at"],
                updated_at=row["created_at"],
            )
        )

    op.drop_table("backtest_results")


def downgrade() -> None:
    op.create_table(
        "backtest_results",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("strategy_id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("date_from", sa.String(), nullable=False),
        sa.Column("date_to", sa.String(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["strategy_id"],
            ["backtest_strategies.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_backtest_results_strategy_id",
        "backtest_results",
        ["strategy_id"],
    )

    connection = op.get_bind()
    runs = sa.table(
        "backtest_runs",
        sa.column("id", sa.String()),
        sa.column("strategy_id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("actual_date_from", sa.String()),
        sa.column("actual_date_to", sa.String()),
        sa.column("result", sa.Text()),
        sa.column("created_at", sa.String()),
        sa.column("status", sa.String()),
    )
    results = sa.table(
        "backtest_results",
        sa.column("id", sa.String()),
        sa.column("strategy_id", sa.String()),
        sa.column("user_id", sa.String()),
        sa.column("date_from", sa.String()),
        sa.column("date_to", sa.String()),
        sa.column("result", sa.Text()),
        sa.column("created_at", sa.String()),
    )
    rows = connection.execute(
        sa.select(runs).where(
            runs.c.status == "completed",
            runs.c.strategy_id.is_not(None),
            runs.c.result.is_not(None),
            runs.c.actual_date_from.is_not(None),
            runs.c.actual_date_to.is_not(None),
        )
    ).mappings()
    for row in rows:
        connection.execute(
            sa.insert(results).values(
                id=row["id"],
                strategy_id=row["strategy_id"],
                user_id=row["user_id"],
                date_from=row["actual_date_from"],
                date_to=row["actual_date_to"],
                result=row["result"],
                created_at=row["created_at"],
            )
        )

    op.drop_index("idx_backtest_runs_status", table_name="backtest_runs")
    op.drop_index("idx_backtest_runs_strategy_id", table_name="backtest_runs")
    op.drop_index("idx_backtest_runs_user_created", table_name="backtest_runs")
    op.drop_table("backtest_runs")
