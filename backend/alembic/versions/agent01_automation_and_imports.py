"""Automation tasks, findings, and staged trade imports.

Revision ID: agent01_automation_and_imports
Revises: billing01_stripe_subscriptions
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "agent01_automation_and_imports"
down_revision: Union[str, None] = "billing01_stripe_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "automation_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("task_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("schedule_kind", sa.String(), nullable=False),
        sa.Column("schedule_config", sa.JSON(), nullable=False),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("notification_config", sa.JSON(), nullable=False),
        sa.Column("next_run_at", sa.String(), nullable=False),
        sa.Column("last_run_at", sa.String(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("task_type IN ('risk_guardian','news_impact')", name="ck_automation_tasks_type"),
        sa.CheckConstraint("status IN ('active','paused','disabled')", name="ck_automation_tasks_status"),
        sa.CheckConstraint("schedule_kind IN ('interval','daily')", name="ck_automation_tasks_schedule_kind"),
    )
    op.create_index("idx_automation_tasks_due", "automation_tasks", ["status", "next_run_at"])
    op.create_index("idx_automation_tasks_user", "automation_tasks", ["user_id", "status"])

    op.create_table(
        "automation_runs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("task_id", sa.String(), sa.ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="queued"),
        sa.Column("scheduled_for", sa.String(), nullable=False),
        sa.Column("started_at", sa.String(), nullable=True),
        sa.Column("finished_at", sa.String(), nullable=True),
        sa.Column("lease_expires_at", sa.String(), nullable=True),
        sa.Column("input_as_of", sa.String(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("output", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.CheckConstraint("trigger_kind IN ('scheduled','manual')", name="ck_automation_runs_trigger"),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','partial','failed','skipped')",
            name="ck_automation_runs_status",
        ),
        sa.UniqueConstraint("task_id", "scheduled_for", name="uq_automation_runs_task_schedule"),
    )
    op.create_index("idx_automation_runs_task_created", "automation_runs", ["task_id", sa.text("created_at DESC")])
    op.create_index("idx_automation_runs_lease", "automation_runs", ["status", "lease_expires_at"])

    op.create_table(
        "agent_findings",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("task_id", sa.String(), sa.ForeignKey("automation_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.String(), sa.ForeignKey("automation_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("fingerprint", sa.String(), nullable=False),
        sa.Column("subject_type", sa.String(), nullable=False, server_default=""),
        sa.Column("subject_id", sa.String(), nullable=False, server_default=""),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("first_seen_at", sa.String(), nullable=False),
        sa.Column("last_seen_at", sa.String(), nullable=False),
        sa.Column("resolved_at", sa.String(), nullable=True),
        sa.Column("expires_at", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("finding_type IN ('risk','news','data_quality')", name="ck_agent_findings_type"),
        sa.CheckConstraint("severity IN ('info','warning','critical')", name="ck_agent_findings_severity"),
        sa.CheckConstraint(
            "status IN ('open','acknowledged','resolved','suppressed')",
            name="ck_agent_findings_status",
        ),
    )
    op.create_index(
        "idx_agent_findings_user_status",
        "agent_findings",
        ["user_id", "status", "severity", sa.text("last_seen_at DESC")],
    )
    op.create_index("idx_agent_findings_task", "agent_findings", ["task_id", "status"])
    op.create_index("idx_agent_findings_fingerprint", "agent_findings", ["user_id", "fingerprint"])

    op.create_table(
        "trade_import_batches",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(), sa.ForeignKey("uploaded_assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_kind", sa.String(), nullable=False),
        sa.Column("source_name", sa.String(), nullable=False, server_default=""),
        sa.Column("status", sa.String(), nullable=False, server_default="preparing"),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.Column("committed_at", sa.String(), nullable=True),
        sa.CheckConstraint("source_kind IN ('csv','json','xlsx','image')", name="ck_trade_import_batches_source"),
        sa.CheckConstraint(
            "status IN ('preparing','needs_review','ready','committing','committed','failed','cancelled')",
            name="ck_trade_import_batches_status",
        ),
    )
    op.create_index("idx_trade_import_batches_user", "trade_import_batches", ["user_id", sa.text("created_at DESC")])

    op.create_table(
        "trade_import_rows",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("batch_id", sa.String(), sa.ForeignKey("trade_import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("record_kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(), nullable=True),
        sa.Column("trade_id", sa.String(), sa.ForeignKey("trades.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.CheckConstraint("record_kind IN ('fill','trade')", name="ck_trade_import_rows_kind"),
        sa.CheckConstraint(
            "status IN ('valid','warning','invalid','duplicate','committed')",
            name="ck_trade_import_rows_status",
        ),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_trade_import_rows_batch_row"),
    )
    op.create_index("idx_trade_import_rows_batch", "trade_import_rows", ["batch_id", "status"])
    op.create_index("idx_trade_import_rows_fingerprint", "trade_import_rows", ["fingerprint"])


def downgrade() -> None:
    op.drop_index("idx_trade_import_rows_fingerprint", table_name="trade_import_rows")
    op.drop_index("idx_trade_import_rows_batch", table_name="trade_import_rows")
    op.drop_table("trade_import_rows")
    op.drop_index("idx_trade_import_batches_user", table_name="trade_import_batches")
    op.drop_table("trade_import_batches")
    op.drop_index("idx_agent_findings_fingerprint", table_name="agent_findings")
    op.drop_index("idx_agent_findings_task", table_name="agent_findings")
    op.drop_index("idx_agent_findings_user_status", table_name="agent_findings")
    op.drop_table("agent_findings")
    op.drop_index("idx_automation_runs_lease", table_name="automation_runs")
    op.drop_index("idx_automation_runs_task_created", table_name="automation_runs")
    op.drop_table("automation_runs")
    op.drop_index("idx_automation_tasks_user", table_name="automation_tasks")
    op.drop_index("idx_automation_tasks_due", table_name="automation_tasks")
    op.drop_table("automation_tasks")
