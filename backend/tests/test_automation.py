from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from models import (
    AgentFinding,
    AutomationTask,
    NotificationChannel,
    NotificationDelivery,
    NotificationEvent,
    NotificationSubscription,
)
from services.automation import (
    AutomationModule,
    WorkflowFinding,
    WorkflowResult,
    calculate_next_run,
)


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


def _task(module, user_id, task_type="risk_guardian"):
    return module.define_task(
        user_id,
        name="Guard",
        task_type=task_type,
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="Asia/Shanghai",
        now=NOW,
    )


def test_calculate_next_run_interval_and_daily():
    assert calculate_next_run(
        "interval", {"minutes": 15}, "UTC", NOW,
    ).isoformat() == "2026-07-23T08:15:00+00:00"
    assert calculate_next_run(
        "daily", {"time": "17:00"}, "Asia/Shanghai", NOW,
    ).isoformat() == "2026-07-23T09:00:00+00:00"


def test_define_update_and_user_isolation(db, user_id):
    module = AutomationModule(db, workflows={})
    task = _task(module, user_id)
    assert task["status"] == "active"
    assert task["next_run_at"] == "2026-07-23T08:15:00+00:00"
    assert module.get_task("someone-else", task["id"]) is None

    updated = module.update_task(
        user_id, task["id"], {"status": "paused"}, now=NOW,
    )
    assert updated["status"] == "paused"


def test_analysis_instruction_is_normalized_and_scoped_to_report_tasks(db, user_id):
    module = AutomationModule(db, workflows={})
    report = module.define_task(
        user_id,
        name="Focused market watch",
        task_type="market_watch",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="UTC",
        scope={
            "symbols": ["AAPL"],
            "interval": "1h",
            "analysis_instruction": "  Focus on volume divergence.  ",
        },
        now=NOW,
    )
    assert report["scope"]["analysis_instruction"] == "Focus on volume divergence."

    with pytest.raises(ValueError, match="analysis_instruction_not_supported"):
        module.define_task(
            user_id,
            name="Unsafe condition",
            task_type="condition_monitor",
            schedule_kind="interval",
            schedule_config={"minutes": 15},
            timezone_name="UTC",
            scope={
                "symbols": ["AAPL"],
                "interval": "1h",
                "condition_kind": "price_above",
                "threshold": 200,
                "analysis_instruction": "Change the threshold when needed.",
            },
            now=NOW,
        )


