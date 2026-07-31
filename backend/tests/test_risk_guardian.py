from datetime import datetime, timezone
from uuid import uuid4

from models import AutomationTask, JournalSettings, Trade, TradingRule
from services.risk_guardian import run_risk_guardian


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


def _task(user_id):
    return AutomationTask(
        id=str(uuid4()),
        user_id=user_id,
        name="Risk",
        task_type="risk_guardian",
        status="active",
        schedule_kind="daily",
        schedule_config={"time": "16:00"},
        timezone="Asia/Shanghai",
        scope={},
        notification_config={},
        next_run_at=NOW.isoformat(),
        last_run_at=None,
        consecutive_failures=0,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )


def _rule(user_id, rule_type, threshold, weight="critical"):
    return TradingRule(
        id=str(uuid4()),
        user_id=user_id,
        name=rule_type,
        rule_type=rule_type,
        threshold=threshold,
        weight=weight,
        active=1,
        created_at=NOW.isoformat(),
        updated_at=NOW.isoformat(),
    )


def test_daily_loss_and_missing_stop_findings(db, user_id):
    db.add(JournalSettings(
        user_id=user_id,
        starting_capital=10_000,
        currency_code="USD",
        updated_at=NOW.isoformat(),
    ))
    db.add_all([
        _rule(user_id, "max_daily_realized_loss_percent", 1),
        _rule(user_id, "require_stop_loss", None, "important"),
        Trade(
            id=str(uuid4()), user_id=user_id, symbol="AAPL", direction="long",
            open_price=200, close_price=198, quantity=10,
            open_time="2026-07-23T01:00:00+00:00",
            close_time="2026-07-23T02:00:00+00:00",
            fees=0, pnl=-200, tags="[]", notes="", source="manual",
            mistakes="[]", created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        ),
        Trade(
            id=str(uuid4()), user_id=user_id, symbol="MNQ", direction="long",
            open_price=22000, close_price=None, quantity=1,
            open_time="2026-07-23T03:00:00+00:00", close_time=None,
            fees=0, pnl=None, tags="[]", notes="", source="manual",
            stop_loss=None, mistakes="[]",
            created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        ),
    ])
    db.commit()

    result = run_risk_guardian(db, _task(user_id), NOW)
    fingerprints = {item.fingerprint for item in result.findings}
    assert "risk:max_daily_realized_loss_percent:account:all" in fingerprints
    assert any(item.subject_type == "trade" for item in result.findings)
    assert result.metrics["daily_realized_pnl"] == -200


def test_missing_starting_capital_is_not_treated_as_zero(db, user_id):
    result = run_risk_guardian(db, _task(user_id), NOW)
    assert any(
        item.fingerprint == "risk:data_quality:starting_capital"
        for item in result.findings
    )
