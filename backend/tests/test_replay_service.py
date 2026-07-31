from datetime import datetime, timezone, timedelta
import pandas as pd
import pytest

from services.market_gateway import (
    Candle,
    InMemoryMarketDataProvider,
    MarketDataGateway,
    ProviderMapping,
    default_catalog,
)
from services.replay import (
    ReplayProblem,
    resolve_exchange,
    infer_interval,
    compute_time_range,
    align_time_to_bar,
    WINDOW_PRESETS,
)


# ── resolve_exchange ──────────────────────────────────────────

def test_resolve_exchange_uses_trade_field_when_set():
    trade = {"symbol": "FOO", "exchange": "MY_EXCHANGE"}
    assert resolve_exchange(trade) == "MY_EXCHANGE"


def test_resolve_exchange_does_not_guess_when_trade_field_empty():
    trade = {"symbol": "BTCUSD", "exchange": None}
    assert resolve_exchange(trade) is None


def test_resolve_exchange_does_not_guess_unknown_symbol():
    trade = {"symbol": "UNKNOWN_SYM", "exchange": None}
    assert resolve_exchange(trade) is None


# ── infer_interval ────────────────────────────────────────────

@pytest.mark.parametrize(
    "minutes,expected",
    [
        (10, "1"),
        (60, "5"),
        (60 * 12, "15"),
        (60 * 24 * 5, "60"),
        (60 * 24 * 30, "240"),
        (60 * 24 * 200, "D"),
    ],
)
def test_infer_interval_buckets(minutes, expected):
    open_t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    close_t = open_t + timedelta(minutes=minutes)
    assert infer_interval(open_t.isoformat(), close_t.isoformat()) == expected


def test_infer_interval_open_trade_uses_now():
    open_t = datetime.now(timezone.utc) - timedelta(hours=1)
    # close_time None → treats holding as (now - open), which is ~1h → "5"
    assert infer_interval(open_t.isoformat(), None) == "5"


# ── compute_time_range ────────────────────────────────────────

def test_compute_time_range_standard_closed_trade():
    open_t = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    close_t = datetime(2026, 1, 10, 14, 0, tzinfo=timezone.utc)
    start, end = compute_time_range(open_t.isoformat(), close_t.isoformat(), "5", "standard")

    # standard = 100 bars before, 50 bars after; 5m = 300s
    assert (open_t - start).total_seconds() == 100 * 300
    assert (end - close_t).total_seconds() == 50 * 300


def test_compute_time_range_full_preset():
    open_t = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)
    close_t = datetime(2026, 1, 10, 14, 0, tzinfo=timezone.utc)
    start, end = compute_time_range(open_t.isoformat(), close_t.isoformat(), "60", "full")
    assert (open_t - start).total_seconds() == 300 * 3600
    assert (end - close_t).total_seconds() == 150 * 3600


def test_compute_time_range_open_trade_end_is_stable_bar_boundary():
    now = datetime(2026, 7, 24, 12, 34, 56, tzinfo=timezone.utc)
    _, end = compute_time_range(
        "2026-07-24T10:00:00Z",
        None,
        "5",
        "compact",
        now=now,
    )

    assert end == datetime(2026, 7, 24, 12, 35, tzinfo=timezone.utc)


# ── align_time_to_bar ─────────────────────────────────────────

def _make_bars(times):
    return [{"time": int(t.timestamp())} for t in times]


def test_align_time_to_bar_t_inside_bar():
    times = [datetime(2026, 1, 1, h, tzinfo=timezone.utc) for h in range(5)]
    bars = _make_bars(times)
    t = datetime(2026, 1, 1, 2, 30, tzinfo=timezone.utc)
    assert align_time_to_bar(t, bars) == 2


def test_align_time_to_bar_t_equals_bar_time():
    times = [datetime(2026, 1, 1, h, tzinfo=timezone.utc) for h in range(5)]
    bars = _make_bars(times)
    t = datetime(2026, 1, 1, 2, tzinfo=timezone.utc)
    assert align_time_to_bar(t, bars) == 2


def test_align_time_to_bar_t_before_first():
    times = [datetime(2026, 1, 1, h, tzinfo=timezone.utc) for h in range(5)]
    bars = _make_bars(times)
    t = datetime(2025, 12, 31, 23, tzinfo=timezone.utc)
    assert align_time_to_bar(t, bars) == 0


def test_align_time_to_bar_t_after_last():
    times = [datetime(2026, 1, 1, h, tzinfo=timezone.utc) for h in range(5)]
    bars = _make_bars(times)
    t = datetime(2026, 1, 2, tzinfo=timezone.utc)
    assert align_time_to_bar(t, bars) == 4


