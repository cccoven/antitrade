"""Add market-watching Agent task and finding types.

Revision ID: agent02_market_agent_types
Revises: journal02_trade_position_status
"""

from typing import Sequence, Union

from alembic import op


revision: str = "agent02_market_agent_types"
down_revision: Union[str, None] = "journal02_trade_position_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "ck_automation_tasks_type",
        "automation_tasks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_automation_tasks_type",
        "automation_tasks",
        "task_type IN ("
        "'risk_guardian','news_impact','market_watch','condition_monitor',"
        "'session_report','plan_guardian'"
        ")",
    )
    op.drop_constraint(
        "ck_agent_findings_type",
        "agent_findings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_findings_type",
        "agent_findings",
        "finding_type IN ('risk','news','data_quality','market','plan')",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM agent_findings WHERE finding_type IN ('market','plan')"
    )
    op.execute(
        "DELETE FROM automation_tasks WHERE task_type IN ("
        "'market_watch','condition_monitor','session_report','plan_guardian'"
        ")"
    )
    op.drop_constraint(
        "ck_agent_findings_type",
        "agent_findings",
        type_="check",
    )
    op.create_check_constraint(
        "ck_agent_findings_type",
        "agent_findings",
        "finding_type IN ('risk','news','data_quality')",
    )
    op.drop_constraint(
        "ck_automation_tasks_type",
        "automation_tasks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_automation_tasks_type",
        "automation_tasks",
        "task_type IN ('risk_guardian','news_impact')",
    )