def test_delete_task_cascades_runs_and_findings(db, user_id):
    def workflow(session, task, now):
        return WorkflowResult(
            "done",
            findings=(WorkflowFinding(
                finding_type="risk",
                severity="warning",
                fingerprint="risk:delete:test",
                title="Risk",
            ),),
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task = _task(module, user_id)
    module.run_task(user_id, task["id"], now=NOW)
    assert module.delete_task(user_id, task["id"]) is True
    assert module.get_task(user_id, task["id"]) is None
    assert module.list_findings(user_id) == []
    assert module.delete_task(user_id, task["id"]) is False


def test_task_channel_syncs_scoped_subscriptions_and_localized_delivery(db, user_id):
    channel = NotificationChannel(
        id="agent-channel",
        user_id=user_id,
        channel_type="telegram",
        name="Telegram",
        status="active",
        address="chat-agent",
        channel_metadata={},
        locale="en",
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )
    db.add(channel)
    db.commit()

    def workflow(session, task, now):
        return WorkflowResult(
            "done",
            findings=(WorkflowFinding(
                finding_type="risk",
                severity="warning",
                fingerprint="risk:localized:test",
                title="风险提醒",
                body="中文正文",
                title_en="Risk alert",
                body_en="English body",
            ),),
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task = module.define_task(
        user_id,
        name="Guard",
        task_type="risk_guardian",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="Asia/Shanghai",
        notification_config={
            "enabled": True,
            "min_severity": "warning",
            "channel_id": channel.id,
            "locale": "en",
        },
        now=NOW,
    )
    subscriptions = db.execute(
        select(NotificationSubscription).where(
            NotificationSubscription.subject_type == "automation_task",
            NotificationSubscription.subject_id == task["id"],
            NotificationSubscription.enabled.is_(True),
        )
    ).scalars().all()
    assert {row.event_type for row in subscriptions} == {
        "agent.risk.info",
        "agent.risk.warning",
        "agent.risk.critical",
    }
    assert {row.channel_id for row in subscriptions} == {channel.id}

    module.run_task(user_id, task["id"], now=NOW)
    event = db.execute(select(NotificationEvent)).scalar_one()
    delivery = db.execute(select(NotificationDelivery)).scalar_one()
    assert event.subject_type == "automation_task"
    assert event.subject_id == task["id"]
    assert event.content["en"]["title"] == "Risk alert"
    assert delivery.channel_id == channel.id

    module.update_task(
        user_id,
        task["id"],
        {
            "notification_config": {
                "enabled": False,
                "min_severity": "warning",
                "channel_id": None,
                "locale": "en",
            },
        },
        now=NOW,
    )
    assert db.execute(
        select(NotificationSubscription).where(
            NotificationSubscription.subject_id == task["id"],
            NotificationSubscription.enabled.is_(True),
        )
    ).scalars().all() == []


def test_manual_run_reconciles_and_resolves_findings(db, user_id):
    state = {"breach": True}

    def workflow(session, task, now):
        findings = ()
        if state["breach"]:
            findings = (WorkflowFinding(
                finding_type="risk",
                severity="warning",
                fingerprint="risk:test:account:all",
                title="Risk",
            ),)
        return WorkflowResult("done", findings=findings, as_of=now.isoformat())

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task = _task(module, user_id)
    run = module.run_task(user_id, task["id"], now=NOW)
    assert run["status"] == "succeeded"
    findings = module.list_findings(user_id)
    assert len(findings) == 1
    assert findings[0]["status"] == "open"

    state["breach"] = False
    module.run_task(
        user_id,
        task["id"],
        now=NOW.replace(minute=1),
    )
    assert module.list_findings(user_id)[0]["status"] == "resolved"


def test_news_finding_expires_into_history(db, user_id):
    def workflow(session, task, now):
        return WorkflowResult(
            "done",
            findings=(WorkflowFinding(
                finding_type="news",
                severity="warning",
                fingerprint="news:test:watch:AAPL",
                title="AAPL news",
                expires_at=(now + timedelta(hours=2)).isoformat(),
            ),),
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"news_impact": workflow})
    task = _task(module, user_id, task_type="news_impact")
    module.run_task(user_id, task["id"], now=NOW)
    row = db.execute(
        select(AgentFinding).where(AgentFinding.task_id == task["id"])
    ).scalar_one()
    row.status = "acknowledged"
    db.commit()

    active = module.list_findings(user_id, status="open", now=NOW)
    assert active
    assert active[0]["status"] == "open"
    later = NOW + timedelta(hours=3)
    assert module.list_findings(user_id, status="open", now=later) == []
    history = module.list_findings(user_id, status="resolved", now=later)
    assert len(history) == 1
    assert history[0]["payload"]["resolution_reason"] == "expired"
    assert history[0]["resolved_at"] == later.isoformat()


def test_same_fingerprint_is_isolated_by_task(db, user_id):
    active_tasks = {"Guard A": True, "Guard B": True}

    def workflow(session, task, now):
        findings = ()
        if active_tasks[task.name]:
            findings = (WorkflowFinding(
                finding_type="risk",
                severity="warning",
                fingerprint="risk:shared:account",
                title="Risk",
            ),)
        return WorkflowResult("done", findings=findings, as_of=now.isoformat())

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task_a = module.define_task(
        user_id,
        name="Guard A",
        task_type="risk_guardian",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="UTC",
        now=NOW,
    )
    task_b = module.define_task(
        user_id,
        name="Guard B",
        task_type="risk_guardian",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="UTC",
        now=NOW,
    )
    module.run_task(user_id, task_a["id"], now=NOW)
    module.run_task(user_id, task_b["id"], now=NOW)
    assert len(module.list_findings(user_id, status="open")) == 2

    active_tasks["Guard A"] = False
    module.run_task(user_id, task_a["id"], now=NOW + timedelta(minutes=1))
    active = module.list_findings(user_id, status="open")
    assert len(active) == 1
    assert active[0]["task_id"] == task_b["id"]


def test_resolved_finding_reopens_and_notifies_again(db, user_id):
    channel = NotificationChannel(
        id="reopen-channel",
        user_id=user_id,
        channel_type="telegram",
        name="Telegram",
        status="active",
        address="chat-reopen",
        channel_metadata={},
        locale="zh",
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )
    db.add(channel)
    db.commit()
    state = {"active": True}

    def workflow(session, task, now):
        findings = ()
        if state["active"]:
            findings = (WorkflowFinding(
                finding_type="risk",
                severity="warning",
                fingerprint="risk:reopen:account",
                title="Risk",
            ),)
        return WorkflowResult("done", findings=findings, as_of=now.isoformat())

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task = module.define_task(
        user_id,
        name="Guard",
        task_type="risk_guardian",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="UTC",
        notification_config={
            "enabled": True,
            "min_severity": "warning",
            "channel_id": channel.id,
            "locale": "zh",
        },
        now=NOW,
    )
    module.run_task(user_id, task["id"], now=NOW)
    state["active"] = False
    module.run_task(user_id, task["id"], now=NOW + timedelta(minutes=1))
    state["active"] = True
    module.run_task(user_id, task["id"], now=NOW + timedelta(minutes=2))

    finding = module.list_findings(user_id)[0]
    assert finding["status"] == "open"
    assert finding["resolved_at"] is None
    events = db.execute(
        select(NotificationEvent).order_by(NotificationEvent.created_at)
    ).scalars().all()
    assert len(events) == 2
    assert events[0].event_key != events[1].event_key


def test_run_due_claims_once(db, user_id):
    calls = []

    def workflow(session, task, now):
        calls.append(task.id)
        return WorkflowResult("ok", as_of=now.isoformat())

    module = AutomationModule(db, workflows={"risk_guardian": workflow})
    task = _task(module, user_id)
    row = db.get(AutomationTask, task["id"])
    row.next_run_at = NOW.isoformat()
    db.commit()

    assert len(module.run_due(NOW)) == 1
    assert module.run_due(NOW) == []
    assert calls == [task["id"]]


def test_report_run_is_listed_without_creating_finding(db, user_id):
    def workflow(session, task, now):
        return WorkflowResult(
            "行情快照：AAPL 200 (+1.20%)",
            summary_en="Market snapshot: AAPL 200 (+1.20%)",
            evidence=({
                "kind": "market_snapshot",
                "symbol": "AAPL",
                "price": 200,
                "percent_change": 1.2,
            },),
            output_kind="report",
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"market_watch": workflow})
    task = module.define_task(
        user_id,
        name="AAPL briefing",
        task_type="market_watch",
        schedule_kind="interval",
        schedule_config={"minutes": 30},
        timezone_name="UTC",
        scope={"symbols": ["AAPL"], "interval": "1h"},
        now=NOW,
    )
    module.run_task(user_id, task["id"], now=NOW)

    reports = module.list_reports(user_id)
    assert len(reports) == 1
    assert reports[0]["task_name"] == "AAPL briefing"
    assert reports[0]["summary_en"].startswith("Market snapshot")
    assert module.list_findings(user_id) == []