def test_align_time_to_bar_empty_raises():
    with pytest.raises(ValueError):
        align_time_to_bar(datetime.now(timezone.utc), [])


# ── presets exposed ───────────────────────────────────────────

def test_window_presets_match_spec():
    assert WINDOW_PRESETS == {
        "compact": (30, 20),
        "standard": (100, 50),
        "full": (300, 150),
    }


from services.replay import build_replay_bundle


def _ohlcv_df(times):
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(len(times))],
            "high": [101.0 + i for i in range(len(times))],
            "low": [99.0 + i for i in range(len(times))],
            "close": [100.5 + i for i in range(len(times))],
            "volume": [10.0] * len(times),
        },
        index=pd.DatetimeIndex(times, tz="UTC"),
    )


def _ohlcv_df_naive(times):
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(len(times))],
            "high": [101.0 + i for i in range(len(times))],
            "low": [99.0 + i for i in range(len(times))],
            "close": [100.5 + i for i in range(len(times))],
            "volume": [10.0] * len(times),
        },
        index=pd.DatetimeIndex(times),
    )


def _make_trade(open_time, close_time=None, exchange=None):
    return {
        "id": "trade-1",
        "user_id": "u1",
        "symbol": "BTCUSD",
        "exchange": exchange,
        "direction": "long",
        "open_price": 100.0,
        "close_price": 110.0 if close_time else None,
        "pnl": 10.0 if close_time else None,
        "open_time": open_time,
        "close_time": close_time,
    }


def _install_gateway(monkeypatch, frame, timeframe, *, include_data=True):
    catalog = default_catalog()
    for target_id in (
        "series:crypto:btc-usd:coinbase",
        "series:crypto:btc-usd:consolidated",
    ):
        catalog.add_provider_mapping(
            ProviderMapping("fixture", "series", target_id, "BTCUSD"),
        )
    provider = InMemoryMarketDataProvider(provider_id="fixture")
    if include_data:
        candles = []
        for timestamp, row in frame.iterrows():
            parsed = pd.Timestamp(timestamp)
            if parsed.tzinfo is None:
                parsed = parsed.tz_localize("UTC")
            candles.append(
                Candle(
                    open_time=parsed.to_pydatetime(),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                    is_closed=True,
                ),
            )
        provider.set_candles(
            provider_symbol="BTCUSD",
            timeframe=timeframe,
            candles=candles,
        )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])
    monkeypatch.setattr(
        "services.replay.get_market_data_gateway",
        lambda: gateway,
    )


def test_build_replay_bundle_closed_trade(monkeypatch):
    times = pd.date_range("2026-01-10 00:00", periods=200, freq="1h", tz="UTC")
    df = _ohlcv_df(times)
    open_iso = times[100].isoformat()
    close_iso = times[110].isoformat()
    trade = _make_trade(open_iso, close_iso, exchange="COINBASE")

    _install_gateway(monkeypatch, df, "60")
    bundle = build_replay_bundle(trade, interval="60", window="standard")

    assert bundle["meta"]["data_source"] == "fixture"
    assert bundle["meta"]["interval"] == "60"
    assert bundle["meta"]["window"] == "standard"
    assert bundle["meta"]["bar_count"] == 160
    assert len(bundle["bars"]) == 160
    assert bundle["open_index"] == 100
    assert bundle["close_index"] == 110
    # Sanity: bar fields present and time is int seconds
    b0 = bundle["bars"][0]
    assert set(b0.keys()) == {"time", "open", "high", "low", "close", "volume"}
    assert isinstance(b0["time"], int)


def test_build_replay_bundle_open_trade(monkeypatch):
    times = pd.date_range("2026-01-10 00:00", periods=50, freq="1h", tz="UTC")
    df = _ohlcv_df(times)
    open_iso = times[20].isoformat()
    trade = _make_trade(open_iso, close_time=None, exchange="COINBASE")

    _install_gateway(monkeypatch, df, "60")
    bundle = build_replay_bundle(trade, interval="60", window="compact")

    assert bundle["meta"]["data_source"] == "fixture"
    assert bundle["close_index"] is None
    assert bundle["open_index"] == 20


def test_build_replay_bundle_auto_interval(monkeypatch):
    times = pd.date_range("2026-01-10 00:00", periods=50, freq="1h", tz="UTC")
    df = _ohlcv_df(times)
    open_iso = times[10].isoformat()
    close_iso = times[25].isoformat()  # 15h hold → "15"
    trade = _make_trade(open_iso, close_iso)

    _install_gateway(monkeypatch, df, "15")
    bundle = build_replay_bundle(trade, interval="auto", window="standard")

    assert bundle["meta"]["interval"] == "15"


