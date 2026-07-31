from datetime import datetime, timezone

from services.market_hours import get_market_hours, list_market_main_openings


def _market(payload, market_id):
    return next(item for item in payload["markets"] if item["id"] == market_id)


def test_nyse_uses_dst_and_reports_main_session():
    summer = get_market_hours(
        "Asia/Shanghai",
        at=datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc),
    )
    winter = get_market_hours(
        "Asia/Shanghai",
        at=datetime(2026, 1, 14, 15, 0, tzinfo=timezone.utc),
    )

    summer_nyse = _market(summer, "nyse")
    winter_nyse = _market(winter, "nyse")
    assert summer_nyse["state"] == "main"
    assert winter_nyse["state"] == "main"
    assert any(value["start_at"].endswith("13:30:00+00:00") for value in summer_nyse["sessions"])
    assert any(value["start_at"].endswith("14:30:00+00:00") for value in winter_nyse["sessions"])


def test_cross_midnight_futures_session_is_active():
    payload = get_market_hours(
        "America/Chicago",
        at=datetime(2026, 7, 15, 3, 0, tzinfo=timezone.utc),
    )

    assert _market(payload, "comex_gold")["state"] == "night"


def test_equities_are_closed_on_weekend():
    payload = get_market_hours(
        "America/New_York",
        at=datetime(2026, 7, 18, 16, 0, tzinfo=timezone.utc),
    )

    assert _market(payload, "nyse")["state"] == "closed"
    assert _market(payload, "lse")["state"] == "closed"


def test_invalid_timezone_is_rejected():
    try:
        get_market_hours("Mars/Olympus")
    except ValueError as exc:
        assert str(exc) == "invalid_timezone"
    else:
        raise AssertionError("invalid timezone should fail")


def test_market_notification_capability_requires_verified_calendar():
    payload = get_market_hours(
        "Asia/Shanghai",
        at=datetime(2026, 7, 15, 0, 0, tzinfo=timezone.utc),
    )

    assert "market.session.main_opened" in _market(payload, "nyse")["notification_capabilities"]
    assert _market(payload, "lse")["notification_capabilities"] == []


def test_main_opening_excludes_pre_market_and_afternoon_resume():
    nyse = list_market_main_openings(
        datetime(2026, 7, 15, 13, 29, tzinfo=timezone.utc),
        datetime(2026, 7, 15, 13, 31, tzinfo=timezone.utc),
    )
    sse_resume = list_market_main_openings(
        datetime(2026, 7, 15, 4, 59, tzinfo=timezone.utc),
        datetime(2026, 7, 15, 5, 1, tzinfo=timezone.utc),
    )

    assert {item.market_id for item in nyse} == {"nyse", "nasdaq"}
    assert all(item.starts_at.hour == 13 and item.starts_at.minute == 30 for item in nyse)
    assert not any(item.market_id in {"sse", "szse"} for item in sse_resume)


def test_verified_holiday_does_not_emit_opening():
    openings = list_market_main_openings(
        datetime(2026, 10, 1, 1, 25, tzinfo=timezone.utc),
        datetime(2026, 10, 1, 1, 35, tzinfo=timezone.utc),
    )

    assert not any(item.market_id in {"sse", "szse", "hkex"} for item in openings)
