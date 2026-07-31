"""Deterministic global market-session timeline calculations."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
UTC = timezone.utc
logger = logging.getLogger(__name__)
MAIN_OPEN_NOTIFICATION_MARKETS = {"nyse", "nasdaq", "sse", "szse", "hkex", "tse"}


@lru_cache(maxsize=1)
def _schedule() -> dict[str, Any]:
    return json.loads((DATA_DIR / "market_hours.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=8)
def _overrides(year: int) -> dict[str, Any]:
    path = DATA_DIR / f"market_hours_overrides_{year}.json"
    if not path.exists():
        return {"version": str(year), "verified_markets": [], "closed_dates": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def _closed_dates(year: int) -> dict[str, set[str]]:
    payload = _overrides(year)
    return {
        market_id: set(values)
        for market_id, values in payload.get("closed_dates", {}).items()
    }


def market_calendar_verified(market_id: str, year: int) -> bool:
    return market_id in set(_overrides(year).get("verified_markets", []))


def missing_notification_calendar_years(at: datetime | None = None) -> list[int]:
    now = (at or datetime.now(UTC)).astimezone(UTC)
    years = (now.year, now.year + 1)
    return [
        year for year in years
        if not MAIN_OPEN_NOTIFICATION_MARKETS.issubset(
            set(_overrides(year).get("verified_markets", []))
        )
    ]


def _clock(day: date, value: str, zone: ZoneInfo) -> datetime:
    hour, minute = (int(part) for part in value.split(":"))
    if hour == 24:
        return datetime.combine(day + timedelta(days=1), time.min, tzinfo=zone)
    return datetime.combine(day, time(hour, minute), tzinfo=zone)


def _session_range(day: date, session: dict[str, Any], zone: ZoneInfo) -> tuple[datetime, datetime]:
    start = _clock(day, session["start"], zone)
    end = _clock(day, session["end"], zone)
    if end <= start:
        end += timedelta(days=1)
    return start.astimezone(UTC), end.astimezone(UTC)


def _ranges(
    item: dict[str, Any],
    window_start: datetime,
    window_end: datetime,
) -> list[dict[str, Any]]:
    zone = ZoneInfo(item["timezone"])
    first_day = window_start.astimezone(zone).date() - timedelta(days=1)
    last_day = window_end.astimezone(zone).date() + timedelta(days=1)
    ranges: list[dict[str, Any]] = []

    day = first_day
    while day <= last_day:
        closures = _closed_dates(day.year).get(item["id"], set())
        if day.isoformat() not in closures:
            for session in item["sessions"]:
                if day.weekday() not in session["weekdays"]:
                    continue
                start, end = _session_range(day, session, zone)
                if end > window_start and start < window_end:
                    ranges.append({"kind": session["kind"], "start": start, "end": end})
        day += timedelta(days=1)

    return sorted(ranges, key=lambda value: (value["start"], value["end"]))


def _serialize_item(
    item: dict[str, Any],
    window_start: datetime,
    window_end: datetime,
    now: datetime,
) -> dict[str, Any]:
    visible_ranges = _ranges(item, window_start, window_end)
    state_ranges = _ranges(item, now - timedelta(days=2), now + timedelta(days=8))
    active = [value for value in state_ranges if value["start"] <= now < value["end"]]
    state = active[0]["kind"] if active else "closed"
    transitions = sorted(
        {
            point
            for value in state_ranges
            for point in (value["start"], value["end"])
            if point > now
        }
    )

    return {
        "id": item["id"],
        "group": item.get("group", "forex_session"),
        "name": item["name"],
        "city": item["city"],
        "country_code": item["country_code"],
        "timezone": item["timezone"],
        "state": state,
        "next_transition_at": transitions[0].isoformat() if transitions else None,
        "note": item.get("note"),
        "notification_capabilities": (
            ["market.session.main_opened"]
            if item["id"] in MAIN_OPEN_NOTIFICATION_MARKETS
            and market_calendar_verified(item["id"], now.astimezone(ZoneInfo(item["timezone"])).year)
            else []
        ),
        "sessions": [
            {
                "kind": value["kind"],
                "start_at": value["start"].isoformat(),
                "end_at": value["end"].isoformat(),
            }
            for value in visible_ranges
        ],
    }


@dataclass(frozen=True)
class MarketMainOpening:
    market_id: str
    market_name: dict[str, str]
    timezone: str
    local_trade_date: date
    starts_at: datetime


def list_market_main_openings(
    window_start: datetime,
    window_end: datetime,
) -> list[MarketMainOpening]:
    """Return the first main-session start per verified market-local trading day."""
    if window_start.tzinfo is None:
        window_start = window_start.replace(tzinfo=UTC)
    if window_end.tzinfo is None:
        window_end = window_end.replace(tzinfo=UTC)
    window_start = window_start.astimezone(UTC)
    window_end = window_end.astimezone(UTC)
    if window_end < window_start:
        return []

    result: list[MarketMainOpening] = []
    for item in _schedule()["markets"]:
        if item["id"] not in MAIN_OPEN_NOTIFICATION_MARKETS:
            continue
        zone = ZoneInfo(item["timezone"])
        day = window_start.astimezone(zone).date() - timedelta(days=1)
        last_day = window_end.astimezone(zone).date() + timedelta(days=1)
        while day <= last_day:
            if not market_calendar_verified(item["id"], day.year):
                day += timedelta(days=1)
                continue
            if day.isoformat() in _closed_dates(day.year).get(item["id"], set()):
                day += timedelta(days=1)
                continue
            candidates = [
                session for session in item["sessions"]
                if session["kind"] == "main" and day.weekday() in session["weekdays"]
            ]
            if candidates:
                first = min(candidates, key=lambda value: value["start"])
                starts_at, _ = _session_range(day, first, zone)
                if window_start <= starts_at <= window_end:
                    result.append(MarketMainOpening(
                        market_id=item["id"],
                        market_name=item["name"],
                        timezone=item["timezone"],
                        local_trade_date=day,
                        starts_at=starts_at,
                    ))
            day += timedelta(days=1)
    return sorted(result, key=lambda value: (value.starts_at, value.market_id))


def _forex_overlaps(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {item["id"]: item for item in items}
    pairs = [
        ("tokyo_london", "tokyo", "london"),
        ("london_new_york", "london", "new_york"),
    ]
    result = []
    for overlap_id, left_id, right_id in pairs:
        sessions = []
        for left in by_id[left_id]["sessions"]:
            for right in by_id[right_id]["sessions"]:
                start = max(left["start_at"], right["start_at"])
                end = min(left["end_at"], right["end_at"])
                if start < end:
                    sessions.append({"start_at": start, "end_at": end})
        result.append({"id": overlap_id, "sessions": sessions})
    return result


def get_market_hours(
    reference_timezone: str = "Asia/Shanghai",
    at: datetime | None = None,
) -> dict[str, Any]:
    """Return market sessions resolved into a selected timezone's current day."""
    try:
        reference_zone = ZoneInfo(reference_timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("invalid_timezone") from exc

    now = at or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    now = now.astimezone(UTC)
    reference_day = now.astimezone(reference_zone).date()
    window_start = datetime.combine(reference_day, time.min, tzinfo=reference_zone).astimezone(UTC)
    window_end = datetime.combine(
        reference_day + timedelta(days=1), time.min, tzinfo=reference_zone
    ).astimezone(UTC)

    payload = _schedule()
    markets = [
        _serialize_item(item, window_start, window_end, now)
        for item in payload["markets"]
    ]
    forex_sessions = [
        _serialize_item(item, window_start, window_end, now)
        for item in payload["forex_sessions"]
    ]

    return {
        "generated_at": now.isoformat(),
        "schedule_version": payload["version"],
        "reference_timezone": reference_timezone,
        "reference_date": reference_day.isoformat(),
        "window_start_at": window_start.isoformat(),
        "window_end_at": window_end.isoformat(),
        "active_count": sum(item["state"] != "closed" for item in markets),
        "markets": markets,
        "forex_sessions": forex_sessions,
        "forex_overlaps": _forex_overlaps(forex_sessions),
        "calendar_notice": {
            "zh": "按常规交易时段计算；节假日、临时休市及品种差异可能导致调整。",
            "en": "Based on regular sessions; holidays, special closures, and contract-specific hours may vary.",
        },
    }