def test_build_replay_bundle_raises_when_data_unavailable(monkeypatch):
    open_iso = "2026-01-10T00:00:00+00:00"
    close_iso = "2026-01-10T02:00:00+00:00"
    trade = _make_trade(open_iso, close_iso)

    _install_gateway(monkeypatch, _ohlcv_df([]), "5", include_data=False)
    with pytest.raises(ReplayProblem) as exc_info:
        build_replay_bundle(trade, interval="5", window="standard")
    assert exc_info.value.code == "interval_unavailable"


def test_build_replay_bundle_raises_when_open_time_missing():
    trade = _make_trade(open_time=None)
    with pytest.raises(ReplayProblem) as exc_info:
        build_replay_bundle(trade, interval="auto", window="standard")
    assert exc_info.value.code == "missing_open_time"


def test_build_replay_bundle_tz_naive_index_is_normalized(monkeypatch):
    # Build a tz-naive DataFrame — what an unguarded `_fetch_tv_range` could produce
    times_naive = pd.date_range("2026-01-10 00:00", periods=50, freq="1h")  # no tz
    df = _ohlcv_df_naive(times_naive)
    open_iso = "2026-01-10T20:00:00+00:00"
    trade = _make_trade(open_iso, close_time=None, exchange="COINBASE")

    _install_gateway(monkeypatch, df, "60")
    bundle = build_replay_bundle(trade, interval="60", window="compact")

    # open_index should have been found (if tz normalization happened, alignment works)
    assert bundle["open_index"] == 20
    # Each bar's time is an int and > 0 (valid POSIX)
    assert all(isinstance(b["time"], int) and b["time"] > 0 for b in bundle["bars"])


def test_build_replay_bundle_uses_gateway_canonical_series(monkeypatch):
    catalog = default_catalog()
    provider = InMemoryMarketDataProvider(provider_id="tradingview")
    times = pd.date_range("2026-01-10 00:00", periods=200, freq="1h", tz="UTC")
    provider.set_candles(
        provider_symbol="BTCUSD",
        timeframe="60",
        candles=[
            Candle(
                open_time=timestamp.to_pydatetime(),
                open=100 + index,
                high=101 + index,
                low=99 + index,
                close=100.5 + index,
                volume=10,
                is_closed=True,
            )
            for index, timestamp in enumerate(times)
        ],
    )
    gateway = MarketDataGateway(catalog=catalog, providers=[provider])
    monkeypatch.setattr(
        "services.replay.get_market_data_gateway",
        lambda: gateway,
    )
    trade = _make_trade(
        times[100].isoformat(),
        times[110].isoformat(),
        exchange="COINBASE",
    )

    bundle = build_replay_bundle(trade, interval="60", window="standard")

    assert bundle["meta"]["data_source"] == "tradingview"
    assert bundle["meta"]["series_id"] == "series:crypto:btc-usd:coinbase"


def test_build_replay_bundle_rejects_nan_provider_payload(monkeypatch):
    import numpy as np
    times = pd.date_range("2026-01-10 00:00", periods=30, freq="1h", tz="UTC")
    df = _ohlcv_df(times)
    # Inject a NaN in one bar's close
    df.iloc[5, df.columns.get_loc("close")] = np.nan

    open_iso = times[10].isoformat()
    close_iso = times[15].isoformat()
    trade = _make_trade(open_iso, close_iso, exchange="COINBASE")

    _install_gateway(monkeypatch, df, "60")
    with pytest.raises(ReplayProblem) as exc_info:
        build_replay_bundle(trade, interval="60", window="compact")
    assert exc_info.value.code == "interval_unavailable"


def test_build_replay_bundle_rejects_entry_outside_coverage(monkeypatch):
    times = pd.date_range("2026-01-11 00:00", periods=30, freq="1h", tz="UTC")
    trade = _make_trade(
        "2026-01-10T12:00:00+00:00",
        "2026-01-10T14:00:00+00:00",
        exchange="COINBASE",
    )

    _install_gateway(monkeypatch, _ohlcv_df(times), "60")
    with pytest.raises(ReplayProblem) as exc_info:
        build_replay_bundle(trade, interval="60", window="full")

    assert exc_info.value.code == "interval_unavailable"


def test_build_replay_bundle_auto_falls_back_to_coarser_interval(monkeypatch):
    times = pd.date_range("2026-01-01 00:00", periods=200, freq="1h", tz="UTC")
    trade = _make_trade(
        times[100].isoformat(),
        times[110].isoformat(),
        exchange="COINBASE",
    )

    _install_gateway(monkeypatch, _ohlcv_df(times), "60")
    bundle = build_replay_bundle(trade, interval="auto", window="standard")

    assert bundle["meta"]["requested_interval"] == "auto"
    assert bundle["meta"]["interval"] == "60"
    assert bundle["meta"]["decision_index"] == bundle["open_index"]
