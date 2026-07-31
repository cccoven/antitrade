"""Durable automation tasks, runs, findings, and notification publication."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models import AgentFinding, AutomationRun, AutomationTask
from services.automation_analysis import normalize_analysis_instruction
from services.notifications import (
    NotificationContent,
    NotificationEventInput,
    NotificationService,
    parse_utc,
    utc_iso,
    utc_now,
)

UTC = timezone.utc
SUPPORTED_TASK_TYPES = {
    "risk_guardian",
    "news_impact",
    "market_watch",
    "condition_monitor",
    "session_report",
    "plan_guardian",
}
REPORT_TASK_TYPES = {"market_watch", "session_report"}
STATEFUL_FINDING_TASK_TYPES = {
    "risk_guardian",
    "condition_monitor",
    "plan_guardian",
}
SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}
TASK_NOTIFICATION_EVENTS = {
    "risk_guardian": {
        "agent.risk.info",
        "agent.risk.warning",
        "agent.risk.critical",
    },
    "news_impact": {"agent.news.material"},
    "condition_monitor": {
        "agent.market.info",
        "agent.market.warning",
        "agent.market.critical",
    },
    "plan_guardian": {
        "agent.plan.info",
        "agent.plan.warning",
        "agent.plan.critical",
    },
    "market_watch": {"agent.report.market"},
    "session_report": {"agent.report.session"},
}


@dataclass(frozen=True)
class WorkflowFinding:
    finding_type: str
    severity: str
    fingerprint: str
    title: str
    body: str = ""
    title_en: str = ""
    body_en: str = ""
    subject_type: str = ""
    subject_id: str = ""
    evidence: tuple[dict[str, Any], ...] = ()
    payload: dict[str, Any] = field(default_factory=dict)
    expires_at: str | None = None


@dataclass(frozen=True)
class WorkflowResult:
    summary: str
    summary_en: str = ""
    findings: tuple[WorkflowFinding, ...] = ()
    evidence: tuple[dict[str, Any], ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    as_of: str | None = None
    status: str = "succeeded"
    output_kind: str = "finding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "summary_en": self.summary_en,
            "status": self.status,
            "output_kind": self.output_kind,
            "findings": [asdict(item) for item in self.findings],
            "evidence": list(self.evidence),
            "metrics": self.metrics,
            "analysis": self.analysis,
            "as_of": self.as_of,
        }


Workflow = Callable[[Session, AutomationTask, datetime], WorkflowResult]


def _task_dict(row: AutomationTask) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "task_type": row.task_type,
        "status": row.status,
        "schedule_kind": row.schedule_kind,
        "schedule_config": row.schedule_config or {},
        "timezone": row.timezone,
        "scope": row.scope or {},
        "notification_config": row.notification_config or {},
        "next_run_at": row.next_run_at,
        "last_run_at": row.last_run_at,
        "consecutive_failures": row.consecutive_failures,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _run_dict(row: AutomationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "trigger_kind": row.trigger_kind,
        "status": row.status,
        "scheduled_for": row.scheduled_for,
        "started_at": row.started_at,
        "finished_at": row.finished_at,
        "input_as_of": row.input_as_of,
        "summary": row.summary,
        "output": row.output or {},
        "error_code": row.error_code,
        "created_at": row.created_at,
    }


def _finding_dict(row: AgentFinding) -> dict[str, Any]:
    return {
        "id": row.id,
        "task_id": row.task_id,
        "run_id": row.run_id,
        "finding_type": row.finding_type,
        "severity": row.severity,
        "status": row.status,
        "fingerprint": row.fingerprint,
        "subject_type": row.subject_type or None,
        "subject_id": row.subject_id or None,
        "title": row.title,
        "body": row.body,
        "evidence": row.evidence or [],
        "payload": row.payload or {},
        "first_seen_at": row.first_seen_at,
        "last_seen_at": row.last_seen_at,
        "resolved_at": row.resolved_at,
        "expires_at": row.expires_at,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _report_dict(run: AutomationRun, task: AutomationTask) -> dict[str, Any]:
    output = run.output or {}
    return {
        "id": run.id,
        "task_id": task.id,
        "task_name": task.name,
        "task_type": task.task_type,
        "status": run.status,
        "summary": run.summary,
        "summary_en": str(output.get("summary_en") or ""),
        "output": output,
        "as_of": run.input_as_of,
        "finished_at": run.finished_at,
        "created_at": run.created_at,
    }


def _parse_clock(value: str) -> time:
    try:
        hour_text, minute_text = value.split(":", 1)
        return time(hour=int(hour_text), minute=int(minute_text))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError("invalid_daily_time") from exc


def validate_schedule(kind: str, config: dict[str, Any], timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("invalid_timezone") from exc
    if kind == "interval":
        try:
            minutes = int(config.get("minutes"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_interval") from exc
        if minutes < 15 or minutes > 10080:
            raise ValueError("invalid_interval")
        return
    if kind == "daily":
        _parse_clock(str(config.get("time") or ""))
        return
    raise ValueError("invalid_schedule_kind")


def validate_task_scope(task_type: str, scope: dict[str, Any] | None) -> None:
    values = scope or {}
    if "analysis_instruction" in values:
        values["analysis_instruction"] = normalize_analysis_instruction(
            task_type,
            values.get("analysis_instruction"),
        )
    symbols = values.get("symbols", [])
    if not isinstance(symbols, list) or len(symbols) > 20:
        raise ValueError("invalid_task_symbols")
    if task_type in {"market_watch", "condition_monitor"} and not any(
        str(symbol).strip() for symbol in symbols
    ):
        raise ValueError("missing_task_symbols")
    interval = str(values.get("interval") or "1h")
    if interval not in {"5min", "15min", "1h", "4h", "1day"}:
        raise ValueError("invalid_market_interval")
    if task_type == "condition_monitor":
        if str(values.get("condition_kind") or "") not in {
            "percent_change", "price_above", "price_below",
        }:
            raise ValueError("invalid_monitor_condition")
        try:
            threshold = float(values.get("threshold"))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_monitor_threshold") from exc
        if threshold <= 0:
            raise ValueError("invalid_monitor_threshold")
    if task_type == "plan_guardian":
        try:
            proximity = float(values.get("proximity_percent", 0.5))
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_plan_proximity") from exc
        if proximity <= 0 or proximity > 10:
            raise ValueError("invalid_plan_proximity")


def calculate_next_run(
    kind: str,
    config: dict[str, Any],
    timezone_name: str,
    now: datetime,
) -> datetime:
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    current = current.astimezone(UTC)
    validate_schedule(kind, config, timezone_name)
    if kind == "interval":
        return current + timedelta(minutes=int(config["minutes"]))

    zone = ZoneInfo(timezone_name)
    local_now = current.astimezone(zone)
    clock = _parse_clock(str(config["time"]))
    candidate = datetime.combine(local_now.date(), clock, tzinfo=zone)
    if candidate <= local_now:
        candidate += timedelta(days=1)
    return candidate.astimezone(UTC)


class AutomationModule:
    def __init__(
        self,
        session: Session,
        *,
        workflows: dict[str, Workflow] | None = None,
    ):
        self.session = session
        self._workflows = workflows or self._default_workflows()

    @staticmethod
    def _default_workflows() -> dict[str, Workflow]:
        from services.market_agents import (
            run_condition_monitor,
            run_market_watch,
            run_plan_guardian,
            run_session_report,
        )
        from services.news_impact import run_news_impact
        from services.risk_guardian import run_risk_guardian

        return {
            "risk_guardian": run_risk_guardian,
            "news_impact": run_news_impact,
            "market_watch": run_market_watch,
            "condition_monitor": run_condition_monitor,
            "session_report": run_session_report,
            "plan_guardian": run_plan_guardian,
        }

    def define_task(
        self,
        user_id: str,
        *,
        name: str,
        task_type: str,
        schedule_kind: str,
        schedule_config: dict[str, Any],
        timezone_name: str,
        scope: dict[str, Any] | None = None,
        notification_config: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError("unsupported_task_type")
        if not name.strip():
            raise ValueError("missing_task_name")
        validate_task_scope(task_type, scope)
        current = now or utc_now()
        next_run = calculate_next_run(
            schedule_kind, schedule_config, timezone_name, current,
        )
        stamp = utc_iso(current)
        row = AutomationTask(
            id=str(uuid4()),
            user_id=user_id,
            name=name.strip()[:160],
            task_type=task_type,
            status="active",
            schedule_kind=schedule_kind,
            schedule_config=schedule_config,
            timezone=timezone_name,
            scope=scope or {},
            notification_config=self._normalize_notification_config(
                user_id, notification_config,
            ),
            next_run_at=utc_iso(next_run),
            last_run_at=None,
            consecutive_failures=0,
            created_at=stamp,
            updated_at=stamp,
        )
        self.session.add(row)
        self.session.commit()
        self._sync_task_notifications(row)
        return _task_dict(row)

    def list_tasks(self, user_id: str) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(AutomationTask)
            .where(AutomationTask.user_id == user_id)
            .order_by(AutomationTask.created_at.desc())
        ).scalars().all()
        return [_task_dict(row) for row in rows]

    def get_task(self, user_id: str, task_id: str) -> dict[str, Any] | None:
        row = self._get_task_row(user_id, task_id)
        return _task_dict(row) if row else None

    def update_task(
        self,
        user_id: str,
        task_id: str,
        updates: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        row = self._get_task_row(user_id, task_id)
        if row is None:
            return None
        allowed = {
            "name", "status", "schedule_kind", "schedule_config", "timezone",
            "scope", "notification_config",
        }
        values = {key: value for key, value in updates.items() if key in allowed}
        status = values.get("status", row.status)
        if status not in {"active", "paused", "disabled"}:
            raise ValueError("invalid_task_status")
        name = str(values.get("name", row.name)).strip()
        if not name:
            raise ValueError("missing_task_name")
        schedule_kind = str(values.get("schedule_kind", row.schedule_kind))
        schedule_config = values.get("schedule_config", row.schedule_config)
        timezone_name = str(values.get("timezone", row.timezone))
        validate_schedule(schedule_kind, schedule_config, timezone_name)
        validate_task_scope(
            row.task_type,
            values.get("scope", row.scope),
        )

        row.name = name[:160]
        row.status = status
        row.schedule_kind = schedule_kind
        row.schedule_config = schedule_config
        row.timezone = timezone_name
        if "scope" in values:
            row.scope = values["scope"] or {}
        if "notification_config" in values:
            row.notification_config = self._normalize_notification_config(
                user_id, values["notification_config"],
            )
        current = now or utc_now()
        if status == "active" and any(
            key in values for key in ("status", "schedule_kind", "schedule_config", "timezone")
        ):
            row.next_run_at = utc_iso(
                calculate_next_run(schedule_kind, schedule_config, timezone_name, current)
            )
            row.consecutive_failures = 0
        row.updated_at = utc_iso(current)
        self.session.commit()
        if "notification_config" in values:
            self._sync_task_notifications(row)
        return _task_dict(row)

    def delete_task(self, user_id: str, task_id: str) -> bool:
        row = self._get_task_row(user_id, task_id)
        if row is None:
            return False
        active_run = self.session.execute(
            select(AutomationRun.id).where(
                AutomationRun.task_id == task_id,
                AutomationRun.status.in_(("queued", "running")),
            )
        ).scalar_one_or_none()
        if active_run:
            raise ValueError("task_already_running")
        NotificationService(self.session).sync_subject_subscriptions(
            user_id=user_id,
            subject_type="automation_task",
            subject_id=task_id,
            channel_id=None,
            event_types=set(),
            locale="zh",
        )
        self.session.delete(row)
        self.session.commit()
        return True

    def list_runs(
        self, user_id: str, task_id: str, *, limit: int = 20,
    ) -> list[dict[str, Any]] | None:
        if self._get_task_row(user_id, task_id) is None:
            return None
        rows = self.session.execute(
            select(AutomationRun)
            .where(
                AutomationRun.user_id == user_id,
                AutomationRun.task_id == task_id,
            )
            .order_by(AutomationRun.created_at.desc())
            .limit(max(1, min(limit, 100)))
        ).scalars().all()
        return [_run_dict(row) for row in rows]

    def list_findings(
        self,
        user_id: str,
        *,
        status: str | None = None,
        severity: str | None = None,
        finding_type: str | None = None,
        limit: int = 50,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        self._resolve_expired_findings(user_id=user_id, now=now)
        conditions = [AgentFinding.user_id == user_id]
        if status:
            conditions.append(AgentFinding.status == status)
        if severity:
            conditions.append(AgentFinding.severity == severity)
        if finding_type:
            conditions.append(AgentFinding.finding_type == finding_type)
        rows = self.session.execute(
            select(AgentFinding)
            .where(*conditions)
            .order_by(AgentFinding.last_seen_at.desc())
            .limit(max(1, min(limit, 200)))
        ).scalars().all()
        return [_finding_dict(row) for row in rows]

    def list_reports(
        self,
        user_id: str,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        rows = self.session.execute(
            select(AutomationRun, AutomationTask)
            .join(AutomationTask, AutomationTask.id == AutomationRun.task_id)
            .where(
                AutomationRun.user_id == user_id,
                AutomationTask.task_type.in_(REPORT_TASK_TYPES),
                AutomationRun.status.in_(("succeeded", "partial")),
            )
            .order_by(AutomationRun.finished_at.desc().nullslast())
            .limit(max(1, min(limit, 100)))
        ).all()
        return [_report_dict(run, task) for run, task in rows]

    def run_due(
        self, now: datetime | None = None, *, limit: int = 50,
    ) -> list[dict[str, Any]]:
        current = now or utc_now()
        self._resolve_expired_findings(now=current)
        due = self.session.execute(
            select(AutomationTask)
            .where(
                AutomationTask.status == "active",
                AutomationTask.next_run_at <= utc_iso(current),
            )
            .order_by(AutomationTask.next_run_at)
            .limit(max(1, min(limit, 100)))
            .with_for_update(skip_locked=True)
        ).scalars().all()
        run_ids: list[str] = []
        for task in due:
            scheduled_for = task.next_run_at
            run = AutomationRun(
                id=str(uuid4()),
                task_id=task.id,
                user_id=task.user_id,
                trigger_kind="scheduled",
                status="queued",
                scheduled_for=scheduled_for,
                started_at=None,
                finished_at=None,
                lease_expires_at=None,
                input_as_of=None,
                summary="",
                output={},
                error_code=None,
                created_at=utc_iso(current),
            )
            self.session.add(run)
            task.next_run_at = utc_iso(calculate_next_run(
                task.schedule_kind,
                task.schedule_config or {},
                task.timezone,
                max(current, parse_utc(scheduled_for) or current),
            ))
            task.updated_at = utc_iso(current)
            try:
                self.session.flush()
            except IntegrityError:
                self.session.rollback()
                continue
            run_ids.append(run.id)
        self.session.commit()
        return [self._execute_run(run_id, current) for run_id in run_ids]

    def run_task(
        self,
        user_id: str,
        task_id: str,
        *,
        trigger: str = "manual",
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        task = self._get_task_row(user_id, task_id)
        if task is None:
            return None
        current = now or utc_now()
        self._resolve_expired_findings(user_id=user_id, now=current)
        active_run = self.session.execute(
            select(AutomationRun.id).where(
                AutomationRun.task_id == task_id,
                AutomationRun.status.in_(("queued", "running")),
            )
        ).scalar_one_or_none()
        if active_run:
            raise ValueError("task_already_running")
        run = AutomationRun(
            id=str(uuid4()),
            task_id=task.id,
            user_id=user_id,
            trigger_kind=trigger,
            status="queued",
            scheduled_for=utc_iso(current),
            started_at=None,
            finished_at=None,
            lease_expires_at=None,
            input_as_of=None,
            summary="",
            output={},
            error_code=None,
            created_at=utc_iso(current),
        )
        self.session.add(run)
        self.session.commit()
        return self._execute_run(run.id, current)

    def _execute_run(self, run_id: str, current: datetime) -> dict[str, Any]:
        run = self.session.get(AutomationRun, run_id)
        if run is None:
            raise ValueError("automation_run_not_found")
        task = self.session.get(AutomationTask, run.task_id)
        if task is None:
            raise ValueError("automation_task_not_found")
        run.status = "running"
        run.started_at = utc_iso(current)
        run.lease_expires_at = utc_iso(current + timedelta(minutes=5))
        self.session.commit()

        workflow = self._workflows.get(task.task_type)
        if workflow is None:
            return self._fail_run(run, task, "workflow_unavailable", current)
        try:
            result = workflow(self.session, task, current)
            if result.status not in {"succeeded", "partial", "skipped"}:
                raise ValueError("invalid_workflow_status")
            run.status = result.status
            run.summary = result.summary
            run.output = result.to_dict()
            run.input_as_of = result.as_of or utc_iso(current)
            run.finished_at = utc_iso()
            run.lease_expires_at = None
            run.error_code = None
            task.last_run_at = run.finished_at
            task.consecutive_failures = 0
            task.updated_at = run.finished_at
            self.session.commit()
            changed = self._reconcile_findings(task, run, result.findings)
            self._publish_changed_findings(task, changed, current)
            self._publish_report(task, run, result, current)
            return _run_dict(run)
        except Exception as exc:
            self.session.rollback()
            error_code = str(exc) if isinstance(exc, ValueError) else "workflow_failed"
            return self._fail_run(run, task, error_code[:120], current)

    def _fail_run(
        self,
        run: AutomationRun,
        task: AutomationTask,
        error_code: str,
        current: datetime,
    ) -> dict[str, Any]:
        run = self.session.get(AutomationRun, run.id) or run
        task = self.session.get(AutomationTask, task.id) or task
        run.status = "failed"
        run.finished_at = utc_iso()
        run.lease_expires_at = None
        run.error_code = error_code
        run.summary = ""
        task.last_run_at = run.finished_at
        task.consecutive_failures += 1
        if task.consecutive_failures >= 3:
            task.status = "disabled"
        task.updated_at = run.finished_at
        self.session.commit()
        return _run_dict(run)

    def _reconcile_findings(
        self,
        task: AutomationTask,
        run: AutomationRun,
        findings: tuple[WorkflowFinding, ...],
    ) -> list[tuple[AgentFinding, bool, WorkflowFinding]]:
        now_value = run.finished_at or utc_iso()
        current_fingerprints = {item.fingerprint for item in findings}
        changed: list[tuple[AgentFinding, bool, WorkflowFinding]] = []
        for item in findings:
            if item.severity not in SEVERITY_RANK:
                continue
            existing = self.session.execute(
                select(AgentFinding)
                .where(
                    AgentFinding.user_id == task.user_id,
                    AgentFinding.task_id == task.id,
                    AgentFinding.fingerprint == item.fingerprint,
                )
                .order_by(AgentFinding.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None and existing.status == "suppressed":
                continue
            created_or_escalated = existing is None
            if existing is None:
                existing = AgentFinding(
                    id=str(uuid4()),
                    user_id=task.user_id,
                    task_id=task.id,
                    run_id=run.id,
                    finding_type=item.finding_type,
                    severity=item.severity,
                    status="open",
                    fingerprint=item.fingerprint,
                    subject_type=item.subject_type,
                    subject_id=item.subject_id,
                    title=item.title,
                    body=item.body,
                    evidence=list(item.evidence),
                    payload=item.payload,
                    first_seen_at=now_value,
                    last_seen_at=now_value,
                    resolved_at=None,
                    expires_at=item.expires_at,
                    created_at=now_value,
                    updated_at=now_value,
                )
                self.session.add(existing)
            else:
                was_closed = existing.status in ("acknowledged", "resolved")
                created_or_escalated = (
                    SEVERITY_RANK[item.severity] > SEVERITY_RANK.get(existing.severity, -1)
                    or was_closed
                )
                existing.run_id = run.id
                existing.task_id = task.id
                existing.finding_type = item.finding_type
                existing.severity = item.severity
                existing.status = "open" if was_closed else existing.status
                existing.subject_type = item.subject_type
                existing.subject_id = item.subject_id
                existing.title = item.title
                existing.body = item.body
                existing.evidence = list(item.evidence)
                existing.payload = item.payload
                existing.last_seen_at = now_value
                existing.resolved_at = None
                existing.expires_at = item.expires_at
                existing.updated_at = now_value
            changed.append((existing, created_or_escalated, item))

        if (
            task.task_type in STATEFUL_FINDING_TASK_TYPES
            and run.status == "succeeded"
        ):
            active = self.session.execute(
                select(AgentFinding).where(
                    AgentFinding.task_id == task.id,
                    AgentFinding.status.in_(("open", "acknowledged")),
                )
            ).scalars().all()
            for existing in active:
                if existing.fingerprint not in current_fingerprints:
                    existing.status = "resolved"
                    existing.resolved_at = now_value
                    existing.payload = {
                        **(existing.payload or {}),
                        "resolution_reason": "recovered",
                    }
                    existing.updated_at = now_value
        self.session.commit()
        return changed

    def _publish_changed_findings(
        self,
        task: AutomationTask,
        changed: list[tuple[AgentFinding, bool, WorkflowFinding]],
        current: datetime,
    ) -> None:
        config = task.notification_config or {}
        if config.get("enabled", True) is False:
            return
        minimum = str(config.get("min_severity") or "warning")
        minimum_rank = SEVERITY_RANK.get(minimum, 1)
        notifications = NotificationService(self.session)
        for finding, should_publish, source in changed:
            if not should_publish or SEVERITY_RANK.get(finding.severity, 0) < minimum_rank:
                continue
            if finding.finding_type in {"risk", "data_quality"}:
                event_type = f"agent.risk.{finding.severity}"
            elif finding.finding_type == "market":
                event_type = f"agent.market.{finding.severity}"
            elif finding.finding_type == "plan":
                event_type = f"agent.plan.{finding.severity}"
            else:
                event_type = "agent.news.material"
            notifications.publish(NotificationEventInput(
                event_key=(
                    f"{event_type}:{task.id}:{finding.fingerprint}:"
                    f"{finding.severity}:{finding.run_id}"
                ),
                event_type=event_type,
                source="automation",
                subject_type="automation_task",
                subject_id=task.id,
                occurred_at=current,
                expires_at=current + timedelta(hours=24),
                content={
                    "zh": NotificationContent(
                        finding.title,
                        finding.body,
                        f"/automations?finding={finding.id}",
                    ),
                    "en": NotificationContent(
                        source.title_en or finding.title,
                        source.body_en or finding.body,
                        f"/automations?finding={finding.id}",
                    ),
                },
                data={"finding_id": finding.id, "task_id": task.id},
            ))

    def _publish_report(
        self,
        task: AutomationTask,
        run: AutomationRun,
        result: WorkflowResult,
        current: datetime,
    ) -> None:
        if result.output_kind != "report":
            return
        config = task.notification_config or {}
        if config.get("enabled", True) is False:
            return
        event_type = (
            "agent.report.session"
            if task.task_type == "session_report"
            else "agent.report.market"
        )
        NotificationService(self.session).publish(NotificationEventInput(
            event_key=f"{event_type}:{task.id}:{run.id}",
            event_type=event_type,
            source="automation",
            subject_type="automation_task",
            subject_id=task.id,
            occurred_at=current,
            expires_at=current + timedelta(hours=24),
            content={
                "zh": NotificationContent(
                    task.name,
                    result.summary,
                    f"/automations?tab=reports&report={run.id}",
                ),
                "en": NotificationContent(
                    task.name,
                    result.summary_en or result.summary,
                    f"/automations?tab=reports&report={run.id}",
                ),
            },
            data={"report_id": run.id, "task_id": task.id},
        ))

    def _resolve_expired_findings(
        self,
        *,
        user_id: str | None = None,
        now: datetime | None = None,
    ) -> int:
        current = now or utc_now()
        conditions = [
            AgentFinding.status.in_(("open", "acknowledged")),
        ]
        if user_id is not None:
            conditions.append(AgentFinding.user_id == user_id)
        rows = self.session.execute(
            select(AgentFinding).where(*conditions)
        ).scalars().all()
        transitioned = 0
        resolved_at = utc_iso(current)
        for row in rows:
            changed = False
            if row.status == "acknowledged":
                row.status = "open"
                row.resolved_at = None
                row.updated_at = resolved_at
                changed = True
            expires_at = parse_utc(row.expires_at)
            if expires_at is not None and expires_at <= current:
                row.status = "resolved"
                row.resolved_at = resolved_at
                row.updated_at = resolved_at
                row.payload = {
                    **(row.payload or {}),
                    "resolution_reason": "expired",
                }
                changed = True
            if changed:
                transitioned += 1
        if transitioned:
            self.session.commit()
        return transitioned

    def _normalize_notification_config(
        self,
        user_id: str,
        config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        raw = config or {}
        minimum = str(raw.get("min_severity") or "warning")
        if minimum not in SEVERITY_RANK:
            raise ValueError("invalid_notification_severity")
        channel_id = str(raw.get("channel_id") or "").strip() or None
        enabled = bool(raw.get("enabled", bool(channel_id))) and channel_id is not None
        channel = None
        if channel_id:
            channel = NotificationService(self.session).get_channel(user_id, channel_id)
            if channel is None or channel.status != "active":
                raise ValueError("notification_channel_unavailable")
        locale = str(raw.get("locale") or (channel.locale if channel else "zh"))
        if locale not in {"zh", "en"}:
            raise ValueError("invalid_notification_locale")
        return {
            "enabled": enabled,
            "min_severity": minimum,
            "channel_id": channel_id,
            "locale": locale,
        }

    def _sync_task_notifications(self, task: AutomationTask) -> None:
        config = task.notification_config or {}
        channel_id = config.get("channel_id") if config.get("enabled") else None
        event_types = TASK_NOTIFICATION_EVENTS.get(task.task_type, set())
        NotificationService(self.session).sync_subject_subscriptions(
            user_id=task.user_id,
            subject_type="automation_task",
            subject_id=task.id,
            channel_id=channel_id,
            event_types=event_types if channel_id else set(),
            locale=str(config.get("locale") or "zh"),
        )

    def _get_task_row(self, user_id: str, task_id: str) -> AutomationTask | None:
        return self.session.execute(
            select(AutomationTask).where(
                AutomationTask.id == task_id,
                AutomationTask.user_id == user_id,
            )
        ).scalar_one_or_none()
