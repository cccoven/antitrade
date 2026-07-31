from datetime import datetime, timezone

from models import AutomationTask, TradePlan
from services import market_agents
from services.automation_analysis import ReportAnalysis


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


def _task(task_type, scope):
    return AutomationTask(
        id=f"task-{task_type}",
        user_id="user-market-agent",
        name=task_type,
        task_type=task_type,
        status="active",
        schedule_kind="interval",
        schedule_config={"minutes": 15},
        timezone="Asia/Shanghai",
        scope=scope,
        notification_config={},
        next_run_at=NOW.isoformat(),
        last_run_at=None,
        consecutive_failures=0,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )


def _snapshot(symbol, price=100.0, change=1.25):
    return {
        "symbol": symbol,
        "provider": "test",
        "as_of": NOW.isoformat(),
        "quote": {
            "price": price,
            "percent_change": change,
            "high": price + 1,
            "low": price - 1,
            "volume": 1000,
        },
        "technicals": {"rsi14": 55},
    }


def test_market_watch_produces_report_without_findings(monkeypatch):
    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol),
    )

    result = market_agents.run_market_watch(
        None,
        _task("market_watch", {"symbols": ["MNQ", "AAPL"], "interval": "1h"}),
        NOW,
    )

    assert result.output_kind == "report"
    assert result.status == "succeeded"
    assert result.findings == ()
    assert result.metrics["available_count"] == 2
    assert "MNQ" in result.summary
    assert result.summary_en.startswith("Market snapshot:")


def test_market_watch_applies_bounded_analysis_without_changing_rule_data(monkeypatch):
    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol),
    )
    monkeypatch.setattr(
        market_agents,
        "generate_report_analysis",
        lambda **_kwargs: ReportAnalysis(
            summary="自定义分析摘要",
            summary_en="Custom analysis summary",
            model="test-model",
        ),
    )

    result = market_agents.run_market_watch(
        None,
        _task("market_watch", {
            "symbols": ["AAPL"],
            "interval": "1h",
            "analysis_instruction": "重点关注量价背离。",
        }),
        NOW,
    )

    assert result.summary == "自定义分析摘要"
    assert result.summary_en == "Custom analysis summary"
    assert result.metrics["available_count"] == 1
    assert result.evidence[0]["symbol"] == "AAPL"
    assert result.analysis == {
        "instruction": "重点关注量价背离。",
        "status": "applied",
        "model": "test-model",
    }


def test_condition_monitor_emits_triggered_market_finding(monkeypatch):
    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol, change=-2.5),
    )

    result = market_agents.run_condition_monitor(
        None,
        _task("condition_monitor", {
            "symbols": ["AAPL"],
            "interval": "1h",
            "condition_kind": "percent_change",
            "threshold": 1,
        }),
        NOW,
    )

    assert len(result.findings) == 1
    assert result.findings[0].finding_type == "market"
    assert result.findings[0].severity == "critical"
    assert result.findings[0].payload["current"] == 2.5


def test_session_report_includes_upcoming_events(monkeypatch):
    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol),
    )
    monkeypatch.setattr(
        market_agents,
        "get_economic_calendar",
        lambda: {
            "items": [{
                "title": "CPI",
                "currency": "USD",
                "impact": "high",
                "date": "2026-07-23T12:00:00+00:00",
            }],
        },
    )

    result = market_agents.run_session_report(
        None,
        _task("session_report", {"symbols": ["QQQ"], "interval": "1h"}),
        NOW,
    )

    assert result.output_kind == "report"
    assert result.metrics["upcoming_event_count"] == 1
    assert any(item["kind"] == "economic_event" for item in result.evidence)


def test_plan_guardian_tracks_entry_and_invalidation(db, user_id, monkeypatch):
    plan = TradePlan(
        id="plan-agent-test",
        user_id=user_id,
        symbol="AAPL",
        market="stock",
        direction="long",
        entry_price=100,
        target_price=110,
        stop_loss=95,
        account_size=10_000,
        risk_percent=1,
        thesis="test",
        strategy_id=None,
        status="active",
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )
    db.add(plan)
    db.flush()
    task = _task("plan_guardian", {"interval": "1h", "proximity_percent": 0.5})
    task.user_id = user_id
    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol, price=100.25),
    )

    near_entry = market_agents.run_plan_guardian(db, task, NOW)
    assert len(near_entry.findings) == 1
    assert near_entry.findings[0].fingerprint == f"plan:entry:{plan.id}"

    monkeypatch.setattr(
        market_agents,
        "get_market_snapshot",
        lambda _asset_class, symbol, _interval: _snapshot(symbol, price=94),
    )
    invalidated = market_agents.run_plan_guardian(db, task, NOW)
    assert len(invalidated.findings) == 1
    assert invalidated.findings[0].severity == "critical"
    assert invalidated.findings[0].fingerprint == f"plan:stop:{plan.id}"
