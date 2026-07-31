from datetime import datetime, timezone
from uuid import uuid4

from models import AutomationTask, FeedItem, TradePlan
from services.news_impact import run_news_impact


NOW = datetime(2026, 7, 23, 8, 0, tzinfo=timezone.utc)


def _task(user_id, symbols=None):
    return AutomationTask(
        id=str(uuid4()), user_id=user_id, name="News",
        task_type="news_impact", status="active",
        schedule_kind="interval", schedule_config={"minutes": 15},
        timezone="Asia/Shanghai", scope={"symbols": symbols or []},
        notification_config={}, next_run_at=NOW.isoformat(), last_run_at=None,
        consecutive_failures=0, created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
    )


def _feed(title, category="general", symbols=None):
    return FeedItem(
        id=str(uuid4()),
        url=f"https://news.test/{uuid4()}",
        source_key="test",
        title=title,
        summary="",
        published_at="2026-07-23T07:30:00+00:00",
        fetched_at="2026-07-23T07:31:00+00:00",
        category=category,
        symbols=symbols or [],
        lang="en",
    )


def test_exact_symbol_news_matches_watch_scope(db, user_id):
    item = _feed("AAPL announces results", symbols=["instrument:equity:aapl"])
    db.add(item)
    db.commit()

    result = run_news_impact(db, _task(user_id, ["AAPL"]), NOW)
    assert len(result.findings) == 1
    assert result.findings[0].payload["source_id"] == item.id


def test_macro_news_matches_sensitive_active_plan(db, user_id):
    task = _task(user_id)
    db.add_all([
        task,
        TradePlan(
            id=str(uuid4()), user_id=user_id, symbol="MNQ", market="futures",
            direction="long", entry_price=22000, target_price=22100,
            stop_loss=21950, account_size=10000, risk_percent=1,
            thesis="", status="active",
            created_at=NOW.isoformat(), updated_at=NOW.isoformat(),
        ),
        _feed("Federal Reserve rate decision", category="macro"),
    ])
    db.commit()

    result = run_news_impact(db, task, NOW)
    assert len(result.findings) == 1
    assert result.findings[0].subject_type == "plan"


def test_unrelated_news_produces_no_finding(db, user_id):
    db.add(_feed("Unrelated retail story"))
    db.commit()
    result = run_news_impact(db, _task(user_id, ["MNQ"]), NOW)
    assert result.findings == ()