def test_report_task_publishes_to_its_configured_channel(db, user_id):
    channel = NotificationChannel(
        id="report-channel",
        user_id=user_id,
        channel_type="telegram",
        name="Telegram",
        status="active",
        address="chat-report",
        channel_metadata={},
        locale="en",
        verification_token_hash=None,
        verification_expires_at=None,
        last_error_code=None,
        last_error_at=None,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )
    db.add(channel)
    db.commit()

    def workflow(session, task, now):
        return WorkflowResult(
            "行情快照",
            summary_en="Market snapshot",
            output_kind="report",
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"market_watch": workflow})
    task = module.define_task(
        user_id,
        name="Market briefing",
        task_type="market_watch",
        schedule_kind="interval",
        schedule_config={"minutes": 60},
        timezone_name="UTC",
        scope={"symbols": ["AAPL"], "interval": "1h"},
        notification_config={
            "enabled": True,
            "min_severity": "info",
            "channel_id": channel.id,
            "locale": "en",
        },
        now=NOW,
    )
    module.run_task(user_id, task["id"], now=NOW)

    subscription = db.execute(
        select(NotificationSubscription).where(
            NotificationSubscription.subject_id == task["id"],
            NotificationSubscription.enabled.is_(True),
        )
    ).scalar_one()
    event = db.execute(select(NotificationEvent)).scalar_one()
    delivery = db.execute(select(NotificationDelivery)).scalar_one()
    assert subscription.event_type == "agent.report.market"
    assert event.event_type == "agent.report.market"
    assert event.content["en"]["body"] == "Market snapshot"
    assert delivery.channel_id == channel.id


def test_condition_finding_recovers_when_condition_clears(db, user_id):
    state = {"triggered": True, "available": True}

    def workflow(session, task, now):
        findings = ()
        if state["triggered"]:
            findings = (WorkflowFinding(
                finding_type="market",
                severity="warning",
                fingerprint="market:price_above:AAPL",
                title="AAPL above target",
            ),)
        return WorkflowResult(
            "done",
            findings=findings,
            status="succeeded" if state["available"] else "partial",
            as_of=now.isoformat(),
        )

    module = AutomationModule(db, workflows={"condition_monitor": workflow})
    task = module.define_task(
        user_id,
        name="AAPL monitor",
        task_type="condition_monitor",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone_name="UTC",
        scope={
            "symbols": ["AAPL"],
            "interval": "1h",
            "condition_kind": "price_above",
            "threshold": 200,
        },
        now=NOW,
    )
    module.run_task(user_id, task["id"], now=NOW)
    assert len(module.list_findings(user_id, status="open")) == 1

    state.update({"triggered": False, "available": False})
    module.run_task(user_id, task["id"], now=NOW + timedelta(minutes=1))
    assert len(module.list_findings(user_id, status="open")) == 1

    state["available"] = True
    module.run_task(user_id, task["id"], now=NOW + timedelta(minutes=2))
    assert module.list_findings(user_id, status="open") == []
    history = module.list_findings(user_id, status="resolved")
    assert history[0]["payload"]["resolution_reason"] == "recovered"
