from __future__ import annotations

import logging
from bisect import bisect_right
from datetime import datetime, timedelta, timezone

from services.market_data import INTERVAL_SECONDS, resolve_legacy_series_id
from services.market_data_runtime import get_market_data_gateway
from services.market_gateway import CandleQuery, MarketDataError

logger = logging.getLogger(__name__)

WINDOW_PRESETS: dict[str, tuple[int, int]] = {
    "compact": (30, 20),
    "standard": (100, 50),
    "full": (300, 150),
}

INTERVAL_ORDER = ("1", "5", "15", "60", "240", "D")


class ReplayProblem(Exception):
    def __init__(
        self,
        code: str,
        *,
        status_code: int = 422,
        retryable: bool = False,
        suggested_intervals: list[str] | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable
        self.suggested_intervals = suggested_intervals or []

    def to_dict(self) -> dict:
        return {
            "problem": self.code,
            "retryable": self.retryable,
            "suggested_intervals": self.suggested_intervals,
        }


def _parse_iso(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ReplayProblem("missing_open_time") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def resolve_exchange(trade: dict) -> str | None:
    explicit = trade.get("exchange")
    return explicit or None


def infer_interval(open_time: str, close_time: str | None) -> str:
    opened_at = _parse_iso(open_time)
    closed_at = _parse_iso(close_time) if close_time else datetime.now(timezone.utc)
    minutes = max((closed_at - opened_at).total_seconds() / 60.0, 0)

    if minutes < 30:
        return "1"
    if minutes < 6 * 60:
        return "5"
    if minutes < 2 * 24 * 60:
        return "15"
    if minutes < 14 * 24 * 60:
        return "60"
    if minutes < 90 * 24 * 60:
        return "240"
    return "D"


def compute_time_range(
    open_time: str,
    close_time: str | None,
    interval: str,
    window: str,
    *,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    if window not in WINDOW_PRESETS:
        raise ValueError(f"Unknown window preset: {window}")
    if interval not in INTERVAL_SECONDS:
        raise ValueError(f"Unknown interval: {interval}")

    before_bars, after_bars = WINDOW_PRESETS[window]
    seconds = INTERVAL_SECONDS[interval]
    opened_at = _parse_iso(open_time)
    start = opened_at - timedelta(seconds=before_bars * seconds)

    if close_time is None:
        current = now or datetime.now(timezone.utc)
        timestamp = int(current.timestamp())
        aligned_timestamp = (timestamp + seconds - 1) // seconds * seconds
        end = datetime.fromtimestamp(aligned_timestamp, timezone.utc)
    else:
        closed_at = _parse_iso(close_time)
        end = closed_at + timedelta(seconds=after_bars * seconds)
    return start, end


def align_time_to_bar(target: datetime, bars: list[dict]) -> int:
    """Legacy helper used by callers that explicitly want clamped alignment."""
    if not bars:
        raise ValueError("bars is empty")
    target_seconds = int(target.timestamp())
    times = [bar["time"] for bar in bars]
    index = bisect_right(times, target_seconds) - 1
    return min(max(index, 0), len(bars) - 1)


def _align_covered_time_to_bar(
    target: datetime,
    bars: list[dict],
    interval: str,
) -> int:
    if not bars:
        raise ReplayProblem("coverage_unavailable")

    target_seconds = int(target.timestamp())
    times = [bar["time"] for bar in bars]
    index = bisect_right(times, target_seconds) - 1
    if index < 0:
        raise ReplayProblem("coverage_unavailable")

    bar_start = times[index]
    if target_seconds >= bar_start + INTERVAL_SECONDS[interval]:
        raise ReplayProblem("coverage_unavailable")
    return index


def _candidate_intervals(interval: str, open_time: str, close_time: str | None) -> list[str]:
    if interval != "auto":
        if interval not in INTERVAL_SECONDS:
            raise ValueError(f"Unknown interval: {interval}")
        return [interval]

    preferred = infer_interval(open_time, close_time)
    start = INTERVAL_ORDER.index(preferred)
    return list(INTERVAL_ORDER[start:])


class ReplayService:
    """Prepare one validated replay session through a small public interface."""

    def __init__(self, gateway):
        self.gateway = gateway

    def prepare(self, trade: dict, interval: str, window: str) -> dict:
        open_time = trade.get("open_time")
        if not open_time:
            raise ReplayProblem("missing_open_time")
        if window not in WINDOW_PRESETS:
            raise ValueError(f"Unknown window: {window}")

        opened_at = _parse_iso(open_time)
        close_time = trade.get("close_time")
        closed_at = _parse_iso(close_time) if close_time else None
        if closed_at is not None and closed_at < opened_at:
            raise ReplayProblem("invalid_trade_time")

        exchange = resolve_exchange(trade)
        series_id = trade.get("series_id")
        if series_id and not self.gateway.has_series(series_id):
            series_id = None
        if not series_id:
            series_id = resolve_legacy_series_id(
                self.gateway,
                trade["symbol"],
                exchange or "",
            )
        if not series_id:
            raise ReplayProblem("instrument_required")

        requested_interval = interval
        candidates = _candidate_intervals(interval, open_time, close_time)
        failures: list[tuple[str, str]] = []

        for candidate in candidates:
            start_at, end_at = compute_time_range(
                open_time,
                close_time,
                candidate,
                window,
            )
            try:
                candle_series = self.gateway.get_candles(
                    CandleQuery(
                        series_id=series_id,
                        timeframe=candidate,
                        start=start_at,
                        end=end_at,
                        purpose="replay",
                    ),
                )
            except MarketDataError as exc:
                failures.append((candidate, exc.code))
                continue

            bars = [
                {
                    "time": int(candle.open_time.timestamp()),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume if candle.volume is not None else 0.0,
                }
                for candle in candle_series.candles
            ]

            try:
                open_index = _align_covered_time_to_bar(opened_at, bars, candidate)
                close_index = (
                    _align_covered_time_to_bar(closed_at, bars, candidate)
                    if closed_at is not None
                    else None
                )
            except ReplayProblem:
                failures.append((candidate, "coverage_unavailable"))
                continue

            start_index = max(1, open_index - 20)
            coverage_start = datetime.fromtimestamp(
                bars[0]["time"],
                timezone.utc,
            ).isoformat()
            coverage_end = datetime.fromtimestamp(
                bars[-1]["time"] + INTERVAL_SECONDS[candidate],
                timezone.utc,
            ).isoformat()

            return {
                "trade": {
                    "id": trade["id"],
                    "symbol": trade["symbol"],
                    "exchange": exchange or candle_series.source.provider_exchange,
                    "direction": trade["direction"],
                    "open_time": open_time,
                    "close_time": close_time,
                    "open_price": trade.get("open_price"),
                    "close_price": trade.get("close_price"),
                    "pnl": trade.get("pnl"),
                },
                "instrument": {
                    "series_id": series_id,
                    "display_symbol": trade["symbol"],
                    "venue": exchange or candle_series.source.provider_exchange,
                    "fidelity": "exact",
                },
                "meta": {
                    "requested_interval": requested_interval,
                    "interval": candidate,
                    "window": window,
                    "series_id": series_id,
                    "data_source": candle_series.source.provider_id,
                    "cache_status": candle_series.source.cache_status,
                    "quality_warnings": list(candle_series.quality.warnings),
                    "coverage_start": coverage_start,
                    "coverage_end": coverage_end,
                    "bar_count": len(bars),
                    "start_index": start_index,
                    "decision_index": open_index,
                },
                "bars": bars,
                "open_index": open_index,
                "close_index": close_index,
            }

        suggestions = [candidate for candidate, _ in failures]
        if requested_interval != "auto":
            if requested_interval in INTERVAL_ORDER:
                preferred_index = INTERVAL_ORDER.index(requested_interval)
                suggestions = list(INTERVAL_ORDER[preferred_index + 1 :])
            else:
                suggestions = []
            raise ReplayProblem(
                "interval_unavailable",
                suggested_intervals=suggestions,
            )

        retryable = any(
            reason not in {"unsupported_timeframe", "coverage_unavailable"}
            for _, reason in failures
        )
        raise ReplayProblem(
            "coverage_unavailable",
            status_code=503 if retryable else 422,
            retryable=retryable,
            suggested_intervals=suggestions,
        )


def build_replay_bundle(trade: dict, interval: str, window: str) -> dict:
    """Compatibility wrapper for existing callers and focused tests."""
    return ReplayService(get_market_data_gateway()).prepare(
        trade,
        interval=interval,
        window=window,
    )
